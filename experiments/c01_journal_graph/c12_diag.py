"""C12 diagnosis: at which CIDRE stage does each named JCR pair drop out? (read-only)

For each named recipient <- donor pair in its data year and one partition: the pair's W, W_all and
condition 1; blocks of both journals; whether the edge survives the dcSBM test (Abar, without and with
condition 1); both journals' donor/recipient scores before peeling; whether each survives peeling;
the within-pair citations against theta_w.

Usage:  python c12_diag.py --src c6_full_20261031_02 --match c10_match_20261031_03 --tag main --run-id c12_diag_<YYYYMMDD>_01
Output: runs/<run_id>/pairs.csv, run.json, SHA256SUMS. Never overwrites.
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import cidre_paper  # noqa: E402
from c12_cidre import build  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--match", required=True)
    ap.add_argument("--tag", default="main")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sup = pd.read_csv(ROOT / "data" / "suppressions.csv")
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    bl = pd.read_parquet(runs / args.src / f"blocks_{args.tag}.parquet").sort_values("journal_id")
    ids = bl.journal_id.values
    pos = pd.Series(np.arange(len(ids)), index=ids)
    out = []
    for r in sup[(sup.role == "recipient") & sup.partner_journal.notna()].itertuples():
        t, R, D = int(r.jcr_data_year), jid.get(r.journal), jid.get(r.partner_journal)
        if R is None or D is None or t > 2023:
            continue
        pairs = duckdb.sql(f"""SELECT t, citing_j, cited_j, eff, prev FROM read_parquet('{runs / args.src / 'pairs_jcr_years.parquet'}')
                               WHERE t = {t} AND citing_j IS NOT NULL AND (eff > 0 OR prev > 0)""").df()
        W, W_all, _ = build(pairs, ids, t)
        A1 = cidre_paper.excessive_edges(W, bl.block.values, None)       # significance only
        A2 = cidre_paper.excessive_edges(W, bl.block.values, W_all)      # + condition 1
        i, j = pos.get(D), pos.get(R)
        row = {"t": t, "recipient": r.journal, "donor": r.partner_journal, "in_network": i is not None and j is not None}
        if row["in_network"]:
            indeg = np.maximum(np.asarray(W.sum(axis=0)).ravel(), 1.0)
            outdeg = np.maximum(np.asarray(W.sum(axis=1)).ravel(), 1.0)
            U = np.ones(W.shape[0])
            donor0, recip0 = (A2 @ U) / outdeg, (U @ A2) / indeg
            groups = cidre_paper.detect(W, group_membership=bl.block.values, W_all=W_all)
            surv = set(np.concatenate([g.node_ids for g in groups])) if groups else set()
            row.update({
                "block_donor": int(bl.block.values[i]), "block_recipient": int(bl.block.values[j]),
                "W_D_to_R": W[i, j], "W_all_D_to_R": W_all[i, j], "W_R_to_D": W[j, i],
                "cond1_share_recent": round(W[i, j] / W_all[i, j], 3) if W_all[i, j] else None,
                "excessive_sig_only": A1[i, j] > 0, "excessive_with_cond1": A2[i, j] > 0,
                "donor_out_strength": outdeg[i], "recipient_in_strength": indeg[j],
                "donor_score_D_prepeel": round(donor0[i], 4), "recipient_score_D_prepeel": round(recip0[i], 4),
                "donor_score_R_prepeel": round(donor0[j], 4), "recipient_score_R_prepeel": round(recip0[j], 4),
                "D_in_final_group": i in surv, "R_in_final_group": j in surv,
                "pair_within_citations": W[i, j] + W[j, i], "theta": cidre_paper.THETA, "theta_w": cidre_paper.THETA_W})
        out.append(row)
        print(json.dumps(row, default=str), flush=True)
    run_dir.mkdir(parents=True)
    pd.DataFrame(out).to_csv(run_dir / "pairs.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "src_run": args.src,
        "match_run": args.match, "tag": args.tag, "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")


if __name__ == "__main__":
    main()
