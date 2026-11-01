"""R4 follow-up (post hoc): consensus over partitions for the recipient-centric flags.

A journal-year is flagged at level k if the variant flags it in at least k of the 7 rule-`main` partitions
(k = 1 "any", 4 "majority", 7 "all"). For each k: journals ever flagged, base rate among journals with max yearly
num >= 20, enrichment of listed journals (self / stacking, with and without the design cases), and lead time.
Labels and matching as c12_eval_labels.py. Laptop, read-only.

Usage:  python c12_consensus.py --recip c12_recip_20261031_01 --scores c9_scores_20261031_02 \\
            --match c10_match_20261031_05 --labels suppressions_v2.csv --run-id c12_consensus_<YYYYMMDD>_01
Output: runs/<run_id>/consensus_flags.csv, enrichment.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import duckdb
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TAGS = ["main", "main_s1", "main_s2", "main_s3", "main_s4", "main_s4311_rep", "main_s4311_t1a"]
DESIGN_CASES = {"Ukrainian Journal of Physical Optics", "Climate Change Economics"}


def main():
    ap = argparse.ArgumentParser()
    for a in ("--recip", "--scores", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    f = pd.read_csv(runs / args.recip / "flags.csv")
    f = f[f.tag.isin(TAGS)]
    votes = f.groupby(["t", "journal_id"]).tag.nunique().rename("partitions").reset_index()
    s = duckdb.sql(f"SELECT journal_id, max(num) AS mx FROM read_parquet('{runs / args.scores / 'journal_year_scores.parquet'}') GROUP BY 1").df()
    base = set(s.journal_id[s.mx >= 20])
    sup = pd.read_csv(ROOT / "data" / args.labels)
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    sup = sup[sup.type.isin(["self", "stacking"])].copy()
    sup["jid"] = sup.journal.map(jid)
    sup = sup[sup.jid.notna()]
    first = sup.groupby("jid").jcr_data_year.min()
    sets = {"self": set(sup[sup.type == "self"].jid.astype(int)), "stacking": set(sup[sup.type == "stacking"].jid.astype(int))}
    design = {jid[n] for n in DESIGN_CASES if n in jid}
    rows = []
    for k in (1, 4, 7):
        ever = set(votes[votes.partitions >= k].journal_id)
        rate = len(ever & base) / len(base)
        for kd, L0 in sets.items():
            for excl in (False, True):
                L = [j for j in L0 if j in base and not (excl and j in design)]
                hit = sum(j in ever for j in L)
                v = votes[(votes.partitions >= k) & votes.journal_id.isin(L)].copy()
                v["first"] = v.journal_id.map(first)
                early = v[v.t < v["first"]].journal_id.nunique()
                rows.append({"min_partitions": k, "kind": kd, "exclude_design_cases": excl, "base_rate": round(rate, 5),
                             "base_flagged": len(ever & base), "listed": len(L), "listed_flagged": hit,
                             "listed_rate": round(hit / len(L), 4), "enrichment": round(hit / len(L) / rate, 2),
                             "p_one_sided": binomtest(hit, len(L), rate, alternative="greater").pvalue,
                             "listed_flagged_before_first_listing": early})
    enr = pd.DataFrame(rows)
    summ = {"flagged_journal_years_by_k": {k: int((votes.partitions >= k).sum()) for k in (1, 4, 7)},
            "stacking_no_design": enr[(enr.kind == "stacking") & enr.exclude_design_cases].drop(columns=["kind", "exclude_design_cases"]).to_dict("records")}
    run_dir.mkdir(parents=True)
    votes.to_csv(run_dir / "consensus_flags.csv", index=False)
    enr.to_csv(run_dir / "enrichment.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "recip_run": args.recip,
        "scores_run": args.scores, "match_run": args.match, "labels": args.labels, "tags": TAGS,
        "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    pd.set_option("display.width", 250)
    print(json.dumps(summ["flagged_journal_years_by_k"])); print(enr.to_string())


if __name__ == "__main__":
    main()
