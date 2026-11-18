"""Railway pre-deploy command: apply pending Supabase migrations to this environment's project.

Usage: ``python scripts/db_migrate.py`` (same as ``python -m foresight.cli db-migrate``, without
importing the pipeline).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from foresight.registry.migrate import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
