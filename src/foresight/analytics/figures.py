"""Small helpers for saving matplotlib figures and embedding them in HTML."""

from __future__ import annotations

import base64
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PASS_COLOR = "#4C78A8"
FAIL_COLOR = "#E45756"


def new_figure(width: float = 8, height: float = 4.5):
    fig, ax = plt.subplots(figsize=(width, height), dpi=110)
    return fig, ax


def save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, format="png")
    plt.close(fig)
    return path


def embed(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:image/png;base64,{data}" alt="{path.stem}">'
