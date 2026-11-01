"""TODO item 3: check that cidre 0.0.1 (+ cidre_paper.py) reproduces the paper's setup on a toy graph.

Usage:
    ../../.venv/bin/python cidre_toy_check.py --run-id <id>

Toy graph: N journals in K blocks (fields), Poisson citations from a dcSBM with heavy-tailed
strengths. Planted on top:
  - cartel: 3 journals in 3 different blocks, donor -> 2 recipients, recent citations;
  - decoy: same excess, but most of the pair's citations go to old papers (fails condition 1);
  - small: 2 journals with excess below theta_w = 50 within-group citations.
Never overwrites a run.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import networkx as nx
import numpy as np
import yaml
from scipy import sparse

import cidre
import cidre_paper as cp

HERE = Path(__file__).resolve().parent


def toy_graph(rng, N=200, K=4, p_in=0.9, base=60.0):
    g = np.repeat(np.arange(K), N // K)
    s_out = rng.pareto(2.5, N) + 0.2
    s_in = rng.pareto(2.5, N) + 0.2
    mix = np.full((K, K), (1 - p_in) / (K - 1))
    np.fill_diagonal(mix, p_in)
    lam = base * np.outer(s_out, s_in) * mix[g][:, g] / np.mean(s_out) / np.mean(s_in) / (N / K)
    W = rng.poisson(lam).astype(float)
    return W, g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    run_dir.mkdir(parents=True)

    seed = yaml.safe_load((HERE / "config.yaml").read_text())["seed"]
    rng = np.random.default_rng(seed)
    W, g = toy_graph(rng)
    N = W.shape[0]
    # "All earlier years" citations: effective citations plus older ones (about 1x as many).
    W_all = W + rng.poisson(W)

    cartel = [5, 60, 115]            # blocks 0, 1, 2
    decoy = [10, 160]                # blocks 0, 3
    # Small pair: the lowest-strength journals in blocks 0 and 2, so 30 extra citations
    # pass theta = 0.15 but stay below theta_w = 50 (run _01 used fixed nodes 20, 130,
    # which never reached theta; see RESULTS_LOG).
    strength = W.sum(0) + W.sum(1)
    small = [int(np.flatnonzero(g == b)[np.argmin(strength[g == b])]) for b in (0, 2)]
    W[5, 60] += 150; W[5, 115] += 150; W[60, 115] += 40
    W_all[5, 60] += 160; W_all[5, 115] += 160; W_all[60, 115] += 45
    W[10, 160] += 150; W_all[10, 160] += 150 + 400          # mostly old papers -> not excessive
    W[small[0], small[1]] += 30; W_all[small[0], small[1]] += 32                 # recent but < theta_w in total
    planted = {"cartel": cartel, "decoy": decoy, "small": small}

    rec = {"run_id": args.run_id, "script": "cidre_toy_check.py", "seed": seed,
           "cidre_version": "0.0.1", "networkx": nx.__version__,
           "toy": {"N": N, "K": 4, "total_citations": float(W.sum()), "planted": planted},
           "checks": {}}
    ck = rec["checks"]

    # 1. Package Cidre.detect as published (needs networkx < 3; shimmed here only for the check).
    try:
        cidre.Cidre(group_membership=g).detect(sparse.csr_matrix(W), threshold=0.15)
        ck["package_runs_unpatched"] = True
    except AttributeError as e:
        ck["package_runs_unpatched"] = False
        ck["package_error"] = str(e)
    nx.from_scipy_sparse_matrix = nx.from_scipy_sparse_array
    pkg = cidre.Cidre(group_membership=g).detect(sparse.csr_matrix(W), threshold=0.15)
    pkg_sets = sorted(sorted(int(x) for x in grp.node_ids) for grp in pkg)
    ours = cp.detect(W, threshold=0.15, theta_w=0, group_membership=g)
    our_sets = sorted(sorted(int(x) for x in grp.node_ids) for grp in ours)
    ck["wrapper_equals_package_without_extras"] = pkg_sets == our_sets
    ck["package_groups"] = pkg_sets

    # 2. Null model: package lambda vs paper eq. 5, by hand.
    Wc = sparse.csr_matrix(W)
    pv, src, dst, w = cidre.filters.EdgeFilter()._calc_p_values_dcsbm(Wc, g, 1)
    s_out, s_in = W.sum(1), W.sum(0)
    Lam = np.array([[W[g == u][:, g == v].sum() for v in range(4)] for u in range(4)])
    S_out = np.array([s_out[g == u].sum() for u in range(4)])
    S_in = np.array([s_in[g == u].sum() for u in range(4)])
    lam = s_out[src] * s_in[dst] * Lam[g[src], g[dst]] / (S_out[g[src]] * S_in[g[dst]])
    from scipy import stats
    p_hand = 1.0 - stats.poisson.cdf(w - 1, np.maximum(lam, 1.0))
    ck["pvalues_match_eq5_eq6_max_abs_diff"] = float(np.max(np.abs(p_hand - pv)))

    # 3. Paper setup: theta 0.15, theta_w 50, alpha 0.01, condition 1, true blocks.
    def run(name, **kw):
        t0 = time.time()
        groups = cp.detect(W, **kw)
        sets = [sorted(int(x) for x in grp.node_ids) for grp in groups]
        res = {"groups": sets,
               "within_citations": [float(grp.get_num_edges()) for grp in groups],
               "seconds": round(time.time() - t0, 3)}
        for k, v in planted.items():
            res[f"{k}_detected"] = any(cp.overlap_detected(v, s) for s in sets)
        ck[name] = res

    run("paper_setup", group_membership=g, W_all=W_all)
    run("no_condition1", group_membership=g)
    run("no_theta_w", group_membership=g, W_all=W_all, theta_w=0)
    run("single_block_null", group_membership=None, W_all=W_all)

    expected = {"cartel_detected": True, "decoy_detected": False, "small_detected": False}
    ps = ck["paper_setup"]
    ck["paper_setup_as_expected"] = all(ps[k] == v for k, v in expected.items())
    ck["condition1_excludes_decoy"] = ck["no_condition1"]["decoy_detected"] and not ps["decoy_detected"]
    ck["theta_w_removes_small"] = ck["no_theta_w"]["small_detected"] and not ps["small_detected"]

    (run_dir / "run.json").write_text(json.dumps(rec, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        f.write(f"{hashlib.sha256((run_dir / 'run.json').read_bytes()).hexdigest()}  run.json\n")
    print(json.dumps({k: v for k, v in ck.items() if not isinstance(v, dict)}, indent=1))
    for k in ("paper_setup", "no_condition1", "no_theta_w", "single_block_null"):
        print(k, {kk: vv for kk, vv in ck[k].items() if kk != "within_citations"})


if __name__ == "__main__":
    main()
