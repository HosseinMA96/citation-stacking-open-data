# Citation stacking on open data: data, code and run records

Companion repository to the paper

> Hossein Mohasel Arjomandi. *Can open citation data detect citation stacking? An audit against Clarivate's journal
> suppressions.* Manuscript submitted for publication.

The paper builds yearly journal citation networks from the OpenCitations snapshot of January 2024 and compares them
with Clarivate's Journal Citation Reports suppressions for data years 2015–2023, with a prospective check on 2024–2025.
It covers how well open data reproduce Clarivate's published figures, why CIDRE misses Clarivate's named stacking
pairs, and a recipient-centric reading of CIDRE's test.

## Contents

| Path | What it holds |
|---|---|
| `data/suppressions_v2.csv` | Clarivate suppressions, data years 2015–2023, transcribed from Clarivate's public lists (built by `data/build_suppressions_v2.py`) |
| `data/suppressions_oos.csv` | Suppressions for data years 2024–2025, used only for the out-of-sample test (built by `data/build_suppressions_oos.py`) |
| `data/suppressions_crosscheck.csv` | Cross-check of `suppressions_v2.csv` against Clarivate's current consolidated spreadsheet |
| `data/suppression_sources/SOURCES.md` | Every Clarivate source used: URL, web-archive link where one exists, SHA-256 of the copy used |
| `experiments/c01_journal_graph/` | All analysis scripts, `config.yaml`, `requirements.lock.txt`, the lab notebook `RESULTS_LOG.md` and `MANIFEST.md` (what each script does) |
| `experiments/c01_journal_graph/runs/` | One folder per run: `run.json` (parameters, input checksums, row counts, runtime), `log.txt`, outputs, `SHA256SUMS` |
| `FINDINGS.md` | Map from every number in the paper to the run and file that produced it |
| `paper/` | LaTeX source, figures and built PDFs (`main.pdf`; Scientometrics version in `paper/journals/scientometrics/`) |
| `vm/` | Scripts and environment for the steps that need a large machine (64 GB RAM) |
| `lit/` | Literature-search records used for the related-work section |

Clarivate's own files (spreadsheets, help pages, PDFs) are **not redistributed**. To rebuild the label tables, download
them from the URLs in `data/suppression_sources/SOURCES.md` to the paths listed there and check the checksums.

## Input data

Not included because of their size:

- Parsed OpenCitations snapshot, January 2024 (Illinois Data Bank), doi:10.13012/B2IDB-5216575_V1:
  `open_citations_jan2024_iid_el.csv.gz` and `open_citations_jan2024_pubs.csv.gz`.
- OpenCitations Meta CSV dump (figshare), doi:10.6084/m9.figshare.21747461.v7 (fetched by `vm/download_meta.sh`).

## Reproducing the results

1. **Environment.** Laptop steps: Python with the packages in `experiments/c01_journal_graph/requirements.lock.txt`
   (DuckDB, pandas, pyarrow, cidre 0.0.1). Block-model steps: the conda environment in `vm/environment.yml`
   (graph-tool is not on PyPI; the exact build is in `vm/environment.lock.yml`).
2. **Large-machine steps** (`vm/run_all.sh`; procedure in `vm/README.md`): `c6_full_run.py` turns the input files into
   journal-level yearly tables, and `c6_blocks.py` fits the degree-corrected stochastic block models.
3. **Analyses** (laptop, in `experiments/c01_journal_graph/`): `c9_scores.py` (journal-year scores), `c10_*`
   (label matching and fidelity), `c12_*` (CIDRE, the recipient-centric variant, enrichment, stability),
   `c13_*`/`c14_*` (paper-level anatomy and evidence check), `c16_*`–`c20_*` (out-of-sample test, baselines, size
   matching, asymmetric thresholds, paired tests), and `c15_figures.py` (paper figures). `MANIFEST.md` describes each
   script and `RESULTS_LOG.md` records each run in order.

Each script writes a new run folder and never overwrites an earlier one. Runs replaced by a later version carry a
`SUPERSEDED.txt` and are not cited in the paper.

## How to read the flag lists

Some run outputs (e.g. `flags.csv`, `consensus_flags.csv`, `groups.csv`) list journals that a statistical screen
flagged for an **anomalous citation pattern** in a given year. This includes journals that Clarivate never listed.

- A flag is a **candidate for expert review, not a finding of misconduct** or of any intent to manipulate. Many flags
  have benign explanations, such as a society journal and its companion, editorial preferences, regional research
  communities, or gaps and artifacts in the open data (see Section 5 of the paper).
- Flags depend on the data snapshot (OpenCitations, January 2024), on missing reference lists, and on the stochastic
  block-model partition. They are not stable verdicts about a journal.
- The paper names only journals that Clarivate itself listed. Please do the same when reusing these files: do not
  present a flag as evidence against a journal, its editors or its authors.
- All analyses are at journal level. The files contain no author or editor names.

## Licence

- Code (`*.py`, `*.sh`): MIT, see `LICENSE`.
- Data tables, run records, figures and documentation: CC BY 4.0, see `LICENSE-DATA`.
- Clarivate's material is not covered and is not included. The input datasets keep their own licences.

## Contact

Hossein Mohasel Arjomandi, hosseinm@microsoft.com. The views expressed here are the author's own and do not
necessarily reflect those of Microsoft.
