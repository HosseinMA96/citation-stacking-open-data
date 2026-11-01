"""C13 (R6): paper-level anatomy of excessive journal-pair citations (SPEC RQ3), on the VM.

Pairs (donor D -> recipient R, JCR year t; window citations = D's items of year t citing R's items of t-1, t-2):
  named    every Clarivate recipient <- donor pair in the labels with both journals matched and >= 1 window citation
  flagged  journal-years flagged by the recipient-centric variant in all 7 partitions (c12_consensus, k = 7), paired
           with their top excessive donor (partition `main`); a seeded sample of --n-flagged plus every listed recipient
  control for each named/flagged pair, --controls pairs from the same year with eff in [0.8, 1.25] x the pair's eff,
           both journals in rule `main`, recipient never flagged in any partition (seeded choice)
Per pair: citations, citing items, share of the pair's citations from the single top citing item (top1_share) and
from the top 10% of citing items (top10pct_share), Gini of citations per citing item, and the mean TF-IDF cosine
between citing and cited titles (titles from the Meta CSV dump; tokens = lowercase words of >= 3 letters, minus
a short stop list; idf over all involved titles). Group comparisons: medians and a two-sided Mann-Whitney U test
(target vs its own controls). Titles are used only for the cosine; no titles or author fields are written out.

Usage:  python c13_anatomy.py --self-test
        python c13_anatomy.py --src c6_full_20261031_02 --match c10_match_20261031_05 --labels suppressions_v2.csv \\
            --recip c12_recip_20261031_01 --consensus c12_consensus_20261031_01 --meta <meta_csv dir> --run-id c13_anatomy_<YYYYMMDD>_01
Output: runs/<run_id>/pairs.csv, summary.json, run.json, SHA256SUMS. Never overwrites.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
from collections import Counter
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import mannwhitneyu

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SEED = 4311
STOP = set("the and for with from that this are was were its their into using use based via under over between among "
           "study analysis new effect effects case report review role during after than also not".split())


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return float("nan")
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def concentration(counts):
    c = np.sort(np.asarray(counts, dtype=float))[::-1]
    k = max(1, math.ceil(0.1 * len(c)))
    return {"citations": int(c.sum()), "citing_items": len(c), "top1_share": float(c[0] / c.sum()),
            "top10pct_share": float(c[:k].sum() / c.sum()), "gini": gini(c), "cites_per_item": float(c.mean())}


def tokens(s):
    return [w for w in re.findall(r"[a-z]{3,}", str(s).lower()) if w not in STOP]


def tfidf(titles):
    """titles: dict key -> title. Returns key -> row index and an L2-normalized sparse matrix."""
    keys = list(titles)
    toks = [tokens(titles[k]) for k in keys]
    df = Counter(w for t in toks for w in set(t))
    vocab = {w: i for i, w in enumerate(sorted(df))}
    n = len(keys)
    rows, cols, vals = [], [], []
    for r, t in enumerate(toks):
        for w, c in Counter(t).items():
            rows.append(r); cols.append(vocab[w]); vals.append(c * math.log((1 + n) / (1 + df[w])) + 0.0)
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(n, len(vocab)))
    norm = np.sqrt(np.asarray(X.multiply(X).sum(axis=1)).ravel())
    norm[norm == 0] = 1
    return {k: i for i, k in enumerate(keys)}, sparse.diags(1 / norm) @ X


def self_test():
    c = concentration([10, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    idx, X = tfidf({"a": "Citation stacking in journal networks", "b": "Journal citation networks and stacking",
                    "c": "Protein folding kinetics"})
    cab = float(X[idx["a"]].multiply(X[idx["b"]]).sum())
    cac = float(X[idx["a"]].multiply(X[idx["c"]]).sum())
    checks = {"citations": c["citations"] == 20, "items": c["citing_items"] == 11, "top1": abs(c["top1_share"] - 0.5) < 1e-12,
              "top10pct": abs(c["top10pct_share"] - 11 / 20) < 1e-12, "gini_equal": abs(gini([2, 2, 2])) < 1e-12,
              "gini_pos": c["gini"] > 0.3, "cos_similar": cab > 0.9, "cos_unrelated": cac == 0.0}
    ok = all(checks.values())
    print(checks, "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    for a in ("--src", "--match", "--labels", "--recip", "--consensus", "--run-id"):
        ap.add_argument(a)
    ap.add_argument("--meta", type=Path)
    ap.add_argument("--n-flagged", type=int, default=200)
    ap.add_argument("--controls", type=int, default=3)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    t0 = time.time()
    work = Path(os.environ.get("C_WORK", ROOT / "data" / "work" / args.src))
    src = runs / args.src
    con = duckdb.connect()
    con.execute(f"SET threads = {int(os.environ.get('C_THREADS', 2))}; SET memory_limit = '{os.environ.get('C_MEM', '2GB')}'; "
                "SET preserve_insertion_order = false")
    if os.environ.get("C_TEMP_DIR"):
        con.execute(f"SET temp_directory = '{os.environ['C_TEMP_DIR']}'")

    # targets
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    sup = pd.read_csv(ROOT / "data" / args.labels)
    nm = sup[(sup.role == "recipient") & sup.partner_journal.notna()].copy()
    nm["R"], nm["D"] = nm.journal.map(jid), nm.partner_journal.map(jid)
    nm = nm[nm.R.notna() & nm.D.notna()]
    named = pd.DataFrame({"group": "named", "t": nm.jcr_data_year.astype(int), "D": nm.D.astype(int), "R": nm.R.astype(int)})
    cons = pd.read_csv(runs / args.consensus / "consensus_flags.csv")
    fl = pd.read_csv(runs / args.recip / "flags.csv")
    fl = fl[fl.tag == "main"][["t", "journal_id", "top_donor"]]
    k7 = cons[cons.partitions == 7].merge(fl, on=["t", "journal_id"])
    k7 = k7[k7.top_donor >= 0]
    listed = set(jid.values())
    k7["h"] = [hashlib.sha256(f"{SEED}-{a}-{b}".encode()).hexdigest() for a, b in zip(k7.t, k7.journal_id)]
    k7 = pd.concat([k7.sort_values("h").head(args.n_flagged), k7[k7.journal_id.isin(listed)]]).drop_duplicates(["t", "journal_id"])
    flagged = pd.DataFrame({"group": "flagged", "t": k7.t.astype(int), "D": k7.top_donor.astype(int), "R": k7.journal_id.astype(int)})
    tg = pd.concat([named, flagged]).drop_duplicates(["group", "t", "D", "R"]).reset_index(drop=True)
    con.register("tg_df", tg)
    con.execute(f"""CREATE TABLE tg AS SELECT tg_df.*, coalesce(p.eff, 0) AS eff FROM tg_df
                    LEFT JOIN read_parquet('{src / 'pairs_jcr_years.parquet'}') p ON p.t = tg_df.t AND p.citing_j = tg_df.D AND p.cited_j = tg_df.R""")
    # controls
    ever = set(cons.journal_id)
    con.register("ever_df", pd.DataFrame({"j": sorted(ever)}))
    con.execute(f"""CREATE TABLE rule AS SELECT journal_id FROM read_parquet('{src / 'journal_flags.parquet'}') WHERE type_journal AND issn""")
    con.execute(f"""CREATE TABLE cand AS SELECT t, citing_j AS D, cited_j AS R, eff FROM read_parquet('{src / 'pairs_jcr_years.parquet'}')
                    WHERE eff > 0 AND citing_j <> cited_j AND citing_j IN (SELECT journal_id FROM rule)
                      AND cited_j IN (SELECT journal_id FROM rule) AND cited_j NOT IN (SELECT j FROM ever_df)""")
    con.execute(f"""CREATE TABLE ctl AS SELECT * FROM (
        SELECT 'control_' || g.group AS "group", c.t, c.D, c.R, c.eff, g.t AS tt, g.D AS tD, g.R AS tR,
               row_number() OVER (PARTITION BY g.group, g.t, g.D, g.R ORDER BY hash(c.D::BIGINT * 1000003 + c.R + {SEED})) AS k
        FROM tg g JOIN cand c ON c.t = g.t AND c.eff BETWEEN 0.8 * g.eff AND 1.25 * g.eff
        WHERE g.eff > 0) WHERE k <= {args.controls}""")
    con.execute("""CREATE TABLE allp AS
        SELECT row_number() OVER () AS pair_id, * FROM (
            SELECT "group", t, D, R, eff, t AS tt, D AS tD, R AS tR FROM tg WHERE eff > 0
            UNION ALL SELECT "group", t, D, R, eff, tt, tD, tR FROM ctl)""")
    # citations of every pair
    pj, ed = f"read_parquet('{work / 'pubs_j.parquet'}')", f"read_parquet('{work / 'edges.parquet'}')"
    con.execute(f"""CREATE TABLE a AS SELECT p.iid, p.journal_id AS D, p.pub_year AS t FROM {pj} p
                    JOIN (SELECT DISTINCT D, t FROM allp) x ON p.journal_id = x.D AND p.pub_year = x.t""")
    con.execute(f"""CREATE TABLE b AS SELECT p.iid, p.journal_id AS R, p.pub_year AS y FROM {pj} p
                    WHERE p.journal_id IN (SELECT DISTINCT R FROM allp)""")
    con.execute(f"""CREATE TABLE cites AS
        SELECT ap.pair_id, e.citing_iid, e.cited_iid FROM {ed} e
        JOIN a ON e.citing_iid = a.iid JOIN b ON e.cited_iid = b.iid
        JOIN allp ap ON ap.D = a.D AND ap.t = a.t AND ap.R = b.R AND b.y IN (a.t - 1, a.t - 2)""")
    # titles from Meta for involved items
    con.execute(f"""CREATE TABLE want AS SELECT DISTINCT s.iid, s.omid FROM read_parquet('{work / 'pubs_slim.parquet'}') s
                    WHERE s.iid IN (SELECT citing_iid FROM cites UNION SELECT cited_iid FROM cites)""")
    files = ", ".join(f"'{f}'" for f in sorted(args.meta.rglob("*.csv")))
    con.execute(f"""CREATE TABLE ti AS SELECT w.iid, any_value(x.title) AS title FROM want w JOIN (
        SELECT NULLIF(regexp_extract(id, 'omid:(br/[0-9]+)', 1), '') AS omid, title
        FROM read_csv([{files}], header = true, all_varchar = true, quote = '"', escape = '"',
                      strict_mode = false, null_padding = true, ignore_errors = true)) x USING (omid) GROUP BY 1""")
    cites = con.execute("SELECT * FROM cites").df()
    titles = dict(con.execute("SELECT iid, title FROM ti WHERE title IS NOT NULL").fetchall())
    allp = con.execute("SELECT * FROM allp").df()
    idx, X = tfidf(titles)
    rows = []
    for pid, g in cites.groupby("pair_id"):
        r = concentration(g.citing_iid.value_counts().values)
        ok = [(idx[a], idx[b]) for a, b in zip(g.citing_iid, g.cited_iid) if a in idx and b in idx]
        if ok:
            ia, ib = map(np.array, zip(*ok))
            cos = np.asarray(X[ia].multiply(X[ib]).sum(axis=1)).ravel()
            r.update({"titled_citations": len(ok), "title_cosine_mean": float(cos.mean())})
        rows.append({"pair_id": pid, **r})
    res = allp.merge(pd.DataFrame(rows), on="pair_id", how="left")
    summ = {"pairs_by_group": res.group.value_counts().to_dict(), "seconds": round(time.time() - t0, 1), "comparisons": {}}
    for tgt in ("named", "flagged"):
        A, B = res[res.group == tgt], res[res.group == f"control_{tgt}"]
        for col in ("top1_share", "top10pct_share", "gini", "cites_per_item", "title_cosine_mean"):
            a, b = A[col].dropna(), B[col].dropna()
            if len(a) and len(b):
                summ["comparisons"][f"{tgt}|{col}"] = {"n_target": len(a), "n_control": len(b),
                                                       "median_target": round(float(a.median()), 4),
                                                       "median_control": round(float(b.median()), 4),
                                                       "mannwhitney_p": float(mannwhitneyu(a, b, alternative="two-sided").pvalue)}
    run_dir.mkdir(parents=True)
    res.to_csv(run_dir / "pairs.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "src_run": args.src,
        "match_run": args.match, "labels": args.labels, "recip_run": args.recip, "consensus_run": args.consensus,
        "n_flagged": args.n_flagged, "controls": args.controls, "seed": SEED, "titles_found": len(titles),
        "python": platform.python_version(), "duckdb": duckdb.__version__}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
