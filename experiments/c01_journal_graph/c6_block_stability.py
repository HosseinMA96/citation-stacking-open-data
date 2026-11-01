"""TODO item 6b: how much does the dcSBM partition depend on the seed? (laptop, no graph-tool)

Compares every pair of block fits of one c6 run, on the journals both fits contain:
  NMI  normalized mutual information, arithmetic-mean normalization (sklearn's default)
  ARI  adjusted Rand index (Hubert & Arabie 1985)
plus per fit: blocks, description length (lower = better fit; the usual way to pick among
stochastic runs, Peixoto's graph-tool docs), block-size summary. Fits are read from
runs/<run>/stage_blocks_<tag>.json + blocks_<tag>.parquet.

Usage:  python c6_block_stability.py --src c6_full_20261031_02 --run-id c6_blockstab_<YYYYMMDD>_01
Output: runs/<run_id>/fits.csv, pairwise.csv, summary.json, run.json, SHA256SUMS. Never overwrites.
"""
import argparse
import hashlib
import itertools
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def entropy(counts):
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log(p)).sum())


def compare(a, b):
    """a, b: integer labels on the same items. Returns NMI (arithmetic) and ARI."""
    n = len(a)
    joint = pd.DataFrame({"a": a, "b": b}).value_counts().to_numpy().astype(float)
    ca = np.bincount(pd.factorize(a)[0]).astype(float)
    cb = np.bincount(pd.factorize(b)[0]).astype(float)
    ha, hb, hab = entropy(ca), entropy(cb), entropy(joint)
    mi = ha + hb - hab
    nmi = 2 * mi / (ha + hb) if ha + hb > 0 else 1.0
    comb = lambda x: (x * (x - 1) / 2).sum()
    sij, sa, sb, tot = comb(joint), comb(ca), comb(cb), n * (n - 1) / 2
    exp = sa * sb / tot
    ari = (sij - exp) / ((sa + sb) / 2 - exp) if (sa + sb) / 2 != exp else 1.0
    return float(nmi), float(ari)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        a = np.array([0, 0, 1, 1, 2, 2]); b = np.array([5, 5, 7, 7, 9, 9]); c = np.array([0, 1, 0, 1, 0, 1])
        r1, r2 = compare(a, b), compare(a, c)
        ok = abs(r1[0] - 1) < 1e-12 and abs(r1[1] - 1) < 1e-12 and r2[1] < 0.01
        print({"relabelled": r1, "unrelated": r2, "pass": ok}); sys.exit(0 if ok else 1)
    src = HERE / "runs" / args.src
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    fits, parts = [], {}
    for st in sorted(src.glob("stage_blocks*.json")):
        tag = st.stem.replace("stage_blocks", "").lstrip("_") or "<untagged>"
        if tag == "<untagged>":
            continue                       # untagged = pre-rule fit, not part of this comparison
        info = json.loads(st.read_text())
        b = pd.read_parquet(src / f"blocks_{tag}.parquet").set_index("journal_id")["block"]
        sizes = b.value_counts()
        parts[tag] = b
        fits.append({"tag": tag, "journal_rule": info.get("journal_rule"), "seed": info["seed"],
                     "journals": len(b), "blocks": info["blocks"], "description_length": info["description_length"],
                     "fit_seconds": info["fit_seconds"], "largest_block": int(sizes.max()),
                     "median_block_size": float(sizes.median()), "singleton_blocks": int((sizes == 1).sum()),
                     "blocks_sha256": hashlib.sha256((src / f"blocks_{tag}.parquet").read_bytes()).hexdigest()})
    fits = pd.DataFrame(fits).sort_values("description_length")
    rows = []
    for x, y in itertools.combinations(sorted(parts), 2):
        common = parts[x].index.intersection(parts[y].index)
        nmi, ari = compare(parts[x].loc[common].to_numpy(), parts[y].loc[common].to_numpy())
        rows.append({"a": x, "b": y, "common_journals": len(common), "nmi": round(nmi, 4), "ari": round(ari, 4),
                     "identical": bool(nmi == 1.0 and ari == 1.0)})
    pw = pd.DataFrame(rows)
    run_dir.mkdir(parents=True)
    fits.to_csv(run_dir / "fits.csv", index=False)
    pw.to_csv(run_dir / "pairwise.csv", index=False)
    same_rule = pw[pw.a.str.startswith("main") & pw.b.str.startswith("main")]
    summary = {"src": args.src, "fits": len(fits),
               "best_fit_by_description_length": fits.iloc[0]["tag"],
               "blocks_range_rule_main": [int(fits[fits.journal_rule == "main"].blocks.min()),
                                          int(fits[fits.journal_rule == "main"].blocks.max())],
               "nmi_rule_main_pairs": [float(same_rule.nmi.min()), float(same_rule.nmi.median()), float(same_rule.nmi.max())],
               "ari_rule_main_pairs": [float(same_rule.ari.min()), float(same_rule.ari.median()), float(same_rule.ari.max())],
               "note": "[min, median, max] over pairs of rule-main fits"}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "src_run": args.src, "python": platform.python_version(), "pandas": pd.__version__,
        "numpy": np.__version__}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(fits.to_string(index=False)); print(pw.to_string(index=False)); print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
