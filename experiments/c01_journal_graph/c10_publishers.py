"""R3: who publishes the journals whose references are missing from OpenCitations, and do they deposit references?

Journals: every citing journal in c10_covsplit with refs_present = False, plus the named donors with zero pair
citations. For each, the Crossref journal record (api.crossref.org/journals/<ISSN>) gives the publisher and
`coverage` fractions, e.g. references-current / references-backfile = share of the journal's current / backfile
DOIs that have reference lists deposited. A control set = the citing journals with refs_present = True.
Raw responses saved. Read-only.

Usage:  python c10_publishers.py --covsplit c10_covsplit_20261031_01 --match c10_match_20261031_05 --run-id c10_publishers_<YYYYMMDD>_01
Output: runs/<run_id>/publishers.csv, crossref_journals_raw.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def crossref_journal(issn):
    url = f"https://api.crossref.org/journals/{issn}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "c10_publishers (research script)"}),
                                    timeout=60) as r:
            return json.load(r)["message"]
    except Exception as e:   # noqa: BLE001 - record the failure, do not guess
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--covsplit", required=True)
    ap.add_argument("--match", required=True)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    f = pd.read_csv(runs / args.covsplit / "fidelity_with_coverage.csv")
    m = pd.read_csv(runs / args.match / "matches.csv").set_index("name")
    rows = []
    for (names, t), g in f[f.refs_present.notna()].groupby(["citing_names", "t"]):
        for n in str(names).split(";"):
            n = n.strip()
            pair_zero = bool(((g.metric != "self_cites_pct_jif_numerator") & (g.pair_eff == 0)).any())
            rows.append({"journal": n, "t": int(t), "refs_present": bool(g.refs_present.iloc[0]),
                         "named_donor_zero_pair": pair_zero,
                         "issns": m.loc[n, "issns"] if n in m.index else None})
    df = pd.DataFrame(rows).drop_duplicates(["journal", "t"])
    raw, out = {}, []
    for n, g in df.groupby("journal"):
        issns = str(g.issns.iloc[0]).split() if isinstance(g.issns.iloc[0], str) else []
        rec = {}
        for i in issns:
            rec = crossref_journal(i)
            time.sleep(1)
            if "error" not in rec:
                break
        raw[n] = rec
        cov = rec.get("coverage", {}) if isinstance(rec, dict) else {}
        out.append({"journal": n, "years": " ".join(map(str, sorted(g.t))), "refs_present_any_year": bool(g.refs_present.any()),
                    "named_donor_zero_pair": bool(g.named_donor_zero_pair.any()), "issns": " ".join(issns),
                    "publisher": rec.get("publisher"), "references_current": cov.get("references-current"),
                    "references_backfile": cov.get("references-backfile"),
                    "total_dois": (rec.get("counts") or {}).get("total-dois"), "crossref_error": rec.get("error")})
    out = pd.DataFrame(out).sort_values(["refs_present_any_year", "journal"])
    run_dir.mkdir(parents=True)
    out.to_csv(run_dir / "publishers.csv", index=False)
    (run_dir / "crossref_journals_raw.json").write_text(json.dumps(raw, indent=1))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "covsplit_run": args.covsplit,
        "match_run": args.match, "queried": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    pd.set_option("display.width", 250)
    print(out.drop(columns=["issns", "years"]).to_string())


if __name__ == "__main__":
    main()
