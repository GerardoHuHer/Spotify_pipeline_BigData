"""
Pipeline Orchestrator
─────────────────────────────────────────────────────────────────────────────
Runs the full Medallion pipeline:  Bronze → Silver → Gold

Usage:
    python run_pipeline.py                   # full run
    python run_pipeline.py --layer bronze    # single layer
    python run_pipeline.py --layer silver
    python run_pipeline.py --layer gold
    python run_pipeline.py --generate-data   # also creates sample data first
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import time
import argparse
from pathlib import Path

# Make sure sibling modules are importable when run from any CWD
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.bronze_layer import ingest
from pipeline.silver_layer import transform
from pipeline.gold_layer   import aggregate


def banner(text: str):
    width = 62
    print("\n" + "═" * width)
    print(f"  {text}")
    print("═" * width)


def run_full_pipeline(generate_data: bool = False):
    banner("Spotify Medallion Pipeline  –  Bronze → Silver → Gold")
    total_start = time.time()

    if generate_data:
        banner("Generating sample data …")
        from data.generate_sample_data import main as gen
        gen()

    # ── BRONZE ────────────────────────────────────────────────────────────────
    banner("Layer 1 / 3  –  BRONZE  (raw ingestion)")
    t0 = time.time()
    b_meta = ingest()
    print(f"  ⏱  Bronze completed in {time.time()-t0:.1f}s")

    # ── SILVER ────────────────────────────────────────────────────────────────
    banner("Layer 2 / 3  –  SILVER  (PySpark transforms)")
    t0 = time.time()
    s_meta = transform()
    print(f"  ⏱  Silver completed in {time.time()-t0:.1f}s")

    # ── GOLD ──────────────────────────────────────────────────────────────────
    banner("Layer 3 / 3  –  GOLD  (analytical aggregations)")
    t0 = time.time()
    g_meta = aggregate()
    print(f"  ⏱  Gold completed in {time.time()-t0:.1f}s")

    elapsed = time.time() - total_start
    banner(f"Pipeline complete  ✓  {elapsed:.1f}s total")
    print(f"  Bronze records  : {b_meta['total_records']:,}")
    print(f"  Silver records  : {s_meta['total_records']:,}")
    print(f"  Gold insights   : {len(g_meta['insights'])}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Spotify Medallion Pipeline")
    parser.add_argument(
        "--layer", choices=["bronze", "silver", "gold"],
        help="Run only one layer"
    )
    parser.add_argument(
        "--generate-data", action="store_true",
        help="Generate sample Spotify data before running"
    )
    args = parser.parse_args()

    if args.generate_data and not args.layer:
        from data.generate_sample_data import main as gen
        banner("Generating sample data")
        gen()

    if args.layer == "bronze":
        banner("BRONZE layer")
        ingest()
    elif args.layer == "silver":
        banner("SILVER layer")
        transform()
    elif args.layer == "gold":
        banner("GOLD layer")
        aggregate()
    else:
        run_full_pipeline(generate_data=args.generate_data)


if __name__ == "__main__":
    main()
