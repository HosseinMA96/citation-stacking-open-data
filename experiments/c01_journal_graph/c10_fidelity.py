"""C10 step 2: fidelity against Clarivate's published JCR-2020 numbers, and ranks of all labeled journals.

Criteria fixed before this script was run (RESULTS_LOG 2026-10-31 "C10 pre-registration"; config.yaml c10):
  1 fidelity: each of the 9 published JCR-2020 percentages is reproduced if |ours - Clarivate| <= pass_abs_pp.
     self:      self_share = c(B->B,t) / num(B,t)                      vs "% Self Cites in JIF Numerator"
     stacking:  c(D->R,t) / num(R,t)                                   vs "% JIF Numerator"
                c(D->R,t) eff / c(D->R,t) prev  (cited years < t; upper bound, same-year citations missing)
                                                                       vs "% Exchange to JIF Years"
  2 signal: a labeled journal "ranks" if in the top pass_top_share of its year among journals with num >= min_num:
     self cases on self_share, stacking recipients on top_donor_share_of_num; other rows get both, reported apart.
     JIF proxy ranks (citable >= min_citable, and the sensitivity values) are reported, not used for the criteria.
  3 checkpoint: signal if at least half of the matched 2020 self and stacking-recipient journals rank (criterion 2).
Main scores: config c10.scores_main (citing items with a journal); sensitivity: c10.scores_sensitivity.

Usage:  python c10_fidelity.py --self-test
        python c10_fidelity.py --src c6_full_20261031_02 --match c10_match_20261031_03 --run-id c10_fidelity_<YYYYMMDD>_01
Output: runs/<run_id>/fidelity.csv, ranks.csv, summary.json, run.json, SHA256SUMS. Never overwrites.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def rank_in_year(scores, t, col, jid, min_num, min_citable=None):
    """Rank (1 = highest) of journal jid on col among eligible journals of year t; ties share the best rank."""
    s = scores[(scores.t == t) & (scores.num >= min_num) & scores[col].notna()]
    if min_citable is not None:
        s = s[s.citable >= min_citable]
    row = s[s.journal_id == jid]
    if row.empty:
        return None, len(s), None
    v = row[col].iloc[0]
    r = int((s[col] > v).sum()) + 1
    return r, len(s), float(v)


def self_test():
    sc = pd.DataFrame({"t": 2020, "journal_id": [1, 2, 3, 4, 5], "num": [100, 100, 100, 5, 100],
                       "citable": [30, 30, 5, 30, 30], "x": [0.9, 0.5, 0.95, 0.99, 0.5]})
    checks = {
        "rank": rank_in_year(sc, 2020, "x", 1, 20) == (2, 4, 0.9),          # 3 is higher; 4 fails min_num
        "tie": rank_in_year(sc, 2020, "x", 5, 20)[0] == 3,                    # 2 and 5 tie at rank 3
        "citable": rank_in_year(sc, 2020, "x", 1, 20, 20) == (1, 3, 0.9),    # 3 fails min_citable
        "ineligible": rank_in_year(sc, 2020, "x", 4, 20)[0] is None,
    }
    ok = all(checks.values())
    print(checks, "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--match")
    ap.add_argument("--run-id")
    ap.add_argument("--labels", default="suppressions.csv", help="file in data/ (v2 since 2026-10-31)")
    ap.add_argument("--fidelity-years", default="2020", help="comma list; v1 run used 2020 only")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())["c10"]
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    fyears = {int(y) for y in args.fidelity_years.split(",")}
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    flags = pd.read_parquet(runs / args.src / "journal_flags.parquet")
    in_rule = set(flags.journal_id[flags.type_journal & flags.issn])
    sc = {k: pd.read_parquet(runs / cfg[k] / "journal_year_scores.parquet") for k in ("scores_main", "scores_sensitivity")}
    mn, pp, top = cfg["min_num"], cfg["pass_abs_pp"], cfg["pass_top_share"]

    # 1 fidelity (rows with published numbers in --fidelity-years)
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'")
    fid = []
    pairs_path = runs / args.src / "pairs_jcr_years.parquet"
    for r in sup[sup.jcr_data_year.isin(fyears)].itertuples():
        t = int(r.jcr_data_year)
        if r.type == "self" and pd.notna(r.pct_self_cites_jif_numerator):
            j = jid.get(r.journal)
            for k, s in sc.items():
                row = s[(s.t == t) & (s.journal_id == j)]
                ours = float(row.self_share.iloc[0]) * 100 if len(row) else np.nan
                fid.append({"t": t, "journal": r.journal, "matched": j is not None,
                            "metric": "self_cites_pct_jif_numerator", "scores": k,
                            "clarivate": r.pct_self_cites_jif_numerator, "ours": round(ours, 2),
                            "num": int(row.num.iloc[0]) if len(row) else None})
    recs = sup[sup.jcr_data_year.isin(fyears) & (sup.role == "recipient") & sup.pct_jif_numerator.notna()]
    for (t, rec, pj, px), g in recs.groupby(["jcr_data_year", "journal", "pct_jif_numerator", "pct_exchange_to_jif_years"]):
        t = int(t)
        donors = sorted(g.partner_journal)
        R, Ds = jid.get(rec), [jid.get(d) for d in donors]
        if R is None or any(d is None for d in Ds):
            fid.append({"t": t, "journal": rec, "partner": "; ".join(donors), "matched": False,
                        "metric": "donor_pct_jif_numerator", "scores": "n/a", "clarivate": pj})
            fid.append({"t": t, "journal": rec, "partner": "; ".join(donors), "matched": False,
                        "metric": "pct_exchange_to_jif_years", "scores": "n/a", "clarivate": px})
            continue
        eff, prev = con.execute(f"""SELECT coalesce(sum(eff), 0), coalesce(sum(prev), 0)
            FROM read_parquet('{pairs_path}')
            WHERE t = {t} AND citing_j IN ({",".join(map(str, Ds))}) AND cited_j = {R}""").fetchone()
        for k, s in sc.items():
            row = s[(s.t == t) & (s.journal_id == R)]
            num = int(row.num.iloc[0]) if len(row) else 0
            fid.append({"t": t, "journal": rec, "partner": "; ".join(donors), "matched": True,
                        "metric": "donor_pct_jif_numerator", "scores": k, "clarivate": pj,
                        "ours": round(100 * eff / num, 2) if num else np.nan, "num": num, "pair_eff": int(eff)})
        fid.append({"t": t, "journal": rec, "partner": "; ".join(donors), "matched": True,
                    "metric": "pct_exchange_to_jif_years", "scores": "pairs (counting-independent)", "clarivate": px,
                    "ours": round(100 * eff / prev, 2) if prev else np.nan, "pair_eff": int(eff), "pair_prev": int(prev)})
    fid = pd.DataFrame(fid)
    fid["diff_pp"] = (fid.ours - fid.clarivate).round(2)
    fid["pass"] = fid.diff_pp.abs() <= pp

    # 2 ranks for every labeled row in the score years
    years = set(sc["scores_main"].t.unique())
    rk = []
    for r in sup.itertuples():
        t = int(r.jcr_data_year)
        j = jid.get(r.journal)
        base = {"jcr_data_year": t, "journal": r.journal, "type": r.type, "role": r.role,
                "journal_id": j, "in_rule_main": j in in_rule if j else None}
        if t not in years or j is None or j not in in_rule:
            rk.append({**base, "note": "year outside scores" if t not in years else
                       ("not matched" if j is None else "not in rule main")})
            continue
        for k, s in sc.items():
            row = {**base, "scores": k}
            row_s = s[(s.t == t) & (s.journal_id == j)]
            row["num"] = int(row_s.num.iloc[0]) if len(row_s) else 0
            row["citable"] = int(row_s.citable.iloc[0]) if len(row_s) else None
            if len(row_s):
                row["top_donor_id"] = row_s.top_donor.iloc[0]
            for col in ("self_share", "top_donor_share_of_num", "reciprocity", "burst_log2"):
                rnk, n, v = rank_in_year(s, t, col, j, mn)
                row[f"{col}"] = v
                row[f"{col}_rank"] = rnk
                row[f"{col}_n"] = n
                row[f"{col}_pct"] = round(rnk / n, 5) if rnk else None
            for c in [cfg["min_citable"]] + cfg["min_citable_sensitivity"]:
                rnk, n, v = rank_in_year(s, t, "jif_proxy", j, mn, c)
                row[f"jif_proxy_cit{c}_rank"], row[f"jif_proxy_cit{c}_n"] = rnk, n
            rk.append(row)
    rk = pd.DataFrame(rk)
    rev = {v: k for k, v in jid.items()}
    if "top_donor_id" in rk:
        rk["top_donor_name_if_labeled"] = rk.top_donor_id.map(lambda x: rev.get(int(x)) if pd.notna(x) else None)

    def relevant(r):
        if r.get("note") is not None and isinstance(r.get("note"), str):
            return None
        if str(r.type).startswith("self"):
            return r.self_share_pct
        if str(r.type).startswith("stacking") and r.role == "recipient":
            return r.top_donor_share_of_num_pct
        return None
    rk["relevant_pct"] = rk.apply(relevant, axis=1)
    rk["ranks_top"] = rk.relevant_pct.map(lambda x: bool(x <= top) if pd.notna(x) else None)

    rk = rk.drop_duplicates(subset=[c for c in ("jcr_data_year", "journal", "type", "role", "scores") if c in rk])
    # 3 checkpoint on the main scores, JCR 2020, self + stacking recipients
    c = rk[(rk.jcr_data_year == 2020) & (rk.get("scores") == "scores_main") & rk.relevant_pct.notna()]
    summ = {"criteria": cfg, "fidelity_pass": {k: f"{int(g['pass'].sum())}/{len(g)}" for k, g in fid.groupby("scores")},
            "checkpoint_2020": {"journals": len(c), "rank_top": int(c.ranks_top.sum()),
                                "signal": bool(len(c) and c.ranks_top.sum() >= len(c) / 2)},
            "ranks_top_by_year_main": {str(int(y)): f"{int(g.ranks_top.sum())}/{len(g)}" for y, g in
                                       rk[(rk.get("scores") == "scores_main") & rk.relevant_pct.notna()].groupby("jcr_data_year")}}
    mm = rk[(rk.get("scores") == "scores_main") & rk.relevant_pct.notna()].copy()
    mm["kind"] = np.where(mm.type.astype(str).str.startswith("self"), "self", "stacking_recipient")
    summ["ranks_top_pooled_main"] = {k: f"{int(g.ranks_top.sum())}/{len(g)}" for k, g in mm.groupby("kind")}
    summ["relevant_pct_median_main"] = {k: round(float(g.relevant_pct.median()), 4) for k, g in mm.groupby("kind")}
    summ["relevant_pct_top5_main"] = {k: f"{int((g.relevant_pct <= 0.05).sum())}/{len(g)}" for k, g in mm.groupby("kind")}
    fm = fid[fid.matched.astype(bool) & fid.ours.notna() & (fid.scores != "scores_sensitivity")]
    summ["fidelity_pass_by_metric"] = {k: f"{int(g['pass'].sum())}/{len(g)}" for k, g in fm.groupby("metric")}
    summ["fidelity_median_abs_diff_pp"] = {k: round(float(g.diff_pp.abs().median()), 2) for k, g in fm.groupby("metric")}
    summ["fidelity_median_signed_diff_pp"] = {k: round(float(g.diff_pp.median()), 2) for k, g in fm.groupby("metric")}
    run_dir.mkdir(parents=True)
    fid.to_csv(run_dir / "fidelity.csv", index=False)
    rk.to_csv(run_dir / "ranks.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256((HERE / "config.yaml").read_bytes()).hexdigest(),
        "labels": args.labels, "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "fidelity_years": sorted(fyears),
        "src_run": args.src, "match_run": args.match, "scores": {k: cfg[k] for k in ("scores_main", "scores_sensitivity")},
        "python": platform.python_version(), "duckdb": duckdb.__version__, "pandas": pd.__version__}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    pd.set_option("display.width", 250)
    print(fid.to_string()); print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
