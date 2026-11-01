"""C12: CIDRE (paper setup, cidre_paper.py) on the yearly journal networks of a c6 run, for several dcSBM partitions.

For each JCR year t and each partition (blocks_<tag>.parquet of the c6 run):
  W[i, j]     = eff: citations from journal i's items of year t to journal j's items of t-1, t-2
  W_all[i, j] = prev: citations from i's items of year t to j's items of any year < t (condition 1)
  over the journals of the partition (the rule's network journals), citing items with a journal only
  (config counting.citing_journal_only). Self-loops are kept (they count in the strengths).
  Groups: cidre_paper.detect (theta 0.15, theta_w 50, alpha 0.01, lambda clipped at 1).
Matching (paper rule, cidre_paper.overlap_detected): a JCR group = a labeled journal and its named partner
in data/suppressions.csv (both matched in the c10 match run), for the same data year; detected if
|JCR & CIDRE| / |CIDRE| >= 0.5 and >= 2 shared journals. Labeled journals without a named partner are
reported only as "in some CIDRE group" (descriptive, not a detection).

Usage:  python c12_cidre.py --self-test
        python c12_cidre.py --src c6_full_20261031_02 --match c10_match_20261031_03 --years 2020 \\
            --tags main --run-id c12_cidre_<YYYYMMDD>_01 [--workers N]
Output: runs/<run_id>/groups.csv (one row per member), group_summary.csv, detections.csv,
        labeled_in_groups.csv, timing.csv, run.json, SHA256SUMS. Never overwrites.
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import cidre_paper  # noqa: E402


def build(pairs, ids, t):
    """W, W_all over journal ids (index = position in ids) for year t from a pairs table (DataFrame)."""
    pos = pd.Series(np.arange(len(ids)), index=ids)
    p = pairs[(pairs.t == t) & pairs.citing_j.isin(pos.index) & pairs.cited_j.isin(pos.index)]
    r, c = pos[p.citing_j.values].values, pos[p.cited_j.values].values
    n = len(ids)
    W = sparse.csr_matrix((p.eff.values.astype(float), (r, c)), shape=(n, n))
    W_all = sparse.csr_matrix((p.prev.values.astype(float), (r, c)), shape=(n, n))
    return W, W_all, int((p.eff > 0).sum())


def run_one(job):
    t, tag, pairs_path, blocks_path = job
    t0 = time.time()
    bl = pd.read_parquet(blocks_path).sort_values("journal_id")
    ids = bl.journal_id.values
    con = duckdb.connect()
    con.execute(f"SET threads = 2; SET memory_limit = '{os.environ.get('C12_JOB_MEM', '6GB')}'")
    pairs = con.execute(f"""SELECT t, citing_j, cited_j, eff, prev FROM read_parquet('{pairs_path}')
                            WHERE t = {t} AND citing_j IS NOT NULL AND (eff > 0 OR prev > 0)""").df()
    W, W_all, n_edges = build(pairs, ids, t)
    del pairs
    groups = cidre_paper.detect(W, group_membership=bl.block.values, W_all=W_all)
    rows = []
    for k, g in enumerate(groups):
        for m in g.node_ids:
            rows.append({"t": t, "tag": tag, "group": k, "journal_id": int(ids[m]),
                         "donor_score": float(g.donor_score[list(g.node_ids).index(m)]),
                         "recipient_score": float(g.recipient_score[list(g.node_ids).index(m)]),
                         "is_donor": m in g.donors, "is_recipient": m in g.recipients,
                         "group_size": g.size(), "within_citations": float(g.get_num_edges())})
    info = {"t": t, "tag": tag, "journals": len(ids), "edges": n_edges, "weight": float(W.sum()),
            "groups": len(groups), "seconds": round(time.time() - t0, 1),
            "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    return rows, info


def match(groups, sup, jid, years):
    """Detections of named JCR pairs, and whether each labeled journal is in some group."""
    det, lab = [], []
    by = {(t, tag): g for (t, tag), g in groups.groupby(["t", "tag"])} if len(groups) else {}
    tags = sorted(groups.tag.unique()) if len(groups) else []
    for r in sup.itertuples():
        t = int(r.jcr_data_year)
        if t not in years:
            continue
        a = jid.get(r.journal)
        b = jid.get(r.partner_journal) if isinstance(r.partner_journal, str) else None
        for tag in tags:
            g = by.get((t, tag))
            in_grp = g[g.journal_id == a].group.unique().tolist() if (g is not None and a) else []
            lab.append({"t": t, "tag": tag, "journal": r.journal, "type": r.type, "matched": a is not None,
                        "in_group": bool(in_grp), "groups": " ".join(map(str, in_grp))})
            if b is not None and a is not None and str(r.role) == "recipient":
                hit = [k for k, gg in (g.groupby("group") if g is not None else [])
                       if cidre_paper.overlap_detected({a, b}, set(gg.journal_id))]
                det.append({"t": t, "tag": tag, "recipient": r.journal, "donor": r.partner_journal,
                            "detected": bool(hit), "groups": " ".join(map(str, hit))})
    return pd.DataFrame(det), pd.DataFrame(lab)


def self_test():
    """Planted pair with heavy window exchange in a 60-journal, 3-block toy network."""
    import tempfile
    rng = np.random.default_rng(4311)
    n, ids = 60, np.arange(1000, 1060)
    blocks = np.repeat([0, 1, 2], 20)
    rows = []
    for i in range(n):
        for j in range(n):
            lam = 4.0 if blocks[i] == blocks[j] else 0.5
            e = rng.poisson(lam)
            if e:
                rows.append((2020, ids[i], ids[j], e, e * 3))
    rows += [(2020, ids[3], ids[25], 300, 310), (2020, ids[25], ids[3], 250, 260)]   # planted, cross-block
    d = Path(tempfile.mkdtemp())
    pd.DataFrame(rows, columns=["t", "citing_j", "cited_j", "eff", "prev"]).to_parquet(d / "pairs.parquet")
    pd.DataFrame({"journal_id": ids, "block": blocks}).to_parquet(d / "blocks_x.parquet")
    out, info = run_one((2020, "x", d / "pairs.parquet", d / "blocks_x.parquet"))
    g = pd.DataFrame(out)
    sup = pd.DataFrame({"jcr_data_year": [2020], "journal": ["R"], "type": ["stacking"], "role": ["recipient"],
                        "partner_journal": ["D"]})
    det, lab = match(g, sup, {"R": int(ids[25]), "D": int(ids[3])}, {2020})
    checks = {"one_group": info["groups"] == 1, "members": set(g.journal_id) == {int(ids[3]), int(ids[25])},
              "detected": bool(det.detected.all()) and len(det) == 1, "labeled": bool(lab.in_group.all())}
    ok = all(checks.values())
    print(checks, info, "ALL PASS" if ok else "FAIL")
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
    years = [int(y) for y in args.years.split(",")]
    tags = args.tags.split(",")
    jobs = [(t, tag, src / "pairs_jcr_years.parquet", src / f"blocks_{tag}.parquet") for t in years for tag in tags]
    t0 = time.time()
    rows, infos = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r, info in ex.map(run_one, jobs):
            rows += r
            infos.append(info)
            print(json.dumps(info), flush=True)
    run_dir.mkdir(parents=True)
    g = pd.DataFrame(rows, columns=["t", "tag", "group", "journal_id", "donor_score", "recipient_score",
                                    "is_donor", "is_recipient", "group_size", "within_citations"])
    g.to_csv(run_dir / "groups.csv", index=False)
    (g.groupby(["t", "tag", "group"]).agg(size=("journal_id", "size"), within_citations=("within_citations", "first"))
      .reset_index().to_csv(run_dir / "group_summary.csv", index=False))
    pd.DataFrame(infos).to_csv(run_dir / "timing.csv", index=False)
    sup = pd.read_csv(ROOT / "data" / "suppressions.csv")
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    det, lab = match(g, sup, jid, set(years))
    det.to_csv(run_dir / "detections.csv", index=False)
    lab.to_csv(run_dir / "labeled_in_groups.csv", index=False)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cidre_paper_sha256": hashlib.sha256((HERE / "cidre_paper.py").read_bytes()).hexdigest(),
        "src_run": args.src, "match_run": args.match, "years": years, "tags": tags, "workers": args.workers,
        "params": {"theta": cidre_paper.THETA, "theta_w": cidre_paper.THETA_W, "alpha": cidre_paper.ALPHA,
                   "citing_journal_only": True},
        "blocks_sha256": {tag: hashlib.sha256((src / f"blocks_{tag}.parquet").read_bytes()).hexdigest() for tag in tags},
        "seconds_total": round(time.time() - t0, 1), "python": platform.python_version(),
        "duckdb": duckdb.__version__, "pandas": pd.__version__, "numpy": np.__version__}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(det.to_string() if len(det) else "no named pairs in these years")


if __name__ == "__main__":
    main()
