"""SECOM dataset (UCI #179): download, checksums and raw loading."""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from pathlib import Path

import pandas as pd
import requests

SOURCE_URL = "https://archive.ics.uci.edu/static/public/179/secom.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/179/secom"
DATA_FILE = "secom.data"
LABELS_FILE = "secom_labels.data"
NAMES_FILE = "secom.names"
N_FEATURES = 590
RAW_LABELS = (-1, 1)  # -1 = pass, 1 = fail
TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"


class SecomDataError(RuntimeError):
    pass


def feature_names(n: int = N_FEATURES) -> list[str]:
    return [f"f_{i:03d}" for i in range(n)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksums(raw_dir: Path) -> dict[str, str]:
    return {name: sha256(raw_dir / name) for name in (DATA_FILE, LABELS_FILE)}


def download_secom(raw_dir: Path, url: str = SOURCE_URL, timeout: int = 120) -> dict[str, str]:
    """Download the UCI zip and extract the data files. Returns their SHA-256 checksums."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in (DATA_FILE, LABELS_FILE, NAMES_FILE):
            (raw_dir / name).write_bytes(archive.read(name))
    return checksums(raw_dir)


def ensure_secom(raw_dir: Path) -> dict[str, str]:
    """Make sure the raw files exist, downloading them unless FORESIGHT_OFFLINE is set."""
    missing = [n for n in (DATA_FILE, LABELS_FILE) if not (raw_dir / n).exists()]
    if missing:
        if os.getenv("FORESIGHT_OFFLINE", "").lower() in {"1", "true", "yes"}:
            raise SecomDataError(f"SECOM files missing in {raw_dir} and downloads are disabled")
        return download_secom(raw_dir)
    return checksums(raw_dir)


def load_raw(raw_dir: Path) -> pd.DataFrame:
    """Load features + labels + timestamps as-is (labels stay -1/1, NaN kept).

    Columns: run_id (original row number), timestamp, label_raw, f_000..f_589.
    """
    try:
        features = pd.read_csv(raw_dir / DATA_FILE, sep=r"\s+", header=None, na_values=["NaN"])
        labels = pd.read_csv(
            raw_dir / LABELS_FILE, sep=r"\s+", header=None, names=["label_raw", "timestamp"],
            quotechar='"',
        )
    except (OSError, pd.errors.ParserError, ValueError) as exc:
        raise SecomDataError(f"cannot read SECOM files: {exc}") from exc

    if len(features) != len(labels):
        raise SecomDataError(
            f"row mismatch: {len(features)} feature rows vs {len(labels)} label rows"
        )
    features.columns = feature_names(features.shape[1])
    frame = pd.DataFrame(
        {
            "run_id": range(len(labels)),
            "timestamp": pd.to_datetime(labels["timestamp"], format=TIMESTAMP_FORMAT,
                                        errors="coerce"),
            "label_raw": labels["label_raw"],
        }
    )
    return pd.concat([frame, features], axis=1)
