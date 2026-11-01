"""C19 / R13: label accounting, from the label rows to every analysis denominator (review round 1). Reads saved
outputs only and recomputes each count from them (no numbers typed in). Also the R13 sensitivity: self-citation
ranks without the 9 v2 rows that Clarivate's current xlsx omits (data/suppressions_crosscheck.csv, status only_v2).

Usage:  python c19_accounting.py --labels suppressions_v2.csv --fidelity c10_fidelity_20261031_02 \\
            --covsplit c10_covsplit_20261031_01 --eval c12_eval_20261031_01 --basesize c17_basesize_20261101_01 \\
            --oos c16_oos_20261101_01 --run-id c19_accounting_<YYYYMMDD>_01
Output: runs/<run_id>/accounting.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main():
    ap = argparse.ArgumentParser()
    for a in ("--labels", "--fidelity", "--covsplit", "--eval", "--basesize", "--oos", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    fid = pd.read_csv(runs / args.fidelity / "fidelity.csv")
    rk = pd.read_csv(runs / args.fidelity / "ranks.csv")
    rk = rk[rk.scores == "scores_main"]
    cov = json.loads((runs / args.covsplit / "summary.json").read_text())
    ev = json.loads((runs / args.eval / "summary.json").read_text())
    bs = pd.read_csv(runs / args.basesize / "baseline_enrichment.csv")
    oos = pd.read_csv(runs / args.oos / "positives.csv")
    rows = []

    def add(block, step, n, source):
        rows.append({"block": block, "step": step, "n": int(n), "source": source})

    # labels
    for ty, g in sup.groupby("type"):
        add("labels", f"rows: {ty}", len(g), args.labels)
    st = sup[sup.type == "stacking"]
    add("labels", "stacking rows: named recipient<-donor", (st.role == "recipient").sum(), args.labels)
    add("labels", "stacking rows: donor", (st.role == "donor").sum(), args.labels)
    add("labels", "stacking rows: no named partner", st.role.isna().sum(), args.labels)
    add("labels", "rows total", len(sup), args.labels)
    # self-citation fidelity
    s = sup[sup.type == "self"]
    add("self fidelity", "self rows", len(s), args.labels)
    add("self fidelity", "with a published self-citation %", s.pct_self_cites_jif_numerator.notna().sum(), args.labels)
    f = fid[(fid.metric == "self_cites_pct_jif_numerator") & (fid.scores.fillna("scores_main") == "scores_main")]
    add("self fidelity", "matched to a journal", f.matched.sum(), f"{args.fidelity}/fidelity.csv")
    add("self fidelity", "evaluated (num >= 20, citable >= 20)", f.ours.notna().sum(), f"{args.fidelity}/fidelity.csv")
    for present in (True, False):
        k = cov[f"self_cites_pct_jif_numerator | refs_present={present}"]
        add("self fidelity", f"evaluated, references {'present' if present else 'absent'} (pass within 10 pp)", k["n"],
            f"{args.covsplit}/summary.json (pass {k['pass']})")
    # ranks
    r = rk[rk.type == "self"]
    add("self ranks", "self rows in ranks", len(r), f"{args.fidelity}/ranks.csv")
    add("self ranks", "matched", r.journal_id.notna().sum(), f"{args.fidelity}/ranks.csv")
    add("self ranks", "ranked (num >= 20, citable >= 20)", r.self_share_pct.notna().sum(), f"{args.fidelity}/ranks.csv")
    add("self ranks", "ranked in the top 5%", (r.self_share_pct <= 0.05).sum(), f"{args.fidelity}/ranks.csv")
    # stacking fidelity
    d = fid[(fid.metric == "donor_pct_jif_numerator") & (fid.scores.fillna("scores_main") == "scores_main")]
    add("stacking fidelity", "named pairs with a published donor %", len(d), f"{args.fidelity}/fidelity.csv")
    add("stacking fidelity", "both journals matched", d.matched.sum(), f"{args.fidelity}/fidelity.csv")
    for present in (True, False):
        k = cov[f"donor_pct_jif_numerator | refs_present={present}"]
        add("stacking fidelity", f"donor references {'present' if present else 'absent'}", k["n"], f"{args.covsplit}/summary.json (pass {k['pass']})")
    # CIDRE
    add("CIDRE", "named recipient<-donor rows 2015-2023 (incl. expression of concern)", ev["cidre_named_pairs"], f"{args.eval}/summary.json")
    add("CIDRE", "both journals matched", ev["cidre_pairs_both_matched"], f"{args.eval}/summary.json")
    add("CIDRE", "detected (any partition)", ev["cidre_detected_any_partition"], f"{args.eval}/summary.json")
    # enrichment
    m = bs[(bs.flag_set == "variant_main")]
    add("variant enrichment", "stacking-listed journals in base (design cases excluded)", m[m.kind == "stacking"].listed.iloc[0], f"{args.basesize}/baseline_enrichment.csv")
    add("variant enrichment", "self-listed journals in base", m[m.kind == "self"].listed.iloc[0], f"{args.basesize}/baseline_enrichment.csv")
    # out of sample
    so = oos[oos.type == "stacking"]
    add("out of sample", "stacking recipients listed, data years 2024-2025", len(so), f"{args.oos}/positives.csv")
    add("out of sample", "in the population", so.in_population.sum(), f"{args.oos}/positives.csv")
    add("out of sample", "flagged in advance (k = 7)", so.pred_k7.sum(), f"{args.oos}/positives.csv")
    acc = pd.DataFrame(rows)

    # R13 sensitivity: ranks without the rows Clarivate's current xlsx omits
    xc = pd.read_csv(ROOT / "data" / "suppressions_crosscheck.csv")
    drop = {(int(a), b) for a, b in xc[xc.status == "only_v2"][["jcr_data_year", "journal"]].values}
    r2 = r[[(int(a), b) not in drop for a, b in r[["jcr_data_year", "journal"]].values]]
    f2 = f[[(int(a), b) not in drop for a, b in f[["t", "journal"]].values]]
    sens = {"dropped_rows": sorted(f"{a} {b}" for a, b in drop),
            "ranks_top5": f"{int((r2.self_share_pct <= 0.05).sum())}/{int(r2.self_share_pct.notna().sum())}",
            "ranks_top1": f"{int((r2.self_share_pct <= 0.01).sum())}/{int(r2.self_share_pct.notna().sum())}",
            "ranks_median_pct": float(r2.self_share_pct.median()),
            "fidelity_self_pass": f"{int(f2['pass'].sum())}/{int(f2.ours.notna().sum())}"}

    run_dir.mkdir(parents=True)
    acc.to_csv(run_dir / "accounting.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps({"sensitivity_without_only_v2": sens}, indent=2))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        **{k: v for k, v in vars(args).items() if k != "run_id"}, "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
    print(acc.to_string()); print(json.dumps(sens, indent=1))


if __name__ == "__main__":
    main()
