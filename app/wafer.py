"""Simulated wafer of one production run (Phase 8.4).

SECOM records one row per production run (sensor readings and pass/fail) but no die positions,
so a wafer can only be a labeled simulation. It is reproducible from the run id:

- scattered defective dies, more of them the higher the run's risk score;
- a failing run also gets one defect pattern (cluster, edge ring, scratch or center), the
  usual spatial signatures on real wafer maps (the WM-811K classes). The pattern is chosen at
  random, seeded by the run id: SECOM can't tell which one a run would have had.

The wafer is only drawn: nothing here feeds the analysis, the metrics or the reports.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DIES_ACROSS = 25
DIE = 2 / DIES_ACROSS  # die pitch on a wafer of radius 1
SEED = 84
PATTERNS = ("cluster", "edge ring", "scratch", "center")
SCATTER_BASE, SCATTER_PER_RISK = 0.005, 0.025  # share of scattered defective dies
NOTE = ("Simulated wafer: SECOM has no die positions. Scattered defects grow with the run's "
        "risk score, and a failing run also gets one typical defect pattern, chosen at random. "
        "An illustration, not measured data.")


@dataclass(frozen=True)
class Wafer:
    run_id: int
    failed: bool
    risk: float
    pattern: str | None
    x: np.ndarray  # die centres
    y: np.ndarray
    bad: np.ndarray  # defective dies

    @property
    def dies(self) -> int:
        return len(self.x)

    @property
    def bad_dies(self) -> int:
        return int(self.bad.sum())

    @property
    def die_yield(self) -> float:
        return 1 - self.bad_dies / self.dies


def die_grid() -> tuple[np.ndarray, np.ndarray]:
    """Centres of the whole dies on the wafer (a die cut by the edge is not counted)."""
    centres = (np.arange(DIES_ACROSS) + 0.5) * DIE - 1
    x, y = (a.ravel() for a in np.meshgrid(centres, centres))
    inside = np.hypot(np.abs(x) + DIE / 2, np.abs(y) + DIE / 2) <= 0.98
    return x[inside], y[inside]


def simulate(run_id: int, failed: bool, risk: float) -> Wafer:
    """The wafer of a run: same run id, same wafer."""
    rng = np.random.default_rng([SEED, int(run_id)])
    x, y = die_grid()
    risk = float(np.clip(risk, 0, 1))
    bad = rng.random(len(x)) < SCATTER_BASE + SCATTER_PER_RISK * risk
    pattern = None
    if failed:
        pattern = PATTERNS[int(rng.integers(len(PATTERNS)))]
        bad |= _pattern(pattern, x, y, rng)
    return Wafer(int(run_id), bool(failed), risk, pattern, x, y, bad)


def _pattern(kind: str, x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    r = np.hypot(x, y)
    hit = rng.random(len(x))
    if kind == "cluster":
        angle, distance = rng.uniform(0, 2 * np.pi), rng.uniform(0.35, 0.65)
        size = rng.uniform(0.18, 0.28)
        near = np.hypot(x - distance * np.cos(angle), y - distance * np.sin(angle)) < size
        return near & (hit < 0.85)
    if kind == "edge ring":
        return (r > 0.8) & (hit < 0.6)
    if kind == "scratch":
        angle = rng.uniform(0, np.pi)
        start = rng.uniform(-0.5, 0.5, size=2)
        direction = np.array([np.cos(angle), np.sin(angle)])
        along = np.clip((x - start[0]) * direction[0] + (y - start[1]) * direction[1],
                        -0.6, 0.6)
        gap = np.hypot(x - start[0] - along * direction[0], y - start[1] - along * direction[1])
        return (gap < DIE * 0.7) & (hit < 0.95)
    if kind == "center":
        return (r < 0.3) & (hit < 0.85)
    raise ValueError(f"unknown pattern {kind!r}")
