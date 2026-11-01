"""C5b laptop prototype: journal->journal citation counts (JCR window) on prefix samples.

Usage:
    ../../.venv/bin/python c5b_prototype.py --run-id <id> --edges <gz> --pubs <gz>

Inputs are partial browser downloads (.crdownload) of the Data Bank files, i.e. file
prefixes. The script snapshots them, decompresses up to the truncation point, drops the
trailing partial line, and runs the full pipeline in DuckDB. Never overwrites a run.
"""
import argparse
import gzip
import hashlib
import json
import platform
import resource
import shutil
import sys
import time
import zlib
from pathlib import Path

import duckdb
import yaml

HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "data" / "samples"


def sha256(path, chunk=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def decompress_prefix(src, dst, log):
    """Stream-decompress a truncated gzip; keep only complete lines."""
    t0 = time.time()
    lines = 0
    tail = b""
    truncated = False
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        while chunk := fin.read(1 << 22):
            try:
                out = d.decompress(chunk)
            except zlib.error as e:  # corrupt tail of a partial download
                log(f"  zlib error at end of {src.name}: {e}")
                truncated = True
                break
            buf = tail + out
            cut = buf.rfind(b"\n") + 1
            fout.write(buf[:cut])
            lines += buf[:cut].count(b"\n")
            tail = buf[cut:]
        if not d.eof:
            truncated = True
    return {
        "compressed_bytes_read": src.stat().st_size,
        "decompressed_bytes_kept": dst.stat().st_size,
        "lines_kept_incl_header": lines,
        "dropped_partial_line_bytes": len(tail),
        "gzip_truncated": truncated,
        "seconds": round(time.time() - t0, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--edges", required=True, type=Path)
    ap.add_argument("--pubs", required=True, type=Path)
    ap.add_argument("--config", default=HERE / "config.yaml", type=Path)
    ap.add_argument("--memory-limit", default="4GB")
    args = ap.parse_args()

    run_dir = HERE / "runs" / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run, pick a new --run-id")
    run_dir.mkdir(parents=True)
    logf = open(run_dir / "log.txt", "w")

    def log(msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    cfg_bytes = args.config.read_bytes()
    cfg = yaml.safe_load(cfg_bytes)
    t_start = time.time()
    rec = {
        "run_id": args.run_id,
        "script": "c5b_prototype.py",
        "config": str(args.config.name),
        "config_sha256": hashlib.sha256(cfg_bytes).hexdigest(),
        "python": platform.python_version(),
        "duckdb": duckdb.__version__,
        "duckdb_memory_limit": args.memory_limit,
        "inputs": {},
        "counts": {},
        "timings_s": {},
    }

    # 1. Snapshot the partial downloads (the browser could resume and append).
    DATA.mkdir(parents=True, exist_ok=True)
    plain = {}
    for name, src in (("edges", args.edges), ("pubs", args.pubs)):
        snap = DATA / src.name.replace(".crdownload", ".prefix")
        if not snap.exists():
            shutil.copyfile(src, snap)
        csv = DATA / (snap.name.replace(".csv.gz.prefix", "") + ".prefix.csv")
        log(f"{name}: snapshot {snap.name} ({snap.stat().st_size:,} bytes)")
        info = {"source": src.name, "snapshot": snap.name, "snapshot_sha256": sha256(snap),
                "compressed_bytes_read": snap.stat().st_size}
        if not csv.exists():
            info.update(decompress_prefix(snap, csv, log))
        else:
            info["note"] = "decompressed CSV reused from an earlier run"
        info["csv"] = csv.name
        info["csv_sha256"] = sha256(csv)
        rec["inputs"][name] = info
        plain[name] = csv
        log(f"{name}: {json.dumps(info)}")

    con = duckdb.connect()
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute("SET preserve_insertion_order=false")

    def timed(key, sql):
        t0 = time.time()
        con.execute(sql)
        rec["timings_s"][key] = round(time.time() - t0, 2)
        log(f"{key}: {rec['timings_s'][key]} s")

    def scalar(sql):
        return con.execute(sql).fetchone()[0]

    # 2. Load edges.
    timed("load_edges", f"""
        CREATE TABLE edges AS
        SELECT * FROM read_csv('{plain['edges']}', header=true,
            columns={{'citing_iid':'BIGINT','cited_iid':'BIGINT'}})""")
    c = rec["counts"]
    c["edges_rows"] = scalar("SELECT count(*) FROM edges")
    c["edges_distinct"] = scalar("SELECT count(*) FROM (SELECT DISTINCT citing_iid, cited_iid FROM edges)")
    c["edges_self_loops"] = scalar("SELECT count(*) FROM edges WHERE citing_iid = cited_iid")
    c["edges_iid_min_max"] = con.execute(
        "SELECT min(least(citing_iid,cited_iid)), max(greatest(citing_iid,cited_iid)) FROM edges").fetchone()

    # 3. Load pubs; parse the journal OMID and ISSNs from `venue`.
    timed("load_pubs", f"""
        CREATE TABLE pubs AS
        SELECT iid,
               pub_year,
               type,
               regexp_extract(venue, '\\[omid:(br/[0-9]+)', 1)            AS venue_omid,
               regexp_extract_all(venue, 'issn:([0-9]{{4}}-[0-9]{{3}}[0-9X])', 1) AS issns,
               venue
        FROM read_csv('{plain['pubs']}', header=true, all_varchar=true, quote='"', escape='"',
                      strict_mode=false, null_padding=true)
        """)
    con.execute("""
        CREATE OR REPLACE TABLE pubs AS
        SELECT TRY_CAST(iid AS BIGINT) AS iid,
               TRY_CAST(pub_year AS INTEGER) AS pub_year,
               type,
               NULLIF(venue_omid, '') AS venue_omid,
               issns,
               venue
        FROM pubs""")
    c["pubs_rows"] = scalar("SELECT count(*) FROM pubs")
    c["pubs_bad_iid"] = scalar("SELECT count(*) FROM pubs WHERE iid IS NULL")
    c["pubs_distinct_iid"] = scalar("SELECT count(DISTINCT iid) FROM pubs")
    c["pubs_iid_min_max"] = con.execute("SELECT min(iid), max(iid) FROM pubs").fetchone()
    c["pubs_with_venue_text"] = scalar("SELECT count(*) FROM pubs WHERE venue IS NOT NULL AND venue <> ''")
    c["pubs_with_venue_omid"] = scalar("SELECT count(*) FROM pubs WHERE venue_omid IS NOT NULL")
    c["pubs_with_issn"] = scalar("SELECT count(*) FROM pubs WHERE len(issns) > 0")
    c["pubs_with_year"] = scalar("SELECT count(*) FROM pubs WHERE pub_year IS NOT NULL")
    c["pubs_type_counts"] = dict(con.execute(
        "SELECT coalesce(type,'<null>'), count(*) FROM pubs GROUP BY 1 ORDER BY 2 DESC LIMIT 25").fetchall())
    c["venues_distinct_omid"] = scalar("SELECT count(DISTINCT venue_omid) FROM pubs")
    c["venues_omid_with_multiple_issn_sets"] = scalar("""
        SELECT count(*) FROM (SELECT venue_omid FROM pubs WHERE venue_omid IS NOT NULL
                              GROUP BY 1 HAVING count(DISTINCT issns) > 1)""")
    # Venue text present but no OMID parsed: show examples to check the regex.
    rec["venue_unparsed_examples"] = [r[0] for r in con.execute("""
        SELECT venue FROM pubs WHERE venue <> '' AND venue_omid IS NULL LIMIT 5""").fetchall()]

    # Clarivate-style counting: types are filtered per side ("all" = no filter).
    def type_filter(types):
        if types == "all":
            return "TRUE"
        return "type IN (" + ", ".join(f"'{t}'" for t in types) + ")"

    cnt = cfg["counting"]
    con.execute(f"""
        CREATE TABLE citing_pubs AS
        SELECT iid, pub_year, venue_omid FROM pubs
        WHERE pub_year IS NOT NULL AND {type_filter(cnt['citing_types'])}""")
    con.execute(f"""
        CREATE TABLE cited_pubs AS
        SELECT iid, pub_year, venue_omid FROM pubs
        WHERE pub_year IS NOT NULL AND venue_omid IS NOT NULL AND {type_filter(cnt['cited_types'])}""")
    c["citing_pubs_rows"] = scalar("SELECT count(*) FROM citing_pubs")
    c["citing_pubs_without_journal"] = scalar("SELECT count(*) FROM citing_pubs WHERE venue_omid IS NULL")
    c["cited_pubs_rows"] = scalar("SELECT count(*) FROM cited_pubs")

    # 4. Join edges to citing and cited journal + year (citing_j may be null).
    timed("join", """
        CREATE TABLE jedges AS
        SELECT a.venue_omid AS citing_j, a.pub_year AS citing_year,
               b.venue_omid AS cited_j,  b.pub_year AS cited_year
        FROM edges e
        JOIN citing_pubs a ON e.citing_iid = a.iid
        JOIN cited_pubs  b ON e.cited_iid  = b.iid""")
    c["edges_citing_in_pubs_sample"] = scalar("SELECT count(*) FROM edges e SEMI JOIN pubs p ON e.citing_iid = p.iid")
    c["edges_cited_in_pubs_sample"] = scalar("SELECT count(*) FROM edges e SEMI JOIN pubs p ON e.cited_iid = p.iid")
    c["edges_joined"] = scalar("SELECT count(*) FROM jedges")
    c["edges_joined_citing_without_journal"] = scalar("SELECT count(*) FROM jedges WHERE citing_j IS NULL")

    # 5. Aggregate c(A->B, t) for the JCR window (cited items from t-1 and t-2).
    years = cfg["jcr_window"]["citing_years"]
    offs = cfg["jcr_window"]["cited_offsets"]
    timed("aggregate", f"""
        CREATE TABLE jcr AS
        SELECT citing_year AS t, citing_j, cited_j, count(*) AS c
        FROM jedges
        WHERE citing_year IN ({', '.join(map(str, years))})
          AND citing_year - cited_year IN ({', '.join(map(str, offs))})
        GROUP BY ALL""")
    c["jcr_pairs"] = scalar("SELECT count(*) FROM jcr")
    c["jcr_citations"] = scalar("SELECT coalesce(sum(c),0) FROM jcr")
    c["jcr_self_citations"] = scalar("SELECT coalesce(sum(c),0) FROM jcr WHERE citing_j = cited_j")
    c["jcr_by_year"] = {str(r[0]): {"pairs": r[1], "citations": int(r[2])} for r in con.execute(
        "SELECT t, count(*), sum(c) FROM jcr GROUP BY t ORDER BY t").fetchall()}

    out = run_dir / "jcr_pairs.parquet"
    con.execute(f"COPY (SELECT * FROM jcr ORDER BY t, citing_j, cited_j) TO '{out}' (FORMAT parquet)")
    # JIF denominator proxy: citable items of journal B published in t-1 and t-2.
    timed("denominator", f"""
        CREATE TABLE citable AS
        SELECT y.t, p.venue_omid AS cited_j, count(*) AS n_citable
        FROM pubs p
        JOIN (SELECT unnest([{', '.join(map(str, years))}]) AS t) y
          ON y.t - p.pub_year IN ({', '.join(map(str, offs))})
        WHERE p.venue_omid IS NOT NULL AND {type_filter(cnt['citable_types'])}
        GROUP BY ALL""")
    c["citable_rows"] = scalar("SELECT count(*) FROM citable")
    con.execute(f"COPY (SELECT * FROM citable ORDER BY t, cited_j) TO '{run_dir / 'citable_items.parquet'}' (FORMAT parquet)")

    venues = run_dir / "venues.parquet"
    con.execute(f"""COPY (SELECT venue_omid, any_value(issns) AS issns, count(*) AS n_pubs
                          FROM pubs WHERE venue_omid IS NOT NULL GROUP BY 1 ORDER BY 1)
                    TO '{venues}' (FORMAT parquet)""")

    # 6. Throughput and a rough full-run estimate (linear in compressed bytes).
    full_gb = {"edges": 13.3, "pubs": 8.44}
    est = {}
    for name in ("edges", "pubs"):
        frac = rec["inputs"][name]["compressed_bytes_read"] / (full_gb[name] * 1e9)
        est[name] = {"sample_fraction_of_file": round(frac, 4),
                     "est_full_rows": int(c[f"{name}_rows"] / frac)}
    rec["full_run_estimate"] = est
    rec["timings_s"]["total"] = round(time.time() - t_start, 2)
    rec["peak_rss_mb"] = round(peak_rss_mb(), 1)

    (run_dir / "run.json").write_text(json.dumps(rec, indent=2, default=str))
    with open(run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run_dir.iterdir()):
            if p.name not in ("SHA256SUMS", "log.txt"):
                f.write(f"{sha256(p)}  {p.name}\n")
    log(json.dumps(rec["counts"], default=str))
    log(f"done in {rec['timings_s']['total']} s, peak RSS {rec['peak_rss_mb']} MB")


if __name__ == "__main__":
    main()
