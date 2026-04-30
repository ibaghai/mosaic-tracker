#!/usr/bin/env python3
"""
One-command growth run:
1) Discover new companies from candidate lists
2) Import hits into DB
3) Run tracker scrape
4) Apply quality gates + midmarket tagging

Usage:
    python3 scripts/growth_run.py
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _run(cmd: list[str], *, stdout_path: Optional[Path] = None, env: Optional[dict] = None):
    printable = " ".join(cmd)
    print(f"\n$ {printable}")
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stdout_path, "w") as handle:
            subprocess.run(cmd, cwd=ROOT, check=True, stdout=handle, env=env)
        print(f"  wrote: {stdout_path}")
        return None
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)
    return None


def _run_json(cmd: list[str], *, env: Optional[dict] = None) -> dict:
    printable = " ".join(cmd)
    print(f"\n$ {printable}")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    if proc.stdout:
        print(proc.stdout.strip())
    return json.loads(proc.stdout)


def _enrich_hits(path_in: Path, path_out: Path, *, source_type: str, confidence: float) -> int:
    rows = json.loads(path_in.read_text())
    if not isinstance(rows, list):
        raise ValueError(f"{path_in} must contain a JSON list")
    enriched = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out = dict(row)
        out["source_type"] = source_type
        out["confidence"] = confidence
        enriched.append(out)
    path_out.write_text(json.dumps(enriched, indent=2))
    return len(enriched)


def _discover_and_import(
    *,
    candidates_file: Path,
    lane_name: str,
    source_type: str,
    confidence: float,
    run_id: str,
) -> dict:
    if not candidates_file.exists():
        print(f"\n[{lane_name}] skip: missing candidates file {candidates_file}")
        return {"lane": lane_name, "hits": 0, "imported": 0}

    raw_hits = SCRIPTS / f"{lane_name}_hits.{run_id}.json"
    enriched_hits = SCRIPTS / f"{lane_name}_hits.{run_id}.enriched.json"

    _run(
        [sys.executable, str(SCRIPTS / "batch_discover.py"), str(candidates_file)],
        stdout_path=raw_hits,
    )

    hits = _enrich_hits(raw_hits, enriched_hits, source_type=source_type, confidence=confidence)
    print(f"[{lane_name}] hits: {hits}")
    if hits == 0:
        return {"lane": lane_name, "hits": 0, "imported": 0}

    imported = _run_json(
        [sys.executable, str(SCRIPTS / "import_bulk_hits.py"), "--hits", str(enriched_hits)]
    )
    return {
        "lane": lane_name,
        "hits": hits,
        "imported": int(imported.get("rows_imported", 0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one full growth ingestion + scrape cycle")
    parser.add_argument(
        "--midmarket-candidates",
        type=Path,
        default=SCRIPTS / "midmarket_candidates.txt",
    )
    parser.add_argument(
        "--general-candidates",
        type=Path,
        default=SCRIPTS / "candidates.txt",
    )
    parser.add_argument("--skip-midmarket", action="store_true")
    parser.add_argument("--skip-general", action="store_true")
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-maintenance", action="store_true")
    parser.add_argument(
        "--tracker-company-source",
        default="merged",
        choices=["merged", "db", "config"],
        help="TRACKER_COMPANY_SOURCE for tracker.py",
    )
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "run_id": run_id,
        "lanes": [],
        "tracker_ran": False,
        "maintenance_applied": False,
    }

    try:
        if not args.skip_midmarket:
            summary["lanes"].append(
                _discover_and_import(
                    candidates_file=args.midmarket_candidates,
                    lane_name="midmarket_batch",
                    source_type="midmarket_batch",
                    confidence=0.85,
                    run_id=run_id,
                )
            )

        if not args.skip_general:
            summary["lanes"].append(
                _discover_and_import(
                    candidates_file=args.general_candidates,
                    lane_name="candidate_batch",
                    source_type="candidate_batch",
                    confidence=0.8,
                    run_id=run_id,
                )
            )

        if not args.skip_scrape:
            env = os.environ.copy()
            env["TRACKER_COMPANY_SOURCE"] = args.tracker_company_source
            _run([sys.executable, str(ROOT / "tracker.py")], env=env)
            summary["tracker_ran"] = True

        if not args.skip_maintenance:
            maintenance = _run_json([sys.executable, str(SCRIPTS / "growth_maintenance.py"), "--apply"])
            summary["maintenance_applied"] = True
            summary["maintenance"] = maintenance

    except subprocess.CalledProcessError as exc:
        print(f"\nGrowth run failed with exit code {exc.returncode}")
        return exc.returncode

    print("\n=== growth_run summary ===")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
