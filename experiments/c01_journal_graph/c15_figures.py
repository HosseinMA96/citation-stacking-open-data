"""C15: paper figures (vector PDF) drawn only from logged run outputs. Laptop.

F1 coverage by citing year (c9_scores_20261031_01/coverage_by_year.csv)
F2 fidelity: Clarivate's published % vs ours, by citing-side reference coverage (c10_covsplit_20261031_01)
F3 why CIDRE misses the 2023 pairs: donor and recipient scores vs theta (c12_diag_20261031_01)
F4 recipient-centric variant: flagged share of listed journals vs base rate, by consensus level (c12_consensus_20261031_01)
F5 lead time: years each listed journal was flagged vs its first listing year (c12_eval_20261031_01)
F6 stability: dcSBM partitions (NMI/ARI) vs CIDRE groups and variant flags (c6_blockstab_20261031_02, c12_stab_20261031_01)
F7 anatomy: concentration and title similarity, targets vs controls (c13_anatomy run, if given)

Usage:  python c15_figures.py --run-id c15_figures_<YYYYMMDD>_01 [--anatomy c13_anatomy_<...>]
Output: ../../paper/figures/F*.pdf and runs/<run_id>/ (run.json with input and output sha256, SHA256SUMS).
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
OUT = HERE.parent.parent / "paper" / "figures"
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42,
                     "figure.dpi": 150, "axes.titlesize": 8, "legend.fontsize": 7, "legend.frameon": False})
C = {"blue": "#2b6cb0", "orange": "#dd6b20", "grey": "#718096", "green": "#2f855a", "red": "#c53030"}
INPUTS = []


def boxes(ax, data):
    """One box per call: matplotlib 3.1 cannot take a ragged list with current numpy."""
    for i, x in enumerate(data):
        ax.boxplot(np.asarray(x, dtype=float), positions=[i + 1], widths=0.5, flierprops={"markersize": 2})
    ax.set_xlim(0.4, len(data) + 0.6)


def read(path):
    INPUTS.append(str(path.relative_to(RUNS)))
    return pd.read_csv(path)


def f1():
    d = read(RUNS / "c9_scores_20261031_01" / "coverage_by_year.csv")
    d = d[d.t <= 2023]
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    for col, lab, c in (("share_citing_journal", "citing item has a journal", C["blue"]),
                        ("share_both_journal", "both items have a journal", C["orange"]),
                        ("share_both_rule", "both in journal rule", C["green"])):
        ax.plot(d.t.to_numpy(), (d[col] * 100).to_numpy(), marker="o", ms=2.5, lw=1.2, label=lab, color=c)
    ax.axvspan(2014.5, 2021.5, color=C["grey"], alpha=0.12, lw=0)
    ax.text(2019.6, 47, "GBIF occurrence-download\ncitations (DataCite)", ha="center", fontsize=6.5, color=C["grey"])
    ax.set_xlabel("citing year"); ax.set_ylabel("% of citation edges"); ax.set_ylim(40, 102)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2, fontsize=6)   # below the axes: no overlap
    return fig


def f2():
    d = read(RUNS / "c10_covsplit_20261031_01" / "fidelity_with_coverage.csv")
    d = d[d.ours.notna() & d.refs_present.notna()]
    fig, ax = plt.subplots(figsize=(3.2, 3.0))
    mk = {"self_cites_pct_jif_numerator": ("o", "self-citation %"), "donor_pct_jif_numerator": ("s", "donor % of JIF numerator"),
          "pct_exchange_to_jif_years": ("^", "% exchange to JIF years")}
    for (metric, rp), g in d.groupby(["metric", "refs_present"]):
        m, lab = mk[metric]
        ax.scatter(g.clarivate.to_numpy(), g.ours.to_numpy(), marker=m, s=14, color=C["blue"] if rp else C["red"], alpha=0.8,
                   label=f"{lab}, refs {'present' if rp else 'absent'}")
    ax.plot([0, 100], [0, 100], color=C["grey"], lw=0.8)
    ax.fill_between([0, 100], [-10, 90], [10, 110], color=C["grey"], alpha=0.12, lw=0)
    ax.set_xlim(0, 102); ax.set_ylim(-3, 102)
    ax.set_xlabel("Clarivate published (%)"); ax.set_ylabel("open data, this study (%)")
    ax.legend(loc="upper left", fontsize=5.8)
    return fig


def f3():
    d = read(RUNS / "c12_diag_20261031_01" / "pairs.csv")
    d = d[d.excessive_with_cond1.astype(str) == "True"]
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    y = np.arange(len(d))
    ax.barh(y + 0.18, d.recipient_score_R_prepeel.to_numpy(), 0.35, color=C["orange"], label="recipient score of recipient")
    ax.barh(y - 0.18, d.donor_score_D_prepeel.to_numpy(), 0.35, color=C["blue"], label="donor score of donor")
    ax.axvline(0.15, color=C["red"], lw=1, ls="--"); ax.text(0.16, len(d) - 0.45, "θ = 0.15", color=C["red"], fontsize=7)
    ax.set_yticks(y)
    short = {"Ukrainian Journal for Physical Optics": "Ukr J Phys Opt", "Ukrainian Journal of Physical Optics": "Ukr J Phys Opt",
             "Climate Change Economics": "Clim Change Econ", "Optik": "Optik",
             "Environmental Science and Pollution Research": "Environ Sci Pollut Res"}
    ax.set_yticklabels([f"{short.get(r.recipient, r.recipient[:18])}\n← {short.get(r.donor, r.donor[:18])} ({r.t})"
                        for r in d.itertuples()], fontsize=6.5)
    ax.set_xlabel("CIDRE score (share of excessive citations)"); ax.set_xlim(0, 1)
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.3), ncol=2)
    return fig


def f4():
    d = read(RUNS / "c12_consensus_20261031_01" / "enrichment.csv")
    d = d[d.exclude_design_cases]
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    ks = [1, 4, 7]
    x = np.arange(len(ks))
    st = [float(d[(d.min_partitions == k) & (d.kind == "stacking")].listed_rate.iloc[0]) * 100 for k in ks]
    se = [float(d[(d.min_partitions == k) & (d.kind == "self")].listed_rate.iloc[0]) * 100 for k in ks]
    ba = [float(d[(d.min_partitions == k) & (d.kind == "stacking")].base_rate.iloc[0]) * 100 for k in ks]
    ax.bar(x - 0.27, st, 0.27, color=C["orange"], label="stacking-listed journals")
    ax.bar(x, se, 0.27, color=C["blue"], label="self-citation-listed journals")
    ax.bar(x + 0.27, ba, 0.27, color=C["grey"], label="all journals (base rate)")
    for i, k in enumerate(ks):
        e = float(d[(d.min_partitions == k) & (d.kind == "stacking")].enrichment.iloc[0])
        ax.text(i - 0.27, st[i] + 1, f"{e:.1f}×", ha="center", fontsize=6.5)
    ax.set_xticks(x); ax.set_xticklabels([f"≥{k} of 7" for k in ks])
    ax.set_xlabel("flagged in partitions"); ax.set_ylabel("% ever flagged, 2015–2023")
    ax.set_ylim(0, 60)
    ax.legend(loc="upper right", ncol=1)
    return fig


def f5():
    d = read(RUNS / "c12_eval_20261031_01" / "lead_time.csv")
    first = d.groupby("journal").first_listed_data_year.first().sort_values()
    fig, ax = plt.subplots(figsize=(3.4, 0.16 * len(first) + 0.6))
    for i, (j, fy) in enumerate(first.items()):
        g = d[d.journal == j]
        k = g.kind.iloc[0]
        ax.scatter(g.t.to_numpy(), [i] * len(g), s=12, color=C["orange"] if "stacking" in k else C["blue"], zorder=3)
        ax.scatter([fy], [i], marker="|", s=80, color="black", zorder=4)
    ax.set_yticks(range(len(first))); ax.set_yticklabels([j[:34] for j in first.index], fontsize=5.8)
    ax.set_xlabel("JCR data year")
    ax.set_xticks(range(2015, 2024)); ax.set_xticklabels([f"'{y % 100:02d}" for y in range(2015, 2024)])
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=C["orange"], label="flagged (stacking-listed)"),
                       Line2D([], [], marker="o", ls="", color=C["blue"], label="flagged (self-citation-listed)"),
                       Line2D([], [], marker="|", ls="", ms=9, color="black", label="first Clarivate listing")],
              loc="upper center", bbox_to_anchor=(0.3, -0.1), ncol=1)
    return fig


def f6():
    b = read(RUNS / "c6_blockstab_20261031_02" / "pairwise.csv")
    b = b[b.a.str.startswith("main") & b.b.str.startswith("main") & ~((b.a == "main_s4311_t1a") & (b.b == "main_s4311_t1b"))]
    s = read(RUNS / "c12_stab_20261031_01" / "pairwise.csv")
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    data = [x.to_numpy() for x in (b.ari, b.nmi, s.cidre_member_jaccard, s.cidre_group_recovery, s.variant_flag_jaccard)]
    boxes(ax, data)
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels(["partition\nARI", "partition\nNMI", "CIDRE\nmembers J", "CIDRE\ngroups rec.", "variant\nflags J"], fontsize=6.5)
    ax.set_ylabel("agreement between fits"); ax.set_ylim(0, 1.05)
    return fig


def f7(run):
    d = read(RUNS / run / "pairs.csv")
    fig, axes = plt.subplots(1, 2, figsize=(3.6, 2.0))
    for ax, col, lab in ((axes[0], "cites_per_item", "citations per citing paper"),
                         (axes[1], "title_cosine_mean", "mean title cosine (TF-IDF)")):
        groups = [("named", "control_named"), ("flagged", "control_flagged")]
        data, labels = [], []
        for a, b in groups:
            xa, xb = d[d.group == a][col].dropna().to_numpy(), d[d.group == b][col].dropna().to_numpy()
            data += [xa, xb]
            labels += [f"{a}\nn={len(xa)}", f"ctrl\nn={len(xb)}"]   # named pairs rest on n = 5: show n
        boxes(ax, data)
        ax.set_xticks(range(1, len(data) + 1))
        ax.set_xticklabels(labels, fontsize=5.5); ax.set_title(lab, fontsize=7)
        if col == "cites_per_item":
            ax.set_yscale("log")
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--anatomy")
    args = ap.parse_args()
    run_dir = RUNS / args.run_id
    if run_dir.exists():
        sys.exit(f"{run_dir} exists; never overwrite a run")
    OUT.mkdir(parents=True, exist_ok=True)
    figs = {"F1_coverage_by_year": f1, "F2_fidelity": f2, "F3_cidre_peeling": f3, "F4_enrichment": f4,
            "F5_lead_time": f5, "F6_stability": f6}
    if args.anatomy:
        figs["F7_anatomy"] = lambda: f7(args.anatomy)
    outs = {}
    for name, fn in figs.items():
        fig = fn()
        fig.tight_layout()
        p = OUT / f"{name}.pdf"
        fig.savefig(p, bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None})
        plt.close(fig)
        outs[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": args.run_id, "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "inputs": sorted(set(INPUTS)),
        "outputs_dir": str(OUT.relative_to(HERE.parent.parent)), "outputs_sha256": outs,
        "matplotlib": matplotlib.__version__, "python": platform.python_version()}, indent=2))
    with open(run_dir / "SHA256SUMS", "w") as fh:
        fh.write(f"{hashlib.sha256((run_dir / 'run.json').read_bytes()).hexdigest()}  run.json\n")
    print(json.dumps(outs, indent=1))


if __name__ == "__main__":
    main()
