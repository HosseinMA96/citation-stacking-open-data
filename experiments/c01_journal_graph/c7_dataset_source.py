"""R2: what are the `dataset`-typed citing items behind the 2015-2021 coverage dip (c7_covgap_20261031_02)?

On the VM (C_WORK of the c6 run; Meta CSV dump):
  D = citing items with type 'dataset', no journal, pub_year 2018-2021, with at least one outgoing edge
  C = items cited by D's 2020 items that have no pub_year (the "cited without year" side of the dip)
One pass over the OpenCitations Meta CSVs gives the DOI (from `id`) and type of every OMID in D and C.
Reported: DOI-prefix distribution (prefix = registrant, e.g. 10.5281 = Zenodo) of D by year and of C, the Meta
`type` of C, and a seeded sample of 25 D and 25 C records (DOI, type, title truncated; no author fields).

Usage:  python c7_dataset_source.py --src c6_full_20261031_02 --meta <meta_csv dir> --run-id c7_dsource_<YYYYMMDD>_01
Output: runs/<run_id>/prefix_citing.csv, prefix_cited.csv, type_cited.csv, samples.csv, summary.json, run.json, SHA256SUMS.
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
SEED = 4311


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--meta", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    work = Path(os.environ.get("C_WORK", ROOT / "data" / "work" / args.src))
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'; "
                "SET preserve_insertion_order = false")
    if os.environ.get("C_TEMP_DIR"):
        con.execute(f"SET temp_directory = '{os.environ['C_TEMP_DIR']}'")
    pj, ps, ed = (f"read_parquet('{work / n}')" for n in ("pubs_j.parquet", "pubs_slim.parquet", "edges.parquet"))
    con.execute(f"""CREATE TABLE d AS SELECT p.iid, p.pub_year AS t, s.omid FROM {pj} p JOIN {ps} s USING (iid)
                    WHERE p.type = 'dataset' AND p.journal_id IS NULL AND p.pub_year BETWEEN 2018 AND 2021""")
    con.execute(f"CREATE TABLE d2 AS SELECT * FROM d WHERE iid IN (SELECT citing_iid FROM {ed} WHERE citing_iid IN (SELECT iid FROM d))")
    con.execute(f"""CREATE TABLE c AS SELECT DISTINCT e.cited_iid AS iid, s.omid FROM {ed} e
                    JOIN (SELECT iid FROM d2 WHERE t = 2020) x ON e.citing_iid = x.iid
                    JOIN {ps} s ON s.iid = e.cited_iid WHERE s.pub_year IS NULL""")
    con.execute("CREATE TABLE want AS SELECT omid FROM d2 UNION SELECT omid FROM c")
    files = ", ".join(f"'{f}'" for f in sorted(args.meta.rglob("*.csv")))
    con.execute(f"""CREATE TABLE m AS SELECT * FROM (
        SELECT NULLIF(regexp_extract(id, 'omid:(br/[0-9]+)', 1), '') AS omid,
               NULLIF(regexp_extract(id, 'doi:(10\\.[0-9]+/[^ ]+)', 1), '') AS doi, type, left(title, 120) AS title
        FROM read_csv([{files}], header = true, all_varchar = true, quote = '"', escape = '"',
                      strict_mode = false, null_padding = true, ignore_errors = true))
        WHERE omid IN (SELECT omid FROM want)""")
    con.execute("CREATE TABLE m1 AS SELECT omid, any_value(doi) AS doi, any_value(type) AS type, any_value(title) AS title FROM m GROUP BY 1")
    pre = "coalesce(regexp_extract(doi, '^(10\\.[0-9]+)/', 1), '<no doi>')"
    run_dir.mkdir(parents=True)
    con.execute(f"""COPY (SELECT d2.t, {pre} AS prefix, count(*) AS items FROM d2 LEFT JOIN m1 USING (omid)
                          GROUP BY ALL ORDER BY t, items DESC) TO '{run_dir / 'prefix_citing.csv'}' (HEADER)""")
    con.execute(f"""COPY (SELECT {pre} AS prefix, count(*) AS items FROM c LEFT JOIN m1 USING (omid)
                          GROUP BY ALL ORDER BY items DESC) TO '{run_dir / 'prefix_cited.csv'}' (HEADER)""")
    con.execute(f"""COPY (SELECT coalesce(m1.type, '<not in meta>') AS meta_type, count(*) AS items FROM c LEFT JOIN m1 USING (omid)
                          GROUP BY ALL ORDER BY items DESC) TO '{run_dir / 'type_cited.csv'}' (HEADER)""")
    con.execute(f"SELECT setseed({SEED / 10000})")
    con.execute(f"""COPY (
        (SELECT 'citing_dataset_2020' AS side, d2.omid, m1.doi, m1.type, m1.title FROM d2 LEFT JOIN m1 USING (omid)
         WHERE d2.t = 2020 ORDER BY hash(d2.omid || '{SEED}') LIMIT 25)
        UNION ALL
        (SELECT 'cited_without_year' AS side, c.omid, m1.doi, m1.type, m1.title FROM c LEFT JOIN m1 USING (omid)
         ORDER BY hash(c.omid || '{SEED}') LIMIT 25)) TO '{run_dir / 'samples.csv'}' (HEADER)""")
    q = lambda s: con.execute(s).fetchall()
    summ = {"citing_dataset_items_by_year": dict(q("SELECT t, count(*) FROM d2 GROUP BY 1 ORDER BY 1")),
            "cited_without_year_items_2020": q("SELECT count(*) FROM c")[0][0],
            "meta_matched_citing": q("SELECT count(*) FROM d2 JOIN m1 USING (omid)")[0][0],
            "meta_matched_cited": q("SELECT count(*) FROM c JOIN m1 USING (omid)")[0][0],
            "top_prefix_citing_2020": q(f"SELECT {pre}, count(*) FROM d2 LEFT JOIN m1 USING (omid) WHERE t = 2020 GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
            "top_prefix_cited": q(f"SELECT {pre}, count(*) FROM c LEFT JOIN m1 USING (omid) GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
            "seconds": round(time.time() - t0, 1)}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "src_run": args.src,
        "work": str(work), "meta": str(args.meta), "seed": SEED, "python": platform.python_version(),
        "duckdb": duckdb.__version__}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
