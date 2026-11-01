"""Fit the dcSBM blocks that CIDRE uses as its null model (Kojaku et al. 2021, Methods).

Paper: non-parametric Bayesian dcSBM without hierarchy (Peixoto 2017) on the journal network
aggregated over all years; here graph-tool's minimize_blockmodel_dl (degree-corrected, directed,
citation counts as edge multiplicities) on agg_eff_network.parquet from c6_full_run.py.

Usage:
    python c6_blocks.py --self-test                    # planted blocks, seconds; run first on the VM
    python c6_blocks.py --run-id <c6 run> --dry-run    # load and summarize, no graph-tool needed
    python c6_blocks.py --run-id <c6 run> [--journal-rule NAME] [--min-strength K] [--seed S]

--journal-rule: keep only the venues that pass the named rule in config.yaml journal_rules
(flags from c6_journal_set.py); the rule name becomes the default --tag.

Threads: C_GT_THREADS (default 2) sets OMP_NUM_THREADS before graph-tool is imported.
Output: runs/<run_id>/blocks.parquet (journal_id, block) and stage_blocks.json. Never overwritten:
a second fit needs --tag (e.g. --tag minstr10 -> blocks_minstr10.parquet).
"""
import argparse
import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent


def peak_rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def import_gt():
    os.environ["OMP_NUM_THREADS"] = os.environ.get("C_GT_THREADS", "2")
    import graph_tool.all as gt
    return gt


def fit(gt, src, dst, w, n, seed):
    gt.seed_rng(seed)
    np.random.seed(seed)
    g = gt.Graph(directed=True)
    g.add_vertex(n)
    ew = g.new_ep("int64_t")
    g.add_edge_list(np.column_stack([src, dst, w]).astype(np.int64), eprops=[ew])
    state = gt.minimize_blockmodel_dl(g, state_args=dict(eweight=ew, deg_corr=True))
    b = np.asarray(state.get_blocks().a)
    return b, float(state.entropy()), int(len(np.unique(b)))   # get_nonempty_B is not in every graph-tool version


def self_test(seed):
    gt = import_gt()
    rng = np.random.default_rng(seed)
    n, k = 200, 4
    truth = np.repeat(np.arange(k), n // k)
    p = np.where(truth[:, None] == truth[None, :], 0.20, 0.01)
    W = rng.poisson(p * 5)
    src, dst = np.nonzero(W)
    t0 = time.time()
    b, dl, B = fit(gt, src, dst, W[src, dst], n, seed)
    purity = sum(np.bincount(b[truth == c]).max() for c in range(k)) / n
    ok = B == k and purity >= 0.95
    print(json.dumps({"graph_tool": gt.__version__, "blocks_found": B, "blocks_planted": k,
                      "purity": round(purity, 3), "description_length": round(dl, 1),
                      "seconds": round(time.time() - t0, 2), "pass": bool(ok)}))
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-strength", type=int, default=0,
                    help="drop journals with in+out weight below this (fallback if the fit does not fit)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--journal-rule", default=None, help="name of a rule in config.yaml journal_rules")
    args = ap.parse_args()
    cfg = yaml.safe_load((HERE / "config.yaml").read_text())
    seed = args.seed if args.seed is not None else cfg["seed"]
    if args.self_test:
        self_test(seed)
    if not args.run_id:
        sys.exit("--run-id is required")

    run_dir = HERE / "runs" / args.run_id
    tag = args.tag or (args.journal_rule or "")
    suffix = f"_{tag}" if tag else ""
    out, marker = run_dir / f"blocks{suffix}.parquet", run_dir / f"stage_blocks{suffix}.json"
    if marker.exists() and not args.dry_run:
        sys.exit(f"{marker} exists; never overwrite, pass a new --tag")

    t0 = time.time()
    net = pd.read_parquet(run_dir / "agg_eff_network.parquet")
    rule_info = {}
    if args.journal_rule:
        rule = cfg["journal_rules"][args.journal_rule]
        fl = pd.read_parquet(run_dir / "journal_flags.parquet")
        ok = pd.Series(True, index=fl.index)
        if "type_journal" in rule:
            ok &= fl.type_journal == rule["type_journal"]
        if "issn" in rule:
            ok &= fl.issn == rule["issn"]
        if "min_ja_share" in rule:
            ok &= fl.ja_share.fillna(0) >= rule["min_ja_share"]
        kept = fl.journal_id[ok]
        rule_info = {"journal_rule": args.journal_rule, "rule": rule, "journals_in_rule": int(len(kept)),
                     "agg_edges_before_rule": int(len(net)), "agg_weight_before_rule": int(net.w.sum())}
        net = net[net.citing_j.isin(kept) & net.cited_j.isin(kept)]
    strength = (net.groupby("citing_j").w.sum().rename("out")
                .to_frame().join(net.groupby("cited_j").w.sum().rename("in"), how="outer").fillna(0))
    strength["s"] = strength["out"] + strength["in"]
    keep = strength.index[strength["s"] >= args.min_strength]
    net = net[net.citing_j.isin(keep) & net.cited_j.isin(keep)]
    ids = np.unique(np.concatenate([net.citing_j.values, net.cited_j.values]))
    pos = pd.Series(np.arange(len(ids)), index=ids)
    src, dst = pos[net.citing_j.values].values, pos[net.cited_j.values].values
    info = {"run_id": args.run_id, "seed": seed, "min_strength": args.min_strength, **rule_info,
            "journals": int(len(ids)), "edges": int(len(net)), "weight": int(net.w.sum()),
            "self_loops": int((src == dst).sum()), "load_seconds": round(time.time() - t0, 1),
            "input_sha256": hashlib.sha256((run_dir / "agg_eff_network.parquet").read_bytes()).hexdigest()}
    if args.dry_run:
        info["peak_rss_mb"] = peak_rss_mb()
        print(json.dumps(info, indent=1))
        return

    gt = import_gt()
    t1 = time.time()
    b, dl, B = fit(gt, src, dst, net.w.values, len(ids), seed)
    info.update({"graph_tool": gt.__version__, "omp_threads": os.environ["OMP_NUM_THREADS"],
                 "blocks": B, "description_length": dl, "fit_seconds": round(time.time() - t1, 1),
                 "peak_rss_mb": peak_rss_mb()})
    pd.DataFrame({"journal_id": ids, "block": b}).to_parquet(out, index=False)
    info["output_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
    marker.write_text(json.dumps(info, indent=2))
    with open(run_dir / "SHA256SUMS", "a") as f:
        f.write(f"{info['output_sha256']}  {out.name}\n")
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
