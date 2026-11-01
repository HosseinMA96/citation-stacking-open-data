"""C12/C12b evaluation against a label file (RESULTS_LOG "pre-registration addendum ... suppressions_v2").

Reuses saved outputs only (no refit):
  CIDRE groups      runs/<cidre>/groups.csv      -> detections of named recipient<-donor pairs (paper's rule,
                                                   cidre_paper.overlap_detected), every partition; labeled journals in any group
  recipient flags   runs/<recip>/flags.csv       -> enrichment of listed journals among flagged journals, by
                                                   suppression kind (self / stacking-involved), with and without the
                                                   design cases; lead time (flags before the first listing year)
Base for enrichment: journals with max yearly num >= K (K = 20, 50, 100) in the main scores, as c12_enrichment.py.
Listed = matched journals with type self or stacking (expressions of concern and warnings excluded).

Usage:  python c12_eval_labels.py --cidre c12_cidre_20261031_02 --recip c12_recip_20261031_01 \\
            --scores c9_scores_20261031_02 --match c10_match_20261031_05 --labels suppressions_v2.csv --run-id c12_eval_<YYYYMMDD>_01
Output: runs/<run_id>/cidre_detections.csv, cidre_labeled_in_groups.csv, enrichment.csv, lead_time.csv,
        summary.json, run.json, SHA256SUMS.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import duckdb
import pandas as pd
from scipy.stats import binomtest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import cidre_paper  # noqa: E402

DESIGN_CASES = {"Ukrainian Journal of Physical Optics", "Ukrainian Journal for Physical Optics", "Climate Change Economics"}


def kind(t):
    t = str(t)
    if t == "self":
        return "self"
    if t == "stacking":
        return "stacking"
    return None   # expressions of concern, warnings, other


def main():
    ap = argparse.ArgumentParser()
    for a in ("--cidre", "--recip", "--scores", "--match", "--labels", "--run-id"):
        ap.add_argument(a, required=True)
    args = ap.parse_args()
    runs = HERE / "runs"
    run_dir = runs / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    sup = pd.read_csv(ROOT / "data" / args.labels)
    m = pd.read_csv(runs / args.match / "matches.csv")
    jid = {r.name: int(r.journal_ids) for r in m.itertuples() if r.status == "matched"}
    name = {v: k for k, v in jid.items()}

    # CIDRE detections of named pairs, all partitions
    g = pd.read_csv(runs / args.cidre / "groups.csv")
    years, tags = set(g.t.unique()), sorted(g.tag.unique())
    det, lab = [], []
    pairs = sup[(sup.role == "recipient") & sup.partner_journal.notna() & sup.jcr_data_year.isin(years)]
    for r in pairs.itertuples():
        a, b = jid.get(r.journal), jid.get(r.partner_journal)
        for tag in tags:
            gg = g[(g.t == r.jcr_data_year) & (g.tag == tag)]
            hit = ([k for k, x in gg.groupby("group") if cidre_paper.overlap_detected({a, b}, set(x.journal_id))]
                   if a is not None and b is not None else [])
            det.append({"t": r.jcr_data_year, "tag": tag, "recipient": r.journal, "donor": r.partner_journal, "type": r.type,
                        "both_matched": a is not None and b is not None, "detected": bool(hit),
                        "recipient_in_any_group": bool(a is not None and (gg.journal_id == a).any()),
                        "donor_in_any_group": bool(b is not None and (gg.journal_id == b).any())})
    for r in sup[sup.jcr_data_year.isin(years)].drop_duplicates(["jcr_data_year", "journal"]).itertuples():
        a = jid.get(r.journal)
        for tag in tags:
            gg = g[(g.t == r.jcr_data_year) & (g.tag == tag)]
            lab.append({"t": r.jcr_data_year, "tag": tag, "journal": r.journal, "type": r.type, "matched": a is not None,
                        "in_group_same_year": bool(a is not None and (gg.journal_id == a).any()),
                        "in_group_any_year": bool(a is not None and (g[g.tag == tag].journal_id == a).any())})
    det, lab = pd.DataFrame(det), pd.DataFrame(lab)

    # Recipient-variant enrichment and lead time
    f = pd.read_csv(runs / args.recip / "flags.csv")
    s = duckdb.sql(f"SELECT journal_id, max(num) AS mx FROM read_parquet('{runs / args.scores / 'journal_year_scores.parquet'}') GROUP BY 1").df()
    sup["kind"] = sup.type.map(kind)
    listed = sup[sup.kind.notna()].copy()
    listed["jid"] = listed.journal.map(jid)
    listed = listed[listed.jid.notna()]
    kinds = {"any": set(listed.jid.astype(int)), "self": set(listed[listed.kind == "self"].jid.astype(int)),
             "stacking": set(listed[listed.kind == "stacking"].jid.astype(int))}
    design = {jid[n] for n in DESIGN_CASES if n in jid}
    rows = []
    for tag in sorted(f.tag.unique()):
        ever = set(f[f.tag == tag].journal_id)
        for K in (20, 50, 100):
            base = set(s.journal_id[s.mx >= K])
            rate = len(ever & base) / len(base)
            for kd, L0 in kinds.items():
                for excl in (False, True):
                    L = [j for j in L0 if j in base and not (excl and j in design)]
                    if not L:
                        continue
                    k = sum(j in ever for j in L)
                    rows.append({"tag": tag, "min_num": K, "kind": kd, "exclude_design_cases": excl,
                                 "base_journals": len(base), "base_rate": round(rate, 5), "listed": len(L), "listed_flagged": k,
                                 "listed_rate": round(k / len(L), 4), "enrichment": round(k / len(L) / rate, 2),
                                 "p_one_sided": binomtest(k, len(L), rate, alternative="greater").pvalue})
    enr = pd.DataFrame(rows)
    first = listed.groupby("jid").jcr_data_year.min()
    kd_of = listed.groupby("jid").kind.agg(lambda x: "/".join(sorted(set(x))))
    lt = f[(f.tag == "main") & f.journal_id.isin(first.index)].copy()
    lt["journal"] = lt.journal_id.map(name)
    lt["kind"] = lt.journal_id.map(kd_of)
    lt["first_listed_data_year"] = lt.journal_id.map(first)
    lt["years_before_first_listing"] = lt.first_listed_data_year - lt.t
    lt["top_donor_name_if_labeled"] = lt.top_donor.map(lambda x: name.get(int(x)))
    lt = lt[["journal", "kind", "t", "first_listed_data_year", "years_before_first_listing", "r", "e", "s_in",
             "top_donor_name_if_labeled"]].sort_values(["journal", "t"])

    em = enr[(enr.tag == "main") & (enr.min_num == 20)]
    summ = {
        "cidre_named_pairs": int(pairs.shape[0]),
        "cidre_pairs_both_matched": int(det[det.tag == "main"].both_matched.sum()),
        "cidre_detected_any_partition": int(det.groupby(["t", "recipient", "donor"]).detected.any().sum()),
        "cidre_labeled_journal_years_in_group_main": f"{int(lab[(lab.tag == 'main') & lab.matched].in_group_same_year.sum())}/{int(lab[(lab.tag == 'main') & lab.matched].shape[0])}",
        "enrichment_main_num20": em[["kind", "exclude_design_cases", "listed", "listed_flagged", "base_rate", "enrichment", "p_one_sided"]].to_dict("records"),
        "enrichment_range_all_partitions_K": {f"{kd}|excl={ex}": [float(g.enrichment.min()), float(g.enrichment.max()), float(g.p_one_sided.max())]
                                               for (kd, ex), g in enr.groupby(["kind", "exclude_design_cases"])},
        "flagged_before_first_listing_main": int((lt.years_before_first_listing > 0).groupby(lt.journal).any().sum()),
        "listed_journals_ever_flagged_main": int(lt.journal.nunique()),
    }
    run_dir.mkdir(parents=True)
    det.to_csv(run_dir / "cidre_detections.csv", index=False)
    lab.to_csv(run_dir / "cidre_labeled_in_groups.csv", index=False)
    enr.to_csv(run_dir / "enrichment.csv", index=False)
    lt.to_csv(run_dir / "lead_time.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cidre_run": args.cidre, "recip_run": args.recip, "scores_run": args.scores, "match_run": args.match,
        "labels": args.labels, "labels_sha256": hashlib.sha256((ROOT / "data" / args.labels).read_bytes()).hexdigest(),
        "design_cases": sorted(DESIGN_CASES), "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        for p in sorted(run_dir.iterdir()):
            if p.name != "SHA256SUMS":
                fh.write(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n")
    print(json.dumps(summ, indent=1, default=str))
    pd.set_option("display.width", 250)
    print(lt.to_string())


if __name__ == "__main__":
    main()
