"""C13 follow-up (post hoc): stratify the anatomy comparisons by whether donor and recipient share a dcSBM block
(partition `main`). Excessive edges are defined against the block model, so flagged pairs could differ from
controls in field distance alone; comparing within strata removes that. Laptop, read-only.

Usage:  python c13_stratify.py --anatomy c13_anatomy_20261031_01 --src c6_full_20261031_02 --run-id c13_strat_<YYYYMMDD>_01
Output: runs/<run_id>/strata.csv, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import mannwhitneyu

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    for a in ("--anatomy", "--src", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    p = pd.read_csv(runs / args.anatomy / "pairs.csv")
    b = pd.read_parquet(runs / args.src / "blocks_main.parquet").set_index("journal_id").block
    p["same_block"] = [d in b.index and r in b.index and b[d] == b[r] for d, r in zip(p.D, p.R)]
    rows = []
    for tgt in ("flagged", "named"):
        for sb in (None, True, False):
            a = p[(p.group == tgt) & ((p.same_block == sb) if sb is not None else True)]
            c = p[(p.group == f"control_{tgt}") & ((p.same_block == sb) if sb is not None else True)]
            for col in ("title_cosine_mean", "cites_per_item", "gini", "top1_share", "top10pct_share"):
                x, y = a[col].dropna(), c[col].dropna()
                if len(x) and len(y):
                    rows.append({"target": tgt, "same_block": "all" if sb is None else sb, "metric": col,
                                 "n_target": len(x), "n_control": len(y), "median_target": round(float(x.median()), 4),
                                 "median_control": round(float(y.median()), 4),
                                 "mannwhitney_p": float(mannwhitneyu(x, y, alternative="two-sided").pvalue)})
    s = pd.DataFrame(rows)
    run_dir.mkdir(parents=True)
    s.to_csv(run_dir / "strata.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "anatomy_run": args.anatomy,
        "src_run": args.src, "same_block_share": p.groupby("group").same_block.mean().round(4).to_dict(),
        "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    print(s.to_string())


if __name__ == "__main__":
    main()
