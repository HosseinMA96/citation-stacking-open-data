"""C6 full run: journal-pair citation tables from the OpenCitations Jan-2024 files (streaming, resumable).

Usage:
    python c6_full_run.py --run-id <id> --edges <csv[.gz]> --pubs <csv[.gz]> [--meta <dir>] [--resume]

--meta: folder with the OpenCitations Meta CSV dump (Figshare 10.6084/m9.figshare.21747461.v7).
In the parsed pubs file most journal articles give their venue as a bare link to an issue-level id
with no row in the file (RESULTS_LOG 2026-10-31), so the journal is taken from Meta, joined on OMID.

Resource limits come from environment variables, so the same script runs small on the laptop
and large on the VM (see ../../vm/vm.env.example):
    C_THREADS   DuckDB threads              (default 2)
    C_MEM       DuckDB memory limit         (default 2GB)
    C_TEMP_DIR  DuckDB spill directory      (default <work>/duckdb_tmp)
    C_MAX_TEMP  DuckDB max spill size       (default 5GB)
    C_WORK      large intermediates         (default ../../data/work/<run_id>)

Stages (each writes a stage_<name>.json marker in runs/<run_id>/ when complete; --resume skips
completed stages and never rewrites them):
    inputs    sha256 of the input files (Meta: per-file sizes and one digest over per-file sha256)
    meta      Meta CSVs -> meta_venue.parquet (article OMID, venue OMID, ISSNs); only with --meta
    pubs      pubs CSV -> pubs_slim.parquet (iid, year, type, venue OMID, ISSNs) + parse rejects;
              venue from Meta when the OMID matches, else from the pubs venue field's bracket form
    journals  merge venue OMIDs that share an ISSN -> journals.parquet, pubs_j.parquet
    edges     edge CSV -> edges.parquet
    coverage  one pass: how many edge ends match a pub, a year, a journal (C7)
    pairs     one pass: (t, citing_j, cited_j) -> eff (cited t-1, t-2) and prev (cited < t);
              all years in C_WORK, analysis years (config) in runs/<run_id>/pairs_jcr_years.parquet
    citable   (journal, year) -> citable items (JIF denominator proxy) and all items
    agg       network summed over all years of eff (input for the dcSBM blocks, c6_blocks.py)
Small outputs go to runs/<run_id>/; large ones (edges, pubs) stay in C_WORK.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha256(path, chunk=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def peak_rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def type_filter(types, col="type"):
    if types == "all":
        return "TRUE"
    return f"{col} IN (" + ", ".join(f"'{t}'" for t in types) + ")"


class Run:
    def __init__(self, args):
        self.run_dir = HERE / "runs" / args.run_id
        if self.run_dir.exists() and not args.resume:
            sys.exit(f"{self.run_dir} exists; use --resume to continue it, or pick a new --run-id")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.work = Path(os.environ.get("C_WORK", ROOT / "data" / "work" / args.run_id))
        self.work.mkdir(parents=True, exist_ok=True)
        self.args = args
        self.cfg_bytes = args.config.read_bytes()
        self.cfg = yaml.safe_load(self.cfg_bytes)
        self.limits = {
            "threads": int(os.environ.get("C_THREADS", 2)),
            "memory_limit": os.environ.get("C_MEM", "2GB"),
            "temp_directory": os.environ.get("C_TEMP_DIR", str(self.work / "duckdb_tmp")),
            "max_temp_directory_size": os.environ.get("C_MAX_TEMP", "5GB"),
        }
        self.logf = open(self.run_dir / "log.txt", "a")
        self.con = duckdb.connect()
        for k, v in self.limits.items():
            self.con.execute(f"SET {k} = '{v}'" if not isinstance(v, int) else f"SET {k} = {v}")
        self.con.execute("SET preserve_insertion_order = false")
        self.log(f"start run {args.run_id}; limits {self.limits}; work {self.work}")

    def log(self, msg):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(line, flush=True)
        self.logf.write(line + "\n")
        self.logf.flush()

    def marker(self, name):
        return self.run_dir / f"stage_{name}.json"

    def stage(self, name, fn):
        if self.marker(name).exists():
            self.log(f"stage {name}: already complete, skipped")
            return json.loads(self.marker(name).read_text())
        self.log(f"stage {name}: start")
        t0 = time.time()
        info = fn() or {}
        info.update({"stage": name, "seconds": round(time.time() - t0, 1),
                     "peak_rss_mb_so_far": peak_rss_mb(), "limits": self.limits,
                     "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
        tmp = self.marker(name).with_suffix(".tmp")
        tmp.write_text(json.dumps(info, indent=2, default=str))
        tmp.rename(self.marker(name))
        self.log(f"stage {name}: done in {info['seconds']} s; {json.dumps(info, default=str)[:600]}")
        return info

    def copy_to(self, sql, out):
        """COPY a query to parquet atomically (tmp file, then rename)."""
        tmp = out.with_name(out.name + ".tmp")
        if tmp.exists():
            tmp.unlink()
        self.con.execute(f"COPY ({sql}) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)")
        tmp.rename(out)

    def q1(self, sql):
        return self.con.execute(sql).fetchone()

    # ---------------------------------------------------------------- stages
    def s_inputs(self):
        out = {}
        for name in ("edges", "pubs"):
            p = getattr(self.args, name)
            out[name] = {"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)}
        if self.args.meta:
            files = self.meta_files()
            per = [f"{sha256(f)}  {f.relative_to(self.args.meta)}" for f in files]
            out["meta"] = {"path": str(self.args.meta), "files": len(files),
                           "bytes": sum(f.stat().st_size for f in files),
                           "sha256_of_per_file_sha256": hashlib.sha256("\n".join(per).encode()).hexdigest()}
            (self.run_dir / "meta_files.sha256").write_text("\n".join(per) + "\n")
        out["config_sha256"] = hashlib.sha256(self.cfg_bytes).hexdigest()
        out["python"] = platform.python_version()
        out["duckdb"] = duckdb.__version__
        return out

    def meta_files(self):
        return sorted(f for f in self.args.meta.rglob("*.csv") if f.is_file())

    def s_meta(self):
        if not self.args.meta:
            return {"used": False}
        out = self.work / "meta_venue.parquet"
        files = ", ".join(f"'{f}'" for f in self.meta_files())
        self.con.execute("DROP TABLE IF EXISTS reject_errors; DROP TABLE IF EXISTS reject_scans")
        self.con.execute(f"""CREATE TEMP TABLE m AS
            SELECT NULLIF(regexp_extract(id, 'omid:(br/[0-9]+)', 1), '') AS omid,
                   NULLIF(regexp_extract(venue, '\\[omid:(br/[0-9]+)', 1), '') AS venue_omid,
                   regexp_extract_all(venue, 'issn:([0-9]{{4}}-[0-9]{{3}}[0-9X])', 1) AS issns
            FROM read_csv([{files}], header = true, all_varchar = true,
                          quote = '"', escape = '"', strict_mode = false, null_padding = true,
                          ignore_errors = true, store_rejects = true)""")
        rejects = self.q1("SELECT count(*) FROM reject_errors")[0]
        r = self.q1("""SELECT count(*), count(omid), count(DISTINCT omid), count(venue_omid),
                              count(DISTINCT venue_omid), count(*) FILTER (len(issns) > 0) FROM m""")
        # One row per article OMID; a repeated OMID keeps its smallest venue OMID (deterministic).
        self.copy_to("""SELECT omid, min(venue_omid) AS venue_omid,
                               arg_min(issns, venue_omid) AS issns, count(DISTINCT venue_omid) AS n_venues
                        FROM m WHERE omid IS NOT NULL AND venue_omid IS NOT NULL GROUP BY omid""", out)
        multi = self.q1(f"SELECT count(*) FILTER (n_venues > 1) FROM read_parquet('{out}')")[0]
        self.con.execute("DROP TABLE m")
        return {"used": True, "rows": r[0], "with_omid": r[1], "distinct_omid": r[2],
                "with_venue_omid": r[3], "distinct_venue_omid": r[4], "with_issn": r[5],
                "omids_with_several_venues": multi, "parse_rejects": rejects,
                "output": str(out), "output_bytes": out.stat().st_size}

    def s_pubs(self):
        out = self.work / "pubs_slim.parquet"
        meta = self.work / "meta_venue.parquet"
        use_meta = bool(self.args.meta)
        self.con.execute("DROP TABLE IF EXISTS reject_errors; DROP TABLE IF EXISTS reject_scans")
        parsed = f"""
            SELECT TRY_CAST(iid AS BIGINT) AS iid,
                   TRY_CAST(pub_year AS SMALLINT) AS pub_year,
                   type,
                   NULLIF(regexp_extract(omid, 'omid:(br/[0-9]+)', 1), '') AS omid,
                   NULLIF(regexp_extract(venue, '\\[omid:(br/[0-9]+)', 1), '') AS venue_omid,
                   regexp_extract_all(venue, 'issn:([0-9]{{4}}-[0-9]{{3}}[0-9X])', 1) AS issns
            FROM read_csv('{self.args.pubs}', header = true, all_varchar = true,
                          quote = '"', escape = '"', strict_mode = false, null_padding = true,
                          ignore_errors = true, store_rejects = true)"""
        if use_meta:
            self.con.execute(f"CREATE TEMP TABLE p AS {parsed}")
            src = self.con.execute(f"""
                SELECT CASE WHEN m.venue_omid IS NOT NULL THEN 'meta'
                            WHEN p.venue_omid IS NOT NULL THEN 'pubs_bracket' ELSE 'none' END AS source,
                       p.type = 'journal article' AS ja,
                       m.omid IS NOT NULL AS omid_in_meta,
                       p.venue_omid IS NOT NULL AND m.venue_omid IS NOT NULL
                           AND p.venue_omid <> m.venue_omid AS disagree,
                       count(*) AS n
                FROM p LEFT JOIN read_parquet('{meta}') m USING (omid) GROUP BY ALL ORDER BY n DESC""").df()
            src.to_csv(self.run_dir / "venue_source.csv", index=False)
            self.copy_to(f"""
                SELECT p.iid, p.pub_year, p.type, p.omid,
                       coalesce(m.venue_omid, p.venue_omid) AS venue_omid,
                       CASE WHEN m.venue_omid IS NOT NULL THEN m.issns ELSE p.issns END AS issns
                FROM p LEFT JOIN read_parquet('{meta}') m USING (omid)""", out)
            self.con.execute("DROP TABLE p")
        else:
            self.copy_to(parsed, out)
        rejects = self.q1("SELECT count(*) FROM reject_errors")[0]
        examples = [r[0] for r in self.con.execute(
            "SELECT error_message FROM reject_errors LIMIT 3").fetchall()]
        v = f"read_parquet('{out}')"
        r = self.q1(f"""SELECT count(*), count(DISTINCT iid), count(*) FILTER (iid IS NULL),
                               count(*) FILTER (pub_year IS NOT NULL),
                               count(*) FILTER (venue_omid IS NOT NULL),
                               count(*) FILTER (len(issns) > 0) FROM {v}""")
        types = dict(self.con.execute(
            f"SELECT coalesce(type, '<null>'), count(*) FROM {v} GROUP BY 1 ORDER BY 2 DESC LIMIT 30").fetchall())
        return {"rows": r[0], "distinct_iid": r[1], "bad_iid": r[2], "with_year": r[3],
                "with_venue_omid": r[4], "with_issn": r[5], "parse_rejects": rejects,
                "reject_examples": examples, "type_counts": types,
                "venue_source": self.venue_source_summary() if use_meta else "pubs_bracket only",
                "output": str(out), "output_bytes": out.stat().st_size}

    def venue_source_summary(self):
        s = pd.read_csv(self.run_dir / "venue_source.csv")
        ja = s[s.ja == True]
        return {"all_rows": {k: int(v) for k, v in s.groupby("source").n.sum().items()},
                "journal_articles": {k: int(v) for k, v in ja.groupby("source").n.sum().items()},
                "journal_articles_omid_in_meta": int(ja.loc[ja.omid_in_meta, "n"].sum()),
                "rows_meta_vs_bracket_disagree": int(s.loc[s.disagree == True, "n"].sum())}

    def s_journals(self):
        slim = f"read_parquet('{self.work / 'pubs_slim.parquet'}')"
        ven = self.con.execute(f"""
            SELECT venue_omid, list_distinct(flatten(list(issns))) AS issns, count(*) AS n_pubs
            FROM {slim} WHERE venue_omid IS NOT NULL GROUP BY 1""").df()
        # Union-find: venue OMIDs that share any ISSN are one journal.
        parent = np.arange(len(ven))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        first = {}
        for i, issns in enumerate(ven["issns"]):
            for s in issns:
                if s in first:
                    a, b = find(i), find(first[s])
                    if a != b:
                        parent[max(a, b)] = min(a, b)
                else:
                    first[s] = i
        roots = np.array([find(i) for i in range(len(ven))])
        ven["root"] = roots
        # journal_id: dense ids ordered by the smallest OMID in the group (deterministic).
        rep = ven.groupby("root")["venue_omid"].min().sort_values()
        jid = pd.Series(np.arange(len(rep)), index=rep.index)
        ven["journal_id"] = ven["root"].map(jid).astype("int32")
        journals = (ven.groupby("journal_id")
                    .agg(omids=("venue_omid", list),
                         issns=("issns", lambda x: sorted({s for l in x for s in l})),
                         n_pubs=("n_pubs", "sum"))
                    .reset_index())
        pq.write_table(pa.Table.from_pandas(journals, preserve_index=False),
                       self.run_dir / "journals.parquet", compression="zstd")
        self.con.register("venue_map", ven[["venue_omid", "journal_id"]])
        out = self.work / "pubs_j.parquet"
        self.copy_to(f"""SELECT p.iid, p.pub_year, p.type, m.journal_id
                         FROM {slim} p LEFT JOIN venue_map m USING (venue_omid)""", out)
        self.con.unregister("venue_map")
        merged = journals[journals["omids"].map(len) > 1]
        return {"venue_omids": len(ven), "journals": len(journals),
                "journals_from_merged_omids": len(merged),
                "omids_in_merged_journals": int(merged["omids"].map(len).sum()),
                "largest_merge": int(journals["omids"].map(len).max()),
                "output": str(out)}

    def s_edges(self):
        out = self.work / "edges.parquet"
        self.copy_to(f"""SELECT * FROM read_csv('{self.args.edges}', header = true,
                         columns = {{'citing_iid': 'BIGINT', 'cited_iid': 'BIGINT'}})""", out)
        n = self.q1(f"SELECT count(*) FROM read_parquet('{out}')")[0]
        return {"rows": n, "output": str(out), "output_bytes": out.stat().st_size}

    def s_coverage(self):
        e, pj = self.work / "edges.parquet", self.work / "pubs_j.parquet"
        rows = self.con.execute(f"""
            SELECT a.iid IS NOT NULL AS citing_found, a.pub_year IS NOT NULL AS citing_year,
                   a.journal_id IS NOT NULL AS citing_journal,
                   b.iid IS NOT NULL AS cited_found, b.pub_year IS NOT NULL AS cited_year,
                   b.journal_id IS NOT NULL AS cited_journal, count(*) AS n
            FROM read_parquet('{e}') x
            LEFT JOIN read_parquet('{pj}') a ON x.citing_iid = a.iid
            LEFT JOIN read_parquet('{pj}') b ON x.cited_iid = b.iid
            GROUP BY ALL ORDER BY n DESC""").df()
        rows.to_csv(self.run_dir / "coverage.csv", index=False)
        tot = int(rows["n"].sum())
        both = int(rows.loc[rows.citing_journal & rows.cited_journal, "n"].sum())
        return {"edges": tot, "both_ends_journal": both,
                "share_both_ends_journal": round(both / tot, 6) if tot else None}

    def s_pairs(self):
        e, pj = self.work / "edges.parquet", self.work / "pubs_j.parquet"
        cnt = self.cfg["counting"]
        offs = ", ".join(map(str, self.cfg["jcr_window"]["cited_offsets"]))
        out = self.work / "pairs_all_years.parquet"   # large; stays on the VM
        self.copy_to(f"""
            SELECT a.pub_year AS t, a.journal_id AS citing_j, b.journal_id AS cited_j,
                   count(*) FILTER (a.pub_year - b.pub_year IN ({offs})) AS eff,
                   count(*) FILTER (b.pub_year < a.pub_year) AS prev
            FROM read_parquet('{e}') x
            JOIN (SELECT * FROM read_parquet('{pj}')
                  WHERE pub_year IS NOT NULL AND {type_filter(cnt['citing_types'])}) a
              ON x.citing_iid = a.iid
            JOIN (SELECT * FROM read_parquet('{pj}')
                  WHERE pub_year IS NOT NULL AND journal_id IS NOT NULL
                    AND {type_filter(cnt['cited_types'])}) b
              ON x.cited_iid = b.iid
            GROUP BY ALL
            HAVING eff > 0 OR prev > 0""", out)
        v = f"read_parquet('{out}')"
        r = self.q1(f"""SELECT count(*), sum(eff), sum(prev), sum(eff) FILTER (citing_j = cited_j),
                               sum(eff) FILTER (citing_j IS NULL), min(t), max(t) FROM {v}""")
        by_year = {str(k): {"pairs": int(p), "eff": int(s)} for k, p, s in self.con.execute(
            f"SELECT t, count(*), sum(eff) FROM {v} WHERE t BETWEEN 2010 AND 2024 GROUP BY t ORDER BY t").fetchall()}
        # Small copy for the laptop: only the analysis years (config jcr_window.citing_years).
        years = ", ".join(map(str, self.cfg["jcr_window"]["citing_years"]))
        sub = self.run_dir / "pairs_jcr_years.parquet"
        self.copy_to(f"SELECT * FROM {v} WHERE t IN ({years})", sub)
        return {"rows": r[0], "eff": r[1], "prev": r[2], "eff_self": r[3],
                "eff_citing_without_journal": r[4], "t_min": r[5], "t_max": r[6],
                "by_year_2010_2024": by_year, "output_bytes": out.stat().st_size,
                "jcr_years_rows": self.q1(f"SELECT count(*) FROM read_parquet('{sub}')")[0],
                "jcr_years_bytes": sub.stat().st_size}

    def s_citable(self):
        pj = self.work / "pubs_j.parquet"
        out = self.run_dir / "citable_by_year.parquet"
        self.copy_to(f"""
            SELECT journal_id, pub_year, count(*) AS n_all,
                   count(*) FILTER ({type_filter(self.cfg['counting']['citable_types'])}) AS n_citable
            FROM read_parquet('{pj}')
            WHERE journal_id IS NOT NULL AND pub_year IS NOT NULL GROUP BY ALL""", out)
        return {"rows": self.q1(f"SELECT count(*) FROM read_parquet('{out}')")[0]}

    def s_agg(self):
        years = self.cfg["cidre"]["blocks"]["aggregate_years"]
        where = "TRUE" if years == "all" else f"t IN ({', '.join(map(str, years))})"
        out = self.run_dir / "agg_eff_network.parquet"
        self.copy_to(f"""
            SELECT citing_j, cited_j, sum(eff) AS w
            FROM read_parquet('{self.work / 'pairs_all_years.parquet'}')
            WHERE citing_j IS NOT NULL AND eff > 0 AND {where}
            GROUP BY ALL""", out)
        r = self.q1(f"""SELECT count(*), sum(w), count(DISTINCT citing_j), count(DISTINCT cited_j),
                               count(*) FILTER (citing_j = cited_j) FROM read_parquet('{out}')""")
        return {"aggregate_years": years, "edges": r[0], "weight": r[1],
                "citing_journals": r[2], "cited_journals": r[3], "self_loops": r[4]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--edges", required=True, type=Path)
    ap.add_argument("--pubs", required=True, type=Path)
    ap.add_argument("--meta", default=None, type=Path, help="folder with the OpenCitations Meta CSV dump")
    ap.add_argument("--config", default=HERE / "config.yaml", type=Path)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--stop-after", default=None, help="stop after this stage (for testing)")
    args = ap.parse_args()

    run = Run(args)
    t0 = time.time()
    stages = [("inputs", run.s_inputs), ("meta", run.s_meta), ("pubs", run.s_pubs), ("journals", run.s_journals),
              ("edges", run.s_edges), ("coverage", run.s_coverage), ("pairs", run.s_pairs),
              ("citable", run.s_citable), ("agg", run.s_agg)]
    summary = {}
    for name, fn in stages:
        summary[name] = run.stage(name, fn)
        if args.stop_after == name:
            run.log(f"stopping after stage {name} as requested")
            return

    rec = {"run_id": args.run_id, "script": "c6_full_run.py", "stages": summary,
           "total_seconds_this_session": round(time.time() - t0, 1), "peak_rss_mb": peak_rss_mb()}
    (run.run_dir / "run.json").write_text(json.dumps(rec, indent=2, default=str))
    with open(run.run_dir / "SHA256SUMS", "w") as f:
        for p in sorted(run.run_dir.iterdir()):
            if p.suffix in (".parquet", ".csv") or p.name in ("run.json", "meta_files.sha256"):
                f.write(f"{sha256(p)}  {p.name}\n")
    shutil.rmtree(run.limits["temp_directory"], ignore_errors=True)   # spill only; C_WORK outputs stay
    run.log(f"run complete; peak RSS {rec['peak_rss_mb']} MB")


if __name__ == "__main__":
    main()
