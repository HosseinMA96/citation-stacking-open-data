"""TODO item 7 (C7-C9): venue coverage by year, and journal-year scores from a finished c6 run.

C7 coverage (needs C_WORK with edges.parquet and pubs_j.parquet, so it runs on the VM): for each
citing year t (2010-2024), all citation edges whose citing item has that year, split by whether the
citing and cited items have a journal, are rule journals, and whether the cited item is in the JCR
window (t-1, t-2). C8 is pairs_jcr_years.parquet from c6 (one file, column t); not copied again.

C9 scores, per recipient journal B in the journal rule and JCR year t (config citing_years), with
c(A->B,t) = eff from pairs_jcr_years (citations from items published in t to B's items from t-1, t-2;
citing items of any type, with or without a journal, as config counting says):
  num            sum_A c(A->B,t), A over all citing items incl. those without a journal (JIF numerator proxy)
  self_share     c(B->B,t) / num
  citable        B's journal articles published in t-1 and t-2 (denominator proxy)
  jif_proxy      num / citable;  jif_proxy_noself = (num - c(B->B,t)) / citable
  ext            sum over citing journals A != B (A not null) of c(A->B,t)
  top_donor      the journal A != B with the largest c(A->B,t) (ties: smallest journal_id)
  top_donor_share_of_num   c(top->B,t) / num       (recipient side of Clarivate's stacking test)
  top_donor_out_share      c(top->B,t) / sum_X c(top->X,t), X over all cited journals
                           (donor side: share of the donor's window citations that go to B)
  donor_hhi      sum_A (c(A->B,t)/ext)^2 over A != B  (concentration of external citations)
  n_donors       number of journals A != B with c(A->B,t) > 0
  reciprocity    sum_{A!=B} min(c(A->B,t), c(B->A,t)) / ext  (share of external citations that B returns)
  burst_log2     log2((num_t + 1) / (num_{t-1} + 1)), num_{t-1} from the same table (0 if absent;
                 for t = 2015 the previous year is not in pairs_jcr_years, so null)
  top_donor_prev c(top->B, t-1) for the same donor (null for t = 2015)
Clarivate's exact suppression formulas are not public in full; these are proxies, checked against the
published JCR-2020 numbers in TODO item 8 (C10). Scores only; no ranking or labels here.

--citing-journal-only (sensitivity, RESULTS_LOG 2026-10-31): drop citing items without a journal from
every count. In 2019-2021 they are 11-14% of num, concentrated in a few taxonomy journals.

Pair table: every (A, B, t) with A != B both rule journals and c(A->B,t) >= pair_min_eff, with both
shares above and the reverse count c(B->A,t). Input for the C10 stacking check.

Usage:  python c9_scores.py --self-test
        python c9_scores.py --src c6_full_20261031_02 --journal-rule main --run-id c9_scores_<YYYYMMDD>_01 [--no-coverage]
Output: runs/<run_id>/journal_year_scores.parquet, pair_scores.parquet, coverage_by_year.csv,
        summary.json, run.json, SHA256SUMS. Never overwrites a run.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

import duckdb
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PAIR_MIN_EFF = 10


def rule_sql(rule):
    c = ["TRUE"]
    if "type_journal" in rule:
        c.append(f"type_journal = {str(rule['type_journal']).upper()}")
    if "issn" in rule:
        c.append(f"issn = {str(rule['issn']).upper()}")
    if "min_ja_share" in rule:
        c.append(f"coalesce(ja_share, 0) >= {rule['min_ja_share']}")
    return " AND ".join(c)


def scores(con, pairs, flags, citable, rule, years, out_scores, out_pairs, citing_journal_only=False):
    yl = ", ".join(map(str, years))
    con.execute(f"CREATE OR REPLACE TABLE rj AS SELECT journal_id FROM read_parquet('{flags}') WHERE {rule_sql(rule)}")
    con.execute(f"""CREATE OR REPLACE TABLE p AS SELECT t, citing_j, cited_j, eff FROM read_parquet('{pairs}')
                    WHERE eff > 0 AND t IN ({yl}){' AND citing_j IS NOT NULL' if citing_journal_only else ''}""")
    con.execute("""CREATE OR REPLACE TABLE dout AS SELECT t, citing_j, sum(eff) AS out_eff FROM p
                   WHERE citing_j IS NOT NULL GROUP BY ALL""")
    con.execute("""CREATE OR REPLACE TABLE pr AS SELECT * FROM p WHERE cited_j IN (SELECT journal_id FROM rj)""")
    con.execute("""CREATE OR REPLACE TABLE ext AS
        SELECT x.t, x.citing_j, x.cited_j, x.eff, coalesce(r.eff, 0) AS rev
        FROM pr x LEFT JOIN p r ON r.t = x.t AND r.citing_j = x.cited_j AND r.cited_j = x.citing_j
        WHERE x.citing_j IS NOT NULL AND x.citing_j <> x.cited_j""")
    con.execute("""CREATE OR REPLACE TABLE base AS
        SELECT t, cited_j AS journal_id, sum(eff) AS num,
               coalesce(sum(eff) FILTER (citing_j = cited_j), 0) AS self
        FROM pr GROUP BY ALL""")
    con.execute("""CREATE OR REPLACE TABLE e AS
        SELECT t, cited_j AS journal_id, sum(eff) AS ext, count(*) AS n_donors,
               sum(least(eff, rev)) AS recip,
               arg_min(citing_j, [-eff, citing_j]) AS top_donor, max(eff) AS top_eff
        FROM ext GROUP BY ALL""")
    con.execute("""CREATE OR REPLACE TABLE h AS
        SELECT x.t, x.cited_j AS journal_id, sum((x.eff / e.ext) ^ 2) AS donor_hhi
        FROM ext x JOIN e ON e.t = x.t AND e.journal_id = x.cited_j GROUP BY ALL""")
    con.execute(f"""CREATE OR REPLACE TABLE cit AS
        SELECT y.t, c.journal_id, sum(c.n_citable) AS citable
        FROM read_parquet('{citable}') c JOIN (SELECT unnest([{yl}]) AS t) y
          ON c.pub_year IN (y.t - 1, y.t - 2) GROUP BY ALL""")
    first = min(years)
    con.execute(f"""COPY (
        SELECT b.t, b.journal_id, b.num, b.self, b.self / b.num AS self_share,
               coalesce(c.citable, 0) AS citable,
               CASE WHEN c.citable > 0 THEN b.num / c.citable END AS jif_proxy,
               CASE WHEN c.citable > 0 THEN (b.num - b.self) / c.citable END AS jif_proxy_noself,
               coalesce(e.ext, 0) AS ext, coalesce(e.n_donors, 0) AS n_donors,
               e.top_donor, e.top_eff AS top_donor_eff,
               e.top_eff / b.num AS top_donor_share_of_num,
               e.top_eff / d.out_eff AS top_donor_out_share,
               h.donor_hhi, e.recip / e.ext AS reciprocity,
               CASE WHEN b.t > {first} THEN log2((b.num + 1) / (coalesce(bp.num, 0) + 1)) END AS burst_log2,
               CASE WHEN b.t > {first} THEN coalesce(tp.eff, 0) END AS top_donor_prev
        FROM base b
        LEFT JOIN e USING (t, journal_id) LEFT JOIN h USING (t, journal_id) LEFT JOIN cit c USING (t, journal_id)
        LEFT JOIN dout d ON d.t = b.t AND d.citing_j = e.top_donor
        LEFT JOIN base bp ON bp.t = b.t - 1 AND bp.journal_id = b.journal_id
        LEFT JOIN p tp ON tp.t = b.t - 1 AND tp.citing_j = e.top_donor AND tp.cited_j = b.journal_id
        ORDER BY b.t, b.journal_id) TO '{out_scores}' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (
        SELECT x.t, x.citing_j, x.cited_j, x.eff, x.rev, x.eff / b.num AS share_of_num,
               x.eff / d.out_eff AS donor_out_share
        FROM ext x JOIN base b ON b.t = x.t AND b.journal_id = x.cited_j
        JOIN dout d ON d.t = x.t AND d.citing_j = x.citing_j
        WHERE x.eff >= {PAIR_MIN_EFF} AND x.citing_j IN (SELECT journal_id FROM rj)
        ORDER BY x.t, x.cited_j, x.citing_j) TO '{out_pairs}' (FORMAT parquet, COMPRESSION zstd)""")


def coverage(con, work, flags, rule):
    con.execute(f"""CREATE OR REPLACE TABLE pj AS SELECT iid, pub_year, journal_id,
                        journal_id IN (SELECT journal_id FROM read_parquet('{flags}') WHERE {rule_sql(rule)}) AS rj
                    FROM read_parquet('{work / 'pubs_j.parquet'}') WHERE pub_year IS NOT NULL""")
    return con.execute(f"""
        SELECT a.pub_year AS t, count(*) AS edges,
               count(*) FILTER (b.iid IS NOT NULL) AS cited_with_year,
               count(*) FILTER (a.journal_id IS NOT NULL) AS citing_journal,
               count(*) FILTER (b.journal_id IS NOT NULL) AS cited_journal,
               count(*) FILTER (a.journal_id IS NOT NULL AND b.journal_id IS NOT NULL) AS both_journal,
               count(*) FILTER (coalesce(a.rj, false) AND coalesce(b.rj, false)) AS both_rule,
               count(*) FILTER (b.journal_id IS NOT NULL AND a.pub_year - b.pub_year IN (1, 2)) AS cited_journal_in_window,
               count(*) FILTER (coalesce(b.rj, false) AND a.pub_year - b.pub_year IN (1, 2)) AS cited_rule_in_window
        FROM read_parquet('{work / 'edges.parquet'}') x
        JOIN pj a ON x.citing_iid = a.iid LEFT JOIN pj b ON x.cited_iid = b.iid
        WHERE a.pub_year BETWEEN 2010 AND 2024 GROUP BY 1 ORDER BY 1""").df()


def self_test():
    """Hand example: journals 1, 2, 3 in the rule, 9 not; years 2015, 2016."""
    d = Path(tempfile.mkdtemp())
    pd.DataFrame({"t": [2015, 2015, 2015, 2015, 2015, 2015, 2016, 2016, 2016],
                  "citing_j": [1, 2, 3, None, 1, 2, 2, 1, 3],
                  "cited_j": [1, 1, 1, 1, 2, 3, 1, 1, 1],
                  "eff": [4, 12, 2, 2, 3, 6, 20, 1, 0], "prev": 0}).astype({"citing_j": "Int32"}) \
        .to_parquet(d / "pairs.parquet", index=False)
    pd.DataFrame({"journal_id": [1, 2, 3, 9], "type_journal": [True, True, True, False],
                  "issn": True, "ja_share": 1.0}).to_parquet(d / "flags.parquet", index=False)
    pd.DataFrame({"journal_id": [1, 1, 1], "pub_year": [2013, 2014, 2015], "n_all": 5,
                  "n_citable": [5, 5, 10]}).to_parquet(d / "cit.parquet", index=False)
    con = duckdb.connect()
    scores(con, d / "pairs.parquet", d / "flags.parquet", d / "cit.parquet", {"type_journal": True},
           [2015, 2016], d / "s.parquet", d / "pp.parquet")
    s = pd.read_parquet(d / "s.parquet").set_index(["t", "journal_id"])
    pp = pd.read_parquet(d / "pp.parquet")
    r = s.loc[(2015, 1)]
    # num 4+12+2+2 = 20; self 4; ext 14; top donor 2 (12); donor 2 out = 12+6 = 18;
    # hhi (12/14)^2 + (2/14)^2; reciprocity: 2->1 12 vs 1->2 3 -> 3; 3->1 2 vs 1->3 0 -> 0 => 3/14.
    checks = {
        "num": r.num == 20, "self_share": abs(r.self_share - 0.2) < 1e-12, "citable": r.citable == 10,
        "jif_proxy": abs(r.jif_proxy - 2.0) < 1e-12, "jif_noself": abs(r.jif_proxy_noself - 1.6) < 1e-12,
        "ext": r.ext == 14, "n_donors": r.n_donors == 2, "top_donor": r.top_donor == 2,
        "share_num": abs(r.top_donor_share_of_num - 0.6) < 1e-12,
        "out_share": abs(r.top_donor_out_share - 12 / 18) < 1e-12,
        "hhi": abs(r.donor_hhi - ((12 / 14) ** 2 + (2 / 14) ** 2)) < 1e-12,
        "recip": abs(r.reciprocity - 3 / 14) < 1e-12,
        "burst_first_null": pd.isna(r.burst_log2),
        # 2016: num 20 + 1 = 21 (eff 0 row dropped); citable 2014+2015 = 15; burst log2(22/21); top donor 2 prev 12.
        "num16": s.loc[(2016, 1)].num == 21, "citable16": s.loc[(2016, 1)].citable == 15,
        "burst16": abs(s.loc[(2016, 1)].burst_log2 - __import__("math").log2(22 / 21)) < 1e-12,
        "prev16": s.loc[(2016, 1)].top_donor_prev == 12,
        "no_journal_9": 9 not in s.index.get_level_values(1),
        # pairs with eff >= 10: (2015, 2->1, 12) and (2016, 2->1, 20)
        "pairs": len(pp) == 2 and set(pp.eff) == {12, 20},
        "pair_rev": int(pp[pp.t == 2015].rev.iloc[0]) == 3,
    }
    scores(con, d / "pairs.parquet", d / "flags.parquet", d / "cit.parquet", {"type_journal": True},
           [2015, 2016], d / "s2.parquet", d / "pp2.parquet", citing_journal_only=True)
    s2 = pd.read_parquet(d / "s2.parquet").set_index(["t", "journal_id"])
    checks["journal_only_num"] = s2.loc[(2015, 1)].num == 18          # the null-journal 2 dropped
    checks["journal_only_share"] = abs(s2.loc[(2015, 1)].top_donor_share_of_num - 12 / 18) < 1e-12
    ok = all(bool(v) for v in checks.values())
    print({k: bool(v) for k, v in checks.items()}, "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--journal-rule", default="main")
    ap.add_argument("--run-id")
    ap.add_argument("--no-coverage", action="store_true")
    ap.add_argument("--citing-journal-only", action="store_true",
                    help="sensitivity: drop citing items without a journal from all counts (default keeps them, config counting)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
    if not (args.src and args.run_id):
        sys.exit("--src and --run-id are required")
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    rule, years = cfg["journal_rules"][args.journal_rule], cfg["jcr_window"]["citing_years"]
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
    if os.environ.get("C_TEMP_DIR"):
        con.execute(f"SET temp_directory = '{os.environ['C_TEMP_DIR']}'")
    sc, pp = run_dir / "journal_year_scores.parquet", run_dir / "pair_scores.parquet"
    scores(con, src / "pairs_jcr_years.parquet", src / "journal_flags.parquet", src / "citable_by_year.parquet",
           rule, years, sc, pp, args.citing_journal_only)
    t_scores = round(time.time() - t0, 1)
    s = f"read_parquet('{sc}')"
    summ = {"src": args.src, "journal_rule": args.journal_rule, "rule": rule, "years": years,
            "pair_min_eff": PAIR_MIN_EFF, "citing_journal_only": args.citing_journal_only, "seconds_scores": t_scores,
            "pair_rows": con.execute(f"SELECT count(*) FROM read_parquet('{pp}')").fetchone()[0], "by_year": {}}
    cols = ["num", "self_share", "jif_proxy", "top_donor_share_of_num", "top_donor_out_share",
            "donor_hhi", "reciprocity", "burst_log2"]
    for t in years:
        row = {"journals": con.execute(f"SELECT count(*) FROM {s} WHERE t = {t}").fetchone()[0],
               "journals_num_ge_20": con.execute(f"SELECT count(*) FROM {s} WHERE t = {t} AND num >= 20").fetchone()[0],
               "journals_citable_0": con.execute(f"SELECT count(*) FROM {s} WHERE t = {t} AND citable = 0").fetchone()[0],
               "num_total": int(con.execute(f"SELECT sum(num) FROM {s} WHERE t = {t}").fetchone()[0])}
        for c in cols:   # quantiles among journals with num >= 20, to avoid tiny-count noise
            q = con.execute(f"""SELECT quantile_cont({c}, [0.5, 0.9, 0.99]) FROM {s}
                                WHERE t = {t} AND num >= 20 AND {c} IS NOT NULL""").fetchone()[0]
            row[f"{c}_p50_p90_p99_num_ge_20"] = [round(v, 4) for v in q] if q else None
        summ["by_year"][str(t)] = row
    if not args.no_coverage:
        t1 = time.time()
        cov = coverage(con, work, src / "journal_flags.parquet", rule)
        for c in ["citing_journal", "cited_journal", "both_journal", "both_rule"]:
            cov[f"share_{c}"] = (cov[c] / cov.edges).round(4)
        cov.to_csv(run_dir / "coverage_by_year.csv", index=False)
        summ["seconds_coverage"] = round(time.time() - t1, 1)
    summ["seconds_total"] = round(time.time() - t0, 1)
    summ["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256((HERE / "config.yaml").read_bytes()).hexdigest(),
        "src_run": args.src, "src_sha256sums": (src / "SHA256SUMS").read_text(), "work": str(work),
        "python": platform.python_version(), "duckdb": duckdb.__version__, "pandas": pd.__version__,
        "threads": os.environ.get("C_THREADS"), "memory": os.environ.get("C_MEM")}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
