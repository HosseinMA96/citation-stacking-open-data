# c01_journal_graph manifest

| Item | Path | Notes |
|---|---|---|
| Config | `config.yaml` | Scope, years, run mode |
| Environment | `requirements.lock.txt` | `pip freeze` of `../../.venv` (duckdb 1.5.6, pandas 2.3.3, pyarrow 25.0.1, cidre 0.0.1) |
| Lab notebook | `RESULTS_LOG.md` | Every run and decision |
| Scripts | `c5b_prototype.py` | C5b laptop prototype on prefix samples |
| Scripts | `cidre_paper.py` | CIDRE as in the paper (wraps cidre 0.0.1; adds condition 1, theta_w, networkx-3 fix, matching rule) |
| Scripts | `cidre_toy_check.py` | TODO item 3 toy-graph check |
| Scripts | `c6_full_run.py` | C6 full run: streaming, resumable stages; limits from C_THREADS, C_MEM, C_TEMP_DIR, C_MAX_TEMP, C_WORK |
| Scripts | `c6_blocks.py` | dcSBM blocks with graph-tool (`--self-test`, `--dry-run`, `--min-strength`, `--tag`) |
| Scripts | `c6_venue_check.py`, `c6_journal_rule_check.py`, `c6_journal_set.py` | Venue-format diagnosis; journal-rule comparison; per-venue journal flags (rules `main`, `type_issn_ja50` in config) |
| Scripts | `c6_block_stability.py` | NMI/ARI between dcSBM fits (seeds, threads, rules) |
| Scripts | `c7_coverage_gap.py`, `c7_dataset_source.py` | Coverage dip diagnosis by item type; DOI registrants of the `dataset` items (Meta dump) |
| Scripts | `c9_scores.py` | C7 coverage by year; C9 journal-year scores (self share, JIF proxy, top-donor shares, HHI, reciprocity, burst) and pair table; `--citing-journal-only` |
| Scripts | `c10_match.py` | Labels → journal_id by Crossref ISSN (aliases and ISSN pins documented in the script) |
| Scripts | `c10_fidelity.py`, `c10_coverage_split.py`, `c10_publishers.py` | Fidelity vs Clarivate's published % and ranks; split by citing-side reference coverage; publishers' Crossref reference deposit |
| Scripts | `c12_cidre.py`, `c12_diag.py` | CIDRE (paper setup) per year × partition; per-pair stage diagnosis |
| Scripts | `c12_recipient.py`, `c12_enrichment.py`, `c12_eval_labels.py`, `c12_stability.py`, `c12_consensus.py` | Recipient-centric variant; enrichment and lead time (v1, v2 labels); stability across partitions; consensus flags |
| Scripts | `c13_anatomy.py`, `c14_evidence.py` | Paper-level concentration and title similarity of pair citations; structured evidence check of flags |
| Scripts | `c15_figures.py` | Paper figures F1–F7 (vector PDFs into `paper/figures/`) from logged runs |
| Scripts | `c16_freeze_predictions.py`, `c16_oos_eval.py` | R11: frozen out-of-sample predictions; test against JCR data years 2024–2025 |
| Scripts | `c17_baseline_size.py` | R9 plain donor-share baselines; R12 size-matched base rates (CMH, matched controls) |
| Scripts | `c18_asym_null.py` (VM), `c18_eval.py` | R10 asymmetric-θ CIDRE; R9b single-block null; evaluation |
| Scripts | `c20_paired.py` | Round 2: paired McNemar tests, bootstrap CIs for size-matched enrichment, size profile of flag rates |
| Scripts | `c19_accounting.py` | R13 label → denominator accounting; sensitivity without rows missing from the current Clarivate xlsx |
| Labels (out of sample) | `../../data/suppressions_oos.csv`, `../../data/suppressions_crosscheck.csv` (built by `../../data/build_suppressions_oos.py`) | JCR data years 2024–2025; cross-check of v2 against Clarivate's current xlsx; sources in `../../data/suppression_sources/clarivate_2026/` |
| Labels | `../../data/suppressions_v2.csv` (built by `../../data/build_suppressions_v2.py`) | Clarivate suppressions, JCR data years 2015–2023, primary sources in `../../data/suppression_sources/` |
| Findings map | `../../FINDINGS.md` | Every paper claim → number → run → file |
| Tests | `test_c6_synthetic.py` | Known-answer test of `c6_full_run.py` (gzip input, ISSN merge, eff/prev, resume) |
| VM | `../../vm/` | Runbook, environment.yml, vmctl.sh (laptop), setup/download/run_all/self_deallocate (VM) |
| Large intermediates | `../../data/work/<run_id>/` (not committed) | pubs_slim, pubs_j, edges, pairs_all_years parquet |
| Runs | `runs/<run_id>/` | One folder per run: `run.json` (config hash, inputs, row counts, runtime, peak memory), `log.txt`, outputs; `SHA256SUMS` for outputs |
| Inputs | `../../data/` (not committed) | Record the checksums of the input files in each `run.json` |
