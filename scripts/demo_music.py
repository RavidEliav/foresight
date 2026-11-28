"""Phase 9: the demo video's music, composed in numpy: upbeat, futuristic electronic at 118 BPM.

A four-chord loop (Am7, Fmaj7, C, G, two bars each) with a pad, a plucked 16th-note arpeggio
in a ping-pong delay, a rolling bass, drums and a lead, arranged in sections that follow the
video: energy 1 (pad and arpeggio), 2 (with kick, hats and bass) and 3 (with claps, 16th hats
and the lead). Risers lead into a rise in energy and a crash marks its first beat; long stretches
change pattern every eight bars so the music never stands still.

    python scripts/demo_music.py <out.wav> [seconds]   (a preview with a sample arrangement)
"""

from __future__ import annotations

import sys
import wave
from functools import cache
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

RATE = 44100
BPM = 118
BEAT = 60 / BPM
BAR = 4 * BEAT
STEP = BEAT / 4      # a 16th note

# (bass root, pad voicing) for each chord, two bars each
CHORDS = [(45, [57, 60, 64, 67]),   # Am7
          (41, [53, 57, 60, 64]),   # Fmaj7
          (48, [55, 60, 64, 67]),   # C
          (43, [55, 59, 62, 67])]   # G
ARPS = [[0, 1, 2, 3, 4, 5, 6, 7, 6, 5, 4, 3, 2, 1, 2, 3],
        [0, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 4, 5, 3],
        [7, 5, 6, 4, 5, 3, 4, 2, 3, 1, 2, 0, 1, 3, 2, 4]]
# the lead: (16th step in a two-bar chord, index into the chord's notes an octave up, 16ths long)
LEAD = [[(0, 3, 3), (3, 2, 3), (6, 3, 2), (8, 4, 6), (16, 3, 3), (19, 2, 3), (22, 1, 4),
         (26, 2, 6)],
        [(0, 4, 2), (2, 3, 2), (4, 2, 4), (10, 3, 2), (12, 4, 4), (16, 5, 6), (24, 4, 2),
         (26, 3, 6)]]


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def saw(f: float, n: int, phase: float = 0.0) -> np.ndarray:
    """A band-limited (polyBLEP) sawtooth."""
    dt = f / RATE
    ph = (phase + dt * np.arange(n)) % 1.0
    y = 2 * ph - 1
    lo = ph < dt
    t = ph[lo] / dt
    y[lo] -= 2 * t - t * t - 1
    hi = ph > 1 - dt
    t = (ph[hi] - 1) / dt
    y[hi] -= t * t + 2 * t + 1
    return y


def lowpass(x: np.ndarray, hz_: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz_, "low", fs=RATE, output="sos"), x)


def highpass(x: np.ndarray, hz_: float, order: int = 2) -> np.ndarray:
    return sosfilt(butter(order, hz_, "high", fs=RATE, output="sos"), x)


def bandpass(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return sosfilt(butter(2, [lo, hi], "band", fs=RATE, output="sos"), x)


def noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


# --- the instruments: each one note, cached --------------------------------------------------

@cache
def kick() -> np.ndarray:
    t = np.arange(int(0.42 * RATE)) / RATE
    f = 48 + 120 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 7.5)
    click = highpass(noise(t.size, 1), 2500) * np.exp(-t * 300) * 0.25
    return np.tanh(1.6 * (body + click)) * 0.9


@cache
def clap() -> np.ndarray:
    t = np.arange(int(0.3 * RATE)) / RATE
    env = np.exp(-t * 18)
    for d in (0.0, 0.011, 0.022):  # three quick bursts, like hands
        env = env + 0.6 * np.exp(-np.clip(t - d, 0, None) * 140) * (t >= d)
    return bandpass(noise(t.size, 2), 900, 3200) * env * 0.5


@cache
def hat(open_: bool) -> np.ndarray:
    t = np.arange(int((0.22 if open_ else 0.06) * RATE)) / RATE
    return highpass(noise(t.size, 3 + open_), 7000, 4) * np.exp(-t * (16 if open_ else 70)) * 0.35


@cache
def crash() -> np.ndarray:
    t = np.arange(int(2.4 * RATE)) / RATE
    return highpass(noise(t.size, 5), 4500, 2) * np.exp(-t * 1.9) * 0.32


@cache
def boom() -> np.ndarray:
    t = np.arange(int(1.6 * RATE)) / RATE
    f = 32 + 50 * np.exp(-t * 6)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 2.6) * 0.6


@cache
def riser(seconds: float) -> np.ndarray:
    """Noise swept upward with a rising tone, growing louder."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    p = t / seconds
    out = np.zeros(n)
    x = noise(n, 6)
    block = 1024
    for i in range(0, n, block):  # the band moves up, block by block
        c = 400 * (16 ** p[i])
        seg = bandpass(x[max(0, i - 2048):i + block], c, min(c * 2.5, 18000))
        out[i:i + block] = seg[-min(block, n - i):]
    tone = np.sin(2 * np.pi * np.cumsum(220 * 4 ** p) / RATE) * 0.12
    return (out * 0.35 + tone) * p ** 2.2


@cache
def pluck(m: int, bright: float) -> np.ndarray:
    """A plucked saw: the higher harmonics fade fastest, more slowly when brighter."""
    t = np.arange(int(0.42 * RATE)) / RATE
    f = hz(m)
    out = np.zeros(t.size)
    for k in range(1, min(28, int(15000 / f)) + 1):
        out += np.sin(2 * np.pi * k * f * t) / k * np.exp(-t * (5 + k * (9 - 6 * bright)))
    return out * np.clip(t / 0.003, 0, 1) * 0.3


@cache
def lead(m: int, steps: int) -> np.ndarray:
    """A bright saw lead with a slight vibrato and a soft release."""
    length = steps * STEP
    t = np.arange(int((length + 0.25) * RATE)) / RATE
    f = hz(m) * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.15) / 0.2, 0, 1))
    ph = np.cumsum(f) / RATE
    out = np.zeros(t.size)
    for det in (-0.006, 0.0, 0.006):  # three voices, a little apart
        out += 2 * ((ph * (1 + det) + det * 7) % 1.0) - 1
    out = lowpass(out, 3800)
    env = np.clip(t / 0.01, 0, 1) * np.where(t < length, 1.0, np.exp(-(t - length) * 18))
    return out * env * 0.09


def pad(voicing: list[int], seconds: float, seed: int) -> np.ndarray:
    """A soft, wide chord: three detuned saws a note, filtered, with a slow swell."""
    n = int((seconds + 0.6) * RATE)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for m in voicing:
        for det in (-0.007, 0.0, 0.007):
            out += saw(hz(m) * (1 + det), n, rng.uniform())
    out = lowpass(out, 1900, 2)
    env = np.clip(t / 0.35, 0, 1) * np.where(t < seconds, 1.0, np.exp(-(t - seconds) * 8))
    return out * env * 0.028


def bass(root: int, seconds: float) -> np.ndarray:
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    tone = lowpass(saw(hz(root), n), 700, 2) * 0.55 + np.sin(2 * np.pi * hz(root - 12) * t)
    env = np.clip(t / 0.004, 0, 1) * np.exp(-t * 5) * np.clip((seconds - t) / 0.01, 0, 1)
    return tone * env * 0.22


# --- the arrangement -------------------------------------------------------------------------

def compose(sections: list[tuple[float, int]], seconds: float, path: Path) -> None:
    """Music of the given length. ``sections`` are (start in seconds, energy 1 to 3), in order;
    each change of energy falls on the nearest bar line."""
    n = int((seconds + 3) * RATE)
    bars = int(np.ceil(seconds / BAR)) + 1
    energy = np.ones(bars, int)
    for start, level in sections:
        energy[min(bars - 1, round(start / BAR)):] = level
    dry = {k: np.zeros((n, 2)) for k in ("drums", "music", "send")}
    duck = np.ones(n)  # the sidechain: the kick pushes the rest down

    def put(bus: str, sound: np.ndarray, at: float, gain: float = 1.0, pan: float = 0.0) -> None:
        i = int(at * RATE)
        if i >= n:
            return
        s = sound[:n - i] * gain
        dry[bus][i:i + s.size, 0] += s * np.sqrt((1 - pan) / 2)
        dry[bus][i:i + s.size, 1] += s * np.sqrt((1 + pan) / 2)

    delays: list[tuple[np.ndarray, float, float]] = []
    for b in range(bars):
        at, e = b * BAR, energy[b]
        chord = CHORDS[(b // 2) % 4]
        first_of_chord = b % 2 == 0
        rise = b + 1 < bars and energy[b + 1] > e
        fall = b > 0 and energy[b - 1] > e
        phrase = b // 8   # long stretches change every 8 bars
        fill = e >= 2 and b % 16 == 15 and not rise  # a breath at the end of 16 bars
        if first_of_chord:
            chord_pad = pad(chord[1], 2 * BAR, b)
            put("music", chord_pad, at, 1.0 if e > 1 else 0.85)
            put("send", chord_pad, at, 0.5)
        if b > 0 and energy[b - 1] < e:  # a rise in energy lands here
            put("drums", crash(), at, 0.9, 0.2)
            put("drums", boom(), at, 0.9)
        if fall:
            put("send", crash(), at, 0.5, -0.3)
        if rise:
            r = riser(BAR)
            put("send", r, at, 0.7)
            put("music", r, at, 0.5)
        # the arpeggio: 16ths over the chord, an octave up, brighter as energy rises
        notes = [m + 12 for m in chord[1]] + [m + 24 for m in chord[1]]
        pattern = ARPS[phrase % len(ARPS)]
        for s in range(16):
            if e == 1 and b < 2 and s % 2:  # the very start: 8ths first
                continue
            ramp = min(1.0, (b + s / 16) / 4) if b < 4 else 1.0
            bright = (0.35 + 0.2 * ramp, 0.65, 0.85)[e - 1]
            gain = (0.75, 0.8, 0.9)[e - 1] * (0.9 if s % 4 else 1.0)
            note = pluck(notes[pattern[s]], round(bright, 2))
            pan = 0.35 * np.sin(s * np.pi / 4)
            put("music", note, at + s * STEP, gain, pan)
            put("send", note, at + s * STEP, gain * 0.4, pan)
            delays.append((note, at + s * STEP, gain))
        if e >= 2:
            for beat in range(4):
                t0 = at + beat * BEAT
                if fill and beat >= 2:
                    continue
                put("drums", kick(), t0, 1.0)
                i = int(t0 * RATE)
                k = np.arange(min(int(0.32 * RATE), n - i)) / RATE
                duck[i:i + k.size] = np.minimum(duck[i:i + k.size],
                                                1 - 0.6 * np.exp(-k / 0.1))
                put("drums", hat(True), t0 + BEAT / 2, 0.55 if e == 2 else 0.6, 0.25)
                if e == 3 or (phrase % 2 and e == 2):  # 16th hats
                    for s in (1, 3):
                        put("drums", hat(False), t0 + s * STEP, 0.45, -0.3)
                if e == 3 and beat in (1, 3):
                    put("drums", clap(), t0, 0.8, -0.05)
                    put("send", clap(), t0, 0.35)
            if fill:
                for s in range(8, 16):  # a snare-like roll into the next phrase
                    put("drums", clap(), at + s * STEP, 0.2 + 0.05 * (s - 8), 0.1)
            # the bass: rolling 8ths, an octave jump on the off-beats
            for s in range(8):
                if fill and s >= 4:
                    continue
                m = chord[0] + (12 if s % 2 else 0) - 12
                put("music", bass(m + 12, STEP * 1.6), at + s * BEAT / 2, 1.0 if s % 2 else 0.9)
        if e == 3:
            for step, idx, length in LEAD[(b // 2) % 2]:
                bar_step = step - (0 if first_of_chord else 16)
                if not 0 <= bar_step < 16:
                    continue
                voice = sorted(chord[1])
                m = (voice + [x + 12 for x in voice])[idx] + 12
                note = lead(m, length)
                put("music", note, at + bar_step * STEP, 1.0, 0.1)
                put("send", note, at + bar_step * STEP, 0.5)
                delays.append((note, at + bar_step * STEP, 0.6))

    # the ping-pong delay (a dotted 8th), on the arpeggio and the lead
    echo = np.zeros((n, 2))
    for note, at, gain in delays:
        for k in range(1, 5):
            i = int((at + k * 0.75 * BEAT) * RATE)
            if i >= n:
                break
            s = note[:n - i] * gain * 0.32 * 0.55 ** (k - 1)
            echo[i:i + s.size, k % 2] += s
    for c in range(2):
        echo[:, c] = lowpass(echo[:, c], 4000)
    wet = reverb(dry["send"] + echo * 0.5)
    music = (dry["music"] + echo) * duck[:, None]
    mix = dry["drums"] * 0.9 + music + wet * 0.45
    mix[:, 0] = highpass(mix[:, 0], 28)
    mix[:, 1] = highpass(mix[:, 1], 28)
    t = np.arange(n) / RATE
    mix *= np.clip(t / 0.05, 0, 1)[:, None] * np.clip((seconds + 0.2 - t) / 3.0, 0, 1)[:, None]
    mix = mix[:int(seconds * RATE)]
    mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.6) / np.tanh(1.6)
    write(path, mix * 0.89)


def reverb(x: np.ndarray, seconds: float = 2.2) -> np.ndarray:
    """A plate-like reverb: decorrelated noise tails, by FFT convolution."""
    n = x.shape[0]
    t = np.arange(int(seconds * RATE)) / RATE
    out = np.zeros_like(x)
    size = 1 << int(np.ceil(np.log2(n + t.size)))
    for c in range(2):
        ir = noise(t.size, 11 + c) * np.exp(-t / 0.42)
        ir = lowpass(ir, 6000) * np.clip(t / 0.02, 0, 1)
        ir /= np.sqrt((ir ** 2).sum())
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], size) * np.fft.rfft(ir, size), size)[:n]
    return highpass(out.T, 250).T


def write(path: Path, stereo: np.ndarray) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((np.clip(stereo, -1, 1) * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    out = Path(sys.argv[1])
    total = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
    compose([(0, 1), (8, 2), (total * 0.6, 3), (total - 12, 1)], total, out)
    print(f"saved {out}")
