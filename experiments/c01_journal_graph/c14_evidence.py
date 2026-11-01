"""C14: structured evidence check of the recipient-centric flags (protocol: RESULTS_LOG "C14 protocol", fixed
before the sample was drawn). Laptop; uses the C13 anatomy pairs and Crossref.

Sample: C13 `flagged` pairs (recipient + its top excessive donor); controls: the first matched control of each
(C13 `control_flagged`, same year, similar window citations, recipient never flagged).
Indicators per pair:
  I1 recipient or donor is in the Clarivate suppression lists 2015-2023 (labels file, any role or year)
  I2 recipient and donor have the same Crossref publisher (exact string after lower-casing)
  I3 top10pct_share >= 0.5 (C13)
Reported: share with each indicator and with any, flagged vs control, Fisher exact tests.

Usage:  python c14_evidence.py --anatomy c13_anatomy_20261031_01 --src c6_full_20261031_02 --match c10_match_20261031_05 \\
            --labels suppressions_v2.csv --run-id c14_evidence_<YYYYMMDD>_01
Output: runs/<run_id>/pairs.csv, crossref_publishers.json, summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def publisher(issns, cache):
    for i in issns:
        if i in cache:
            return cache[i]
        try:
            with urllib.request.urlopen(urllib.request.Request(f"https://api.crossref.org/journals/{i}",
                                        headers={"User-Agent": "c14_evidence (research script)"}), timeout=60) as r:
                cache[i] = json.load(r)["message"].get("publisher")
        except Exception:   # noqa: BLE001 - not found or network error: try the next ISSN
            cache[i] = None
        time.sleep(0.5)
        if cache[i]:
            return cache[i]
    return None


def main():
    ap = argparse.ArgumentParser()
    for a in ("--anatomy", "--src", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    p = pd.read_csv(runs / args.anatomy / "pairs.csv")
    flagged = p[p.group == "flagged"].copy()
    ctl = p[p.group == "control_flagged"].sort_values("pair_id").groupby(["tt", "tD", "tR"]).head(1).copy()
    df = pd.concat([flagged, ctl])
    m = pd.read_csv(runs / args.match / "matches.csv")
    sup =pd.read_csv(ROOT / "data" / args.labels)
    names = set(sup.journal) | {x.strip() for v in sup.partner_journal.dropna() for x in str(v).split(";")}
    listed = {int(r.journal_ids) for r in m.itertuples() if r.status == "matched" and r.name in names}
    ids = sorted(set(df.D) | set(df.R))
    iss = duckdb.sql(f"""SELECT journal_id, issns FROM read_parquet('{runs / args.src / 'journals.parquet'}')
                         WHERE journal_id IN ({",".join(map(str, ids))})""").df()
    iss = dict(zip(iss.journal_id, iss.issns))
    cache = {}
    pub = {j: publisher(list(iss.get(j, [])), cache) for j in ids}
    df["publisher_D"], df["publisher_R"] = df.D.map(pub), df.R.map(pub)
    df["I1_listed"] = df.D.isin(listed) | df.R.isin(listed)
    df["I2_same_publisher"] = (df.publisher_D.notna() & df.publisher_R.notna()
                               & (df.publisher_D.str.lower() == df.publisher_R.str.lower()))
    df["I3_concentrated"] = df.top10pct_share >= 0.5
    df["any"] = df[["I1_listed", "I2_same_publisher", "I3_concentrated"]].any(axis=1)
    summ = {"n_flagged": int((df.group == "flagged").sum()), "n_control": int((df.group == "control_flagged").sum()),
            "publisher_found_share": round(float(df[["publisher_D", "publisher_R"]].notna().all(axis=1).mean()), 4)}
    for col in ("I1_listed", "I2_same_publisher", "I3_concentrated", "any"):
        a, b = df[df.group == "flagged"][col], df[df.group == "control_flagged"][col]
        odds, pv = fisher_exact([[int(a.sum()), int((~a).sum())], [int(b.sum()), int((~b).sum())]])
        summ[col] = {"flagged": f"{int(a.sum())}/{len(a)}", "control": f"{int(b.sum())}/{len(b)}",
                     "flagged_share": round(float(a.mean()), 4), "control_share": round(float(b.mean()), 4),
                     "odds_ratio": odds, "fisher_p": pv}
    run_dir.mkdir(parents=True)
    df.to_csv(run_dir / "pairs.csv", index=False)
    (run_dir / "crossref_publishers.json").write_text(json.dumps(cache, indent=1))
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "anatomy_run": args.anatomy,
        "src_run": args.src, "match_run": args.match, "labels": args.labels,
        "queried": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for q in sorted(run_dir.iterdir()):
            if q.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}\n")
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
