"""Why does coverage dip for citing years 2015-2021 (c9_scores_20261031_01 coverage_by_year.csv)?

Read-only diagnosis on the VM (C_WORK of the c6 run). For citing years 2014, 2018, 2020, 2022:
  citing side: edges by citing item type x whether the citing item has a journal;
  cited side:  edges by whether the cited iid has a pubs row, a year, and its type;
  cross:       citing item type x whether the cited item has a year (do the two gaps coincide?).
Output: runs/<run_id>/citing_side.csv, cited_side.csv, cross.csv, run.json, SHA256SUMS. Never overwrites.

Usage:  python c7_coverage_gap.py --src c6_full_20261031_02 --run-id c7_covgap_<YYYYMMDD>_01
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
YEARS = [2014, 2018, 2020, 2022]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    work = Path(os.environ.get("C_WORK", ROOT / "data" / "work" / args.src))
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    run_dir.mkdir(parents=True)
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; "
                f"SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'; SET preserve_insertion_order = false")
    if os.environ.get("C_TEMP_DIR"):
        con.execute(f"SET temp_directory = '{os.environ['C_TEMP_DIR']}'")
    yl = ", ".join(map(str, YEARS))
    pj = f"read_parquet('{work / 'pubs_j.parquet'}')"
    con.execute(f"""CREATE TABLE e AS SELECT x.citing_iid, x.cited_iid, a.pub_year AS t, a.type AS citing_type,
                        a.journal_id IS NOT NULL AS citing_journal
                    FROM read_parquet('{work / 'edges.parquet'}') x JOIN {pj} a ON x.citing_iid = a.iid
                    WHERE a.pub_year IN ({yl})""")
    con.execute(f"""COPY (SELECT t, citing_type, citing_journal, count(*) AS edges FROM e GROUP BY ALL
                          ORDER BY t, edges DESC) TO '{run_dir / 'citing_side.csv'}' (HEADER)""")
    con.execute(f"""COPY (SELECT e.t, b.iid IS NOT NULL AS cited_in_pubs, b.pub_year IS NOT NULL AS cited_year,
                                 b.journal_id IS NOT NULL AS cited_journal, b.type AS cited_type, count(*) AS edges
                          FROM e LEFT JOIN {pj} b ON e.cited_iid = b.iid GROUP BY ALL
                          ORDER BY t, edges DESC) TO '{run_dir / 'cited_side.csv'}' (HEADER)""")
    con.execute(f"""COPY (SELECT e.t, e.citing_type, e.citing_journal, b.pub_year IS NOT NULL AS cited_year,
                                 count(*) AS edges, count(DISTINCT e.citing_iid) AS citing_items
                          FROM e LEFT JOIN {pj} b ON e.cited_iid = b.iid GROUP BY ALL
                          ORDER BY t, edges DESC) TO '{run_dir / 'cross.csv'}' (HEADER)""")
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "src_run": args.src,
        "work": str(work), "years": YEARS, "python": platform.python_version(), "duckdb": duckdb.__version__,
        "threads": os.environ.get("C_THREADS"), "memory": os.environ.get("C_MEM"),
        "seconds": round(time.time() - t0, 1)}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print((run_dir / "citing_side.csv").read_text()[:4000]); print((run_dir / "cited_side.csv").read_text()[:6000])
    print((run_dir / "cross.csv").read_text()[:3000])


if __name__ == "__main__":
    main()
