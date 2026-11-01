"""C16 / R11 step 2: out-of-sample test of the frozen predictions against the JCR data-year 2024-2025 suppressions
(protocol: RESULTS_LOG "Review round 1 ... pre-registration of R9-R13").

Population = predictions.csv of the freeze run (base journals not listed 2015-2023). A journal is positive if it is
listed in data/suppressions_oos.csv (data years 2024-2025) with type stacking (primary: recipients; Clarivate's
"Type" column) or with any type (secondary). Journals are matched by the c10 match run on suppressions_oos.csv;
an `ambiguous` match (one title, several ISSN-split venue groups) counts every candidate journal_id, and the
journal is counted as flagged if any of them is flagged (reported per journal).
Test: one-sided Fisher exact test, flagged vs not flagged, for pred_k7 (primary), pred_main and pred_k1.

Usage:  python c16_oos_eval.py --pred c16_predict_20261031_01 --match c10_match_20261101_01 \\
            --recip c12_recip_20261031_01 --labels suppressions_oos.csv --run-id c16_oos_<YYYYMMDD>_01
Output: runs/<run_id>/positives.csv, tests.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PREDS = ("pred_k7", "pred_main", "pred_k1")


def main():
    ap = argparse.ArgumentParser()
    for a in ("--pred", "--match", "--recip", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    pop = pd.read_csv(runs / args.pred / "predictions.csv")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    sup = sup[sup.journal.notna()]                       # donor rows carry an abbreviation only
    m = pd.read_csv(runs / args.match / "matches.csv")
    ids = {r.name: [int(x) for x in str(r.journal_ids).split()] for r in m.itertuples()
           if r.status in ("matched", "ambiguous")}
    status = dict(zip(m.name, m.status))
    f = pd.read_csv(runs / args.recip / "flags.csv")
    fm = f[f.tag == "main"]
    inpop = set(pop.journal_id)
    rows = []
    for r in sup.drop_duplicates(["journal", "type"]).itertuples():
        js = ids.get(r.journal, [])
        p = pop[pop.journal_id.isin(js)]
        fl = fm[fm.journal_id.isin(js)]
        rows.append({"journal": r.journal, "jcr_data_year": r.jcr_data_year, "type": r.type,
                     "partner_journal": r.partner_journal if isinstance(r.partner_journal, str) else "",
                     "match_status": status.get(r.journal), "journal_ids": " ".join(map(str, js)),
                     "in_population": bool(len(p)), "excluded_reason": "" if len(p) else
                     ("not matched" if not js else "listed 2015-2023 or max num < 20"),
                     **{k: bool(p[k].any()) if len(p) else False for k in PREDS},
                     "main_flag_years": " ".join(map(str, sorted(fl.t.unique()))),
                     "main_top_donor_ids": " ".join(map(str, sorted(fl.top_donor.unique())))})
    pos = pd.DataFrame(rows)
    tests = []
    for outcome, sel in (("stacking", pos.type == "stacking"), ("any", pos.type.notna())):
        P = pos[sel & pos.in_population]
        pos_ids = {int(x) for v in P.journal_ids for x in v.split()} & inpop
        # one row per journal (ambiguous titles: the population rows of all candidates are merged into one unit)
        units = pop[~pop.journal_id.isin(pos_ids)][list(PREDS)].astype(bool)
        neg_n = len(units)
        for k in PREDS:
            a = int(P[k].sum()); b = len(P) - a
            c = int(units[k].sum()); d = neg_n - c
            odds, pv = fisher_exact([[a, b], [c, d]], alternative="greater")
            tests.append({"outcome": outcome, "prediction": k, "positives": len(P), "positives_flagged": a,
                          "negatives": neg_n, "negatives_flagged": c, "rate_pos": round(a / len(P), 4) if len(P) else None,
                          "rate_neg": round(c / neg_n, 5), "enrichment": round((a / len(P)) / (c / neg_n), 2) if len(P) and c else None,
                          "odds_ratio": odds, "p_one_sided": pv})
    tests = pd.DataFrame(tests)
    run_dir.mkdir(parents=True)
    pos.to_csv(run_dir / "positives.csv", index=False)
    tests.to_csv(run_dir / "tests.csv", index=False)
    summ = {"labels_rows_named": len(sup), "tests": tests.to_dict("records")}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        **{k: v for k, v in vars(args).items() if k != "run_id"},
        "predictions_sha256": hashlib.sha256((runs / args.pred / "predictions.csv").read_bytes()).hexdigest(),
        "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    pd.set_option("display.width", 250)
    print(pos.drop(columns=["main_top_donor_ids"]).to_string())
    print(tests.to_string())


if __name__ == "__main__":
    main()
