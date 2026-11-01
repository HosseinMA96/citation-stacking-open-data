"""Which venues count as journals? Compare candidate rules on a finished c6 run (read-only).

Why (RESULTS_LOG 2026-10-31): with the Meta venues, c6_full_20261031_02 has 9.0M venue groups,
because books (for chapters) and proceedings volumes are venues too. The CIDRE network should
have journals only. Candidate rules, per venue group (journal_id after the ISSN merge):
  type_journal    one of its venue OMIDs has its own record of type 'journal' in the pubs file
  issn            it has at least one ISSN
  ja_share>=x     share of its items that are journal articles is at least x (0.3, 0.5, 0.7)
  and combinations. For each rule: venues kept, journal articles covered, the aggregated eff
network (nodes, edges, weight) and 2015-2023 eff citations with both ends kept; the overlap of
the rules; and sampled venues where the rules disagree, with names from the Meta dump.

Usage (VM):
  python c6_journal_rule_check.py --src c6_full_20261031_02 --meta <meta_csv dir> \\
      --run-id c6_journalrule_<YYYYMMDD>_01
Output: runs/<run_id>/journal_rules.json, rule_overlap.csv, samples.csv, run.json, SHA256SUMS.
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
RULES = {
    "type_journal": "t",
    "issn": "i",
    "ja_share>=0.3": "s >= 0.3",
    "ja_share>=0.5": "s >= 0.5",
    "ja_share>=0.7": "s >= 0.7",
    "issn & ja_share>=0.5": "i AND s >= 0.5",
    "type_journal & issn": "t AND i",
    "type_journal | (issn & ja_share>=0.5)": "t OR (i AND s >= 0.5)",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="finished c6_full run id")
    ap.add_argument("--meta", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    src = HERE / "runs" / args.src
    work = Path(os.environ.get("C_WORK", ROOT / "data" / "work" / args.src))
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    run_dir.mkdir(parents=True)
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; "
                f"SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'; SET preserve_insertion_order = false")
    q = lambda s: con.execute(s).fetchall()

    con.execute(f"""CREATE TABLE jo AS SELECT journal_id, unnest(omids) AS omid, len(issns) AS n_issn
                    FROM read_parquet('{src / 'journals.parquet'}')""")
    con.execute(f"""CREATE TABLE rec AS SELECT omid, type FROM read_parquet('{work / 'pubs_slim.parquet'}')
                    WHERE omid IN (SELECT omid FROM jo)""")
    con.execute(f"""CREATE TABLE items AS SELECT journal_id, count(*) AS n,
                        count(*) FILTER (type = 'journal article') AS n_ja,
                        mode(type) AS top_type
                    FROM read_parquet('{work / 'pubs_j.parquet'}') WHERE journal_id IS NOT NULL GROUP BY 1""")
    con.execute("""CREATE TABLE v AS
        SELECT j.journal_id, bool_or(r.type = 'journal') AS t, max(j.n_issn) > 0 AS i,
               string_agg(DISTINCT coalesce(r.type, '<no record>'), '|') AS rec_types,
               min(j.omid) AS omid, any_value(it.n) AS n, any_value(it.n_ja) AS n_ja,
               any_value(it.n_ja) / any_value(it.n) AS s, any_value(it.top_type) AS top_type
        FROM jo j LEFT JOIN rec r USING (omid) JOIN items it USING (journal_id) GROUP BY 1""")
    for c in ("t", "i"):
        con.execute(f"UPDATE v SET {c} = coalesce({c}, false)")
    agg = f"read_parquet('{src / 'agg_eff_network.parquet'}')"
    jcr = f"read_parquet('{src / 'pairs_jcr_years.parquet'}')"
    tot = q(f"""SELECT (SELECT count(*) FROM v), (SELECT sum(n_ja) FROM v),
                       (SELECT count(*) FROM read_parquet('{work / 'pubs_j.parquet'}') WHERE type = 'journal article'),
                       (SELECT sum(w) FROM {agg}), (SELECT sum(eff) FROM {jcr} WHERE citing_j IS NOT NULL),
                       (SELECT sum(eff) FROM {jcr})""")[0]
    out = {"src": args.src, "venue_groups": tot[0], "journal_articles_with_venue": int(tot[1]),
           "journal_articles_all": tot[2], "agg_weight": float(tot[3]),
           "eff_2015_2023_both_ends_venue": int(tot[4]), "eff_2015_2023_cited_venue": int(tot[5]),
           "rules": {}}
    for name, cond in RULES.items():
        con.execute(f"CREATE OR REPLACE TEMP TABLE k AS SELECT journal_id FROM v WHERE {cond}")
        kept, ja = q(f"SELECT count(*), sum(n_ja) FROM v WHERE {cond}")[0]
        a = q(f"""SELECT count(*), sum(w), count(DISTINCT citing_j) FROM {agg}
                  WHERE citing_j IN (SELECT journal_id FROM k) AND cited_j IN (SELECT journal_id FROM k)""")[0]
        nodes = q(f"""SELECT count(*) FROM (SELECT citing_j AS j FROM {agg} WHERE citing_j IN (SELECT journal_id FROM k)
                         AND cited_j IN (SELECT journal_id FROM k)
                      UNION SELECT cited_j FROM {agg} WHERE citing_j IN (SELECT journal_id FROM k)
                         AND cited_j IN (SELECT journal_id FROM k))""")[0][0]
        e = q(f"""SELECT sum(eff) FROM {jcr} WHERE citing_j IN (SELECT journal_id FROM k)
                  AND cited_j IN (SELECT journal_id FROM k)""")[0][0]
        out["rules"][name] = {
            "venues_kept": kept, "journal_articles_covered": int(ja or 0),
            "share_of_journal_articles_with_venue": round((ja or 0) / tot[1], 4),
            "agg_nodes": nodes, "agg_edges": a[0], "agg_weight_share": round((a[1] or 0) / tot[3], 4),
            "eff_2015_2023_both_ends": int(e or 0),
            "eff_2015_2023_share_of_both_ends_venue": round((e or 0) / tot[4], 4)}
    ov = con.execute("""SELECT t AS type_journal, i AS issn, s >= 0.5 AS ja_share_ge_05,
                               count(*) AS venues, sum(n_ja) AS journal_articles, sum(n) AS items
                        FROM v GROUP BY ALL ORDER BY journal_articles DESC""").df()
    ov.to_csv(run_dir / "rule_overlap.csv", index=False)
    out["rec_types_top"] = {k: n for k, n in q(
        "SELECT rec_types, count(*) FROM v GROUP BY 1 ORDER BY 2 DESC LIMIT 12")}
    out["top_type_of_venues_not_type_journal"] = {k: n for k, n in q(
        "SELECT top_type, count(*) FROM v WHERE NOT t GROUP BY 1 ORDER BY 2 DESC LIMIT 10")}

    # Samples where rules disagree or a venue is excluded; reproducible (largest + seeded random).
    groups = {
        "excluded_by_type_journal_largest": "NOT t ORDER BY n_ja DESC LIMIT 15",
        "excluded_by_type_journal_random": "NOT t AND n >= 20 ORDER BY hash(journal_id + 4311) LIMIT 10",
        "type_journal_but_ja_share<0.5_largest": "t AND s < 0.5 ORDER BY n DESC LIMIT 10",
        "not_type_journal_but_issn&ja>=0.5_largest": "NOT t AND i AND s >= 0.5 ORDER BY n_ja DESC LIMIT 15",
        "type_journal_no_issn_largest": "t AND NOT i ORDER BY n_ja DESC LIMIT 10",
    }
    con.execute("CREATE TABLE samp (grp VARCHAR, journal_id INTEGER, omid VARCHAR, n BIGINT, n_ja BIGINT, "
                "s DOUBLE, top_type VARCHAR, rec_types VARCHAR, t BOOLEAN, i BOOLEAN)")
    for g, cond in groups.items():
        con.execute(f"INSERT INTO samp SELECT '{g}', journal_id, omid, n, n_ja, s, top_type, rec_types, t, i "
                    f"FROM v WHERE {cond}")
    files = ", ".join(f"'{f}'" for f in sorted(args.meta.rglob("*.csv")))
    con.execute(f"""CREATE TABLE names AS SELECT vo AS omid, any_value(name) AS name FROM (
        SELECT regexp_extract(venue, '\\[omid:(br/[0-9]+)', 1) AS vo, trim(regexp_extract(venue, '^([^\\[]*)\\[', 1)) AS name
        FROM read_csv([{files}], header = true, all_varchar = true, quote = '"', escape = '"',
                      strict_mode = false, null_padding = true, ignore_errors = true))
        WHERE vo IN (SELECT omid FROM samp) GROUP BY 1""")
    samples = con.execute("""SELECT s.grp, s.journal_id, s.omid, n.name, s.n AS items, s.n_ja AS journal_articles,
                                    round(s.s, 3) AS ja_share, s.top_type, s.rec_types, s.t AS type_journal, s.i AS issn
                             FROM samp s LEFT JOIN names n USING (omid) ORDER BY s.grp, s.n_ja DESC""").df()
    samples.to_csv(run_dir / "samples.csv", index=False)
    out["seconds"] = round(time.time() - t0, 1)
    res = run_dir / "journal_rules.json"
    res.write_text(json.dumps(out, indent=2, default=str))
    meta = {"run_id": args.run_id, "script": Path(__file__).name,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "src_run": args.src, "src_sha256sums": (src / "SHA256SUMS").read_text(),
            "work": str(work), "meta": str(args.meta), "python": platform.python_version(),
            "duckdb": duckdb.__version__, "threads": os.environ.get("C_THREADS"), "memory": os.environ.get("C_MEM")}
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
