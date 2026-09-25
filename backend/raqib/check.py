"""`python -m raqib.check` - exit 0 if the built artifacts load (used by run_demo to skip the build)."""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from .data import hs_table
        from .engine import artifacts_status, get_engine, load_train_index
        missing = [k for k, ok in artifacts_status().items() if not ok]
        if missing:
            print(f"[check] missing artifacts: {', '.join(missing)}")
            return 1
        get_engine()
        load_train_index()
        hs_table()
    except Exception as exc:  # noqa: BLE001 - any failure means "rebuild"
        print(f"[check] artifacts do not load: {exc}")
        return 1
    print("[check] artifacts OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
