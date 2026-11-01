"""C18 evaluation (laptop): R10 asymmetric-theta CIDRE and R9b single-block variant against the labels
(protocol: RESULTS_LOG "Review round 1 ... pre-registration of R9-R13"). Definitions as c12_eval_labels.py.

R10, per theta_d: groups per year, median / max group size, named recipient<-donor pairs detected (paper rule,
     cidre_paper.overlap_detected; both journals matched), stacking-listed journals (design cases excluded) ever in a
     group: enrichment over base journals (max num >= 20). Sanity: theta_d = 0.15 must reproduce c12_cidre (main).
R9b  single-block flags: enrichment (Wilson 95% CI) for stacking-listed (design cases excluded) and self-listed;
     Jaccard with the dcSBM variant (c12_recip, main); listed stacking journals flagged before their first listing.

Usage:  python c18_eval.py --asym c18_asym_20261101_01 --cidre c12_cidre_20261031_02 --recip c12_recip_20261031_01 \\
            --scores c9_scores_20261031_02 --match c10_match_20261031_05 --labels suppressions_v2.csv --run-id c18_eval_<YYYYMMDD>_01
Output: runs/<run_id>/asym_summary.csv, asym_detections.csv, null_enrichment.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import cidre_paper  # noqa: E402
from c17_baseline_size import DESIGN_CASES, wilson  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    for a in ("--asym", "--cidre", "--recip", "--scores", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    g = pd.read_csv(runs / args.asym / "groups_asym.csv")
    fl1 = pd.read_csv(runs / args.asym / "flags_1block.csv")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    s = duckdb.sql(f"SELECT journal_id, max(num) AS mx FROM read_parquet('{runs / args.scores / 'journal_year_scores.parquet'}') GROUP BY 1").df()
    B = set(s.journal_id[s.mx >= 20])
    lst = sup[sup.type.isin(["self", "stacking"])].copy()
    lst["jid"] = lst.journal.map(jid)
    lst = lst[lst.jid.notna()]
    lst["jid"] = lst.jid.astype(int)
    design = {jid[n] for n in DESIGN_CASES if n in jid}
    L = {"stacking": (set(lst[lst.type == "stacking"].jid) - design) & B, "self": set(lst[lst.type == "self"].jid) & B}
    first = lst[lst.type == "stacking"].groupby("jid").jcr_data_year.min()

    # sanity: theta_d = 0.15 reproduces c12 main
    c12 = pd.read_csv(runs / args.cidre / "groups.csv")
    c12 = c12[c12.tag == "main"]
    a = {(t, frozenset(x.journal_id)) for (t, k), x in c12.groupby(["t", "group"])}
    b = {(t, frozenset(x.journal_id)) for (t, k), x in g[g.theta_d == 0.15].groupby(["t", "group"])}
    sanity = a == b

    pairs = sup[(sup.role == "recipient") & sup.partner_journal.notna() & sup.jcr_data_year.between(2015, 2023)]
    det, summ_rows = [], []
    for th, gt in g.groupby("theta_d"):
        sizes = gt.groupby(["t", "group"]).size()
        for r in pairs.itertuples():
            x, y = jid.get(r.journal), jid.get(r.partner_journal)
            if x is None or y is None:
                continue
            gy = gt[gt.t == r.jcr_data_year]
            hit = [k for k, z in gy.groupby("group") if cidre_paper.overlap_detected({x, y}, set(z.journal_id))]
            same = [k for k, z in gy.groupby("group") if {x, y} <= set(z.journal_id)]
            det.append({"theta_d": th, "t": r.jcr_data_year, "recipient": r.journal, "donor": r.partner_journal,
                        "detected_paper_rule": bool(hit), "both_in_same_group": bool(same),
                        "size_of_shared_group": int(sizes[(r.jcr_data_year, same[0])]) if same else None})
        ever = set(gt.journal_id) & B
        rate = len(ever) / len(B)
        Ls = L["stacking"]
        h = len(Ls & ever)
        summ_rows.append({"theta_d": th, "groups": int(sizes.size), "groups_per_year_median": float(gt.groupby("t").group.nunique().median()),
                          "group_size_median": float(sizes.median()), "group_size_max": int(sizes.max()),
                          "journals_in_any_group": len(ever), "base_rate": round(rate, 5),
                          "stacking_listed": len(Ls), "stacking_listed_in_group": h,
                          "enrichment": round(h / len(Ls) / rate, 2) if rate else None,
                          "p_one_sided": binomtest(h, len(Ls), rate, alternative="greater").pvalue if rate else None})
    det = pd.DataFrame(det)
    asum = pd.DataFrame(summ_rows)
    asum = asum.merge(det.groupby("theta_d").agg(named_pairs=("recipient", "size"), detected=("detected_paper_rule", "sum"),
                                                 same_group=("both_in_same_group", "sum")).reset_index(), on="theta_d")

    # R9b
    f = pd.read_csv(runs / args.recip / "flags.csv")
    ev = {"dcsbm_main": set(f[f.tag == "main"].journal_id) & B, "one_block": set(fl1.journal_id) & B}
    fy = {"dcsbm_main": f[f.tag == "main"], "one_block": fl1}
    rows = []
    for k, E in ev.items():
        rate = len(E) / len(B)
        for kind, Lk in L.items():
            h = len(Lk & E)
            lo, hi = wilson(h, len(Lk))
            before = (sum(1 for j in Lk & E if (fy[k][fy[k].journal_id == j].t < first.get(j, 0)).any())
                      if kind == "stacking" else None)
            rows.append({"flag_set": k, "kind": kind, "base_rate": round(rate, 5), "listed": len(Lk), "listed_flagged": h,
                         "enrichment": round(h / len(Lk) / rate, 2), "enrichment_ci95": [round(lo / rate, 2), round(hi / rate, 2)],
                         "p_one_sided": binomtest(h, len(Lk), rate, alternative="greater").pvalue,
                         "flagged_before_first_listing": before})
    nul = pd.DataFrame(rows)
    jac = round(len(ev["dcsbm_main"] & ev["one_block"]) / len(ev["dcsbm_main"] | ev["one_block"]), 3)

    run_dir.mkdir(parents=True)
    asum.to_csv(run_dir / "asym_summary.csv", index=False)
    det.to_csv(run_dir / "asym_detections.csv", index=False)
    nul.to_csv(run_dir / "null_enrichment.csv", index=False)
    summ = {"sanity_theta_d_015_equals_c12_main": sanity, "asym": asum.to_dict("records"),
            "one_block_vs_dcsbm": nul.to_dict("records"), "jaccard_dcsbm_one_block": jac,
            "one_block_flags_per_year": fl1.groupby("t").size().to_dict()}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        **{k: v for k, v in vars(args).items() if k != "run_id"},
        "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    pd.set_option("display.width", 250)
    print("sanity", sanity, "jaccard", jac)
    print(asum.to_string()); print(nul.to_string())
    print(det[det.both_in_same_group | det.detected_paper_rule].to_string())


if __name__ == "__main__":
    main()
