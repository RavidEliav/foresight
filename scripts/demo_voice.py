"""Phase 9: the demo video's narration in a cloned voice, with Chatterbox (Resemble AI, MIT).

Runs in its own environment (Chatterbox pins its own PyTorch), not the project's:

    <chatterbox python> scripts/demo_voice.py <spec.json>

The spec is {"sample": <a WAV of the voice>, "language": "en" or "he", "lines": [{"text": ...,
"out": <WAV>}, ...]}. English uses Chatterbox's English model; other languages its multilingual
one (Hebrew gets its vowel marks from Dicta's model, in models/ beside this environment). Each
line is generated on the CPU with a fixed seed, so a rerun gives the same reading.
"""

from __future__ import annotations

import json
import re
import sys
import time
import wave
from pathlib import Path

import chatterbox.models.tokenizers.tokenizer as tokenizer
import chatterbox.mtl_tts
import chatterbox.tts
import numpy as np
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from chatterbox.tts import ChatterboxTTS

DICTA = Path(sys.executable).parents[1] / "models" / "dicta-1.0.int8.onnx"
# about how fast each language is read (measured on 23 good lines in each), and how much longer
# a line may run before it's suspect: the multilingual model sometimes goes on after the
# sentence, into noise, clicks or a hum
CHARS_PER_S = {"en": 15.0, "he": 13.5}
RUN_ON = 1.3

DTYPES = {"F32": (np.float32, None), "F16": (np.float16, None), "I64": (np.int64, None),
          "I32": (np.int32, None), "BF16": (np.int16, torch.bfloat16)}


def _load_file(path, device: str = "cpu") -> dict[str, torch.Tensor]:
    """The weights read tensor by tensor, without a memory map: safetensors' loaders crashed
    (an access violation, then a panic) on Windows when memory was short, on intact files."""
    with open(path, "rb") as f:
        size = int.from_bytes(f.read(8), "little")
        header = json.loads(f.read(size))
        out = {}
        for name, info in header.items():
            if name == "__metadata__":
                continue
            dtype, view = DTYPES[info["dtype"]]
            start, end = info["data_offsets"]
            f.seek(8 + size + start)
            data = np.fromfile(f, dtype, (end - start) // np.dtype(dtype).itemsize)
            tensor = torch.from_numpy(data).reshape(info["shape"])
            out[name] = tensor.view(view) if view else tensor
    return out


chatterbox.tts.load_file = _load_file
chatterbox.mtl_tts.load_safetensors = _load_file


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    language = spec.get("language", "en")
    if language == "en":
        model = ChatterboxTTS.from_pretrained(device="cpu")
        extra = {}
    else:
        model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
        extra = {"language_id": language}
        if language == "he":  # Chatterbox calls Dicta() without its model: give it one
            from dicta_onnx import Dicta
            tokenizer._dicta = Pronounce(Dicta(str(DICTA)), spec.get("pronounce", {}))
    for i, line in enumerate(spec["lines"]):
        start = time.time()
        expected = len(line["text"]) / CHARS_PER_S.get(language, 11.0)
        best = None
        for attempt in range(4):  # a line that runs on into noise is cut, or made again
            torch.manual_seed(1000 + i + 100 * attempt)
            audio = model.generate(line["text"], audio_prompt_path=spec.get("sample"),
                                   exaggeration=spec.get("exaggeration", 0.5),
                                   cfg_weight=spec.get("cfg_weight", 0.5), **extra)
            samples = audio.squeeze().cpu().numpy()
            if samples.size / model.sr > RUN_ON * expected:
                end = speech_end(samples, model.sr, expected)
                if end is None:
                    print(f"  ran on ({samples.size / model.sr:.1f} s, about {expected:.1f} "
                          "expected): again", flush=True)
                    if best is None or abs(samples.size / model.sr - expected) < abs(
                            best.size / model.sr - expected):
                        best = samples
                    continue
                print(f"  ran on: cut at {end / model.sr:.1f} s", flush=True)
                samples = samples[:end]
            best = samples
            break
        with wave.open(line["out"], "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(model.sr)
            f.writeframes((np.clip(best, -1, 1) * 32767).astype("<i2").tobytes())
        print(f"{i + 1}/{len(spec['lines'])}: {best.size / model.sr:.1f} s of speech in "
              f"{time.time() - start:.0f} s", flush=True)
    return 0


class Pronounce:
    """Dicta's vowel marks, except for the words given: those read as written (a name, a
    number, English names in Hebrew letters), whatever Dicta guesses."""

    def __init__(self, dicta, words: dict[str, str]):
        self.dicta, self.words = dicta, words

    def add_diacritics(self, text: str) -> str:
        marked = self.dicta.add_diacritics(text)

        def fix(match: re.Match) -> str:
            plain = MARKS.sub("", match.group(0))
            return self.words.get(plain, match.group(0))

        return WORD.sub(fix, marked)


MARKS = re.compile("[\u0591-\u05C7]")
WORD = re.compile("[\u05D0-\u05EA\u0591-\u05C7'\u05F3]+")


def speech_end(samples: np.ndarray, rate: int, expected: float) -> int | None:
    """Where a line that ran on into noise really ends: the last pause (0.2 s, 35 dB under the
    peak) that starts near the expected length. None when there is no such pause."""
    step = int(0.02 * rate)
    power = np.array([(samples[i:i + step] ** 2).mean()
                      for i in range(0, samples.size - step, step)])
    db = 10 * np.log10(power + 1e-10)
    quiet = db < db.max() - 35
    found, run = None, 0
    for k, q in enumerate(quiet):
        run = run + 1 if q else 0
        begin = (k - run + 1) * 0.02
        if run == 10 and 0.6 * expected <= begin <= 1.35 * expected:
            found = begin
    return None if found is None else int((found + 0.08) * rate)


if __name__ == "__main__":
    raise SystemExit(main())
