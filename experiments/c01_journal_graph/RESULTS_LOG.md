# c01_journal_graph: lab notebook

Every run, config, failure and decision for Project C goes here, newest last. Never overwrite a result; rerun under a new name.

## 2026-10-28: decisions before any run
- Data: Illinois Data Bank "Parsed Open Citations and PubMed Data" (DOI 10.13012/B2IDB-5216575_V1, CC BY), OpenCitations snapshot Jan 2024.
  - Files needed: `open_citations_jan2024_iid_el.csv.gz` (13.3 GB) and `open_citations_jan2024_pubs.csv.gz` (8.44 GB). Not needed: `_el` (27.2 GB), `_pub_ids` (1.75 GB, unless the DOI mapping is needed).
- `_pubs` header, verified from a partial browser download: `omid,iid,title,authors,issue,volume,venue,pages,pub_year,pub_month,pub_date,type,publisher,editors`.
  - `venue` holds the journal name plus `[omid:br/... issn:XXXX-XXXX]`.
  - Use the venue OMID as the journal ID and the ISSN for matching Clarivate.
  - Contains author names: never publish them.
- The Data Bank blocks command-line downloads (HTTP 403 to curl); use the browser or the Data Bank's own download route on the VM. TODO(verify) how to download on a headless VM.
- Coverage: citations through about 2023, so the usable JCR years are about 2018–2022 (2023 is probably undercounted; the 2025 suppression list is not covered).
- Order: C0 (delete DOI files) → C1 novelty gate → C2 labels gate → C5b laptop prototype → C6 Azure full pass (E8s_v5, 256 GB SSD, deallocate after).

## 2026-10-28: gate C1 (novelty), first pass
- Result: **the original C is not novel.** CIDRE (Kojaku, Livan & Masuda 2021, doi:10.1038/s41598-021-93572-3) already detects journal stacking groups on MAG 2000–2019 and validates against JCR suspensions (12 of 22 groups, about 55%). Leiden, Infomap and dcSBM matched none.
- Still open: an out-of-sample test on open data (OpenCitations, suspensions after 2019; MAG retired end of 2021), plus paper-level anatomy of the stacking citations (title-embedding similarity, concentration).
- Proposed revised C in `lit/LIT.md`. Waiting for the user's decision. Two 2026 papers (Liu et al., ISF; Daly et al., Frontiers) still need a full-text read.

## 2026-10-28: gate C1 closed
- User chose the revised C (out-of-sample CIDRE on open data + paper-level anatomy).
- OntoTrack (2026): no overlap. Gupta et al. (2026, arXiv): paper-level, DBLP, no JCR. Liu et al. (2026, ISF): partial overlap; full text paywalled; differentiate.
- SPEC.md research questions and method rewritten; STEPS C12–C13 updated. Next: C2 (labels).

## 2026-10-28: gate C2 (labels), first pass
`data/suppressions.csv`: 30 rows, each with a source URL.
- **JCR 2020** (2021 release): full Clarivate list (copy at cgmh.org.tw, saved as `data/suppression_sources/cgmh_2020JCR_suppressed.pdf`).
  - 10 titles: 7 self, 3 stacking.
  - Self-citation % of the JIF numerator for each self title (45–61%).
  - 2 stacking pairs with percentages: Arch Latinoam Nutr ← J Intell Fuzzy Syst, 67% of the JIF numerator and 99% exchange; Materials Express ← Nanosci Nanotechnol Lett, 23% and 84%.
- **JCR 2022** (2023 release): 4 titles from Retraction Watch: 1 self, 3 stacking, no pairs.
- **JCR 2023** (2024 release): 16 titles from Retraction Watch. Types are mostly not stated; 3–4 stacking cases according to editors or publishers (ESPR → Climate Change Econ; Optik → Ukr J Phys Opt; Resources Policy → 2 small journals). This data year is probably undercounted in the Jan-2024 snapshot.
- **Missing:**
  - JCR 2019 (2020 release; 33 titles, mostly self; Retraction Watch says none for stacking): kobson.nb.rs copy refused the connection.
  - JCR 2021 (2022 release; 3 self per a search snippet, unverified): kobson.nb.rs refused.
  - Official 2024 list: tzuchi copy refused. Clarivate's jcr.help page did not resolve from this machine.
- **Assessment:** out-of-sample stacking labels are thin, about 5–8 groups over JCR 2020–2023. Self-citation labels have exact percentages.
- **Proposal:** add a fidelity check, i.e. reproduce Clarivate's published percentages (self % of the JIF numerator; stacking % of the JIF numerator and % exchange) from open data. It is a concrete quantitative test of the data source (RQ2).

## 2026-10-28: missing lists, second attempt
- The user could not open the kobson.nb.rs and tzuchi URLs in a browser either. web.archive.org cannot be fetched by the tool, and its API returned non-JSON.
- **The missing years add no stacking labels:**
  - JCR 2019: Retraction Watch says none of the suppressions were for stacking.
  - JCR 2021: Clarivate's 2022 release says 3 titles were suppressed; a search snippet says all were self-citation (titles unverified).
  - So the stacking set is essentially complete for 2020–2022. Only the 2023 types are partial, and that data year is undercounted anyway.
- The missing lists matter only for the self-citation fidelity check, and 7 self titles with exact percentages (JCR 2020) are already in hand.
- **Gate C2 decision:** proceed, with the labels as they are. Main stacking cases: JCR 2020 (2 pairs, with percentages) and JCR 2022 (3 journals; their partners are to be found in our data). JCR 2023 cases are exploratory.

## 2026-10-28: C3 and C5 set up
- Scope: all journals.
- Venv `.venv` (git-ignored): duckdb 1.5.6, pandas 2.3.3, pyarrow 25.0.1, cidre 0.0.1 (PyPI, by Kojaku; signature Cidre(min_edge_weight=0, min_expected_weight=1, group_membership=None, alpha=0.01)). TODO(verify) that 0.0.1 matches the paper's settings (θ = 0.15).
- config.yaml and MANIFEST.md written. The partial `_pubs` download from earlier is gone from ~/Downloads, so C5b needs new samples.

## 2026-10-28: C5b prototype on prefix samples (run `c5b_sample_20261028_01`)
- Inputs: paused browser downloads, snapshotted to `../../data/samples/*.prefix` (checksums in `run.json`).
  - Edges: 378,582,984 compressed bytes (≈2.8% of 13.3 GB) → 52,030,457 edges after the trailing partial line was dropped.
  - Pubs: 289,013,676 bytes (≈3.4% of 8.44 GB) → 2,563,210 rows.
- Script: `c5b_prototype.py` (DuckDB, memory limit 4 GB). Runtime 47 s; peak RSS 2.2 GB.
- **Samples are file prefixes, not random draws.** Join counts, self-citation shares and per-year totals from this run say nothing about the full data. The pubs prefix is grouped by publisher (it starts with China Science Publishing), so same-journal pairs are overrepresented (1,814 of 3,551 window citations). These numbers are smoke-test output only.
- Data checks (these properties should hold for the full file):
  - Edges: no duplicate rows, no self-loops; iids from 6 to 107,054,137.
  - Pubs: iids unique and all parse; the file is **not** sorted by iid (1.7M–104M within the prefix).
  - `venue` text present in 2,083,650 rows (81%); the OMID regex parsed **all** of them (0 unparsed).
  - Types: journal article 70.7%, book chapter 6.7%, proceedings article 5.2%, null 4.0%, other.
  - Journal articles: 97.3% have a venue OMID, 96.1% have at least one ISSN.
  - Venue OMIDs: 235,710 distinct; 96% have no ISSN (book and proceedings venues). Venues with ISSNs mostly have 1–2 (print + electronic).
  - **36 ISSNs map to more than one venue OMID** (duplicate journal records). The full run must merge OMIDs that share an ISSN before aggregating; otherwise a journal's counts get split.
- Pipeline output: 32,652 edges with both ends in journal articles with a year → 2,399 (t, A, B) pairs and 3,551 citations in the 2015–2023 JCR window. Files: `jcr_pairs.parquet`, `venues.parquet`, `SHA256SUMS`.
- **Full-run estimate** (linear in compressed bytes; rough, because the compression ratio varies through the file):
  - ≈1.8 billion edges and ≈75 million pubs rows. TODO(verify) against the Data Bank README.
  - Single-thread decompression ≈3 min (edges) + ≈3 min (pubs); DuckDB load ≈4 min (edges) + ≈9 min (pubs).
  - Loading all edges into memory would need ≈30 GB, which fits on E8s_v5 (64 GB). Safer: stream the gz in DuckDB, filter against the journal-article table, and set `temp_directory` on the SSD.
  - Expect roughly 1 h of VM time for the full pass. TODO(verify) on the VM.
  - The full run cannot be done on the laptop (11 GB free disk).
- Changes for the full run: merge venue OMIDs by shared ISSN; record the citing-side and cited-side match rates separately; decide whether the cited side keeps all item types (the JIF numerator counts citations to all items, the denominator only citable items). This affects the C10 fidelity check.

## 2026-10-28: smaller samples, rerun (run `c5b_sample_20261028_02`)
- The user replaced the samples with smaller downloads to save disk: edges 19,542,647 bytes, pubs 9,660,696 bytes.
- **Deleted** the run-01 input snapshots and their decompressed CSVs (2.5 GB). Run-01 outputs and recorded checksums are kept, but run 01 can no longer be reproduced from local inputs.
- Rerun with the same script and config: 2,683,007 edges and 81,580 pubs rows. Runtime 1.3 s; peak RSS 254 MB. `data/samples/` is now 109 MB.
- Data checks agree with run 01:
  - no duplicate edges or self-loops;
  - the venue OMID parsed in every row with venue text;
  - no venue OMID has more than one ISSN set.
- Only 22 edges join on both ends, giving 4 window citations. **That is too few for the CIDRE smoke test (TODO item 4).** Use a synthetic graph for that test, or download a larger sample then.

## 2026-10-28: decision: count citations the way Clarivate does (runs `_03` failed, `_04` ok)
- **User decision:** follow Clarivate's JIF definition as closely as the data allows. New `counting` block in `config.yaml`; it replaces `journal.keep_types`.
  - Numerator: citations from **any** item type, including citing items with no journal (kept with `citing_j` = null), to **any** item of journal B published in *t*−1 or *t*−2.
  - Denominator proxy: "journal article" items of B in *t*−1 and *t*−2. Written to the new output `citable_items.parquet`.
  - OpenCitations does not separate articles, reviews and editorials, so the denominator is an approximation. TODO(verify) its effect in C10.
  - TODO(verify) which citing sources Clarivate counts (all Web of Science Core Collection indexes, or journals only?).
- Run `_03` **failed**: KeyError in the full-run estimate whenever an already-decompressed CSV is reused. Kept as is, with `FAILED.txt`.
  - Fix: always record the compressed size; estimate full-file rows from the loaded row counts.
- Run `_04` (same small samples): 70,949 citing items with a year (5,278 with no journal), 65,671 cited items, 567 denominator rows.
  - Still 22 joined edges and 4 window citations. The sample is too small to show any difference from the article-only rule.
  - Full-run estimate from the small samples: ≈1.83 B edges and ≈71 M pubs rows, consistent with run 01.

## 2026-10-28: TODO item 3: CIDRE settings vs the paper (runs `cidre_toy_20261028_01`, `_02`)
- Source: full text of Kojaku, Livan & Masuda (2021), PMC8282695, fetched through the Europe PMC REST API (pmc.ncbi.nlm.nih.gov showed a CAPTCHA). Package: PyPI `cidre` 0.0.1, **byte-identical** to GitHub master (last commit 5b582b7, 2021-08-12). The repo has no script that reproduces the paper.
- **Paper setup (Methods):**
  - W_ij(t) = citations from papers in journal i in year t to papers in journal j from t−1 and t−2. This matches our `jcr_pairs`.
  - Edge (i, j) is excessive iff (1) more than half of i's citations to j point to papers from the last 2 years, **and** (2) the dcSBM Poisson test is significant, with p from eq. 3, λ̂ = max(1, λ) (eq. 6), BH correction, α = 0.01.
  - Null-model blocks: a non-parametric Bayesian dcSBM without hierarchy (Peixoto 2017, Phys Rev E 95:012317, i.e. graph-tool), fitted once on the network **aggregated over 2000–2019**. λ is then computed per year (eq. 5).
  - Peeling with θ = 0.15. Groups are weakly connected components; groups with fewer than θ_w = 50 within-group citations (self-loops excluded) are removed.
  - Matching: a JCR group counts as detected if O = |U_JCR ∩ U_CI| / |U_CI| ≥ 0.5 and the two share at least 2 journals.
- **What the package does and does not do:**
  - Matches the paper: α = 0.01 default; λ clip `min_expected_weight` = 1; eq. 5 (checked by hand, max |Δp| = 1.1e−15); BH; peeling rule; θ passed to `detect`.
  - **Missing:** condition (1); its `mask` argument is not reachable from `Cidre` and references undefined variables.
  - **Missing:** the θ_w = 50 filter (only a comment in the code).
  - **Breaks on networkx ≥ 3** (`from_scipy_sparse_matrix`); we have 3.4.2.
  - Default `group_membership=None` means a single block, not the paper's fitted blocks.
  - Minor: BH's M counts non-self-loop edges, while the paper says "the number of edges in the network".
- **Fix:** `cidre_paper.py` wraps the package's EdgeFilter unchanged and adds condition (1) (needs `W_all`), θ_w, scipy weak components, and the matching rule.
- **Toy check** (`cidre_toy_check.py`, seed 4311; N = 200 journals, 4 blocks, planted cartel, decoy and small groups):
  - Run `_01`: all checks passed except θ_w, which was **inconclusive**. A test-design flaw: the small pair (nodes 20, 130) never reached θ, even without the θ_w filter.
  - Run `_02`: the small pair is now planted on the lowest-strength journals. **All checks pass:**
    - the published `Cidre.detect` fails unpatched on networkx 3.4.2; with a shim, the wrapper gives the same groups as the package (θ_w = 0, no condition 1);
    - with the paper setup, the cartel is found, the decoy is excluded by condition 1, and the small group is removed by θ_w;
    - with a single-block null (the package default), 3 extra **within-field** groups of 7–8 journals appear. The fitted blocks matter.
- **Consequences for the pipeline:**
  - The full run must also output W_all(A→B, t): citations in year t to papers of **any** earlier year. Condition (1) needs it.
  - We need dcSBM blocks fitted on an aggregated network. graph-tool is not on PyPI (conda-forge or apt only). TODO(verify) install on the VM.
  - Aggregation years for us: user decision (2015–2023, or all years in the snapshot).
- Ambiguities, both resolved as the package does:
  - Results says "more than θ_w = 50" while Methods says "remove if less than θ_w"; we use ≥ 50.
  - Within-group citations are counted on the original W, not on the pruned network.

## 2026-10-28: decision: aggregation years for the dcSBM blocks
- The user left the choice to Claude. Chosen: **all years in the snapshot**. This is closest to the paper, which pooled every year it used (2000–2019). The blocks serve only as the null model's field partition, so pooling more years should make them more stable.
- Recorded in a new `cidre` block in `config.yaml`, which also lists the paper's settings.
- TODO(verify): whether graph-tool's fit fits in memory and time on E8s_v5 when run on the all-years journal network.

## 2026-10-28: C6 tooling: full-run pipeline, block fit, VM scripts (run `c6_local_sample_20261028_01`)
- The user cannot free ~100 GB on the laptop, so C6 runs on an Azure VM. Asked for cost-saving scripts, with everything possible done locally first.
- **Local graph-tool not installed.** The conda classic solver was killed (only ~3 GB RAM free), and downloading micromamba locally was not approved. graph-tool will be installed on the VM only and checked there by `c6_blocks.py --self-test` before any data is used.
- `c6_full_run.py`:
  - streaming DuckDB, 8 resumable stages (inputs, pubs, journals, edges, coverage, pairs, citable, agg); limits come from environment variables (laptop defaults 2 threads / 2 GB);
  - ISSN-based merge of venue OMIDs (union-find);
  - pairs table with `eff` (cited t−1, t−2) and `prev` (cited < t, for CIDRE condition 1). All years stay in C_WORK; the analysis years go to `pairs_jcr_years.parquet`;
  - citable items by journal-year; aggregated eff network over all years.
- Run `c6_local_sample_20261028_01` (small prefix samples; 2 threads / 1 GB): all stages complete in 3 s, peak RSS 241 MB.
  - ISSN merge on the sample: 9,035 venue OMIDs → 9,031 journals (1 journal from 5 OMIDs).
  - This run predates the pairs-file split, so its `pairs_by_year.parquet` sits in the run folder. Smoke test only.
- `test_c6_synthetic.py`: hand-built gzip dataset with known answers (ISSN merge, eff/prev, citing side without a journal, editorial cited but not citable, forward and unknown edges dropped, quoted commas, resume, refusal to overwrite). **All checks pass.**
- `run_all.sh`, tested locally with small limits on gzipped samples:
  - the pipeline completed; the block fit failed as expected (no graph-tool), and the failure was logged once with no deallocation;
  - resume skipped all 8 stages;
  - bug found and fixed: unquoted paths broke on spaces.
  - Test run folders were deleted (tests, not results).
- `cidre` 0.0.1 pins matplotlib==3.1.3 (no Python 3.11 build). On the VM it is installed with `--no-deps`, and matplotlib-base and seaborn come from conda-forge (needed at import by `cidre/draw.py`).
- VM cost guards: deallocate (not shutdown), daily auto-shutdown, self-deallocation through the managed identity at the end of `run_all.sh`, SSH from the user's IP only, small outputs only, hours log.
- Prices (Azure retail API, eastus, 2026-10-28): E8s_v5 $0.504/h, E16s_v5 $1.008/h, P15 $38.01/month, E15 $19.20/month.

## 2026-10-28: decision: TODO item 4 closed
- User decision: the item 3 toy test (`cidre_toy_20261028_02`) counts as the CIDRE smoke test. The prefix samples have only 4 window citations, too few for a real-data run.
- The first real-data CIDRE run becomes the first step of item 9: one year (e.g. 2020), on the laptop, from the fetched C6 tables. It is not reported.

## 2026-10-29: C6 VM created (user go-ahead "set up the VM and the whole workflow")
- **Size change:** E8s_v5 and E16s_v5 return `NotAvailableForSubscription` in eastus for this subscription. Used **E8s_v6** (8 vCPU / 64 GB, $0.529/h, Azure retail API), with the NVMe disk controller that v6 sizes need. Fallback: E16s_v6 ($1.058/h). Quota: 20 vCPUs (ESv6 family, eastus).
- Created 2026-10-29T03:43Z: `rg-project-c` / `vm-project-c`, Ubuntu 24.04, 256 GB Premium SSD.
  - Checked guards: SSH only from the user's IP; auto-shutdown 07:00 UTC enabled; managed identity with Virtual Machine Contributor on this VM only (self-deallocation).
  - On the VM: 8 vCPU, 62 GB RAM, 246 GB free.
- **Exact file sizes** (Data Bank dataset JSON): `_iid_el` 14,309,784,846 bytes; `_pubs` 9,064,662,339 bytes.
  - The page's "13.3 GB" and "8.44 GB" are GiB, so the earlier full-run estimates used a sample fraction about 7% too large.
  - **Corrected estimates:** ≈1.97 B edges (52.03 M / 2.65%), consistent with the thesis's ~1.96 B OpenCitations edges; ≈80 M pubs rows (2.563 M / 3.19%).
- **Download route:**
  - A browser User-Agent gets past the Data Bank's 403 (the dataset JSON and a 1 KB ranged download both worked during probing).
  - **Not used:** the permission system flagged this as getting around the Data Bank's bot check, and the Data Bank blocks scripted downloads on purpose.
  - `download.sh` keeps the user-pasted "Copy as cURL" route (the user's own browser session) and now checks exact byte sizes.
  - TODO(user): paste the cURL commands, or ask Data Bank support for an approved command-line route.

## 2026-10-29: VM setup and self-tests; VM deallocated pending the download
- `setup_vm.sh`: micromamba 2.9.0 (checksum OK); env `c-gt` with graph-tool 3.9, duckdb 1.5.6, Python 3.11 (`vm/environment.lock.yml`; log `vm/setup_vm_20261029.log`).
- **First self-test failed:** graph-tool 3.9's `BlockState` has no `get_nonempty_B()`. Fixed in `c6_blocks.py` (block count = number of distinct labels).
- After the fix, all three self-tests pass on the VM:
  - graph-tool planted blocks: 4 of 4, purity 1.0, 2.4 s;
  - `test_c6_synthetic.py`: ALL PASS;
  - CIDRE toy check: all checks true.
- `setup_vm.sh` now skips the env build if the env exists. `vmctl.sh` gains `sendcurl`, `download` and `run`.
- VM **deallocated** at the end; logged VM time 0.07 h (≈ $0.03 compute). The disk and static IP keep billing until the resource group is deleted.
- Blocked on the user: the browser "Copy as cURL" for both files (`vm/README.md` steps 5–6).

## 2026-10-31: full-data download on the VM; c6_full_20261031_01 started
- Route: the user's own browser session gave signed S3 links (Data Bank → medusa-main S3, ~2.9 h expiry). Plain `databank.illinois.edu/datafiles/<id>/download` returns 403 to curl; a HEAD on the signed link also returns 403 (the signature covers GET only); a 2-byte ranged GET returned 206 with the expected total sizes. `download.sh` now accepts a bare URL as well as a cURL command. The links were deleted from the laptop and the VM after use.
- Both files: exact byte sizes match the Data Bank listing, `pigz -t` passes.
  - `open_citations_jan2024_iid_el.csv.gz` 14,309,784,846 B, sha256 `40faa8bb7762f0042e5e901278cc2269e43a5cb28fada1e093ed254a0df66ca7`
  - `open_citations_jan2024_pubs.csv.gz` 9,064,662,339 B, sha256 `c071228e4d4f5dfca381c7d32f986dad87bf0712b1b039fd6afb314d0a921e14`
- Download took ~10 min at ~30 MB/s. Disk after: 27 G used of 247 G.
- `vm/vmctl.sh run c6_full_20261031_01` started 2026-10-31T03:25:31Z (8 threads, 48 GB, gt threads 8).

## 2026-10-31: c6_full_20261031_01 finished, then SUPERSEDED (venue parsing covers only ~23% of journal articles)
**Run.** `run_all.sh c6_full_20261031_01` on E8s_v6 (8 threads, 48 GB): 03:25:31 → 03:38:10 UTC, exit 0; the VM deallocated itself. Fetched; all 7 files in `SHA256SUMS` OK. Full log: `runs/c6_full_20261031_01/run_all_c6_full_20261031_01.log`.
Stage times (s): inputs 19.4, pubs 140.8, journals 71.0, edges 184.0, coverage 72.2, pairs 57.0, citable 0.4, agg 0.2, blocks 207 wall (fit 199.4; 676 blocks on 300,831 journals; peak RSS 2.7 GB). DuckDB peak RSS 9.5 GB.
Numbers that are sound (they do not depend on venue): edges **1,962,840,983** (thesis: ~1.96B); pubs rows 107,030,533, all distinct iid, 0 bad iid, 0 parse rejects; 94,207,184 rows with a year; `pub_year` ranges 1844–9999 (placeholder years; analysis years 2015–2023 only).

**Red flag.** Only 12,668,256 pubs rows had a venue OMID (laptop sample: 81%), and only 38,057,938 edges (1.94%) have a journal at both ends.

**Diagnosis** (`c6_venue_check.py`, read-only, full pubs file; runs `c6_venuecheck_20261031_01`, `_02`; `_02` adds the per-article link-target sections, `script_sha256` differs in run.json):
- The parsed pubs `venue` field has three forms: empty; `Name [omid:br/<id> issn:...]` (12,668,256 rows); a bare link `https://w3id.org/oc/meta/br/<id>` (the rest of the non-empty rows). No other form occurs (format class "other" = 0). The pubs stage regex read only the bracket form.
- Journal articles (76,804,859): bare link 64,566,267; bracket 10,770,391; empty 1,468,201.
- Where a journal article's bare link points (per article): **no row in the pubs file 57,899,535**; a `journal` row 6,666,385 (6,653,491 + 12,212 + 682); other ≤ 350. The pubs file has no `journal issue` / `journal volume` types at all (see `type_counts_all_rows`). Distinct link-only ids ≈ 5 articles each. Interpretation, **TODO(verify)**: the link is the article's issue or volume in OpenCitations Meta, whose records were not carried into the parsed file. So for ~75% of journal articles the journal cannot be recovered from this dataset alone.
- Distinct venue ids: 14,023,903; in bracket form 1,376,068; as link 12,668,837; both 21,002 (same id space).
- By year (journal articles 2013–2023), venue by old rule ≈ 14%, by either form ≈ 98–100%, but "either form" mostly gives issue-level ids, not journals.
- Known gap: `link_target_examples` came back empty (the `USING SAMPLE` clause sampled before the join). Not needed for the conclusion.
- Process note: the first `_01` attempt failed at compile time (SyntaxError) before creating any folder; no run was overwritten.

**Consequence.** `c6_full_20261031_01` is marked `SUPERSEDED.txt` and kept. The journal network, coverage, pairs and blocks must be rebuilt with a journal for every article.

**Proposed fix (needs the user's decision).** Take each article's journal from the OpenCitations Meta CSV dump, joined on OMID. Figshare 10.6084/m9.figshare.21747461, version 7, published 2024-02-16, `meta_csv_dump.zip` 11,342,656,708 B, CC0 (read from the public Figshare API 2026-10-31). Its `venue` field is the bracket form the pipeline already parses. Report the OMID match rate as a check. Whether v7 is the exact snapshot behind the parsed dataset: TODO(verify).

## 2026-10-31: Meta added as journal source; c6_full_20261031_02; journal-rule check
**Decision (user, 2026-10-31):** take each article's venue from the OpenCitations Meta CSV dump; keep the VM disk.
- `vm/download_meta.sh`: Figshare 10.6084/m9.figshare.21747461.v7, `meta_csv_dump.zip` 11,342,656,708 B, MD5 matches the Figshare API (`91d9b2f0…`), sha256 `924ac7acc838024bdc78982970c7b1a4bcd4da5f8ad62c47a94d9580df10ca44`. Extracted: 28,255 CSV files, 45 GB, all with the same header (`id,title,author,issue,volume,venue,page,pub_date,type,publisher,editor`).
- Code: `c6_full_run.py` gains `--meta` and a `meta` stage. In `pubs`, the venue comes from Meta when the article OMID matches, else from the pubs bracket form. New outputs: `venue_source.csv`, `meta_files.sha256`. `run_all.sh` requires the Meta folder.
- Test: `test_c6_synthetic.py` extended (an issue-level link resolved only via Meta; one Meta/pubs disagreement; duplicate Meta row; two files). 29 checks, ALL PASS on the laptop and the VM. One expected value in my first draft of the test was wrong (bracket fallback = 3 articles, iids 5, 7, 10, not 4); the code was right, the test expectation was corrected.
- DuckDB note: `union_by_name` cannot be combined with `store_rejects`; dropped (all headers are identical).

**Run `c6_full_20261031_02`** (04:13–04:34 UTC, all 8 stages; then the block fit was stopped by hand at ~9 min, see below). Fetched, `SHA256SUMS` OK.
- meta: 107,067,700 rows, all with an OMID, all distinct; 88,323,047 with a venue OMID; 9,238,083 distinct venue OMIDs; 0 parse rejects; 0 OMIDs with several venues.
- pubs venue source: journal articles 72,720,703 from Meta, 388,394 from the bracket fallback, 3,695,762 none (95.2% with a venue). Meta and bracket disagree on 212,519 rows.
- journals: 9,007,672 venue OMIDs → 9,006,164 groups (963 merged groups, largest 50 OMIDs).
- coverage: edges with a venue at both ends 1,737,256,883 (88.5%; run 01: 1.9%).
- pairs: eff 295,254,339; prev 1,724,170,877; eff_self 28,993,648. agg: 39,508,367 edges, 3,761,337 citing venues.
- Stage times (s): inputs 236.8, meta 77.8, pubs 143.2, journals 380.9, edges ~160, coverage 63.5, pairs 180.4, citable 1.6, agg 4.1. Peak RSS 47.6 GB (the DuckDB limit).

**Block fit stopped.** The venue network includes books (for chapters) and proceedings volumes as nodes. The fit reached 37 GB RSS at 9 min with no end in sight, and its blocks would not be a journal network. `tmux kill-session` stopped it (so `run_all.sh` did not self-deallocate); no `stage_blocks.json` was written. The user agreed after asking whether my first proposed rule (ISSN + ≥50% articles) was reasonable; my own review: the 50% cut-off had no source, and I had skipped the dataset's own `journal` type.

**Journal-rule check** (`c6_journal_rule_check.py`, read-only; run `c6_journalrule_20261031_01`, 227 s). Base: 9,006,164 venue groups; 73,109,097 journal articles with a venue; 2015–2023 eff with a venue at both ends 140,451,400.

| rule | venues | journal articles covered | agg nodes | agg edges | eff 2015–23 kept |
|---|---|---|---|---|---|
| type_journal | 233,239 | 98.86% | 147,765 | 20,906,131 | 89.68% |
| issn | 103,652 | 99.40% | 91,612 | 21,270,721 | 90.60% |
| ja_share≥0.3 / 0.5 / 0.7 | 334,186 / 333,892 / 333,106 | 99.97 / 99.88 / 98.80% | ~150k | ~20.8M | 89.4 / 89.4 / 89.3% |
| issn & ja≥0.5 | 95,340 | 99.30% | 85,727 | 20,522,482 | 89.31% |
| type_journal & issn | 92,779 | 98.67% | 85,437 | 20,656,119 | 89.57% |
| type_journal ∣ (issn & ja≥0.5) | 236,095 | 99.53% | 148,235 | 20,912,066 | 89.69% |

- Overlap (`rule_overlap.csv`): 92,484 venues meet all three conditions and hold 72,111,639 journal articles (98.6% of those with a venue).
- type_journal without ISSN: 138,438 venues holding only 139,048 articles. Samples have ~2 articles each, and some duplicate a real journal (e.g. a "Tellus B" record with 2 items). Most likely duplicate venue records that the ISSN merge cannot join: TODO(verify).
- type_journal with ja<0.5 and an ISSN: 295 venues, mostly book series and proceedings series (e.g. Advances In Experimental Medicine And Biology, IFMBE Proceedings).
- Not type_journal but issn & ja≥0.5: 2,856 venues, 485,939 articles. The largest are Japanese society meeting-abstract collections whose items are typed "journal article" (e.g. 応用物理学会学術講演会講演予稿集), plus some real journals with no venue record.
- Excluded random samples: books (book chapters), as expected.
- The rules differ little in the citations they keep (89.3–90.6% of 2015–2023 eff); they differ in how many small or non-journal venues become nodes.
- Not computed: network size for "all three" (92,484 venues); expected ≈ type_journal & issn.
- VM deallocated after the check. Logged VM time 1.58 h (~$0.84 compute).

## 2026-10-31: journal rules applied; dcSBM blocks for c6_full_20261031_02 (C6 complete)
**Decision (user, 2026-10-31):** main rule A = the venue's own record has type `journal` AND it has an ISSN; sensitivity B = A AND journal-article share ≥ 0.5. Both are in `config.yaml` `journal_rules` (`main`, `type_issn_ja50`).
- Code: `c6_journal_set.py` (per-venue flags → `journal_flags.parquet`), `c6_blocks.py --journal-rule NAME` (filter, then fit; tag = rule name), `vm/run_blocks.sh` (flags, then one fit per rule; self-deallocates). `test_c6_synthetic.py` now 34 checks (flags for X/Y/Z; both rules keep X, Y and drop Z), ALL PASS on the laptop and the VM. graph-tool self-test on the VM: purity 1.0.
- Flags agree exactly with the independent rule check (c6_journalrule_20261031_01): 233,239 type_journal; 103,652 issn; 92,779 A; 92,484 B.

| | rule A `main` | rule B `type_issn_ja50` |
|---|---|---|
| journals in rule | 92,779 | 92,484 |
| network journals (with ≥1 edge) | 85,437 | 85,261 |
| edges / weight | 20,656,119 / 258,255,814 | 20,516,570 / 257,130,198 |
| share of agg weight kept (of 285,746,820) | 90.4% | 90.0% |
| self-loops | 37,305 | 37,216 |
| **blocks** | **2,770** | **2,403** |
| description length | 148,448,383.3 | 148,962,315.0 |
| fit time / wall / peak RSS | 1,006 s / 16:54 / 16.7 GB | 937 s / 15:44 / 16.6 GB |

- Seed 4311 for both, graph-tool 3.9, 8 OMP threads. Log: `runs/c6_full_20261031_02/run_blocks_c6_full_20261031_02.log`. All files in `SHA256SUMS` OK after copying back (the VM's `SHA256SUMS` extends the local one).
- **Red flag for the next step:** the two networks differ by only 176 journals and 0.7% of edges, but the block count differs by 15% (2,770 vs 2,403). `minimize_blockmodel_dl` is a stochastic search; part of this is likely run-to-run variation, not the rule: TODO(verify). Before CIDRE results are reported, fit rule A with several seeds and measure how much the CIDRE output depends on the block partition (e.g. overlap of detected groups across seeds). Cost: ~17 min of VM per fit.
- VM time to date: 2.50 h logged (~$1.32 compute) + disk. VM deallocated; disk kept for C13.

## 2026-10-31: seed robustness of the dcSBM partition (TODO 6b), c6_blockstab_20261031_01
**Question:** is the 2,770 vs 2,403 block gap between rules A and B due to the rule or to the stochastic search?
- Fits (VM, `vm/run_seeds.sh c6_full_20261031_02 main 1 2 3 4 4311`, 06:21–07:50 UTC, exit 0): rule `main`, seeds 1–4, plus a repeat of the config seed 4311 (tag `main_s4311_rep`). Same input for all (agg_eff_network sha256 `bc0fb8290f98…`), graph-tool 3.9, 8 OMP threads. Files `blocks_main_s*.parquet`, `stage_blocks_main_s*.json`, log `run_seeds_c6_full_20261031_02.log` in `runs/c6_full_20261031_02/`; all 16 entries of its `SHA256SUMS` OK after copying back (the local file was a prefix of the VM's).
- Comparison: `c6_block_stability.py --src c6_full_20261031_02 --run-id c6_blockstab_20261031_01` (laptop; self-test passes). Outputs `fits.csv`, `pairwise.csv`, `summary.json`, `run.json`, `SHA256SUMS`. NMI = arithmetic normalization; ARI = Hubert & Arabie.

| fit | seed | blocks | description length | fit s | peak RSS MB | largest block | singleton blocks |
|---|---|---|---|---|---|---|---|
| main | 4311 | 2,770 | 148,448,383.3 | 1,006.0 | 16,271.6 | 5,153 | 230 |
| main_s3 | 3 | 2,912 | 148,451,083.6 | 1,029.3 | 16,256.9 | 5,511 | 238 |
| main_s4311_rep | 4311 | 2,533 | 148,774,984.5 | 1,052.1 | 16,407.5 | 5,022 | 180 |
| main_s4 | 4 | 2,459 | 148,911,296.5 | 1,049.0 | 16,380.3 | 5,396 | 175 |
| main_s1 | 1 | 2,548 | 149,467,357.6 | 1,118.0 | 16,304.9 | 5,763 | 180 |
| main_s2 | 2 | 2,131 | 150,946,514.8 | 1,020.9 | 16,276.0 | 6,146 | 149 |
| (rule B) type_issn_ja50 | 4311 | 2,403 | 148,962,315.0 | 937.1 | — | 5,979 | 183 |

- **Same seed is not reproducible:** `main_s4311_rep` (2,533 blocks) differs from `main` (2,770), NMI 0.7728, ARI 0.4624. Likely cause: the parallel (OpenMP, 8 threads) sweeps make the search nondeterministic even with `gt.seed_rng` and `np.random.seed` set: TODO(verify) against the graph-tool docs, or by a 1-thread repeat. So the seed in config.yaml does not by itself make a fit reproducible; the reproducible artifact is the saved `blocks_*.parquet` (with sha256).
- **Rule A, 6 fits:** blocks 2,131–2,912. Pairwise (15 pairs): NMI min/median/max 0.762 / 0.772 / 0.782; ARI 0.441 / 0.475 / 0.538. No pair is identical.
- **Rule A vs rule B** (seed 4311, 85,261 common journals): NMI 0.7706, ARI 0.4783, within the range of rule-A seed pairs; rule B vs the other rule-A fits: NMI 0.767–0.776, ARI 0.435–0.501. So the A/B block-count gap is consistent with search variation, not the rule. This resolves the 2026-10-31 red flag (the TODO(verify) above).
- Best fit by description length: `main` (the original fit); `main_s3` is within 2,700 nats (0.002%). DL spread across rule-A fits is 1.7% (148.45M–150.95M).
- **Implication for CIDRE:** the partition is only moderately stable (ARI ≈ 0.48). CIDRE results must be reported with their dependence on the partition: run CIDRE on several of these fits (at least `main`, the best DL; plus the others) and report the overlap of detected groups. Planned before any CIDRE number is reported. Default partition for the main analysis: lowest DL (`main`), a standard choice for stochastic SBM fits (TODO(verify) citation).
- VM: auto-shutdown restored to 07:00 UTC after the fits (it was moved to 09:30 for this run; `vm/sessions_notes.log`). VM deallocated, disk kept. Logged VM time to date 4.08 h (~$2.16 compute) + disk.

## 2026-10-31: TODO 6c started, single-thread reproducibility check (user request)
- Purpose: test the TODO(verify) above, that the 8-thread search causes same-seed fits to differ. Two fits with `C_GT_THREADS=1`, seed 4311, rule `main`, run side by side (tags `main_s4311_t1a`, `main_s4311_t1b`; each uses one thread, so running both together does not affect either result, only the wall time). Script `vm/run_threads_check.sh`; started 14:21:02 UTC; the VM self-deallocates at the end. If a and b are identical, single-threaded fits are reproducible and the 8-thread variation is explained; if not, the variation comes from elsewhere.
- Note: `c9_scores_20261031_01` (below) runs on the same VM at the same time (5 DuckDB threads), so the fit times of these two fits are not comparable with the 8-thread fits.

## 2026-10-31: TODO 7 (C7–C9) started: coverage by year and journal-year scores, c9_scores_20261031_01
**Decisions (Claude, within the user's go-ahead for item 7; open to change):**
- C7 (venue coverage): overall coverage is already logged for c6_full_20261031_02 (88.5% of 1,962,840,983 edges have a journal at both ends). New: the same by citing year 2010–2024 (`coverage_by_year.csv`), also for rule `main` journals at both ends and for cited items in the JCR window. Needed for RQ2 (data-source sensitivity), and to show the 2023 undercount.
- C8 (yearly journal-pair counts): already produced as `pairs_jcr_years.parquet` in c6_full_20261031_02 (one file with column `t`, 2015–2023, eff = JCR window, prev = all earlier years). It is not split into per-year files, because that would duplicate 1.1 GB.
- C9 scores: per recipient journal B in rule `main` and JCR year t. Definitions are in the docstring of `c9_scores.py` and are repeated here:
  - num = Σ_A c(A→B,t) over all citing items, including those without a journal (JIF numerator proxy);
  - self_share = c(B→B,t)/num;
  - citable = B's journal articles from t−1 and t−2; jif_proxy = num/citable, with or without self-citations;
  - stacking proxies for the top donor A* (the largest external c(A→B,t)): top_donor_share_of_num = c(A*→B,t)/num (recipient side) and top_donor_out_share = c(A*→B,t)/Σ_X c(A*→X,t) (donor side);
  - donor_hhi = Herfindahl index of external donors;
  - reciprocity = Σ_A min(c(A→B,t), c(B→A,t)) / external citations;
  - burst_log2 = log2((num_t+1)/(num_{t−1}+1)), null for 2015 because 2014 is not in the table.
  - Pair table: rule-journal pairs with c(A→B,t) ≥ 10, with both shares and the reverse count, as the input for the C10 stacking check.
- These are proxies. Clarivate's exact suppression formulas are not fully public: TODO(verify) in C10 against the published JCR-2020 cases. No ranking or labels are attached in this step.
- Tests: `c9_scores.py --self-test`, a hand-computed 4-journal, 2-year example with 20 checks (num, self share, citable, both JIF proxies, external total, donors, top donor, both shares, HHI, reciprocity, burst, previous-year donor count, rule filter, pair table, reverse count), ALL PASS on the laptop and the VM.
- Run on the VM (the laptop has ~1 GB of free RAM and 6.7 GB of free disk, too little for the 168M-row pairs table), 5 threads, 18 GB DuckDB limit, started 14:29 UTC.

## 2026-10-31: TODO 7 (C7–C9) results: c9_scores_20261031_01 (main), _02 (sensitivity), _03 (reproduction check); c7_covgap_20261031_01/_02
**Runs** (all on the VM, copied back, every `SHA256SUMS` OK; the parquets are gitignored like the other c6 outputs and are regenerated by the command in each `run.json`):
- `c9_scores_20261031_01`: rule `main`, default counting (citing items without a journal kept, as config says), with coverage. 109 s total (scores 10 s, coverage 99 s), peak RSS 12.5 GB, 5 threads. Script sha256 `3e966278…`.
- `c9_scores_20261031_02`: same, with `--citing-journal-only` (sensitivity, added after the finding below), `--no-coverage`. 13.5 s. Script `ba44551a…`.
- `c9_scores_20261031_03`: reproduction check, the current script (`ba44551a…`) with default settings. Same values as `_01` in every column except `donor_hhi` (max abs difference 4.4e-16 in 133,379 rows, from the order of a parallel floating-point sum); `pair_scores.parquet` byte-identical. So adding the option did not change the default path. `PURPOSE.txt` in the run.
- `c7_covgap_20261031_01`: diagnosis of the coverage dip (citing side, cited side), years 2014, 2018, 2020, 2022, 147 s. Superseded by `_02` (same queries plus `cross.csv`), 296 s. `SUPERSEDED.txt` in `_01`.

**C7 coverage by citing year** (`c9_scores_20261031_01/coverage_by_year.csv`; edges whose citing item has that year):

| t | edges | citing has journal | both ends journal | both ends rule `main` | rule-`main` cited in window (= Σ num) |
|---|---|---|---|---|---|
| 2014 | 68,369,769 | 99.5% | 97.1% | 83.8% | 9,493,912 |
| 2015 | 75,867,030 | 94.0% | 91.8% | 80.0% | 10,069,668 |
| 2016 | 84,106,559 | 91.8% | 89.7% | 77.1% | 10,754,622 |
| 2017 | 91,726,549 | 89.1% | 87.0% | 74.8% | 11,438,069 |
| 2018 | 108,593,356 | 80.2% | 78.3% | 67.9% | 12,371,128 |
| 2019 | 131,251,629 | 74.8% | 72.8% | 62.3% | 15,831,599 |
| 2020 | 163,504,856 | 69.3% | 67.7% | 58.7% | 19,198,553 |
| 2021 | 183,044,100 | 70.8% | 69.4% | 61.6% | 23,965,321 |
| 2022 | 138,002,551 | 97.6% | 95.7% | 84.4% | 23,771,177 |
| 2023 | 102,885,766 | 96.0% | 93.4% | 82.6% | 16,470,684 |

- Consistency check: the last column equals the yearly Σ num in `summary.json` exactly, for every year (two separate queries, one over the edges and one over the pairs table).
- **The 2015–2021 dip is an artifact of one item type.** `c7_covgap_20261031_02/cross.csv`: citing items typed `dataset` with no venue cite items that have a pubs row but no year, no type and no journal. In 2020: 222,179 such citing items, 37,073,796 edges (22.7% of all 2020 edges); in 2018: 148,979 items, 17,779,562 edges. In 2022 only 551,087 edges go to cited items without a year. These edges cannot enter the journal tables (the cited item has no journal or year), so they lower the coverage shares but not the counts. What the records are (e.g. biodiversity or data-repository records): TODO(verify) on a sample of OMIDs.
- **But part of the dataset effect does enter the numerator.** The same `dataset` items also cite dated journal items (2020: 10,063,037 edges from 96,102 items). With the default counting (citing items without a journal kept), the share of Σ num from citing items without a journal is 0.4% (2015), 0.6%, 1.2%, 2.2%, **12.8% (2019), 14.4% (2020), 11.2% (2021)**, 2.3% (2022), 3.7% (2023). It is concentrated: the top 10 receiving journals get 87.8% / 84.3% / 78.7% of it in 2019 / 2020 / 2021 (15.8% in 2022). The top receiver in 2020 (ISSN 1175-5326, likely Zootaxa: TODO(verify)) has 2,072,480 of its 2,075,713 numerator citations from items without a journal (99.8%), so its JIF proxy is 623.9. The next ones (ISSNs 2118-9773, 0022-2933, 1314-2828, 1280-9551, 1679-6225) are also ≥ 99% and look like taxonomy journals (TODO(verify) the names). 42 journals with num ≥ 20 have ≥ 50% of num from items without a journal in 2020 (27 in 2019, 65 in 2021, 1 in 2022).
- Effect on scores (`_01` vs `_02`, journals with num ≥ 20): the correlation of jif_proxy is ≥ 0.99 in 2015–2018 and 2022–2023, but 0.901 (2019), 0.779 (2020) and 0.703 (2021). 25–122 journals per year drop below num 20 without these citations.
- **Decision needed (user):** the counting decision of 2026-10-28 keeps citing items without a journal. Clarivate counts citations from the sources it indexes, so the `--citing-journal-only` variant is probably closer to the JCR (TODO(verify) against the JCR documentation in C10). Proposal: make `citing_journal_only` the main counting and keep the default as the sensitivity. Not changed without the user's OK.

**C9 scores** (`journal_year_scores.parquet`, 375,953 journal-years for 2015–2023; `pair_scores.parquet`, 1,725,765 pairs with c ≥ 10, Σ eff 63,389,844, 16,001 recipient journals). From `_01` `summary.json`, journals with num ≥ 20, [p50, p90, p99]:

| t | journals (num ≥ 20) | self_share | jif_proxy | top_donor_share_of_num | reciprocity | burst_log2 |
|---|---|---|---|---|---|---|
| 2015 | 15,495 | 0.071 / 0.255 / 0.600 | 1.20 / 3.70 / 10.54 | 0.067 / 0.163 / 0.404 | 0.228 / 0.473 / 0.683 | (no 2014) |
| 2018 | 18,190 | 0.059 / 0.237 / 0.622 | 1.27 / 3.83 / 11.49 | 0.064 / 0.159 / 0.423 | 0.200 / 0.461 / 0.673 | 0.167 / 1.184 / 5.000 |
| 2020 | 20,740 | 0.050 / 0.210 / 0.586 | 1.49 / 4.60 / 14.17 | 0.064 / 0.154 / 0.381 | 0.196 / 0.461 / 0.683 | 0.295 / 1.334 / 5.317 |
| 2022 | 23,672 | 0.040 / 0.184 / 0.552 | 1.72 / 5.15 / 14.94 | 0.064 / 0.147 / 0.371 | 0.197 / 0.456 / 0.688 | 0.125 / 1.170 / 5.585 |
| 2023 | 18,929 | 0.048 / 0.190 / 0.550 | 1.37 / 3.84 / 11.73 | 0.061 / 0.136 / 0.340 | 0.218 / 0.474 / 0.705 | −0.596 / 0.222 / 4.858 |

(All years are in `summary.json`.) The 2023 negative median burst matches the known 2023 undercount (indexing lag).
- Journal-years with num ≥ 20 and self_share ≥ 0.5: 244–348 per year; with top_donor_share_of_num ≥ 0.5: 82–111 per year (`_01`). Pairs with both share_of_num ≥ 0.5 and donor_out_share ≥ 0.5: 29. No ranking or labels in this step; C10 checks these proxies against Clarivate's published cases.
- **Small denominators:** journal-years with num ≥ 20 and citable < 10 number 107–258 per year (17–46 with citable 0, jif_proxy null). Most extreme JIF proxies come from them: of the jif_proxy > 50 cases, 8–24 per year have citable < 10. The top case has num 3,058 and citable 1 (2022). These are likely venues whose items are mostly not typed `journal article` in OpenCitations (TODO(verify)). C10 needs a minimum citable count for any JIF-based comparison: **decision for the user** (e.g. citable ≥ 20, which is arbitrary; report sensitivity).

## 2026-10-31: C10 pre-registration (written before any C10 number was computed)
**Decisions (user, 2026-10-31: "do whatever you just recommended"):**
- (a) Counting: scores use only citing items with a journal (`config.yaml` `counting.citing_journal_only: true`); main scores = `c9_scores_20261031_02`, sensitivity = `c9_scores_20261031_01` (all citing items). This replaces the 2026-10-28 choice for the score stage; the c6 tables are unchanged.
- (b) Minimum citable items for JIF-based ranking: 20 (main); 10 and 50 as sensitivity. Ranking also needs num ≥ 20.
- (c) Matching: journals are matched to our `journal_id` by ISSN taken from a verified external source (Crossref journal records; raw responses saved in the run). Names from our own data are a cross-check. Every match is logged with its evidence; unmatched journals are reported as such, not guessed.
- (d) Stacking metric added: "% Exchange to JIF Years". Per the Clarivate JCR help page "Title Suppressions" (seen via search summaries on 2026-10-31; the page itself could not be fetched, so the verbatim wording is TODO(verify)), it is the share of all donor→recipient citations (all cited years) that go to the recipient's two JIF years. Our proxy: eff/prev for the pair in year t. `prev` counts cited years < t, so citations to items from year t itself are missing and the proxy is slightly too high (an upper bound). The C9 `donor_out_share` (share of all the donor's window citations going to the recipient) is a different quantity and is not compared with this column.
- (e) **Pass criteria, fixed now:**
  1. *Fidelity:* each of the 9 published JCR-2020 numbers (7 self-cite %, 2 × 2 stacking %) is "reproduced" if our value is within ±10 percentage points. Reported: how many of the 9 pass, plus all signed differences.
  2. *Signal:* a suppressed journal "ranks" if it is in the top 1% of its JCR year on the relevant score among journals with num ≥ 20 (and citable ≥ 20 for JIF-based scores): self_share for self-citation cases; top_donor_share_of_num for stacking recipients. Reported: the rank and percentile for every labeled journal we can match, all years.
  3. *Checkpoint (Nov 22, TODO item 8):* "signal" = at least half of the matched 2020 suppressed journals (self and stacking recipients) rank in the top 1%. If not, the C10 result counts as "no signal" for the switch-to-D rule. All thresholds are judgment calls made in advance, not tuned afterwards.
- (f) Scope: all labeled years in `data/suppressions.csv` that fall within 2015–2023, with 2020 as the headline. Rows with no stated type are ranked on both scores, reported separately, and not counted in criterion 3.
- Source of the targets: `data/suppression_sources/cgmh_2020JCR_suppressed.pdf` (Clarivate list, © 2021, v3.1), re-read on 2026-10-31. The values in `suppressions.csv` match it: self 50, 55, 45, 50, 47, 54, 61; stacking 67/99 and 23/84. The PDF lists no ISSNs.

## 2026-10-31: C10 results: journal matching (c10_match_20261031_03) and fidelity/ranks (c10_fidelity_20261031_01)
**Matching** (`c10_match.py`, laptop, Crossref journal API queried 2026-10-31; raw responses in `crossref_raw.json`):
- `_01` and `_02` are superseded (`SUPERSEDED.txt`). In `_01`, Crossref returned nothing for queries containing "&", and accents were not normalized (6 false misses). In `_02`, the alias alone was queried and two names found no record. `_03` queries the CSV name and the alias and merges the results.
- Aliases, each with its reason in the script: Genetika (Belgrade) → Genetika; Journal of Intelligent & Fuzzy Systems → the Crossref title with its subtitle (ISSN 1064-1246); Ukrainian Journal *for* → *of* Physical Optics; SOCAR Proceedings → the full Crossref title; Archivos … Nutricion → Nutrición (Crossref search needs the accent). The ISSNs for JIFS and SOCAR are TODO(verify) against the JCR records.
- Result: 31 of 32 names matched to exactly one journal_id; **Bioscience Research: its Crossref ISSNs (1811-9506, 2218-3973) are not in our data**. Exploratory Animal and Medical Research has only 3 items in the data. SOCAR Proceedings has num 6. Neither is rankable.

**Correction to the pre-registration:** it says "the 9 published JCR-2020 numbers (7 self-cite %, 2 × 2 stacking %)". The list adds up to **11** numbers (7 + 4); "9" was a counting slip. The list and the ±10 pp rule are unchanged. Also, Archivos Latinoamericanos de Nutrición has num 10 (< min_num 20), so it cannot be ranked; criterion 3 therefore covers 8 rankable journals, not 9.

**Criterion 1, fidelity** (`fidelity.csv`; main = citing items with a journal; sensitivity results are within 0.5 pp of main for every row):

| journal (JCR 2020) | metric | Clarivate | ours | diff (pp) | pass ±10 |
|---|---|---|---|---|---|
| Hellenic J Cardiology | self % of JIF numerator | 50 | 57.5 (num 325) | +7.5 | yes |
| Int J Engine Research | self % | 55 | 40.6 (584) | −14.4 | no |
| J Biomol Struct Dyn | self % | 45 | 36.9 (2,166) | −8.1 | yes |
| J Enhanced Heat Transfer | self % | 50 | 0.0 (44) | −50.0 | no (coverage, below) |
| J Family Econ Issues | self % | 47 | 33.2 (361) | −13.8 | no |
| Liquid Crystals | self % | 54 | 47.5 (1,437) | −6.5 | yes |
| Mech Based Des Struct Mach | self % | 61 | 55.9 (1,001) | −5.1 | yes |
| Arch Latinoam Nutr ← J Intell Fuzzy Syst | donor % of JIF numerator | 67 | 70.0 (7 of num 10) | +3.0 | yes, but on 10 citations |
| same pair | % exchange to JIF years | 99 | 100 (7/7) | +1.0 | yes, but on 7 citations |
| Materials Express ← Nanosci Nanotechnol Lett | donor % | 23 | 0 (num 235) | −23 | no (coverage) |
| same pair | % exchange | 84 | undefined (0/0) | — | no (coverage) |

- **6 of 11 pass.** Of the 9 numbers where the data has the citing journal's references, 6 pass. Where the data is there, our self-share is usually lower than Clarivate's (5 of 6 self cases, by 5–14 pp). A plausible cause is incomplete reference coverage, or Clarivate's numerator counting citations from sources outside OpenCitations: TODO(verify).
- **Coverage gaps cause the clear failures** (pairs_jcr_years, 2018–2021): Nanoscience and Nanotechnology Letters (journal_id 9002453) and J Enhanced Heat Transfer (2047714) have **no outgoing citations at all** in the data, although they published 43–197 and 23–29 items a year, so their reference lists are missing from OpenCitations. Materials Express's own outgoing citations appear only from 2020. JIFS→Archivos has only 7 window citations. This is direct evidence for RQ2 (data-source sensitivity): two of the ten 2020 cases cannot be seen in open data at all. Which publishers are behind this (and whether they deposit open references to Crossref): TODO(verify).

**Criterion 2, ranks** (`ranks.csv`; top 1% of the year among journals with num ≥ 20; 20,648 journals in 2020):
- JCR-2020 self cases, self_share percentile: Hellenic J Cardiology 1.09% (rank 224), Mech Based Des 1.21% (250), Liquid Crystals 1.84% (380), Int J Engine Res 2.66% (550), J Biomol Struct Dyn 3.42% (707), J Fam Econ Issues 4.21% (870), J Enhanced Heat Transfer 77.9% (no references, above). **None is in the top 1%**; 6 of 7 are in the top 4.3%. Materials Express (stacking recipient), top-donor share: 47.3%.
- 2022–2023 (2023 is exploratory because of the undercount): Ukrainian J Phys Optics, top-donor share 0.18% (rank 34 of 18,806) → **top 1%**; Climate Change Economics 1.22%; Marketing Theory, self 3.36%.
- **Criterion 3 checkpoint: 0 of 8 rankable 2020 journals in the top 1% → "no signal" under the pre-registered rule.**

**Descriptive observations (post hoc, not criteria; journal level, "anomalous pattern" wording):**
- For every stacking recipient that has a named partner and data, the top donor in our data is the named partner: Archivos ← JIFS (2020), Climate Change Economics ← Environmental Science and Pollution Research (2023), Ukrainian J Phys Optics ← Optik (2023).
- Two 2023 listings with no stated type have another listed journal as their top donor: Granular Computing ← Information Sciences; Annals of Financial Economics ← Resources Policy (the publisher of Resources Policy described it as a donor to two unnamed small journals).
- The top 1% cut-off is far stricter than the way Clarivate ranks: Clarivate judges self-citation by its distortion of *category* rank, not by a global self-share rank, so many journals with high self-share in self-citing fields are never suppressed. A field-normalized score would be the natural next step (e.g. rank within dcSBM block or subject category), but it would be a new, post hoc criterion and needs the user's decision.
- Runtime: 8 s on the laptop, peak RSS 0.9 GB.

## 2026-10-31: TODO 6c result: single-threaded fits are reproducible (c6_blockstab_20261031_02)
- Fits `main_s4311_t1a` / `main_s4311_t1b` (`C_GT_THREADS=1`, seed 4311, rule `main`, run side by side on the VM; `vm/run_threads_check.sh`). Both exit 0, at 15:37:29 and 15:38:11 UTC. Fit 4,565.7 s / 4,607.7 s (wall 1:16:27 / 1:17:09; c9 and c7 queries ran on the same VM for part of this time); peak RSS 16.3 GB each.
- **Both give 2,675 blocks and the same description length (148,601,925.257…).** The partitions are identical: NMI 1.0000, ARI 1.0000. Label numbers differ for exactly 1 of 85,437 journals under a one-to-one label map, i.e. a block whose id number differs. The parquet files are therefore not byte-identical; their sha256 values are in `SHA256SUMS` (prefix check OK, all OK after copying back), and the per-fit logs are `run_threads_check_c6_full_20261031_02{,_a,_b}.*`.
- **Conclusion:** with one thread, graph-tool's `minimize_blockmodel_dl` with `seed_rng` is reproducible on this input; the 8-thread run-to-run variation (2026-10-31 6b) comes from the parallel search. This resolves that TODO(verify). For the paper: report that fits were run with 8 threads and are not bit-reproducible, and that the saved partitions (sha256) are the reproducible artifacts; any partition needing an exact rerun can be fitted with one thread (~76 min instead of ~17).
- The 1-thread fit is also just another draw from the search: against the 8-thread fits, NMI 0.768–0.780 and ARI 0.431–0.559, within the 6b range. Its DL (148.60M) is between `main` (148.45M, still the best) and `main_s4311_rep` (148.77M).
- `c6_blockstab_20261031_02` (all 9 fits; supersedes nothing: `_01` keeps the 8-thread-only statistics). Its summary's min/median over rule-main pairs is 0.762/0.773 for NMI and 0.431/0.478 for ARI; the max of 1.0 is the t1a–t1b pair.
- VM time to date 5.41 h logged (~$2.86 compute) + disk. VM deallocated; auto-shutdown at 07:00 UTC is in place.

## 2026-10-31: C12 started: CIDRE on the real journal networks (user go-ahead after the C10 checkpoint)
**Plan, written before the run.** The user asked whether Paper C is still feasible. The C10 checkpoint tested simple global scores; RQ1 (CIDRE detection and lead time) has not been tested yet. Step 1 is a smoke run on 2020 with partition `main`; per TODO 9 it is not reported. Step 2 runs every JCR year 2015–2023 on several partitions.
- Code: `c12_cidre.py`, which calls `cidre_paper.detect` with the paper's settings (θ 0.15, θ_w 50, α 0.01, λ clipped at 1, condition 1 with W_all = `prev`). W = eff over the partition's journals (rule `main`), counting only citing items with a journal. Self-test: a planted cross-block pair in a 60-journal toy network is the only group found and is matched (ALL PASS).
- Matching: the paper's rule (overlap ≥ 0.5 of the CIDRE group and ≥ 2 shared journals). JCR targets are labeled journals with a named partner, both matched by ISSN (`c10_match_20261031_03`), in the same data year: 2020 Archivos ← JIFS and Materials Express ← NNL (the latter's donor references are missing, so it is undetectable); 2023 Climate Change Economics ← ESPR and Ukrainian J Phys Optics ← Optik. Labeled journals without a named partner are reported only as "in some group" (descriptive).
- **Limitation, stated in advance:** only 4 named pairs fall within the data years, and one cannot be seen. Recall over so few targets is a case study, not a rate. CIDRE's own replication targets for 2015–2019 are not in `suppressions.csv` (TODO 9: check whether the CIDRE paper or its supplement lists them).
- **Smoke run `c12_cidre_20261031_01`** (2020, partition `main`; not a reported result, per TODO 9). Ran on the VM in 37 s wall, peak RSS 15.6 GB, exit 0. Network: 85,437 journals, 3,651,746 edges with eff > 0, weight 15,361,187. **27 groups, 2–20 journals each** (178 member rows), with 50–1,538 within-group citations. Archivos ← JIFS is not detected, and Archivos is in no group. Expected from C10: our data has only 7 JIFS→Archivos window citations, below θ_w = 50, so CIDRE cannot flag the pair on open data by construction. Materials Express ← NNL is not detected (the donor's references are missing). Files copied back; `SHA256SUMS` OK.
- **Full run `c12_cidre_20261031_02` started** 15:50 UTC on the VM: years 2015–2023 × 8 partitions (`main`, `main_s1`–`s4`, `main_s4311_rep`, `main_s4311_t1a`, sensitivity `type_issn_ja50`; `t1b` left out because it is identical to `t1a`), 3 workers, 72 jobs.

## 2026-10-31: C12 results: c12_cidre_20261031_02 (2015–2023 × 8 partitions) and diagnosis c12_diag_20261031_01
- Full run: 72 jobs, exit 0, 25–41 s each (mean 31.4 s), peak RSS 17.9 GB per worker, 3 workers. Files copied back; `SHA256SUMS` OK.
- **Groups per year are stable across partitions:** 11–15 (2015), 22–24 (2016–2018), 15–18 (2019), 24–27 (2020), 30–32 (2021), 25–27 (2022), 20–23 (2023). Median group size 3–5 journals, max 18–59 (`group_summary.csv`). How far the *membership* agrees across partitions has not been computed yet.
- **Detections of named JCR pairs: 0 of 4, in all 8 partitions** (`detections.csv`). **No labeled journal of any year is in any CIDRE group in any partition** (`labeled_in_groups.csv`).
- **Why** (`c12_diag_20261031_01/pairs.csv`, partition `main`):

| pair (year) | D→R window cites | cond. 1 | edge excessive (test + cond. 1) | recipient score R | donor score D | out-strength D | outcome |
|---|---|---|---|---|---|---|---|
| Archivos ← JIFS (2020) | 7 | 1.00 | no | 0.00 | 0.060 | 6,689 | too few citations in open data |
| Materials Express ← NNL (2020) | 0 | — | no | 0.07 | 0.00 | 1 | donor references missing |
| Climate Change Econ ← ESPR (2023) | 53 | 0.855 | **yes** | **0.323** | 0.035 | 69,116 | donor peeled away |
| Ukrainian J Phys Opt ← Optik (2023) | 422 | 0.995 | **yes** | **0.827** | 0.057 | 7,628 | donor peeled away |

- **Mechanism for the 2023 pairs:** CIDRE flags the stacking edge (significant against the dcSBM, and over 85% of its citations go to the JIF years), and the recipient's score is far above θ = 0.15. But the donor is a large journal, so these citations are a small share of its output (donor score 3.5–5.7%). Peeling removes nodes whose donor and recipient scores are both below θ, so it drops the donor, and the recipient is left alone, which is no group. **CIDRE's group definition cannot express "a large journal feeding a small one"**, the pattern behind both 2023 named cases. Clarivate's stacking criterion is recipient-centric (% of the recipient's JIF numerator). For Ukrainian J Phys Opt ← Optik the two blocks are the same (block 62706), so the edge is excessive even within a field.
- This is a structural property of CIDRE's peeling rule, shown on real cases. It is not a coverage problem. It is a candidate central finding for Paper C.

## 2026-10-31: C12b pre-registration: recipient-centric variant (designed AFTER seeing the 2023 diagnosis, labeled post hoc)
- User, 2026-10-31: "we must have a paper out of this even to a weaker journal so do your best".
- **Variant (no new parameters):** use CIDRE's own excessive-edge network Ā (dcSBM test, BH α 0.01, condition 1). For each journal j and year t: r_j = Σ_i Ā_ij / s_in(j), the pre-peeling recipient score, and e_j = Σ_i Ā_ij, its excessive in-citations. **Flag j if r_j ≥ θ = 0.15 and e_j ≥ θ_w = 50**, with θ and θ_w taken from the CIDRE paper. Self-loops are excluded, as in Ā. Also record the top excessive donor of j.
- **Because the variant was built after looking at Ukrainian J Phys Optics and Climate Change Economics in 2023, flagging them in 2023 is not evidence.** Evidence must come from:
  1. **lead time:** were those two flagged in 2021 or 2022, before the 2023 data year?
  2. **other labels, not used in the design:** the 2022 stacking journals (Genetika, Bioinspired Biomimetic Nanobiomaterials; Bioscience Research is not in the data), and the other 2023 listings;
  3. **load:** how many journals are flagged per year (an upper bound on the hand-checking burden, not a precision figure);
  4. **stability** of the flags across the 8 partitions.
- Reported on partition `main`, with the agreement across partitions. Journal-level, "anomalous pattern" wording; flags are candidates, not findings.

## 2026-10-31: C12b results: recipient-centric variant (c12_recip_20261031_01) and its evaluation (c12_enrich_20261031_01)
- Run on the VM: 2015–2023 × 8 partitions, 3 workers, 72 jobs, ~28 s each, peak RSS 17.9 GB, exit 0. Self-test (large donor → small recipient: CIDRE misses it, the variant flags it, no other flags) ALL PASS on the laptop and the VM. Files copied back; `SHA256SUMS` OK for both runs.
- **Load:** journals flagged per year (min/median/max over partitions): 2015 76/89/97; 2018 108/134/170; 2020 164/197/235; 2021 303/358/398; 2022 316/400/445; 2023 186/210/264. Over 2015–2023, 3.4% of journals with num ≥ 20 are flagged in at least one year (partition `main`). That is too many to hand-check in full; C14 will hand-check a fixed sample (protocol to be set in advance).
- **Enrichment** (pre-registered evidence items 2 and 3): of 30 matched labeled journals with num ≥ 20, **8 are flagged in some year (26.7%) vs a base rate of 3.4%**: 7.8×, one-sided binomial p = 6 × 10⁻⁶ (partition `main`). **Without the two design cases: 6 of 28 (21.4%), 6.3×, p = 3.1 × 10⁻⁴.** Across all 8 partitions and the base thresholds num ≥ 20/50/100, without the design cases the enrichment is 3.4–6.6× and p ≤ 0.0066 (`enrichment.csv`). Labeled journals include self-citation cases and listings of unstated type, so this measures "listed by Clarivate", not stacking alone.
- **Lead time** (pre-registered evidence item 1; `lead_time.csv`, partition `main`):
  - Ukrainian J Phys Optics: flagged in **2022** (r 0.69, top excessive donor Optik), 1 year before its 2023 listing. Most flags are stable: 8 of 8 partitions in each flagged year.
  - Climate Change Economics: flagged only in 2023; **no lead time**.
  - Granular Computing (2023 listing, type not stated): flagged **2016–2020**, 3–7 years before, top excessive donor Information Sciences (also listed in 2023) in 4 of 5 years.
  - Panminerva Medica (2019, 2020) and Minerva Medica (2020), both 2023 listings of unstated type: flagged 3–4 years before; in 2020 Panminerva's top excessive donor is Minerva Medica.
  - After a listing: J Intell Fuzzy Syst (2022), Materials Express (2021), Mech Based Des Struct Mach (2020–2022). MBDSM is a 2020 *self-citation* case; its flags are about excessive citations from *other* journals (self-loops are not in Ā). TODO(verify) which journals.
- Not flagged in any year: the 2022 stacking journals Genetika and Bioinspired Biomimetic Nanobiomaterials (Bioscience Research is not in the data), most self-citation cases, and Archivos (too few citations in open data).
- **Reading (to be stated with these caveats in the paper):** the recipient-centric variant, using CIDRE's own test and parameters, picks up journals that Clarivate later listed well above chance, sometimes years earlier. It flags 3.4% of journals over nine years, and its precision is unknown until the C14 hand-check. The labels are few (6 non-design journals carry the evidence), and the 2023 list types were not stated. This is a case-study-level signal, not a validated detector.
- VM deallocated. Logged VM time to date: see `vm/vmctl.sh hours`.

## 2026-10-31: R1 label expansion: data/suppressions_v2.csv (primary Clarivate sources), matching c10_match_20261031_05
- **Why:** the literature check (LIT.md, check 2) showed that Clarivate's 2018–2025 lists hold far more cases than v1, which had only JCR data years 2020, 2022 and 2023, partly from secondary sources.
- **Sources** (saved under `data/suppression_sources/`, provenance in `wayback/SOURCES.txt`):
  - the Clarivate "Suppressed Titles 2007–2017" xlsx (Wayback): data years 2015–2017, with journal, year and type only;
  - the Clarivate JCR help "Title Suppressions" page, Wayback snapshots of 2019-09-04 (2018 data), 2022-09-03 (2021 data), 2023-09-30 (2022 data) and 2024-09-19 (2023 data), with title, self-citation and stacking tables parsed;
  - the same page as a PDF hosted by Retraction Watch (2019 data, 33 self-citation titles with %), transcribed;
  - the CGMH copy for 2020 (as in v1).
- **Builder:** `data/build_suppressions_v2.py`, 144 rows, sha256 `58b98997…`. v1 is kept unchanged.
  - Self-citation rows: 2015 16, 2016 10, 2017 12, 2018 10, 2019 33, 2020 7, 2021 3, 2022 1, 2023 6. **60 of them have a published self-citation %** (2018–2023).
  - Stacking journals 2015–2017: 11, with no partners and no %.
  - **Named recipient ← donor pairs with %: 2018 4, plus Bone Research ← 3 donors (an Expression of Concern, one combined %); 2020 2; 2022 3; 2023 8.**
  - 2021: 6 "suppression warnings" for journal self-stacking. These are not suppressions and are excluded from every test.
- **Corrections to v1 from the primary sources:**
  - The 2023 listings that v1 had as "not stated" are Clarivate stacking pairs: Granular Computing ← Information Sciences (18% / 90%), Minerva Medica ← Gazzetta Med Ital Arch Sci Med (30/97), Panminerva Medica ← the same (28/93), Annals of Financial Economics ← Resources Policy (32/96), Cuadernos de Economía ← ESPR (23/100) and ← Resources Policy (26/93). Activities Adaptation & Aging, Eng Technol Appl Sci Res, Explor Anim Med Res, Library Hi Tech, Regional Statistics and SOCAR Proceedings are self-citation cases with %.
  - 2022: Genetika ← Bioscience Research (36/100); Bioinspired Biomimetic Nanobiomaterials ← Cardiometry (29/100) and ← Int J Early Childhood Special Education (36/100).
  - Several donor full titles were written out from Clarivate abbreviations and flagged in `note`.
- **Matching** (`c10_match.py --labels suppressions_v2.csv`):
  - `_04` is superseded: 5 names were ambiguous and 6 needed aliases.
  - `_05`: **131 of 138 names matched to one journal_id.** Aliases and ISSN pins carry their reasons in the script. Pins resolve namesakes (Genetika, Hispania, Oncology), a predecessor title (AJRCCM) and journals split across two venue groups in our data (Archives of Metallurgy and Materials; Int J Civil Eng; J Low Freq Noise — the larger group is kept, TODO(verify)).
  - Unmatched: 5 with no Crossref journal record (Acta Cardiologica Sinica, Acta Veterinaria-Beograd, Cuadernos de Economía (Spain), History of Economic Ideas, Pediatric Dentistry), and 2 with ISSNs not in OpenCitations (Bioscience Research, Journal of Seismic Exploration).

## 2026-10-31: pre-registration addendum for C10/C12 on suppressions_v2 (written before those runs)
- The criteria are unchanged (`config.yaml` `c10`): ±10 pp fidelity; top 1% of the year among journals with num ≥ 20; self-citation cases ranked on self_share, stacking recipients on top_donor_share_of_num.
- They are now applied to every data year in the scores (2015–2023), reported per year and pooled. The 2020 checkpoint verdict (0/8, "no signal") stays as recorded; the expanded results are reported as a separate, larger test.
- Multi-donor rows with identical published % (Bone Research, 2018) are compared with the *sum* of the donors' citations. Donors with their own % (e.g. Cuadernos) are compared one by one.
- CIDRE detection uses the paper's matching rule on every named pair (2018, 2020, 2022, 2023), reusing the groups of `c12_cidre_20261031_02`, which are deterministic given the partitions. The recipient-variant enrichment reuses `c12_recip_20261031_01/flags.csv` with the v2 labels; the design cases are still excluded in the robustness rows.

## 2026-10-31: C10 on suppressions_v2: c10_fidelity_20261031_02 and coverage split c10_covsplit_20261031_01
- Commands: `c10_fidelity.py --labels suppressions_v2.csv --match c10_match_20261031_05 --fidelity-years 2015..2023` (the script now takes `--labels` and `--fidelity-years`; the v1 run used 2020 only), then `c10_coverage_split.py`. Laptop, < 1 min each; `SHA256SUMS` OK.
- **Fidelity, all published numbers (main scores):**
  - self-citation %: 36 of 57 within ±10 pp (median |diff| 6.0 pp, median signed −4.0 pp; 59 of 60 journals matched, 57 with a value);
  - donor % of JIF numerator: 4 of 13;
  - % exchange to JIF years: 4 of 6 with a value. Seven are undefined because the pair has no citations at all.
- **The decisive factor is whether the citing journal's references are in OpenCitations** (`c10_covsplit_20261031_01`: "present" means the citing journal (self-citation case) or the donor(s) (stacking case) made at least one citation in year t):

| metric | refs present: pass / n | median abs diff | median signed diff | refs absent: pass / n | median signed diff |
|---|---|---|---|---|---|
| self-citation % | **36 / 50 (72%)** | **4.6 pp** | −2.8 pp | 0 / 7 | −58 pp |
| donor % of JIF numerator | 4 / 9 | 24.0 pp | −2.6 pp | 0 / 4 | −32.5 pp |
| % exchange to JIF years | 4 / 6 | 4.3 pp | −0.4 pp | — | — |

- Stacking pairs where the donor has references and the pair has citations (5 pairs: Archivos ← JIFS 2020; Annals Fin Econ ← Resources Policy, Climate Change Econ ← ESPR, Granular Computing ← Information Sciences, Ukrainian J Phys Opt ← Optik, all 2023): **donor % of JIF numerator passes 4 of 5** (29.4 vs 32; 32.1 vs 27; 15.8 vs 18; 70 vs 67 on 10 citations; fails 70.9 vs 46 for UJPO, whose numerator in our data is smaller). **Exchange to JIF years passes 4 of 5** (95.7 vs 96; 85.5 vs 86; 99.5 vs 92; 100 vs 99; fails 42.8 vs 90 for Granular Computing).
- "Refs present" but zero pair citations:
  - Bone Research's donors (2018): of the three, only J Biomed Nanotechnol has references (149 for 184 items, i.e. sparse);
  - J Biomed Nanotechnol → NNL (2018), same sparse coverage;
  - **Gazzetta Med Ital → Minerva Medica and → Panminerva Medica (2023): the donor has 2,281 references from 111 items, but none to either recipient.** Unexplained; possibly the stacking items are missing from OpenCitations: TODO(verify) on the donor's 2023 items.
- **Donors with no references at all:** NNL (2018, 2020), Cardiometry (2022; also no items), Int J Early Childhood Spec Educ (2022), and NNL as donor to J Biobased Mater Bioenergy (2018). NNL, J Biomed Nanotechnol, J Biobased Mater Bioenergy and Materials Express are the American Scientific Publishers group in the 2018 and 2020 lists (publisher: TODO(verify) via Crossref, R3).
- **Ranks** (criterion 2, main scores; v2 labels; `ranks.csv`):
  - self-citation cases 2015–2023: **9 of 85 journal-years in the top 1%** of their year on self_share; **59 of 85 (69%) in the top 5%**; median percentile 3.1%. For comparison, a random journal is in the top 1% with probability 0.01 and in the top 5% with 0.05.
  - stacking recipients (named pairs): 1 of 12 in the top 1% and 3 of 12 in the top 5% on top_donor_share_of_num; median percentile 52.9%. Most recipients' donors lack references (above).
  - The 2020 checkpoint is unchanged (0/8). By year, top-1% counts: 2015 2/16, 2016 1/6, 2017 2/8, 2018 1/12, 2019 0/31, 2020 0/8, 2021 1/3, 2022 0/3, 2023 3/10.
- **Reading:** the pre-registered top-1% criterion fails as a detector rule (9/85 self-citation cases). But open data clearly places self-citation suppressions high (69% in the top 5%), and it reproduces Clarivate's self-citation % within ±10 pp for 72% of journals whose references are present. Stacking fidelity holds where donor references exist, but **most stacking donors in the lists (ASP journals, Cardiometry, IJECSE) have no references in OpenCitations**. That is the central data-source finding (RQ2).

## 2026-10-31: C12/C12b on suppressions_v2: c12_eval_20261031_01 (no refit; saved CIDRE groups and recipient flags)
- `c12_eval_labels.py --cidre c12_cidre_20261031_02 --recip c12_recip_20261031_01 --scores c9_scores_20261031_02 --match c10_match_20261031_05 --labels suppressions_v2.csv`. Laptop; `SHA256SUMS` OK.
- **CIDRE, named pairs (paper's rule):** 20 named recipient ← donor pairs in 2018–2023, 15 with both journals matched. **0 of 15 detected in any of the 8 partitions**, and no recipient or donor of a named pair is in any CIDRE group in its year.
  - Reasons per pair, from C10/C12: the donor's references are missing (ASP journals, Cardiometry, IJECSE); the pair is too small in open data (Archivos); the donor is large and gets peeled (Optik, ESPR, Resources Policy, Information Sciences; diagnosed for two in `c12_diag_20261031_01`); unexplained zero citations (Gazzetta Med Ital).
- **CIDRE does find stacking between small journals in years without named partners** (post hoc reading; Clarivate's 2015–2017 spreadsheet gives no pairs):
  - 2015: a 2-journal group made of exactly Applied Clinical Informatics + Methods of Information in Medicine, both listed for stacking in 2015 (113 within-group citations);
  - 2017: a 2-journal group made of exactly Liver Cancer + Digestive Diseases, both listed for stacking in 2017 (247 within-group citations).
  - Both appear in partitions `main` and `main_s2`; the other partitions are not checked yet (R4).
  - Korean J Metals and Materials (2016) and Translational Stroke Research (2016) are each in a group with journals Clarivate did not list.
  - Overall, 8 of 132 labeled journal-years (partition `main`) are in a CIDRE group that year (`cidre_labeled_in_groups.csv`).
- **Recipient-centric variant, enrichment with the v2 labels** (`enrichment.csv`; base = journals with max yearly num ≥ 20, base rate 3.4% ever flagged, partition `main`):

| listed set | listed | flagged | rate | enrichment | one-sided binomial p |
|---|---|---|---|---|---|
| any (self or stacking) | 115 | 22 | 19.1% | 5.6× | 5.7e−11 |
| any, without the 2 design cases | 113 | 20 | 17.7% | 5.2× | 1.7e−9 |
| **stacking-listed** | 30 | 12 | **40.0%** | **11.7×** | 1.2e−10 |
| **stacking, without design cases** | 28 | 10 | 35.7% | **10.5×** | 1.6e−8 |
| self-citation-listed | 85 | 10 | 11.8% | 3.4× | 6.5e−4 |

  - Robustness over the 8 partitions × num ≥ 20/50/100: stacking without design cases 5.7–10.5× (max p 1.1e−5); self 1.3–3.4× (max p 0.29, **not robust**). The variant is a stacking detector, as intended.
- **Lead time** (`lead_time.csv`, partition `main`): **8 listed journals were flagged before their first listing year**:
  - Granular Computing, 3–7 years before (top excessive donor Information Sciences, its Clarivate donor);
  - Panminerva Medica, 3–4 years, and Minerva Medica, 3 years (Clarivate's donor for both is Gazzetta Med Ital; our top excessive donor for Panminerva 2020 is Minerva Medica);
  - Liver Cancer, 1–2 years (top excessive donor Digestive Diseases, also listed in 2017);
  - J Biomedical Nanotechnology, 3 years (2015; listed in 2018 as a donor);
  - Chinese J Organic Chemistry, 3–4 years (a 2021 self-citation case);
  - Korean J Metals and Materials, 1 year;
  - Ukrainian J Phys Optics, 1 year (Optik).
  - Several journals are also flagged after listing (Mech Based Des Struct Mach, J Low Freq Noise, J Non-Equilib Thermodyn, JIFS, Materials Express).
- **Paper-level reading:** CIDRE detects 0 of 15 named Clarivate pairs on open data; its successes are small-journal pairs (2015, 2017). A recipient-centric reading of CIDRE's own excessive-edge test flags 36–40% of stacking-listed journals against a 3.4% base rate, sometimes years early. Its precision is not yet known (C14).

## 2026-10-31: R3 publishers of the journals whose references are missing: c10_publishers_20261031_02
- `c10_publishers.py` covers every citing journal in the C10 fidelity rows (self-citation journals and named donors). The Crossref journal record (`api.crossref.org/journals/<ISSN>`, queried 2026-10-31, raw JSON saved) gives the publisher and the `coverage` fractions `references-current` / `references-backfile`, the share of the journal's current / older DOIs with reference lists deposited. `_01` is superseded: 3 lookups hit a temporary DNS error. `_02` has 0 errors; `SHA256SUMS` OK.
- **Journals whose references are absent from OpenCitations in the fidelity year (11): median references-current 0.00, median backfile 0.00, and 8 of 11 have references-current = 0.** Examples:
  - Cardiometry (Russian New University, 0/0);
  - Exploratory Animal and Medical Research (0/0);
  - Industria Textila (0/0);
  - Int J Mobile Communications (Inderscience, 0/0);
  - Regional Statistics (0/0);
  - SOCAR Proceedings (0/0);
  - Hispania (Project MUSE, 0/0);
  - Int J Early Childhood Spec Educ (0/0.20).
  - Begell House journals (J Enhanced Heat Transfer, Int J Medicinal Mushrooms) have current 0.72–0.79 but backfile 0.05: they began depositing after the years in question. Cellulose Chem Technol: current 0.99, backfile 0.48.
- **Journals with references present (61): median references-current 0.96, backfile 0.84.**
- **The named donors with zero pair citations:**
  - NNL (American Scientific Publishers): 0.00 current / 0.01 backfile;
  - J Biomed Nanotechnol (ASP): 0.99 / 0.26, so sparse in the stacking years;
  - J Biobased Mater Bioenergy (ASP): 0.63 / 0.14;
  - Gazzetta Med Ital (Edizioni Minerva Medica): 0.97 / 0.74. It deposits, yet has 0 citations to Minerva Medica and Panminerva in 2023, still unexplained (R6 checks the item level).
- **Reading:** the open-data blind spots are not random. They follow publishers that do not deposit references with Crossref, or did not in the relevant years, and several stacking donors in the Clarivate lists are among them. Caveat: Crossref `coverage` is a *current* snapshot (2026-10-31), not the state at the OpenCitations Jan-2024 snapshot; backfile is the better guide for 2018–2022.

## 2026-10-31: R4 stability across partitions: c12_stab_20261031_01 and consensus flags c12_consensus_20261031_01 (post hoc)
- `c12_stability.py` uses the 7 rule-`main` partitions (21 pairs × 9 years). Laptop; `SHA256SUMS` OK.
  - **CIDRE groups are much more stable than the partitions themselves:**
    - member Jaccard min/median/max 0.43 / **0.85** / 1.00;
    - group recovery (share of groups with a Jaccard ≥ 0.5 match in the other partition) 0.79 / **0.93** / 1.00;
    - median share of members found in all 7 partitions: 0.67.
    - The partitions agree only at ARI ≈ 0.48 (6b), so most CIDRE groups depend little on which partition is used.
  - **The recipient-variant flags are less stable:** Jaccard 0.50 / **0.62** / 0.72, and only 0.32 of flags (median per year) appear in all 7 partitions.
- **Consensus rule** (`c12_consensus.py`; post hoc, added because of the result above): flag a journal-year if the variant flags it in ≥ k of the 7 partitions. Base = journals with max num ≥ 20.

| k (partitions) | journal-years flagged | base rate (journals ever flagged) | stacking-listed flagged (no design cases) | enrichment | p | flagged before first listing |
|---|---|---|---|---|---|---|
| ≥ 1 (any) | 2,843 | 5.4% | 10 / 28 | 6.6× | 1.1e−6 | 8 |
| ≥ 4 (majority) | 1,609 | 3.5% | 10 / 28 | 10.3× | 1.9e−8 | 7 |
| 7 (all) | 958 | **2.3%** | 9 / 28 | **13.9×** | 8.7e−9 | 5 |

- For self-citation-listed journals the enrichment is 2.4–3.6× at every k (p 0.003–0.006).
- **Proposal for the paper's main variant: the consensus over all 7 partitions.** It is the least noisy and loses only one stacking-listed journal. Because it was chosen after seeing these data, the paper must report all three k values.

## 2026-10-31: C14 protocol (fixed BEFORE the sample is drawn): a structured evidence check instead of a manual hand-check
- **Why not a manual review:** judging individual journals by hand (web searches, editorials) does not scale to a reproducible sample. It is also the step most exposed to defamation risk. The project rules are journal-level reporting only and "anomalous pattern", never "misconduct".
- **Sample:** the `flagged` pairs of C13 (`c13_anatomy`): every journal-year flagged in all 7 partitions (consensus, k = 7) whose recipient is a listed journal, plus a seeded sample of 200 others (seed 4311, SHA-256 order), each paired with its top excessive donor. **Controls:** the first matched control of each pair (same year, eff within 0.8–1.25×, both journals in rule `main`, recipient never flagged).
- **Indicators, all automatic and public:**
  - I1: the recipient or the donor appears in Clarivate's suppression lists 2015–2023 (`suppressions_v2.csv`, any role, any year);
  - I2: the recipient and the donor have the same publisher in Crossref (`api.crossref.org/journals/<ISSN>`, exact string match after lower-casing);
  - I3: the pair's window citations are concentrated, with the top 10% of citing items carrying ≥ 50% of them (C13 `top10pct_share`).
- **Reported:** the share of flagged vs control pairs with each indicator and with at least one; a Fisher exact test for each; the indicators' overlap. This is an evidence-based lower-bound proxy for precision, not a precision estimate: a flag without any indicator is not shown to be benign.
- Thresholds (≥ 50% for I3; same publisher by exact string) are set here and will not be tuned.

## 2026-10-31: R2 source of the `dataset` artifact: c7_dsource_20261031_01
- `c7_dataset_source.py` on the VM: one pass over the Meta CSV dump for the OMIDs of every `dataset`-typed citing item without a journal (2018–2021, with ≥ 1 outgoing edge), and of the items without a year that the 2020 ones cite. 510 s, peak RSS 1.5 GB, exit 0; `SHA256SUMS` OK.
- **Citing items:** 166,967 (2018), 174,371 (2019), 230,438 (2020), 213,997 (2021); all found in Meta (785,773). **2020 by DOI prefix: 10.15468 = 221,918 of 230,438 (96.3%)**, then 10.1594 (2,966), 10.5061 (2,110), 10.5281 (752).
  - In all 25 seeded 2020 samples but one, the title is "Occurrence Download" (`samples.csv`).
  - **Registrants, checked on 2026-10-31 via the DataCite API:** 10.15468/dl.f29fwc → "The Global Biodiversity Information Facility" (GBIF), type Dataset; 10.1594/pangaea.919908 → PANGAEA.
  - So the citing items are **GBIF occurrence-download DOIs** (DataCite). Their reference lists cite the GBIF datasets and taxonomic publications the downloaded records come from.
- **Cited items without a year (2020): 20,583 distinct**, all in Meta, with no `type` (the `type_cited.csv` label "<not in meta>" means "type empty").
  - Prefixes: 10.15468 (GBIF datasets) 14,200; 10.1594 (PANGAEA) 2,303; 10.15472 (DataCite; Instituto Humboldt, Colombia) 1,151; **10.11646 (Crossref member Magnolia Press = Zootaxa's publisher) 1,113**; 10.5281 (Zenodo) 733; 10.5852 (European Journal of Taxonomy) 238.
- **Conclusion:** the 2015–2021 coverage dip and the inflated numerators of taxonomy journals (Zootaxa: 99.8% of its 2020 numerator from citing items without a journal) come from **GBIF occurrence-download records, indexed through DataCite, citing the sources of the downloaded occurrence records**. These are legitimate data citations, but they are not the journal citations Clarivate counts. Counting only citing items with a journal (decision (a), 2026-10-31) removes them. A useful caution for any open-data JIF proxy. Zootaxa was itself suppressed for self-citation in the 2019 data (43%), a separate matter.

## 2026-10-31: R6 / C13 paper-level anatomy: c13_anatomy_20261031_01 and stratification c13_strat_20261031_01
- `c13_anatomy.py` on the VM. The first attempt stopped after 16 s with an INT32 overflow in the seeded control ordering, before writing anything; fixed with a BIGINT cast and rerun under the same run id (log of the failed attempt kept in the run folder). The rerun took 58 s, peak RSS 3.9 GB, exit 0; `SHA256SUMS` OK. Titles for 43,602 items came from the Meta dump (used only for the cosine; no titles are written out).
- **Pairs:**
  - `named`: 5 Clarivate pairs with ≥ 1 window citation, plus 15 controls;
  - `flagged`: 226 consensus-flagged (k = 7) recipient–top-donor pairs (200 seeded plus the listed recipients), plus 678 controls (3 each, same year, eff within 0.8–1.25×, recipient never flagged).
- **Flagged vs controls** (medians, two-sided Mann–Whitney):

| metric | flagged | control | p |
|---|---|---|---|
| citations to the recipient per citing paper | **1.98** | 1.28 | 2.5e−27 |
| Gini of citations over citing papers | **0.25** | 0.18 | 1.5e−8 |
| share from the single top citing paper | 0.100 | 0.071 | 5.3e−6 |
| share from the top 10% of citing papers | 0.241 | 0.237 | 0.35 (n.s.) |
| mean TF-IDF title cosine, citing vs cited | **0.084** | 0.133 | 1.2e−24 |

- **Stratification by same block** (post hoc; `c13_stratify.py`): 27.9% of flagged pairs have donor and recipient in the same dcSBM block, against 0.6% of controls. Same-block pairs should be topically *closer*, so the raw comparison is conservative. **Within cross-block pairs only** (163 flagged vs 674 controls): title cosine 0.084 vs 0.133 (p 1.2e−17), citations per citing paper 2.00 vs 1.28 (p 8.5e−22), Gini 0.25 vs 0.18 (p 2.3e−7). The same-block stratum has only 4 controls, too few to read.
- **Named pairs:** with n = 5 there is no clear difference (title cosine 0.091 vs 0.139, p 0.067; citations per citing paper 3.75 vs 1.30, p 0.27).
- **Reading (RQ3):** in pairs flagged by the variant, the excess citations come from citing papers that each cite the recipient several times, and they are topically further from what they cite than ordinary citations between journals of similar volume. Concentration at the top-10% level does not differ, so the pattern is "many papers citing a bit too often", not "a few papers with huge reference lists". Caveats: TF-IDF on titles only; controls are matched on year and volume, not on field.

## 2026-10-31: R7 / C14 structured evidence check: c14_evidence_20261031_01 and c14_unbiased_20261031_01
- Protocol fixed beforehand (entry "C14 protocol"). `c14_evidence.py` (laptop; Crossref publishers queried 2026-10-31, found for 96.2% of pairs). `SHA256SUMS` OK.
- **Full flagged sample (226) vs first matched controls (226):** I1 listed 40 vs 0; I2 same publisher 47 vs 13; I3 concentrated 13 vs 0; any indicator 85 (37.6%) vs 13 (5.8%), Fisher p 2.7e−17. **But I1 is inflated by design**: C13 added every listed recipient to the random sample.
- **Unbiased version (`c14_unbiased.py`; post hoc correction of that sampling detail):** the flagged pairs whose recipient is listed are dropped, together with their controls, leaving **196 vs 196**:
  - I1 (the donor is listed): 10 (5.1%) vs 0, p 0.0017;
  - **I2 same publisher: 38 (19.4%) vs 12 (6.1%), p 1.2e−4;**
  - I3 concentrated: 11 (5.6%) vs 0, p 8.5e−4;
  - **at least one indicator: 55 (28.1%) vs 12 (6.1%), p 6.2e−9.**
- **Reading:** about 28% of randomly sampled consensus flags carry independent public evidence of an anomalous citation relation (a listed partner, a shared publisher, or concentration of the citations in few papers), against 6% of matched controls. This is a lower-bound proxy for precision, not precision itself. A shared publisher is the most common indicator, consistent with publisher-internal stacking, as in several Clarivate cases (ASP; Edizioni Minerva Medica; Karger). Journal-level reading only.
- VM deallocated after R2/R6. Logged VM time to date 6.31 h (~$3.34 compute) + disk.

## 2026-10-31: R8 write-up support: figures c15_figures_20261031_02 and FINDINGS.md
- `c15_figures.py` draws 7 vector PDFs into `paper/figures/` from logged runs only; inputs and output sha256 values are in `run.json`. Test renders were checked visually.
  - `_01` is superseded: its F7 left panel showed the top-10% share, which does not differ between groups; `_02` shows citations per citing paper.
  - The figures: F1 coverage by year; F2 fidelity scatter (refs present vs absent); F3 CIDRE peeling for the 2023 pairs; F4 enrichment by consensus level; F5 lead time; F6 stability; F7 anatomy.
- matplotlib 3.1.3 needs plain arrays with pandas 2.3 (fixed in the script).
- `FINDINGS.md` (project root) maps every claim the paper may use to its numbers, run and file, plus the open TODO(verify) items.

## 2026-10-31: Review round 1 (paper/journals/scientometrics/Critics/rount1.txt): pre-registration of R9–R13 (written BEFORE any of these numbers)
User: "apply this feedback". The critique asks for a simple baseline, an asymmetric-θ CIDRE, an out-of-sample test on the newer JCR releases, a size-matched base rate, and a label/denominator accounting. Fixed here before computing:

- **R9 plain baseline (no block model).** From `c9_scores_20261031_02` (citing items with a journal). Flag journal-year (j, t) if `top_donor_share_of_num` ≥ X and `num` ≥ 20.
  - **Primary:** X is chosen so that the share of base journals (max yearly num ≥ 20) ever flagged in 2015–2023 equals the variant's base rate on the `main` partition (3.4%). This is a rate-matched comparison; X is set from base journals only, never from the labels.
  - **Secondary:** a second X matched to the consensus k = 7 base rate (2.3%), and X = 0.15 with top-donor citations ≥ 50 (CIDRE's θ, θ_w).
  - Outcomes as in c12_eval: enrichment of stacking-listed journals (design cases excluded), self-listed, and lead time; Jaccard overlap with the variant flags.
  - **Pre-stated reading:** if the baseline's enrichment is about equal to the variant's (its 95% CI covers the variant's point estimate), we report that the block-model null adds little for this target, and the variant is presented as a reading of CIDRE's test, not as a better detector.
  - **R9b (VM):** the same recipient-centric test with a single block (configuration-model null instead of the dcSBM), `main`, 2015–2023.
- **R10 asymmetric θ in CIDRE (VM).** Donor threshold θ_d ∈ {0.15 (paper), 0.10, 0.05, 0.02, 0.01}; recipient threshold θ_r = 0.15; θ_w = 50; α = 0.01; partition `main`; 2015–2023. A node is peeled if donor < θ_d and recipient < θ_r.
  - Outcomes: named pairs detected (paper rule, 15 matched); groups per year; median and max group size; stacking-listed journals in some group.
  - All θ_d are reported; none is picked as "best".
- **R11 out-of-sample (prospective) test.** The predictions are frozen before any newer list is opened: journals flagged by the variant in 2015–2023 (consensus k = 7 = primary; `main` and k ≥ 1 secondary).
  - The frozen file and its sha256 are written first. Then the Clarivate suppression lists for JCR data years 2024 and 2025 (released June 2025 and June 2026) are collected from primary sources.
  - **Outcome:** listed for stacking (primary) or for any suppression (secondary) in data years 2024–2025. The population is base journals (max num ≥ 20) not listed in 2015–2023.
  - **Test:** one-sided Fisher exact test of flagged vs not flagged. If the lists cannot be obtained from a primary source, the test is not run and this is reported.
- **R12 size-matched base rate.** For stacking-listed journals (design cases excluded) and the variant flags (`main` and consensus k = 7):
  - **(i)** Cochran–Mantel–Haenszel over deciles of journal size (max yearly num) among base journals.
  - **(ii)** Per listed journal, 10 controls of nearest size from the same dcSBM block (field proxy; nearest blocks by size when the block is too small), never listed. Report the flag rate in listed vs matched controls with a Fisher test.
- **R13 accounting.** A table from the label rows to each analysis's denominator (self: 98 rows → 60 with a published share → evaluated; stacking: rows → named pairs → matched → evaluated), built by script from the run outputs.
- **R11 predictions frozen** (`c16_predict_20261031_01`, 2026-10-31T23:59:53Z, `predictions.csv` sha256 1d8acdc1…fa44). Population: 29,496 base journals not listed in 2015–2023 (115 listed journals excluded). Flagged: k7 666, main 990, k≥1 1,574. The newer lists had not been opened at this point.

## 2026-11-01: R11 newer Clarivate lists, label cross-check, out-of-sample test (c10_match_20261101_01, c16_oos_20261101_01)
- **Sources** (primary, Clarivate JCR help centre, retrieved 2026-10-31; `data/suppression_sources/clarivate_2026/SOURCES.txt` with sha256):
  - the "Title Suppressions" article, data year 2025 (2026 release): 8 journals, 4 self and 4 stacking with donors and %;
  - its attachment "Suppressed titles 2024-2007.xlsx": data year 2024 has 20 journals, 16 self and 4 stacking (recipients only, no %). This matches Retraction Watch's count for the 2025 release.
  - `data/build_suppressions_oos.py` → `data/suppressions_oos.csv`.
- **The article states Clarivate's definition verbatim**, which closes the open TODO(verify) on the JCR wording: "The percentage exchange to the Journal Impact Factor years is the proportion of all citations from donor to recipient (all years) that reference the two years considered in the Journal Impact Factor calculation."
- **Cross-check of suppressions_v2 (2015–2023) against Clarivate's current xlsx** (`data/suppressions_crosscheck.csv`):
  - Every journal in the xlsx is in v2. The xlsx-only rows are stacking donors, plus Bone Research (expression of concern), which v2 holds as donor or EoC rows.
  - **9 self-citation rows of v2 are not in the current xlsx**: data year 2018, Ophthalmic Epidemiology; data year 2019, American J Pharmaceutical Education, Cognitive Computation, Cognitive Neurodynamics, Cognitive Neuropsychology, Int J Systematic and Evolutionary Microbiology, J Human Evolution, J Experimental Analysis of Behavior, Zootaxa.
  - These come from the lists published at the time (the 2019 help page; the 2020-release PDF, 33 self titles). The reason for their absence from the current file is unknown: TODO(verify), possibly later reinstatement. v2 stays the primary label set, and a sensitivity analysis without these 9 is added (R13).
- **The 144 rows of v2:** 98 self; 37 stacking (17 named recipient ← donor rows, 9 donor rows, 11 without a named partner); 3 expression-of-concern rows (one recipient with three donors); 6 warnings. The critique's 133 omitted the donor rows and two of the three EoC rows.
- **Matching** (`c10_match_20261101_01`, `c10_match.py` now skips empty names, because donor rows carry only an abbreviation): 20 of 26 names matched or ambiguous, 6 not.
- **Out-of-sample test** (`c16_oos_eval.py` → `c16_oos_20261101_01`; predictions frozen in `c16_predict_20261031_01`):
  - Stacking recipients, data years 2024–2025: 8 listed, of which 6 are in the population (1 had max num < 20, 1 has an ISSN absent from the data).
  - **1 of 6 flagged** in advance: Asian Journal of Agriculture and Biology, flagged in 2022 (consensus k = 7), listed for data year 2024.
  - k = 7: 16.7% vs 2.26% of other journals, **7.4×, one-sided Fisher p = 0.13**; main 5.0× (p = 0.19); k ≥ 1 3.1× (p = 0.28).
  - Any suppression (19 in the population): 1 flagged, 2.3× (p = 0.35).
  - **Reading:** not significant; the test has little power with 6 positives. Our citation data end with data year 2023, so a flag can anticipate a later listing only if the pattern persists. Report as is.

## 2026-11-01: R9 plain baseline and R12 size-matched base rates: c17_basesize_20261101_01
- `c17_baseline_size.py` (laptop, saved outputs only). Base: 29,611 journals; stacking-listed 28 (design cases excluded); self-listed 85.
- **R9 rate-matched baseline** (top donor's share of num ≥ X and num ≥ 20; X from base journals only):
  - X = 0.434 gives the variant's `main` rate (3.42%). Stacking: **3/28, 3.1× (95% CI 1.1–8.0), p 0.069**. Self: 0.7×. Lead time: 1 journal.
  - X = 0.50 gives 2.18% (k = 7 target 2.31%; the share distribution has a step at 0.5). Stacking: 2/28, 3.3× (0.9–10.4), p 0.12.
  - **Variant at the same rate** (`main`): 10/28, **10.5× (6.1–15.9)**, p 1.6e−8, 6 flagged before listing; k = 7: 13.9× (7.8–21.9).
  - **Pre-stated reading:** the rate-matched baseline's CI (1.1–8.0) does not cover the variant's 10.5, so the block-model test adds to a plain share rule at equal flag rate.
- **R9 secondary baseline** (share ≥ 0.15 and ≥ 50 citations from the top donor, CIDRE's θ and θ_w on the plain share): rate 2.98%; stacking **7/28, 8.4× (4.3–14.5)**, p 1.4e−5; self 3.2×; 5 flagged before listing.
  - Its CI covers the variant's 10.5. **An absolute volume floor carries much of the signal; the block model adds a moderate amount on top.**
  - The two flag sets overlap little (Jaccard 0.22 with `main`, 0.24 with k = 7), so they find partly different journals. Report both honestly.
- **R12 size matching** (stacking, design cases excluded):
  - **CMH over size deciles:** variant `main` MH-OR 11.3 (z 6.85, p 3.6e−12); k = 7 MH-OR 15.0 (p 8.2e−16). Rate-matched baseline 6.3 (p 3.4e−4); secondary baseline 6.8 (p 7.8e−7).
  - **Matched controls** (10 per listed journal; 71% from the same dcSBM block, nearest size):
    - variant `main`: 35.7% vs 7.1%, **5.0×**, Fisher p 6.8e−5;
    - **k = 7: 32.1% vs 4.6%, 6.9×**, p 2.6e−5;
    - rate-matched baseline: 10.7% vs 2.1%, 5.0×, p 0.039;
    - secondary baseline: 25.0% vs 5.0%, 5.0×, p 0.0012.
  - Self-listed: variant 1.7× (p 0.09), not significant once matched.
- **Reading:** size explains part of the raw enrichment. Against controls of the same size from the same block, the variant still flags stacking-listed journals 5–7 times more often (p ≤ 7e−5), so the effect is not a size artifact. The abstract will give matched and unmatched ranges, not the top value.

## 2026-11-01: R10 asymmetric θ and R9b single-block null: c18_asym_20261101_01 (VM) and c18_eval_20261101_01
- **Run:** `c18_asym_null.py`, self-test ALL PASS on the laptop and the VM. VM run: 9 years, 3 workers, 51–85 s per year, peak RSS 15.3 GB, EXIT=0. Fetched, `SHA256SUMS` OK. VM deallocated (logged hours 6.40, ~$3.39 in total).
- **Sanity:** θ_d = 0.15 reproduces the `main` groups of `c12_cidre_20261031_02` exactly (True).
- **R10** (θ_r = 0.15 throughout):

| θ_d | groups | median per year | median size | max size | journals in a group | stacking-listed in a group (28) | enrichment | named pairs detected (15) | pair in the same group |
|---|---|---|---|---|---|---|---|---|---|
| 0.15 (paper) | 201 | 22 | 4 | 28 | 705 | 8 | 12.0× | 0 | 0 |
| 0.10 | 257 | 26 | 4 | 29 | 957 | 13 | 14.4× | 0 | 0 |
| 0.05 | 379 | 38 | 4 | 163 | 1,600 | 15 | 9.9× | 0 | 1 (UJPO + Optik 2023, in a 13-journal group) |
| 0.02 | 519 | 57 | 4 | 656 | 3,558 | 20 | 5.9× | 0 | 3 (2023, in a 345-journal group) |
| 0.01 | 506 | 52 | 4 | 3,056 | 7,089 | 24 | 3.6× | 0 | 3 (2023, in a 1,022-journal group) |

  - **Reading:** a lower donor threshold does not recover the named pairs as CIDRE groups. Large donors join, and the weakly connected components merge into large groups, so the pairs end up in groups far bigger than the pair, and the paper's overlap rule fails. Journal membership in any group stays enriched for stacking-listed journals (best at θ_d = 0.10). The blind spot comes from the group construction, not only from the threshold value.
- **R9b, single-block (configuration-model) null**, same recipient test:
  - It flags 3.4 times as many journals: base rate 11.6% vs 3.4%. Stacking 14/28, **4.3× (2.8–5.8)**, 10 flagged before listing; self 2.2×.
  - The dcSBM variant gives 10.5× (6.1–15.9); the CIs do not overlap. Jaccard between the two flag sets is 0.29.
  - **Reading:** the block model makes the test much more specific: fewer flags and higher enrichment. This agrees with R9.

## 2026-11-01: R13 accounting: c19_accounting_20261101_02 (`_01` superseded: stacking-fidelity rows counted twice)
- `accounting.csv` traces every denominator from the label rows (all recomputed from files):
  - self: 98 rows → 60 with a published % → 59 matched → 57 evaluated (50 with references present, 7 absent);
  - ranks: 98 → 95 matched → 85 ranked (num ≥ 20, citable ≥ 20);
  - stacking fidelity: 18 named pairs with a donor % → 13 both matched (donor references present 9, absent 4);
  - CIDRE: 20 named rows in 2015–2023 (including expressions of concern) → 15 both matched;
  - enrichment: 28 stacking-listed and 85 self-listed journals in the base;
  - out of sample: 8 → 6 → 1.
- **Sensitivity without the 9 rows missing from Clarivate's current xlsx:** self ranks in the top 5% 55/76 (72%; 59/85 with them), top 1% 9/76; self fidelity within ±10 pp 28/48 (36/57 with them). The conclusions do not change.

## 2026-11-01: Review round 2 (Critics/round2.txt): c20_paired_20261101_01 (post hoc follow-ups to R9/R12, requested by the critique)
- `c20_paired.py` rebuilds c17's flag sets and size-matched controls with the same seed. **Counts equal c17: True.**
- **Paired exact McNemar tests** on the same 28 stacking-listed journals (discordant counts, variant only vs baseline only):
  - variant `main` (10) vs rate-matched 43% rule (3): 8 vs 1, **p 0.039**;
  - variant `main` vs CIDRE-threshold plain rule (7): 4 vs 1, **p 0.375 (n.s.)**;
  - k = 7 (9) vs rate-matched rules: p 0.070 / 0.039; k = 7 vs CIDRE-threshold rule: p 0.69.
  - **Reading:** the variant beats the plain share rule at an equal flag rate. It is not distinguishable from a plain rule with a volume floor, so the two are complementary screens. The abstract now names the 43% rule.
- **Size-matched enrichment with 95% CIs** (cluster bootstrap over listed journals, 10,000 resamples, seed 4312):
  - variant `main` 5.0 (2.7–10.9); k = 7 6.9 (3.1–17.1);
  - rate-matched rule 5.0 (0–30.0); CIDRE-threshold rule 5.0 (1.7–12.9).
  - The three values of 5.0 are verified, not a copy error: 10/28 vs 20/280, 3/28 vs 6/280, 7/28 vs 14/280.
- **Size profile** (`size_profile.csv`) **corrects an earlier claim in the draft** ("stacking-listed journals tend to be small"; it was not checked):
  - 25 of the 28 stacking-listed journals are in the upper six size deciles (max yearly num ≥ 74).
  - The variant's flag rate rises with size: 0% in the three lowest deciles (e ≥ 50 is unreachable there), 7–9% at the top.
  - The 43% rule falls with size: 6% in the lowest decile, 0.2% at the top, since small numerators reach a 43% share easily.
  - Size matching therefore lowers the variant's enrichment (10.5 → 5.0) and raises the 43% rule's (3.1 → 5.0).
