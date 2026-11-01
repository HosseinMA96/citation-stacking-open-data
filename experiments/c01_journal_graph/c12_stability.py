"""R4: how much do CIDRE's groups and the recipient-variant flags depend on the dcSBM partition?

Per year, for every pair of the rule-`main` partitions (main, main_s1..s4, main_s4311_rep, main_s4311_t1a):
  CIDRE   member Jaccard  = |A & B| / |A | B| over the sets of journals in any group
          group recovery  = share of A's groups with a group in B of Jaccard >= 0.5 (best match), averaged both ways
  variant flag Jaccard    = Jaccard of the flagged journal sets
Also the share of flags/members that appear in all 7 partitions ("core").
type_issn_ja50 (different journal set) is left out. Laptop, read-only.

Usage:  python c12_stability.py --cidre c12_cidre_20261031_02 --recip c12_recip_20261031_01 --run-id c12_stab_<YYYYMMDD>_01
Output: runs/<run_id>/pairwise.csv, by_year.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import itertools
import json
import platform
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TAGS = ["main", "main_s1", "main_s2", "main_s3", "main_s4", "main_s4311_rep", "main_s4311_t1a"]


def jac(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def recovery(ga, gb):
    if not ga:
        return 1.0 if not gb else 0.0
    return sum(any(jac(x, y) >= 0.5 for y in gb) for x in ga) / len(ga)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cidre", required=True)
    ap.add_argument("--recip", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    g = pd.read_csv(runs / args.cidre / "groups.csv")
    f = pd.read_csv(runs / args.recip / "flags.csv")
    rows, by = [], []
    for t in sorted(g.t.unique()):
        groups = {tag: [frozenset(x.journal_id) for _, x in g[(g.t == t) & (g.tag == tag)].groupby("group")] for tag in TAGS}
        members = {tag: set().union(*groups[tag]) if groups[tag] else set() for tag in TAGS}
        flags = {tag: set(f[(f.t == t) & (f.tag == tag)].journal_id) for tag in TAGS}
        for a, b in itertools.combinations(TAGS, 2):
            rows.append({"t": t, "a": a, "b": b, "cidre_member_jaccard": round(jac(members[a], members[b]), 4),
                         "cidre_group_recovery": round((recovery(groups[a], groups[b]) + recovery(groups[b], groups[a])) / 2, 4),
                         "variant_flag_jaccard": round(jac(flags[a], flags[b]), 4)})
        core_m = set.intersection(*members.values()); any_m = set.union(*members.values())
        core_f = set.intersection(*flags.values()); any_f = set.union(*flags.values())
        by.append({"t": t, "cidre_members_core": len(core_m), "cidre_members_any": len(any_m),
                   "cidre_core_share": round(len(core_m) / len(any_m), 4) if any_m else None,
                   "variant_flags_core": len(core_f), "variant_flags_any": len(any_f),
                   "variant_core_share": round(len(core_f) / len(any_f), 4) if any_f else None})
    pw, by = pd.DataFrame(rows), pd.DataFrame(by)
    summ = {c: [float(pw[c].min()), float(pw[c].median()), float(pw[c].max())]
            for c in ("cidre_member_jaccard", "cidre_group_recovery", "variant_flag_jaccard")}
    summ["note"] = "[min, median, max] over 21 partition pairs x 9 years"
    summ["core_share_median"] = {"cidre": float(by.cidre_core_share.median()), "variant": float(by.variant_core_share.median())}
    run_dir.mkdir(parents=True)
    pw.to_csv(run_dir / "pairwise.csv", index=False)
    by.to_csv(run_dir / "by_year.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "cidre_run": args.cidre,
        "recip_run": args.recip, "tags": TAGS, "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(summ, indent=1)); print(by.to_string())


if __name__ == "__main__":
    main()
