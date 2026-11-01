"""C10 follow-up: split the fidelity results by whether the CITING side has references in OpenCitations.

For each fidelity row (c10_fidelity run): the citing journal is the journal itself (self-citation rows) or the
donor(s) (stacking rows). out_eff(j, t) = window citations made by j's items of year t (pairs_jcr_years,
any cited journal), out_all(j, t) = the same over all cited years (prev). "References present" = out_all > 0.
Also n_items(j, t) from citable_by_year (n_all), to show that the journal published in t.
Reported: pass rate and median |diff| with references present vs absent. Read-only.

Usage:  python c10_coverage_split.py --src c6_full_20261031_02 --fidelity c10_fidelity_20261031_02 \\
            --match c10_match_20261031_05 --run-id c10_covsplit_<YYYYMMDD>_01
Output: runs/<run_id>/fidelity_with_coverage.csv, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--fidelity", required=True)
    ap.add_argument("--match", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    f = pd.read_csv(runs / args.fidelity / "fidelity.csv")
    f = f[f.scores != "scores_sensitivity"].copy()
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    f["citing_names"] = [p if mt != "self_cites_pct_jif_numerator" else j
                         for j, p, mt in zip(f.journal, f.partner, f.metric)]
    f["citing_ids"] = f.citing_names.map(lambda s: [jid.get(x.strip()) for x in str(s).split(";")])
    ids = sorted({i for l in f.citing_ids for i in l if i is not None})
    con = duckdb.connect()
    con.execute(f"SET threads = 2; SET memory_limit = '{os.environ.get('C_MEM', '1GB')}'")
    out = con.execute(f"""SELECT t, citing_j AS j, sum(eff) AS out_eff, sum(prev) AS out_all
        FROM read_parquet('{runs / args.src / 'pairs_jcr_years.parquet'}')
        WHERE citing_j IN ({",".join(map(str, ids))}) GROUP BY ALL""").df()
    items = con.execute(f"""SELECT pub_year AS t, journal_id AS j, n_all FROM read_parquet('{runs / args.src / 'citable_by_year.parquet'}')
        WHERE journal_id IN ({",".join(map(str, ids))})""").df()
    oa = {(int(r.t), int(r.j)): (int(r.out_eff), int(r.out_all)) for r in out.itertuples()}
    it = {(int(r.t), int(r.j)): int(r.n_all) for r in items.itertuples()}

    def cov(row):
        l = [i for i in row.citing_ids if i is not None]
        if not l or len(l) < len(row.citing_ids):
            return pd.Series({"citing_out_all": None, "citing_items": None, "refs_present": None})
        oall = sum(oa.get((int(row.t), i), (0, 0))[1] for i in l)
        n = sum(it.get((int(row.t), i), 0) for i in l)
        return pd.Series({"citing_out_all": oall, "citing_items": n, "refs_present": oall > 0})
    f = pd.concat([f, f.apply(cov, axis=1)], axis=1)
    f["has_value"] = f.ours.notna()
    summ = {}
    for (mt, rp), g in f[f.has_value & f.refs_present.notna()].groupby(["metric", "refs_present"]):
        summ[f"{mt} | refs_present={rp}"] = {"n": len(g), "pass": int(g["pass"].sum()),
                                             "median_abs_diff_pp": round(float(g.diff_pp.abs().median()), 2),
                                             "median_signed_diff_pp": round(float(g.diff_pp.median()), 2)}
    nov = f[f.refs_present.notna() & ~f.has_value]
    summ["rows_without_value"] = {"n": len(nov), "refs_present_false": int((nov.refs_present == False).sum())}  # noqa: E712
    summ["unmatched_rows"] = int(f.refs_present.isna().sum())
    run_dir.mkdir(parents=True)
    f.drop(columns=["citing_ids"]).to_csv(run_dir / "fidelity_with_coverage.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "src_run": args.src, "fidelity_run": args.fidelity, "match_run": args.match,
        "python": platform.python_version(), "duckdb": duckdb.__version__}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
