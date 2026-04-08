#!/usr/bin/env python3

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "tracker.db"
TARGET = ROOT / "data" / "tracker-demo.db"


def main() -> None:
    TARGET.unlink(missing_ok=True)
    source_conn = sqlite3.connect(SOURCE)
    target_conn = sqlite3.connect(TARGET)
    source_conn.backup(target_conn)
    source_conn.close()
    with target_conn:
        target_conn.execute("UPDATE job_postings SET description = NULL")
    target_conn.execute("VACUUM")
    target_conn.close()
    size_mb = TARGET.stat().st_size / (1024 * 1024)
    print(f"Created {TARGET} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
