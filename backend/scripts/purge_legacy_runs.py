"""Delete analysis results saved before accounts existed (plaintext backend/runs/*.json).

They have no owner, so the API can no longer serve them. Dry run by default:

    python -m scripts.purge_legacy_runs          (from backend/)  lists them
    python -m scripts.purge_legacy_runs --delete                  deletes them
"""

from __future__ import annotations

import sys

from ain import config


def main() -> None:
    legacy = sorted(config.RUNS_DIR.glob("*.json"))
    for path in legacy:
        print(path.name)
    if "--delete" in sys.argv[1:]:
        for path in legacy:
            path.unlink()
        print(f"deleted {len(legacy)} plaintext result file(s)")
    else:
        print(f"{len(legacy)} plaintext result file(s); re-run with --delete to remove them")


if __name__ == "__main__":
    main()
