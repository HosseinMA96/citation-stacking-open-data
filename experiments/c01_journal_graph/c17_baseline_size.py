"""C17: R9 plain baseline (no block model) and R12 size-matched base rates (protocol: RESULTS_LOG "Review round 1 ...
pre-registration of R9-R13"). Laptop; saved outputs only.

Definitions as in c12_eval_labels.py: base = journals with max yearly num >= 20 (main scores); listed = matched journals
of type self or stacking (any role) in the labels; stacking analyses exclude the two design cases.
Flag sets (journal "ever flagged" in 2015-2023):
  variant_main   c12_recip flags, partition main            variant_k7   consensus over 7 partitions (c12_consensus)
  base_rate_main / base_rate_k7: baseline (R9) top_donor_share_of_num >= X and num >= 20 in some year, with X set by
                 bisection on base journals so that its ever-flag rate equals the variant's (labels not used)
  base_015_w50   top_donor_share_of_num >= 0.15 and top_donor_eff >= 50 (CIDRE's theta, theta_w on the plain share)
R9 outputs: enrichment with Wilson 95% CI of the listed rate (divided by the base rate), one-sided binomial p; Jaccard
            with the variant; listed stacking journals flagged before their first listing year.
R12 outputs, per flag set: (i) Mantel-Haenszel odds ratio and one-sided CMH z-test over deciles of max num;
            (ii) 10 never-listed controls per listed journal, same dcSBM block (main) and nearest |log max num|,
            topped up from the whole base by nearest size when the block has fewer than 10; Fisher one-sided test.

Usage:  python c17_baseline_size.py --scores c9_scores_20261031_02 --recip c12_recip_20261031_01 \\
            --consensus c12_consensus_20261031_01 --src c6_full_20261031_02 --match c10_match_20261031_05 \\
            --labels suppressions_v2.csv --run-id c17_basesize_<YYYYMMDD>_01
Output: runs/<run_id>/baseline_enrichment.csv, size_matched.csv, thresholds.json, summary.json, run.json, SHA256SUMS.
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
from scipy.stats import binomtest, fisher_exact, norm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DESIGN_CASES = {"Ukrainian Journal of Physical Optics", "Ukrainian Journal for Physical Optics", "Climate Change Economics"}


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def cmh(df, flag, listed, strata):
    """Mantel-Haenszel OR and one-sided CMH z over strata; df rows = base journals."""
    num = den = sa = se = sv = 0.0
    for _, g in df.groupby(strata):
        a = int((g[listed] & g[flag]).sum()); b = int((g[listed] & ~g[flag]).sum())
        c = int((~g[listed] & g[flag]).sum()); d = int((~g[listed] & ~g[flag]).sum())
        n = a + b + c + d
        if n < 2 or a + b == 0:
            continue
        num += a * d / n; den += b * c / n
        n1, m1 = a + b, a + c
        sa += a; se += n1 * m1 / n
        sv += n1 * (n - n1) * m1 * (n - m1) / (n * n * (n - 1))
    z = (sa - se) / np.sqrt(sv) if sv > 0 else float("nan")
    return (num / den if den > 0 else float("inf")), z, float(norm.sf(z))


def main():
    ap = argparse.ArgumentParser()
    for a in ("--scores", "--recip", "--consensus", "--src", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sc = duckdb.sql(f"""SELECT t, journal_id, num, top_donor_share_of_num AS share, top_donor_eff AS top_eff
                        FROM read_parquet('{runs / args.scores / 'journal_year_scores.parquet'}')""").df()
    base = sc.groupby("journal_id").num.max().rename("max_num").reset_index()
    base = base[base.max_num >= 20].copy()
    B = set(base.journal_id)

    sup = pd.read_csv(ROOT / "data" / args.labels)
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    lst = sup[sup.type.isin(["self", "stacking"])].copy()
    lst["jid"] = lst.journal.map(jid)
    lst = lst[lst.jid.notna()]
    lst["jid"] = lst.jid.astype(int)
    design = {jid[n] for n in DESIGN_CASES if n in jid}
    L = {"stacking": set(lst[lst.type == "stacking"].jid) - design, "self": set(lst[lst.type == "self"].jid)}
    listed_any = set(lst.jid)
    first = lst[lst.type == "stacking"].groupby("jid").jcr_data_year.min()

    f = pd.read_csv(runs / args.recip / "flags.csv")
    c = pd.read_csv(runs / args.consensus / "consensus_flags.csv")
    fy = {"variant_main": f[f.tag == "main"][["t", "journal_id"]], "variant_k7": c[c.partitions == 7][["t", "journal_id"]]}
    ever = {k: set(v.journal_id) & B for k, v in fy.items()}

    elig = sc[sc.num >= 20]

    def base_flags(X):
        return elig[elig.share >= X][["t", "journal_id"]]

    thresholds = {}
    for v in ("main", "k7"):
        target = len(ever[f"variant_{v}"]) / len(B)
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if len(set(base_flags(mid).journal_id) & B) / len(B) > target:
                lo = mid
            else:
                hi = mid
        X = hi
        fy[f"baseline_rate_{v}"] = base_flags(X)
        ever[f"baseline_rate_{v}"] = set(fy[f"baseline_rate_{v}"].journal_id) & B
        thresholds[f"baseline_rate_{v}"] = {"X": X, "target_rate": target, "achieved_rate": len(ever[f"baseline_rate_{v}"]) / len(B)}
    fy["baseline_015_w50"] = sc[(sc.share >= 0.15) & (sc.top_eff >= 50)][["t", "journal_id"]]
    ever["baseline_015_w50"] = set(fy["baseline_015_w50"].journal_id) & B
    thresholds["baseline_015_w50"] = {"X": 0.15, "min_top_eff": 50, "achieved_rate": len(ever["baseline_015_w50"]) / len(B)}

    # R9 enrichment
    rows = []
    for k, E in ever.items():
        rate = len(E) / len(B)
        for kind, LL in L.items():
            Lb = LL & B
            h = len(Lb & E)
            lo, hi = wilson(h, len(Lb))
            fyk = fy[k]
            before = sum(1 for j in Lb & E if (fyk[fyk.journal_id == j].t < first.get(j, 0)).any()) if kind == "stacking" else None
            rows.append({"flag_set": k, "kind": kind, "base_journals": len(B), "base_rate": round(rate, 5),
                         "listed": len(Lb), "listed_flagged": h, "enrichment": round(h / len(Lb) / rate, 2),
                         "enrichment_ci95": [round(lo / rate, 2), round(hi / rate, 2)],
                         "p_one_sided": binomtest(h, len(Lb), rate, alternative="greater").pvalue,
                         "flagged_before_first_listing": before})
    enr = pd.DataFrame(rows)
    jac = {f"{a}|{b}": round(len(ever[a] & ever[b]) / len(ever[a] | ever[b]), 3)
           for a in ("variant_main", "variant_k7") for b in ever if b.startswith("baseline")}
    jac["variant_main|variant_k7"] = round(len(ever["variant_main"] & ever["variant_k7"]) / len(ever["variant_main"] | ever["variant_k7"]), 3)

    # R12 size matching
    blocks = pd.read_parquet(runs / args.src / "blocks_main.parquet")
    base = base.merge(blocks, on="journal_id", how="left")
    base["dec"] = pd.qcut(base.max_num.rank(method="first"), 10, labels=False)
    base["lognum"] = np.log(base.max_num)
    rng = np.random.default_rng(4311)
    srows = []
    for kind, LL in L.items():
        base["listed"] = base.journal_id.isin(LL)
        pool = base[~base.journal_id.isin(listed_any)]
        ctrl = []
        for r in base[base.listed].itertuples():
            same = pool[pool.block == r.block].copy()
            same["d"] = (same.lognum - r.lognum).abs() + rng.random(len(same)) * 1e-9
            pick = list(same.nsmallest(10, "d").journal_id)
            if len(pick) < 10:
                rest = pool[~pool.journal_id.isin(pick)].copy()
                rest["d"] = (rest.lognum - r.lognum).abs() + rng.random(len(rest)) * 1e-9
                pick += list(rest.nsmallest(10 - len(pick), "d").journal_id)
            ctrl += [(r.journal_id, j, j in set(same.journal_id)) for j in pick]
        ctrl = pd.DataFrame(ctrl, columns=["listed_journal", "control", "same_block"])
        for k, E in ever.items():
            base["flag"] = base.journal_id.isin(E)
            orr, z, p = cmh(base, "flag", "listed", "dec")
            a = int(base[base.listed].flag.sum()); n1 = int(base.listed.sum())
            cf = int(ctrl.control.isin(E).sum()); n0 = len(ctrl)
            _, pf = fisher_exact([[a, n1 - a], [cf, n0 - cf]], alternative="greater")
            srows.append({"flag_set": k, "kind": kind, "listed": n1, "listed_flagged": a,
                          "cmh_mh_odds_ratio": round(orr, 2), "cmh_z": round(z, 2), "cmh_p_one_sided": p,
                          "controls": n0, "controls_same_block_share": round(ctrl.same_block.mean(), 3),
                          "controls_flagged": cf, "listed_rate": round(a / n1, 4), "control_rate": round(cf / n0, 4),
                          "matched_enrichment": round((a / n1) / (cf / n0), 2) if cf else None, "fisher_p_one_sided": pf})
    sz = pd.DataFrame(srows)

    run_dir.mkdir(parents=True)
    enr.to_csv(run_dir / "baseline_enrichment.csv", index=False)
    sz.to_csv(run_dir / "size_matched.csv", index=False)
    (run_dir / "thresholds.json").write_text(json.dumps(thresholds, indent=2))
    summ = {"thresholds": thresholds, "jaccard": jac,
            "enrichment_stacking": enr[enr.kind == "stacking"].drop(columns="kind").to_dict("records"),
            "size_matched_stacking": sz[sz.kind == "stacking"].drop(columns="kind").to_dict("records")}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        **{k: v for k, v in vars(args).items() if k != "run_id"},
        "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "design_cases": sorted(DESIGN_CASES), "seed": 4311, "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    pd.set_option("display.width", 250)
    print(json.dumps(thresholds, indent=1)); print(jac)
    print(enr.to_string()); print(sz.to_string())


if __name__ == "__main__":
    main()
