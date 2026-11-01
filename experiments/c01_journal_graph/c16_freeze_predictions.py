"""C16 / R11 step 1: freeze the out-of-sample predictions BEFORE the newer Clarivate lists are opened
(RESULTS_LOG "Review round 1 ... pre-registration of R9-R13").

Population: base journals (max yearly num >= 20 in the main scores) that are not listed (self or stacking, matched)
in the 2015-2023 labels. Prediction flags, any year 2015-2023:
  pred_k7    consensus over all 7 partitions (c12_consensus, partitions == 7)   -- primary
  pred_main  variant flag on partition main (c12_recip)
  pred_k1    consensus >= 1 partition
Writes ISSNs so the newer lists can be matched by ISSN later.

Usage:  python c16_freeze_predictions.py --recip c12_recip_20261031_01 --consensus c12_consensus_20261031_01 \\
            --scores c9_scores_20261031_02 --src c6_full_20261031_02 --match c10_match_20261031_05 \\
            --labels suppressions_v2.csv --run-id c16_predict_<YYYYMMDD>_01
Output: runs/<run_id>/predictions.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main():
    ap = argparse.ArgumentParser()
    for a in ("--recip", "--consensus", "--scores", "--src", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    s = duckdb.sql(f"""SELECT journal_id, max(num) AS max_num FROM read_parquet('{runs / args.scores / 'journal_year_scores.parquet'}')
                       GROUP BY 1 HAVING max(num) >= 20""").df()
    sup = pd.read_csv(ROOT / "data" / args.labels)
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    listed = {jid[n] for n in sup[sup.type.isin(["self", "stacking"])].journal if n in jid}
    f = pd.read_csv(runs / args.recip / "flags.csv")
    c = pd.read_csv(runs / args.consensus / "consensus_flags.csv")
    pop = s[~s.journal_id.isin(listed)].copy()
    pop["pred_k7"] = pop.journal_id.isin(c[c.partitions == 7].journal_id)
    pop["pred_main"] = pop.journal_id.isin(f[f.tag == "main"].journal_id)
    pop["pred_k1"] = pop.journal_id.isin(c.journal_id)
    first = c[c.partitions == 7].groupby("journal_id").t.agg(["min", "max"])
    pop["k7_first_year"] = pop.journal_id.map(first["min"])
    pop["k7_last_year"] = pop.journal_id.map(first["max"])
    iss = duckdb.sql(f"""SELECT journal_id, issns FROM read_parquet('{runs / args.src / 'journals.parquet'}')
                         WHERE journal_id IN (SELECT unnest(?))""", params=[pop.journal_id.tolist()]).df()
    pop["issns"] = pop.journal_id.map(dict(zip(iss.journal_id, iss.issns.map(lambda x: " ".join(x)))))
    run_dir.mkdir(parents=True)
    pop.sort_values("journal_id").to_csv(run_dir / "predictions.csv", index=False)
    summ = {"population": len(pop), "excluded_listed_2015_2023": len(listed & set(s.journal_id)),
            "pred_k7": int(pop.pred_k7.sum()), "pred_main": int(pop.pred_main.sum()), "pred_k1": int(pop.pred_k1.sum()),
            "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "written before the JCR data-year 2024/2025 lists were opened"}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2))
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
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
