#!/usr/bin/env python3

import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "tracker.db"
TARGET = ROOT / "data" / "tracker-demo.db"


def main() -> None:
    shutil.copy2(SOURCE, TARGET)
    conn = sqlite3.connect(TARGET)
    with conn:
        conn.execute("UPDATE job_postings SET description = NULL")
    conn.execute("VACUUM")
    conn.close()
    size_mb = TARGET.stat().st_size / (1024 * 1024)
    print(f"Created {TARGET} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
