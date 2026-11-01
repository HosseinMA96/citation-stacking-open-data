"""C12b: recipient-centric variant of CIDRE (post hoc; RESULTS_LOG 2026-10-31 "C12b pre-registration").

Uses CIDRE's excessive-edge network Abar (cidre_paper.excessive_edges: dcSBM test, BH alpha 0.01,
condition 1) without the group peeling. Per journal j and year t:
  r_j = sum_i Abar_ij / s_in(j)   (pre-peeling recipient score; s_in includes self-citations, as in CIDRE)
  e_j = sum_i Abar_ij             (excessive in-citations, self-loops excluded)
Flag j if r_j >= THETA (0.15) and e_j >= THETA_W (50); both from the CIDRE paper, not tuned.
Also: the top excessive donor of j and its share of e_j.

Usage:  python c12_recipient.py --self-test
        python c12_recipient.py --src c6_full_20261031_02 --match c10_match_20261031_03 \\
            --years 2015,...,2023 --tags main,... --run-id c12_recip_<YYYYMMDD>_01 [--workers N]
Output: runs/<run_id>/flags.csv (flagged journal-years, all partitions), labeled.csv (scores of every
        labeled journal in every year and partition), timing.csv, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import cidre_paper  # noqa: E402
from c12_cidre import build  # noqa: E402


def scores(W, W_all, blocks):
    A = cidre_paper.excessive_edges(W, blocks, W_all).tocsc()
    s_in = np.maximum(np.asarray(W.sum(axis=0)).ravel(), 1.0)
    e = np.asarray(A.sum(axis=0)).ravel()
    top_donor = np.full(A.shape[1], -1)
    top_w = np.zeros(A.shape[1])
    for j in np.nonzero(e)[0]:
        col = A[:, j]
        k = col.indices[np.argmax(col.data)]
        top_donor[j], top_w[j] = k, col.data.max()
    return e / s_in, e, s_in, top_donor, top_w


def run_one(job):
    t, tag, pairs_path, blocks_path, labeled_ids = job
    t0 = time.time()
    bl = pd.read_parquet(blocks_path).sort_values("journal_id")
    ids = bl.journal_id.values
    con = duckdb.connect()
    con.execute(f"SET threads = 2; SET memory_limit = '{os.environ.get('C12_JOB_MEM', '6GB')}'")
    pairs = con.execute(f"""SELECT t, citing_j, cited_j, eff, prev FROM read_parquet('{pairs_path}')
                            WHERE t = {t} AND citing_j IS NOT NULL AND (eff > 0 OR prev > 0)""").df()
    W, W_all, _ = build(pairs, ids, t)
    del pairs
    r, e, s_in, td, tw = scores(W, W_all, bl.block.values)
    df = pd.DataFrame({"t": t, "tag": tag, "journal_id": ids, "r": r, "e": e, "s_in": s_in,
                       "top_donor": np.where(td >= 0, ids[np.maximum(td, 0)], -1), "top_donor_excess": tw})
    df["flag"] = (df.r >= cidre_paper.THETA) & (df.e >= cidre_paper.THETA_W)
    keep = df[df.flag | df.journal_id.isin(labeled_ids)]
    info = {"t": t, "tag": tag, "journals": len(ids), "flagged": int(df.flag.sum()),
            "seconds": round(time.time() - t0, 1),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    return keep, info


def self_test():
    """Large donor (out-strength >> pair) feeding a small recipient: CIDRE drops it, the variant flags it."""
    rng = np.random.default_rng(4311)
    n = 60
    blocks = np.repeat([0, 1, 2], 20)
    rows = []
    for i in range(n):
        for j in range(n):
            e = rng.poisson(4.0 if blocks[i] == blocks[j] else 0.5)
            if e:
                rows.append((i, j, e, e * 3))
    rows.append((5, 45, 200, 202))                 # donor 5 -> recipient 45, cross-block
    rows += [(5, j, 150, 450) for j in range(20) if j != 5]  # donor 5 is large: many ordinary citations
    p = pd.DataFrame(rows, columns=["citing_j", "cited_j", "eff", "prev"]).groupby(["citing_j", "cited_j"]).sum().reset_index()
    p["t"] = 2020
    W, W_all, _ = build(p, np.arange(n), 2020)
    groups = cidre_paper.detect(W, group_membership=blocks, W_all=W_all)
    in_groups = set(np.concatenate([g.node_ids for g in groups])) if groups else set()
    r, e, s_in, td, tw = scores(W, W_all, blocks)
    flagged = set(np.nonzero((r >= 0.15) & (e >= 50))[0])
    checks = {"cidre_misses": 45 not in in_groups, "variant_flags": 45 in flagged, "top_donor": td[45] == 5,
              "only_45": flagged == {45}}
    ok = all(checks.values())
    print(checks, {"r45": round(r[45], 3), "e45": e[45]}, "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--match")
    ap.add_argument("--years", default="2020")
    ap.add_argument("--tags", default="main")
    ap.add_argument("--run-id")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
    runs = HERE / "runs"
    src, run_dir = runs / args.src, runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sup = pd.read_csv(ROOT / "data" / "suppressions.csv")
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    labeled = sorted(set(jid.values()))
    years, tags = [int(y) for y in args.years.split(",")], args.tags.split(",")
    jobs = [(t, tag, src / "pairs_jcr_years.parquet", src / f"blocks_{tag}.parquet", labeled) for t in years for tag in tags]
    t0 = time.time()
    parts, infos = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for df, info in ex.map(run_one, jobs):
            parts.append(df)
            infos.append(info)
            print(json.dumps(info), flush=True)
    run_dir.mkdir(parents=True)
    allr = pd.concat(parts, ignore_index=True)
    allr[allr.flag].to_csv(run_dir / "flags.csv", index=False)
    name = {v: k for k, v in jid.items()}
    lab = allr[allr.journal_id.isin(labeled)].copy()
    lab["journal"] = lab.journal_id.map(name)
    lab["top_donor_name_if_labeled"] = lab.top_donor.map(lambda x: name.get(int(x)))
    lab.to_csv(run_dir / "labeled.csv", index=False)
    pd.DataFrame(infos).to_csv(run_dir / "timing.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cidre_paper_sha256": hashlib.sha256((HERE / "cidre_paper.py").read_bytes()).hexdigest(),
        "src_run": args.src, "match_run": args.match, "years": years, "tags": tags,
        "params": {"theta": cidre_paper.THETA, "theta_w": cidre_paper.THETA_W, "alpha": cidre_paper.ALPHA},
        "seconds_total": round(time.time() - t0, 1), "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")


if __name__ == "__main__":
    main()
