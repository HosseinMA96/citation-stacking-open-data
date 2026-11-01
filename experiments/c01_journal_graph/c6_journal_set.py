"""Per-venue journal flags for a finished c6 run, the input to the journal rules in config.yaml.

Rules were chosen on 2026-10-31 from c6_journalrule_20261031_01 (RESULTS_LOG): main = the venue
has its own record of type 'journal' and an ISSN; sensitivity type_issn_ja50 adds a journal-article
share of at least 0.5. This script only computes the flags; c6_blocks.py --journal-rule applies a rule.

Usage:  python c6_journal_set.py --run-id <c6 run>      (C_WORK as for c6_full_run.py)
Output: runs/<run_id>/journal_flags.parquet (journal_id, type_journal, issn, n_items, n_ja, ja_share)
        and stage_journal_flags.json; the hash is appended to SHA256SUMS. Never overwritten.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run_dir = HERE / "runs" / args.run_id
    work = Path(os.environ.get("C_WORK", ROOT / "data" / "work" / args.run_id))
    out, marker = run_dir / "journal_flags.parquet", run_dir / "stage_journal_flags.json"
    if marker.exists():
        sys.exit(f"{marker} exists; never overwrite")
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; "
                f"SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'; SET preserve_insertion_order = false")
    con.execute(f"""CREATE TABLE jo AS SELECT journal_id, unnest(omids) AS omid, len(issns) > 0 AS issn
                    FROM read_parquet('{run_dir / 'journals.parquet'}')""")
    # A venue's own record: the pubs row whose OMID is the venue OMID.
    con.execute(f"""CREATE TABLE rec AS SELECT DISTINCT journal_id FROM jo
                    JOIN read_parquet('{work / 'pubs_slim.parquet'}') p USING (omid) WHERE p.type = 'journal'""")
    tmp = out.with_name(out.name + ".tmp")
    con.execute(f"""COPY (
        SELECT j.journal_id, j.journal_id IN (SELECT journal_id FROM rec) AS type_journal, j.issn,
               coalesce(it.n, 0) AS n_items, coalesce(it.n_ja, 0) AS n_ja,
               CASE WHEN it.n > 0 THEN it.n_ja / it.n END AS ja_share
        FROM (SELECT journal_id, bool_or(issn) AS issn FROM jo GROUP BY 1) j
        LEFT JOIN (SELECT journal_id, count(*) AS n, count(*) FILTER (type = 'journal article') AS n_ja
                   FROM read_parquet('{work / 'pubs_j.parquet'}') WHERE journal_id IS NOT NULL GROUP BY 1) it
          USING (journal_id) ORDER BY j.journal_id) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)""")
    tmp.rename(out)
    r = con.execute(f"""SELECT count(*), count(*) FILTER (type_journal), count(*) FILTER (issn),
                               count(*) FILTER (type_journal AND issn),
                               count(*) FILTER (type_journal AND issn AND ja_share >= 0.5)
                        FROM read_parquet('{out}')""").fetchone()
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    info = {"run_id": args.run_id, "venue_groups": r[0], "type_journal": r[1], "issn": r[2],
            "type_journal_and_issn": r[3], "type_journal_and_issn_and_ja_ge_0.5": r[4],
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "output_sha256": digest, "seconds": round(time.time() - t0, 1)}
    marker.write_text(json.dumps(info, indent=2))
    with open(run_dir / "SHA256SUMS", "a") as f:
        f.write(f"{digest}  {out.name}\n")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
