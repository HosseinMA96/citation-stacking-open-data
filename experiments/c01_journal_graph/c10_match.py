"""C10 step 1: match the journals in data/suppressions.csv (and named partners) to journal_id by ISSN.

Pre-registered rule (RESULTS_LOG 2026-10-31, C10 pre-registration, decision c): ISSNs come from Crossref
journal records (api.crossref.org/journals?query=<name>); a record is accepted only if its normalized
title equals the normalized journal name (case, accents, punctuation, '&'/'and', a leading 'The' ignored), or
equals a manual alias listed in ALIASES with its reason. Accepted ISSNs are looked up in the c6 run's
journals.parquet (ISSN-merged venue groups). Unmatched names are reported, never guessed. Raw Crossref
responses are saved in the run for audit.

Usage:  python c10_match.py --src c6_full_20261031_02 --run-id c10_match_<YYYYMMDD>_01
Output: runs/<run_id>/matches.csv, crossref_raw.json, run.json, SHA256SUMS. Never overwrites.
"""
import argparse
import hashlib
import json
import platform
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ALIASES = {   # suppressions.csv name -> Crossref title, only where the CSV uses a variant (reason in comment)
    "Genetika (Belgrade)": "Genetika",   # CSV adds the city to disambiguate; Crossref title is plain
    # Crossref record carries a subtitle; ISSN 1064-1246 (TODO(verify) against the JCR record)
    "Journal of Intelligent & Fuzzy Systems": "Journal of Intelligent & Fuzzy Systems Applications in Engineering and Technology",
    "Ukrainian Journal for Physical Optics": "Ukrainian Journal of Physical Optics",   # CSV wording variant ("for"/"of")
    "Archivos Latinoamericanos de Nutricion": "Archivos Latinoamericanos de Nutrición",   # Crossref search needs the accent
    # added 2026-10-31 for suppressions_v2.csv (Clarivate's own titles)
    "Genetika-Belgrade": "Genetika",
    "Business Ethics": "Business Ethics A European Review",          # its title in the 2019 data year (renamed 2021)
    "Clinical And Experimental Allergy": "Clinical & Experimental Allergy",
    "Hispania-A Journal Devoted to the Teaching of Spanish and Portuguese": "Hispania",
    "Journal of Manufacturing Science and Engineering-Transactions of the ASME": "Journal of Manufacturing Science and Engineering",
    "Journal of Politeness Research-Language Behaviour Culture": "Journal of Politeness Research",
    "Ukrainian Journal of Physical Optics": "Ukrainian Journal of Physical Optics",
    # JCR uses the short title; Crossref has the full one (TODO(verify) ISSN against the JCR record)
    "SOCAR Proceedings": '"Proceedings" of "OilGasScientificResearchProjects" Institute SOCAR',
}
PIN = {   # name -> the one ISSN to use, where the title matches several journals or our data splits one journal
    "Genetika (Belgrade)": "0534-0012", "Genetika-Belgrade": "0534-0012",   # Serbian Genetika; 2828-3139 is an Indonesian namesake
    "Hispania-A Journal Devoted to the Teaching of Spanish and Portuguese": "0018-2133",   # AATSP journal (Project MUSE); 0018-2141 is CSIC's Hispania
    "ONCOLOGY": "0030-2414",                                  # Karger, Basel (JCR "ONCOLOGY-BASEL"); other Crossref "Oncology" titles differ
    "American Journal Of Respiratory And Critical Care Medicine": "1073-449X",   # 0003-0805 is its predecessor title, a separate venue group
    "Archives of Metallurgy and Materials": "2300-1909",       # data splits print 1733-3490 (587 items) / online 2300-1909 (1,311); larger kept
    "International Journal of Civil Engineering": "1735-0522",  # 2348-8352 is a different journal with the same title (TODO(verify))
    "Journal of Low Frequency Noise Vibration and Active Control": "1461-3484",   # 0263-0923 group has 2 items
}


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"^the ", "", re.sub(r"\s+", " ", s).strip())
    return s


def crossref(name):
    q = re.sub(r"[&\"]", " ", name)   # Crossref returns nothing for a query containing '&'
    url = "https://api.crossref.org/journals?" + urllib.parse.urlencode({"query": q, "rows": 20})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "c10_match (research script)"}),
                                timeout=60) as r:
        return json.load(r)["message"]["items"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--labels", default="suppressions.csv", help="file in data/ (v2 since 2026-10-31)")
    args = ap.parse_args()
    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    partners = [x.strip() for p in sup.partner_journal.dropna() for x in str(p).split(";")]
    names = sorted(set(sup.journal.dropna()) | {p for p in partners if p and p[0].isupper() and "unnamed" not in p})
    run_dir.mkdir(parents=True)
    raw, rows = {}, []
    con = duckdb.connect()
    con.execute(f"""CREATE TABLE ji AS SELECT journal_id, unnest(issns) AS issn, n_pubs
                    FROM read_parquet('{HERE / 'runs' / args.src / 'journals.parquet'}')""")
    for n in names:
        target = norm(ALIASES.get(n, n))
        items = crossref(n)                 # query both the CSV name and the alias; Crossref search is brittle
        time.sleep(1)
        if n in ALIASES:
            seen = {i.get("URL") for i in items}
            items += [i for i in crossref(ALIASES[n]) if i.get("URL") not in seen]
            time.sleep(1)
        raw[n] = items
        hits = [i for i in items if norm(i.get("title", "")) == target]
        issns = sorted({x for i in hits for x in i.get("ISSN", [])})
        if n in PIN and PIN[n] in issns:
            issns = [PIN[n]]
        ids = con.execute("SELECT journal_id, n_pubs, list(issn ORDER BY issn) FROM ji WHERE issn IN "
                          f"(SELECT unnest(?::VARCHAR[])) GROUP BY ALL ORDER BY n_pubs DESC", [issns]).fetchall() if issns else []
        rows.append({"name": n, "alias_used": ALIASES.get(n, ""), "issn_pinned": PIN.get(n, ""), "crossref_records": len(hits),
                     "crossref_titles": " | ".join(sorted({i["title"] for i in hits})),
                     "crossref_publishers": " | ".join(sorted({i.get("publisher", "") for i in hits})),
                     "issns": " ".join(issns), "journal_ids": " ".join(str(r[0]) for r in ids),
                     "n_pubs": " ".join(str(r[1]) for r in ids),
                     "status": "matched" if len(ids) == 1 else ("ambiguous" if ids else
                               ("issn_not_in_data" if issns else "no_crossref_title_match"))})
    m = pd.DataFrame(rows)
    m.to_csv(run_dir / "matches.csv", index=False)
    (run_dir / "crossref_raw.json").write_text(json.dumps(raw, indent=1))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "src_run": args.src,
        "labels": args.labels, "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "queried": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "python": platform.python_version(),
        "duckdb": duckdb.__version__, "status_counts": m.status.value_counts().to_dict()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                f.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(m[["name", "status", "issns", "journal_ids", "n_pubs"]].to_string())


if __name__ == "__main__":
    main()
