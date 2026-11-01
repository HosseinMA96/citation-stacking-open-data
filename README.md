# Draft README for the public data and code release of Paper C

Status: draft, 2026-11-01. Copy into the root of the public release (e.g. the Zenodo deposit) and fill in the TODOs.
Do not copy the project-internal `README.md`; it holds planning notes that do not belong in the release.

## Citation stacking on open data: data and code

TODO(authors), TODO(repository DOI). Companion to the paper "Can open citation data detect citation stacking? An audit
against Clarivate's journal suppressions" (TODO: journal reference).

### Contents
- `data/suppressions_v2.csv`, `data/suppressions_oos.csv`: Clarivate JCR title suppressions for data years 2015–2025,
  transcribed from Clarivate's public material. Clarivate's own files are not redistributed:
  `data/suppression_sources/SOURCES.md` lists each source with its URL, a web-archive link where one exists, and the
  SHA-256 checksum of the copy used. To rerun `data/build_suppressions_*.py`, download those files to the listed paths.
- `experiments/c01_journal_graph/`: all scripts, configuration, run records (`run.json`, `SHA256SUMS`) and the lab
  notebook (`RESULTS_LOG.md`).
- `paper/`: LaTeX source.

### How to read the flag lists
Some run outputs (e.g. `flags.csv`, `consensus_flags.csv`, `groups.csv`) list journals that a statistical screen
flagged for an **anomalous citation pattern** in a given year. This includes journals that Clarivate never listed.

- A flag is a **candidate for expert review, not a finding of misconduct** or of any intent to manipulate. Many flags
  have benign explanations, such as a society journal and its companion, editorial preferences, regional research
  communities, or gaps and artifacts in the open data (see the paper's Section 5).
- Flags depend on the data snapshot (OpenCitations, January 2024), on missing reference lists, and on the stochastic
  block-model partition. They are not stable verdicts about a journal.
- The paper names only journals that Clarivate itself listed. Please do the same when reusing these files: do not
  present a flag as evidence against a journal, its editors or its authors.
- All analyses are at journal level. The files contain no author or editor names.
