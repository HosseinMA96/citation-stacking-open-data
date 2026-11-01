"""C12b evaluation: are Clarivate-listed journals flagged by the recipient-centric variant more often than others?

Base: journals with max yearly num >= K in the main scores (K = 20, 50, 100). A journal is "ever flagged" if
the variant flags it in any year 2015-2023 on the given partition. Labeled = journals matched in the c10
match run. Reported with and without the two design cases (Ukrainian J Phys Optics, Climate Change
Economics; RESULTS_LOG "C12b pre-registration"), plus a one-sided binomial test against the base rate,
per partition. Also: flags BEFORE the journal's listing year (lead time).

Usage:  python c12_enrichment.py --recip c12_recip_20261031_01 --scores c9_scores_20261031_02 \\
            --match c10_match_20261031_03 --run-id c12_enrich_<YYYYMMDD>_01
Output: runs/<run_id>/enrichment.csv, lead_time.csv, run.json, SHA256SUMS.
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
DESIGN_CASES = {"Ukrainian Journal for Physical Optics", "Climate Change Economics"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recip", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--match", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    f = pd.read_csv(runs / args.recip / "flags.csv")
    lab = pd.read_csv(runs / args.recip / "labeled.csv")
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    design_ids = {jid[n] for n in DESIGN_CASES}
    s = duckdb.sql(f"SELECT journal_id, max(num) AS mx FROM read_parquet('{runs / args.scores / 'journal_year_scores.parquet'}') GROUP BY 1").df()
    rows = []
    for tag in sorted(f.tag.unique()):
        ever = set(f[f.tag == tag].journal_id)
        lf = lab[lab.tag == tag].groupby("journal_id").flag.any()
        for K in (20, 50, 100):
            base = set(s.journal_id[s.mx >= K])
            rate = sum(j in ever for j in base) / len(base)
            for excl in (False, True):
                L = [j for j in lf.index if j in base and not (excl and j in design_ids)]
                k = int(sum(lf[j] for j in L))
                p = binomtest(k, len(L), rate, alternative="greater").pvalue
                rows.append({"tag": tag, "min_num": K, "exclude_design_cases": excl, "base_journals": len(base),
                             "base_rate_ever_flagged": round(rate, 5), "labeled": len(L), "labeled_flagged": k,
                             "labeled_rate": round(k / len(L), 4), "enrichment": round(k / len(L) / rate, 2),
                             "p_one_sided": p})
    enr = pd.DataFrame(rows)
    sup = pd.read_csv(ROOT / "data" / "suppressions.csv")
    listed = sup.groupby("journal").jcr_data_year.min()
    main = lab[(lab.tag == "main") & lab.flag].copy()
    main["listed_data_year"] = main.journal.map(listed)
    main["years_before_listing"] = main.listed_data_year - main.t
    main = main[["journal", "t", "listed_data_year", "years_before_listing", "r", "e", "s_in",
                 "top_donor_name_if_labeled"]].sort_values(["journal", "t"])
    run_dir.mkdir(parents=True)
    enr.to_csv(run_dir / "enrichment.csv", index=False)
    main.to_csv(run_dir / "lead_time.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "recip_run": args.recip, "scores_run": args.scores, "match_run": args.match,
        "design_cases": sorted(DESIGN_CASES), "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    pd.set_option("display.width", 250)
    print(enr[enr.tag == "main"].to_string())
    print(enr.groupby(["min_num", "exclude_design_cases"]).agg(enr_min=("enrichment", "min"), enr_max=("enrichment", "max"),
                                                              p_max=("p_one_sided", "max")).to_string())
    print(main.to_string())


if __name__ == "__main__":
    main()
