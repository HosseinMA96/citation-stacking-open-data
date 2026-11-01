"""C18 (VM): R10 asymmetric-theta CIDRE and R9b single-block recipient variant (protocol: RESULTS_LOG "Review round 1 ...
pre-registration of R9-R13"). Labels are not needed here; c18_eval.py scores the outputs on the laptop.

Per JCR year t, partition `main` of a c6 run, W / W_all as in c12_cidre.build:
  R10  Abar = cidre_paper.excessive_edges(W, dcSBM blocks, W_all) (unchanged test). Peeling with separate thresholds:
       a node is removed when donor < theta_d AND recipient < theta_r (paper: theta_d = theta_r = 0.15); then weak
       components and theta_w = 50 exactly as cidre_paper.detect. theta_d in THETA_D, theta_r = 0.15.
  R9b  Abar1 = excessive_edges(W, one block for all journals, W_all): configuration-model null instead of the dcSBM.
       Recipient flags as c12_recipient: r = e / s_in >= 0.15 and e >= 50.

Usage:  python c18_asym_null.py --self-test
        python c18_asym_null.py --src c6_full_20261031_02 --years 2015,...,2023 --run-id c18_asym_<YYYYMMDD>_01 [--workers N]
Output: runs/<run_id>/groups_asym.csv, flags_1block.csv, timing.csv, run.json, SHA256SUMS. Never overwrites.
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
from scipy import sparse
from scipy.sparse.csgraph import connected_components

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cidre_paper  # noqa: E402
from c12_cidre import build  # noqa: E402
from c12_recipient import scores  # noqa: E402
from cidre.cidre import Group  # noqa: E402

THETA_D = (0.15, 0.10, 0.05, 0.02, 0.01)
THETA_R = cidre_paper.THETA


def detect_asym(W, Abar, theta_d, theta_r=THETA_R, theta_w=cidre_paper.THETA_W):
    """cidre_paper.detect on a precomputed Abar, with separate donor / recipient thresholds."""
    N = W.shape[0]
    U = np.ones(N)
    indeg = np.maximum(np.asarray(W.sum(axis=0)).ravel(), 1.0)
    outdeg = np.maximum(np.asarray(W.sum(axis=1)).ravel(), 1.0)
    while True:
        donor = U * (Abar @ U) / outdeg
        recip = U * (U @ Abar) / indeg
        drop = (U > 0) & (donor < theta_d) & (recip < theta_r)
        if not drop.any():
            break
        U[drop] = 0
    nodes = np.where(U)[0]
    sub = Abar[nodes][:, nodes]
    _, comp = connected_components(sub, directed=True, connection="weak")
    deg = np.asarray(sub.sum(axis=0)).ravel() + np.asarray(sub.sum(axis=1)).ravel()
    groups = []
    for c in np.unique(comp[deg > 0]):
        members = nodes[comp == c]
        g = Group(members, donor[members], recip[members], min(theta_d, theta_r))
        g.set_within_net(W, members)
        if g.get_num_edges() >= theta_w:
            groups.append((g, donor[members], recip[members]))
    return groups


def run_one(job):
    t, pairs_path, blocks_path = job
    t0 = time.time()
    bl = pd.read_parquet(blocks_path).sort_values("journal_id")
    ids = bl.journal_id.values
    con = duckdb.connect()
    con.execute(f"SET threads = 2; SET memory_limit = '{os.environ.get('C12_JOB_MEM', '6GB')}'")
    pairs = con.execute(f"""SELECT t, citing_j, cited_j, eff, prev FROM read_parquet('{pairs_path}')
                            WHERE t = {t} AND citing_j IS NOT NULL AND (eff > 0 OR prev > 0)""").df()
    W, W_all, _ = build(pairs, ids, t)
    del pairs
    Abar = cidre_paper.excessive_edges(W, bl.block.values, W_all)
    grows = []
    for th in THETA_D:
        for k, (g, dsc, rsc) in enumerate(detect_asym(W, Abar, th)):
            for m, d, r in zip(g.node_ids, dsc, rsc):
                grows.append({"t": t, "theta_d": th, "group": k, "journal_id": int(ids[m]), "donor_score": float(d),
                              "recipient_score": float(r), "group_size": g.size(), "within_citations": float(g.get_num_edges())})
    del Abar
    r, e, s_in, td, tw = scores(W, W_all, np.zeros(len(ids), dtype=int))
    df = pd.DataFrame({"t": t, "journal_id": ids, "r": r, "e": e, "s_in": s_in,
                       "top_donor": np.where(td >= 0, ids[np.maximum(td, 0)], -1), "top_donor_excess": tw})
    flags = df[(df.r >= cidre_paper.THETA) & (df.e >= cidre_paper.THETA_W)]
    info = {"t": t, "journals": len(ids), "groups_by_theta_d": {th: len({(x["group"]) for x in grows if x["theta_d"] == th})
                                                                 for th in THETA_D},
            "flags_1block": len(flags), "seconds": round(time.time() - t0, 1),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    return grows, flags, info


def self_test():
    """c12_recipient's toy: a large donor (5) feeding a small recipient (45). Paper theta misses it; a low theta_d finds
    the pair; the single-block variant still flags 45."""
    rng = np.random.default_rng(4311)
    n = 60
    blocks = np.repeat([0, 1, 2], 20)
    rows = []
    for i in range(n):
        for j in range(n):
            e = rng.poisson(4.0 if blocks[i] == blocks[j] else 0.5)
            if e:
                rows.append((i, j, e, e * 3))
    rows.append((5, 45, 200, 202))
    rows += [(5, j, 150, 450) for j in range(20) if j != 5]
    p = pd.DataFrame(rows, columns=["citing_j", "cited_j", "eff", "prev"]).groupby(["citing_j", "cited_j"]).sum().reset_index()
    p["t"] = 2020
    W, W_all, _ = build(p, np.arange(n), 2020)
    Abar = cidre_paper.excessive_edges(W, blocks, W_all)
    found = {th: [set(g.node_ids) for g, _, _ in detect_asym(W, Abar, th)] for th in THETA_D}
    paper = [set(g.node_ids) for g in cidre_paper.detect(W, group_membership=blocks, W_all=W_all)]
    r, e, *_ = scores(W, W_all, np.zeros(n, dtype=int))
    checks = {"theta_d_0.15_equals_paper": found[0.15] == paper,
              "paper_misses_pair": not any({5, 45} <= s for s in found[0.15]),
              "low_theta_d_finds_pair": any({5, 45} <= s for s in found[0.01]),
              "one_block_flags_45": bool(r[45] >= 0.15 and e[45] >= 50)}
    ok = all(checks.values())
    print(checks, {th: [sorted(s) for s in v] for th, v in found.items()}, "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--years", default="2020")
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
    years = [int(y) for y in args.years.split(",")]
    jobs = [(t, src / "pairs_jcr_years.parquet", src / "blocks_main.parquet") for t in years]
    t0 = time.time()
    grows, flags, infos = [], [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for g, f, info in ex.map(run_one, jobs):
            grows += g
            flags.append(f)
            infos.append(info)
            print(json.dumps(info), flush=True)
    run_dir.mkdir(parents=True)
    pd.DataFrame(grows, columns=["t", "theta_d", "group", "journal_id", "donor_score", "recipient_score", "group_size",
                                 "within_citations"]).to_csv(run_dir / "groups_asym.csv", index=False)
    pd.concat(flags, ignore_index=True).to_csv(run_dir / "flags_1block.csv", index=False)
    pd.DataFrame(infos).to_csv(run_dir / "timing.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cidre_paper_sha256": hashlib.sha256((HERE / "cidre_paper.py").read_bytes()).hexdigest(),
        "src_run": args.src, "years": years, "tag": "main", "theta_d": list(THETA_D), "theta_r": THETA_R,
        "theta_w": cidre_paper.THETA_W, "alpha": cidre_paper.ALPHA, "workers": args.workers,
        "blocks_sha256": hashlib.sha256((src / "blocks_main.parquet").read_bytes()).hexdigest(),
        "seconds_total": round(time.time() - t0, 1), "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")


if __name__ == "__main__":
    main()
