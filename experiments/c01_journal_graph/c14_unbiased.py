"""C14 follow-up: the evidence check on the random part of the flagged sample only.

c13_anatomy added every listed recipient to the 200 random flagged pairs, which inflates indicator I1 (listed).
Here the flagged pairs whose recipient is in the labels (any role, any year) are dropped, with their controls.
Laptop, read-only; reuses runs/<evidence>/pairs.csv.

Usage:  python c14_unbiased.py --evidence c14_evidence_20261031_01 --match c10_match_20261031_05 --labels suppressions_v2.csv --run-id c14_unbiased_<YYYYMMDD>_01
Output: runs/<run_id>/summary.json, run.json, SHA256SUMS.
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
COLS = ["I1_listed", "I2_same_publisher", "I3_concentrated"]


def main():
    ap = argparse.ArgumentParser()
    for a in ("--evidence", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    p = pd.read_csv(runs / args.evidence / "pairs.csv")
    m = pd.read_csv(runs / args.match / "matches.csv")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    names = set(sup.journal) | {x.strip() for v in sup.partner_journal.dropna() for x in str(v).split(";")}
    listed = {int(r.journal_ids) for r in m.itertuples() if r.status == "matched" and r.name in names}
    f = p[(p.group == "flagged") & ~p.R.isin(listed)].copy()
    keys = set(zip(f.t, f.D, f.R))
    c = p[(p.group == "control_flagged") & pd.Series([k in keys for k in zip(p.tt, p.tD, p.tR)], index=p.index)].copy()
    summ = {"n_flagged": len(f), "n_control": len(c)}
    for d in (f, c):
        d["any"] = d[COLS].any(axis=1)
    for col in COLS + ["any"]:
        a, b = f[col].astype(bool), c[col].astype(bool)
        odds, pv = fisher_exact([[int(a.sum()), int((~a).sum())], [int(b.sum()), int((~b).sum())]])
        summ[col] = {"flagged": f"{int(a.sum())}/{len(a)}", "control": f"{int(b.sum())}/{len(b)}",
                     "flagged_share": round(float(a.mean()), 4), "control_share": round(float(b.mean()), 4),
                     "odds_ratio": odds, "fisher_p": pv}
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "evidence_run": args.evidence,
        "match_run": args.match, "labels": args.labels, "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
