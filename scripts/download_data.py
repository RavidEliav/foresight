"""Download SECOM from UCI into data/raw and print the file checksums.

Usage: python scripts/download_data.py [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from foresight.data.secom import SOURCE_URL, download_secom, ensure_secom  # noqa: E402
from foresight.settings import load_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download even if files exist")
    args = parser.parse_args()

    settings = load_settings()
    raw_dir = settings.resolve(settings.paths.data_raw_dir)
    checksums = download_secom(raw_dir) if args.force else ensure_secom(raw_dir)
    print(f"SECOM ({SOURCE_URL}) in {raw_dir}")
    for name, digest in checksums.items():
        print(f"  {name}  sha256={digest}")


if __name__ == "__main__":
    main()
