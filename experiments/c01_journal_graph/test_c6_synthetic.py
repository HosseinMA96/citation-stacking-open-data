"""Correctness test for c6_full_run.py on a hand-built dataset with known answers.

Usage:
    ../../.venv/bin/python test_c6_synthetic.py

Writes gzip inputs to a temporary folder, runs c6_full_run.py as a subprocess with small limits,
checks every count by hand, then deletes its run folder (it is a test, not a result).
"""
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RUN_ID = "test_c6_synthetic"

HEADER = "omid,iid,title,authors,issue,volume,venue,pages,pub_year,pub_month,pub_date,type,publisher,editors"
# iid, venue, year, type. Journal X has two OMID records sharing ISSN 1111-1111 (must merge);
# journal Y has one record; iid 9 has no venue; iid 10 has no year.
PUBS = [
    (1, "Journal X [omid:br/100 issn:1111-1111]", 2020, "journal article"),
    (2, "Journal X [omid:br/101 issn:1111-1111 issn:2222-2222]", 2018, "journal article"),
    (3, "Journal X [omid:br/100 issn:1111-1111]", 2019, "editorial"),
    (4, "Journal Y [omid:br/200 issn:3333-3333]", 2018, "journal article"),
    (5, "Journal Y [omid:br/200 issn:3333-3333]", 2015, "journal article"),
    (6, "https://w3id.org/oc/meta/br/555", 2020, "journal article"),     # issue-level link: journal only via Meta
    (7, 'Journal "Z", Part 1 [omid:br/300]', 2019, "journal article"),   # quoted comma field, no ISSN
    (9, "", 2020, "book chapter"),
    (10, "Journal Y [omid:br/200 issn:3333-3333]", "", "journal article"),
]
# OpenCitations Meta rows (id, venue), split over two files in a subfolder. Meta gives iid 6 its
# journal; for iid 1 Meta says br/101 while the pubs bracket says br/100 (one disagreement, same
# journal X after the ISSN merge); iid 4 appears twice; br/94 matches no pubs row's venue issue.
META = [[("omid:br/91 doi:10.1/a", "Journal X [omid:br/101 issn:1111-1111 issn:2222-2222]"),
         ("omid:br/92", "Journal X [omid:br/101 issn:1111-1111 issn:2222-2222]"),
         ("omid:br/96 doi:10.1/f", "Journal Y [omid:br/200 issn:3333-3333]")],
        [("omid:br/94", "Journal Y [omid:br/200 issn:3333-3333]"),
         ("omid:br/94", "Journal Y [omid:br/200 issn:3333-3333]"),
         ("omid:br/8888", "Journal W [omid:br/700]")]]
META_HEADER = "id,title,author,pub_date,venue,volume,issue,page,type,publisher,editor"
# (citing, cited). Expected in year t = 2020 (journals: X = {br/100, br/101}, Y, Z):
#   X(1) -> Y(4, 2018): eff;   X(1) -> Y(5, 2015): prev only;   X(1) -> X(3, 2019 editorial): eff, self
#   Y(6) -> X(2, 2018): eff;   Y(6) -> Z(7, 2019): eff;          none(9) -> Y(4, 2018): eff, citing_j null
#   Y(6) -> 10 (no year): dropped;   1 -> 999 (unknown iid): dropped;   Y(4, 2018) -> X(1, 2020): forward, dropped
# Venue records (own rows of type 'journal', no venue, no year) for X (br/100) and Y (br/200); Z has
# none and no ISSN. Journal rule 'main' (type_journal & issn) must keep X and Y and drop Z.
VENUE_RECORDS = [(20, "omid:br/100"), (21, "omid:br/200")]
EDGES = [(1, 4), (1, 5), (1, 3), (6, 2), (6, 7), (9, 4), (6, 10), (1, 999), (4, 1)]


def csv_field(x):
    s = str(x)
    return '"' + s.replace('"', '""') + '"' if any(c in s for c in ',"') else s


def write_inputs(d):
    with gzip.open(d / "pubs.csv.gz", "wt") as f:
        f.write(HEADER + "\n")
        for iid, venue, year, typ in PUBS:
            row = [f"omid:br/9{iid}", iid, "Title, with comma", "Doe, J [omid:ra/1]", "", "", venue,
                   "", year, "", "", typ, "Pub", ""]
            f.write(",".join(csv_field(x) for x in row) + "\n")
        for iid, omid in VENUE_RECORDS:
            row = [omid, iid, "Venue", "", "", "", "", "", "", "", "", "journal", "Pub", ""]
            f.write(",".join(csv_field(x) for x in row) + "\n")
    for k, rows in enumerate(META):
        (d / "meta" / "csv").mkdir(parents=True, exist_ok=True)
        with open(d / "meta" / "csv" / f"part_{k}.csv", "w") as f:
            f.write(META_HEADER + "\n")
            for i, v in rows:
                f.write(",".join(csv_field(x) for x in [i, "T", "A", "2020", v, "", "", "", "journal article", "P", ""]) + "\n")
    with gzip.open(d / "edges.csv.gz", "wt") as f:
        f.write("citing_iid,cited_iid\n")
        for a, b in EDGES:
            f.write(f"{a},{b}\n")


def run(d, *extra):
    env = dict(os.environ, C_THREADS="1", C_MEM="500MB", C_MAX_TEMP="200MB", C_WORK=str(d / "work"))
    return subprocess.run([sys.executable, str(HERE / "c6_full_run.py"), "--run-id", RUN_ID,
                           "--edges", str(d / "edges.csv.gz"), "--pubs", str(d / "pubs.csv.gz"), "--meta", str(d / "meta"), *extra],
                          env=env, capture_output=True, text=True)


def main():
    run_dir = HERE / "runs" / RUN_ID
    if run_dir.exists():
        shutil.rmtree(run_dir)
    d = Path(tempfile.mkdtemp())
    fails = []

    def check(name, got, want):
        ok = got == want
        print(f"{'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
        if not ok:
            fails.append(name)

    try:
        write_inputs(d)
        p = run(d, "--stop-after", "journals")
        check("partial run exit code", p.returncode, 0)
        check("refuses existing run without --resume", run(d).returncode != 0, True)
        p = run(d, "--resume")
        check("resume exit code", p.returncode, 0)
        check("resume skipped completed stages", "stage pubs: already complete" in p.stdout, True)
        if p.returncode:
            print(p.stdout[-2000:], p.stderr[-2000:])
            raise SystemExit(1)

        import json
        m = json.loads((run_dir / "stage_meta.json").read_text())
        check("meta rows read from two files", m["rows"], 6)
        check("meta distinct article OMIDs", m["distinct_omid"], 5)
        vs = json.loads((run_dir / "stage_pubs.json").read_text())["venue_source"]
        check("journal articles with venue from Meta", vs["journal_articles"].get("meta"), 4)
        check("journal articles with venue from pubs bracket (iids 5, 7, 10)", vs["journal_articles"].get("pubs_bracket"), 3)
        check("Meta vs pubs bracket disagreements", vs["rows_meta_vs_bracket_disagree"], 1)
        check("meta file checksums recorded", (run_dir / "meta_files.sha256").read_text().count("\n"), 2)

        j = pd.read_parquet(run_dir / "journals.parquet")
        check("journals after ISSN merge", len(j), 3)
        x = j[j["omids"].map(lambda o: "br/100" in list(o))].iloc[0]
        check("X merged OMIDs", sorted(x["omids"]), ["br/100", "br/101"])
        check("X ISSNs", list(x["issns"]), ["1111-1111", "2222-2222"])
        jid = {o: int(r.journal_id) for r in j.itertuples() for o in r.omids}
        X, Y, Z = jid["br/100"], jid["br/200"], jid["br/300"]

        pairs = pd.read_parquet(d / "work" / "pairs_all_years.parquet")
        sub = pd.read_parquet(run_dir / "pairs_jcr_years.parquet")
        check("analysis-year subset only has config years", sorted(sub.t.unique().tolist()), [2020])
        t20 = pairs[pairs.t == 2020]
        def cell(a, b, col):
            m = t20[(t20.citing_j.isna() if a is None else t20.citing_j == a) & (t20.cited_j == b)]
            return int(m[col].sum())
        check("X->Y eff 2020", cell(X, Y, "eff"), 1)
        check("X->Y prev 2020", cell(X, Y, "prev"), 2)
        check("X->X self eff (editorial cited counts)", cell(X, X, "eff"), 1)
        check("Y->X eff", cell(Y, X, "eff"), 1)
        check("Y->Z eff", cell(Y, Z, "eff"), 1)
        check("no-journal citing -> Y eff", cell(None, Y, "eff"), 1)
        check("total eff all years", int(pairs.eff.sum()), 5)
        check("no forward citation (t=2018 row)", int(pairs[pairs.t == 2018].eff.sum()), 0)

        cit = pd.read_parquet(run_dir / "citable_by_year.parquet")
        xr = cit[(cit.journal_id == X) & (cit.pub_year == 2019)]
        check("X 2019 citable (editorial excluded)", int(xr.n_citable.sum()), 0)
        check("X 2019 all items", int(xr.n_all.sum()), 1)

        agg = pd.read_parquet(run_dir / "agg_eff_network.parquet")
        check("agg excludes null citing", bool(agg.citing_j.isna().any()), False)
        check("agg total weight", int(agg.w.sum()), 4)

        cov = pd.read_csv(run_dir / "coverage.csv")
        check("coverage total edges", int(cov.n.sum()), len(EDGES))
        check("SHA256SUMS written", (run_dir / "SHA256SUMS").exists(), True)

        # Journal flags and rules (c6_journal_set.py, then c6_blocks.py --dry-run --journal-rule).
        env = dict(os.environ, C_THREADS="1", C_MEM="500MB", C_WORK=str(d / "work"))
        p = subprocess.run([sys.executable, str(HERE / "c6_journal_set.py"), "--run-id", RUN_ID],
                           env=env, capture_output=True, text=True)
        check("journal flags exit code", p.returncode, 0)
        fl = pd.read_parquet(run_dir / "journal_flags.parquet").set_index("journal_id")
        check("X flags (record, ISSN, 2 of 3 items JA)", (bool(fl.loc[X, "type_journal"]), bool(fl.loc[X, "issn"]),
              int(fl.loc[X, "n_items"]), int(fl.loc[X, "n_ja"])), (True, True, 3, 2))
        check("Y flags (item 6 via Meta)", (bool(fl.loc[Y, "type_journal"]), int(fl.loc[Y, "n_items"])), (True, 4))
        check("Z flags (no record, no ISSN)", (bool(fl.loc[Z, "type_journal"]), bool(fl.loc[Z, "issn"])), (False, False))
        for rule in ("main", "type_issn_ja50"):
            p = subprocess.run([sys.executable, str(HERE / "c6_blocks.py"), "--run-id", RUN_ID, "--dry-run",
                                "--journal-rule", rule], capture_output=True, text=True)
            info = json.loads(p.stdout) if p.returncode == 0 else {}
            if p.returncode:
                print(p.stderr[-1500:])
            check(f"rule {rule}: journals, edges, weight (X->Y, X->X, Y->X; Y->Z dropped)",
                  (info.get("journals_in_rule"), info.get("journals"), info.get("edges"), info.get("weight")), (2, 2, 3, 3))
    finally:
        shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(run_dir, ignore_errors=True)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
