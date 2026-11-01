"""Diagnose the venue column of the full pubs file (found 2026-10-31 after c6_full_20261031_01).

c6_full_20261031_01 found a venue OMID for only 12.7M of 107M pubs rows, against 81% in the
laptop sample. Spot checks showed most venues as a bare link (https://w3id.org/oc/meta/br/<id>)
instead of "Name [omid:br/<id> issn:...]", which the pubs stage regex does not match.
This script measures that over the whole file, read-only:
  formats    venue string classes (empty, bracket with omid, bare link, other) + examples
  overlap    are bare-link OMIDs the same id space as bracket OMIDs (distinct-id overlap)
  targets    do bare-link OMIDs exist as rows of the pubs file, with which type
  by_year    journal articles 2013-2023 with a venue OMID, old rule vs either form

Usage (VM):  python c6_venue_check.py --pubs <pubs.csv.gz> --run-id c6_venuecheck_<YYYYMMDD>_01
Output: runs/<run_id>/venue_check.json, run.json, SHA256SUMS. Never overwrites a run.
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
BRACKET = r"\[omid:(br/[0-9]+)"
LINK = r"^https://w3id\.org/oc/meta/(br/[0-9]+)$"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pubs", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    run_dir.mkdir(parents=True)
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; "
                f"SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'")
    con.execute(f"""CREATE TABLE p AS SELECT omid, TRY_CAST(pub_year AS SMALLINT) AS y, type, trim(venue) AS v
        FROM read_csv('{args.pubs}', header = true, all_varchar = true, quote = '"', escape = '"',
                      strict_mode = false, null_padding = true, ignore_errors = true)""")
    con.execute(f"""CREATE TABLE c AS SELECT *,
        CASE WHEN v IS NULL OR v = '' THEN 'empty'
             WHEN regexp_matches(v, '{BRACKET}') THEN 'bracket_omid'
             WHEN regexp_matches(v, '{LINK}') THEN 'bare_link'
             ELSE 'other' END AS fmt,
        coalesce(NULLIF(regexp_extract(v, '{BRACKET}', 1), ''),
                 NULLIF(regexp_extract(v, '{LINK}', 1), '')) AS vo FROM p""")
    q = lambda s: con.execute(s).fetchall()
    out = {"rows": q("SELECT count(*) FROM c")[0][0]}
    out["formats"] = {f: n for f, n in q("SELECT fmt, count(*) FROM c GROUP BY 1 ORDER BY 2 DESC")}
    out["format_examples"] = {f: [r[0][:160] for r in q(
        f"SELECT v FROM c WHERE fmt = '{f}' USING SAMPLE reservoir(5 ROWS) REPEATABLE (4311)")]
        for f in ("bracket_omid", "bare_link", "other")}
    out["formats_journal_articles"] = {f: n for f, n in q(
        "SELECT fmt, count(*) FROM c WHERE type = 'journal article' GROUP BY 1 ORDER BY 2 DESC")}
    con.execute("CREATE TABLE ids AS SELECT vo, bool_or(fmt = 'bracket_omid') AS b, bool_or(fmt = 'bare_link') AS l "
                "FROM c WHERE vo IS NOT NULL GROUP BY 1")
    r = q("SELECT count(*), count(*) FILTER (b), count(*) FILTER (l), count(*) FILTER (b AND l) FROM ids")[0]
    out["overlap"] = {"distinct_venue_omids": r[0], "seen_in_bracket": r[1], "seen_as_link": r[2], "seen_both": r[3]}
    # Each pubs row's own id is "omid:br/<id>" (checked on sampled rows); does a bare-link venue point at one?
    t = q("""SELECT coalesce(p.type, '<no row>'), count(*) FROM ids
             LEFT JOIN (SELECT replace(omid, 'omid:', '') AS o, type FROM p) p ON p.o = ids.vo
             WHERE ids.l AND NOT ids.b GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
    out["link_only_targets_by_type"] = {k: n for k, n in t}
    # Added for run _02: what does a journal article's bare link point to, counted per article, and
    # does that target row carry a bracket venue itself (an issue/volume pointing up to its journal)?
    con.execute("CREATE TABLE t AS SELECT replace(omid, 'omid:', '') AS o, type, fmt, vo FROM c")
    out["journal_article_link_targets"] = [
        {"target_type": a, "target_venue_format": b, "articles": n} for a, b, n in q("""
            SELECT coalesce(t.type, '<no row>'), coalesce(t.fmt, '<no row>'), count(*) FROM c
            LEFT JOIN t ON t.o = c.vo WHERE c.type = 'journal article' AND c.fmt = 'bare_link'
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20""")]
    out["link_target_examples"] = [
        {"article_venue": a, "target_type": b, "target_venue": (v or "")[:160]} for a, b, v in q("""
            SELECT c.v, t.type, t2.v FROM c JOIN t ON t.o = c.vo JOIN c t2 ON replace(t2.omid, 'omid:', '') = t.o
            WHERE c.type = 'journal article' AND c.fmt = 'bare_link'
            USING SAMPLE reservoir(8 ROWS) REPEATABLE (4311)""")]
    out["type_counts_all_rows"] = {k or "<null>": n for k, n in q(
        "SELECT type, count(*) FROM c GROUP BY 1 ORDER BY 2 DESC")}
    out["by_year_journal_articles"] = {str(y): {"rows": n, "venue_old_rule": a, "venue_either_form": b}
        for y, n, a, b in q("""SELECT y, count(*), count(*) FILTER (fmt = 'bracket_omid'), count(vo)
            FROM c WHERE type = 'journal article' AND y BETWEEN 2013 AND 2023 GROUP BY 1 ORDER BY 1""")}
    out["seconds"] = round(time.time() - t0, 1)
    res = run_dir / "venue_check.json"
    res.write_text(json.dumps(out, indent=2))
    meta = {"run_id": args.run_id, "script": Path(__file__).name,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "pubs": str(args.pubs), "pubs_bytes": args.pubs.stat().st_size,
            "python": platform.python_version(), "duckdb": duckdb.__version__,
            "threads": os.environ.get("C_THREADS"), "memory": os.environ.get("C_MEM")}
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in (res, run_dir / "run.json"):
            f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
