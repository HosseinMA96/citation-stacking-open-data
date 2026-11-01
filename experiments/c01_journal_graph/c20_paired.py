"""C20: review round 2 (paper/journals/scientometrics/Critics/round2.txt) follow-ups to c17_basesize (R9/R12).

Rebuilds the flag sets and the size-matched controls exactly as c17_baseline_size.py (same inputs, thresholds from its
thresholds.json, seed 4311) and checks that the counts equal c17's size_matched.csv. Then:
  1. paired exact McNemar tests on the same 28 stacking-listed journals (design cases excluded): variant vs each plain
     rule (discordant pairs; two-sided binomial test on the discordant counts);
  2. 95% CIs for the size-matched enrichment: cluster bootstrap over listed journals (each with its 10 controls),
     10,000 resamples, percentile intervals;
  3. size profile: share of base journals ever flagged by size decile (max yearly num), for each rule, and the decile
     distribution of the listed journals (explains why size matching moves the rules in different directions).

Usage:  python c20_paired.py --basesize c17_basesize_20261101_01 --scores c9_scores_20261031_02 --recip c12_recip_20261031_01 \\
            --consensus c12_consensus_20261031_01 --src c6_full_20261031_02 --match c10_match_20261031_05 \\
            --labels suppressions_v2.csv --run-id c20_paired_<YYYYMMDD>_01
Output: runs/<run_id>/paired.csv, size_matched_ci.csv, size_profile.csv, summary.json, run.json, SHA256SUMS.
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
from c17_baseline_size import DESIGN_CASES  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    for a in ("--basesize", "--scores", "--recip", "--consensus", "--src", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    th = json.loads((runs / args.basesize / "thresholds.json").read_text())
    ref = pd.read_csv(runs / args.basesize / "size_matched.csv")

    # flag sets, as c17
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
    f = pd.read_csv(runs / args.recip / "flags.csv")
    c = pd.read_csv(runs / args.consensus / "consensus_flags.csv")
    elig = sc[sc.num >= 20]
    ever = {"variant_main": set(f[f.tag == "main"].journal_id) & B,
            "variant_k7": set(c[c.partitions == 7].journal_id) & B,
            "baseline_rate_main": set(elig[elig.share >= th["baseline_rate_main"]["X"]].journal_id) & B,
            "baseline_rate_k7": set(elig[elig.share >= th["baseline_rate_k7"]["X"]].journal_id) & B,
            "baseline_015_w50": set(sc[(sc.share >= 0.15) & (sc.top_eff >= 50)].journal_id) & B}

    # 1. paired McNemar on the stacking-listed journals
    Ls = sorted(L["stacking"] & B)
    prow = []
    for a in ("variant_main", "variant_k7"):
        for b in ("baseline_rate_main", "baseline_rate_k7", "baseline_015_w50"):
            xa = np.array([j in ever[a] for j in Ls]); xb = np.array([j in ever[b] for j in Ls])
            n10, n01 = int((xa & ~xb).sum()), int((~xa & xb).sum())
            p = binomtest(n10, n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
            prow.append({"rule_a": a, "rule_b": b, "listed": len(Ls), "a_flagged": int(xa.sum()), "b_flagged": int(xb.sum()),
                         "both": int((xa & xb).sum()), "only_a": n10, "only_b": n01, "mcnemar_exact_p_two_sided": p})
    paired = pd.DataFrame(prow)

    # 2. controls as c17 (same rng sequence) and cluster-bootstrap CIs
    blocks = pd.read_parquet(runs / args.src / "blocks_main.parquet")
    base = base.merge(blocks, on="journal_id", how="left")
    base["dec"] = pd.qcut(base.max_num.rank(method="first"), 10, labels=False)
    base["lognum"] = np.log(base.max_num)
    rng = np.random.default_rng(4311)
    srows, check = [], []
    boot = np.random.default_rng(4312)
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
            ctrl += [(r.journal_id, j) for j in pick]
        ctrl = pd.DataFrame(ctrl, columns=["listed_journal", "control"])
        lj = ctrl.listed_journal.unique()
        for k, E in ever.items():
            lf = np.array([j in E for j in lj], dtype=float)
            cf = ctrl.assign(fl=ctrl.control.isin(E)).groupby("listed_journal").fl.sum().reindex(lj).to_numpy(dtype=float)
            a, cc = lf.sum(), cf.sum()
            refrow = ref[(ref.flag_set == k) & (ref.kind == kind)].iloc[0]
            check.append(int(a) == refrow.listed_flagged and int(cc) == refrow.controls_flagged)
            est = (a / len(lj)) / (cc / (10 * len(lj))) if cc else float("nan")
            bs = []
            for _ in range(10000):
                i = boot.integers(0, len(lj), len(lj))
                num, den = lf[i].sum(), cf[i].sum()
                if den > 0:
                    bs.append((num / len(i)) / (den / (10 * len(i))))
            lo, hi = (np.percentile(bs, [2.5, 97.5]) if bs else (np.nan, np.nan))
            srows.append({"flag_set": k, "kind": kind, "listed": len(lj), "listed_flagged": int(a), "controls": 10 * len(lj),
                          "controls_flagged": int(cc), "listed_rate": round(a / len(lj), 4), "control_rate": round(cc / (10 * len(lj)), 4),
                          "matched_enrichment": round(est, 2), "ci95_cluster_bootstrap": [round(lo, 2), round(hi, 2)],
                          "bootstrap_valid": len(bs)})
    sm = pd.DataFrame(srows)

    # 3. size profile
    prof = []
    for d, g in base.groupby("dec"):
        row = {"size_decile": int(d), "max_num_min": float(g.max_num.min()), "max_num_max": float(g.max_num.max()),
               "journals": len(g), "stacking_listed": int(g.journal_id.isin(L["stacking"]).sum())}
        for k, E in ever.items():
            row[f"rate_{k}"] = round(float(g.journal_id.isin(E).mean()), 4)
        prof.append(row)
    prof = pd.DataFrame(prof)

    run_dir.mkdir(parents=True)
    paired.to_csv(run_dir / "paired.csv", index=False)
    sm.to_csv(run_dir / "size_matched_ci.csv", index=False)
    prof.to_csv(run_dir / "size_profile.csv", index=False)
    summ = {"counts_equal_c17": all(check), "paired": paired.to_dict("records"),
            "size_matched_stacking": sm[sm.kind == "stacking"].drop(columns="kind").to_dict("records")}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        **{k: v for k, v in vars(args).items() if k != "run_id"},
        "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "seeds": {"controls": 4311, "bootstrap": 4312}, "bootstrap_resamples": 10000,
        "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    pd.set_option("display.width", 250)
    print("counts equal c17:", all(check))
    print(paired.to_string()); print(sm.to_string()); print(prof.to_string())


if __name__ == "__main__":
    main()
