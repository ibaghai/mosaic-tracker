"""Load `.env.local` from the repo root into os.environ.

Stdlib-only. Vars already set in the shell take precedence over the file.
Imported once by db/models.py so anything that touches the DB picks it up.
"""

import os
from pathlib import Path


_LOADED = False


def load_env_local() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True

    path = Path(__file__).resolve().parent.parent / ".env.local"
    if not path.exists():
        return

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue
        os.environ[key] = value
