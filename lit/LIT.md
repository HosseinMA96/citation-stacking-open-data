# Project C literature (gate C1)

Started 2026-10-28. Every DOI below was resolved through the Crossref API on 2026-10-28 (status OK). The citing-works list comes from OpenAlex (`cites:W3178476290`; 53 works citing CIDRE as of 2026-10-28). The abstracts were read through OpenAlex and PMC.

## Closest prior work

**Kojaku, Livan & Masuda (2021). Detecting anomalous citation groups in journal networks. *Scientific Reports*. doi:10.1038/s41598-021-93572-3. Method name: CIDRE.**
This paper already does the core of the original Project C. Details, read from the PMC full text:
- **Data:** Microsoft Academic Graph (MAG) snapshot of 2020-01-30: 231,926,308 papers from 48,821 journals. Yearly journal networks for 2000–2019; groups detected in 2010–2019 (184 groups).
- **Labels:** JCR suspensions since 2007 (227 journals). The 46 suspended journal pairs were merged into 22 groups, each assigned to the year before suspension.
- **Result:**
  - 12 of the 22 groups were detected at least once, about 55%. The Fig. 2 caption says 11 "in the year of the suspension or before", which disagrees with the text.
  - 10 groups were detected earlier than JCR suspended them.
  - **Community detection (Leiden, Infomap, dcSBM) matched none of the suspended groups.**
- **Code:** github.com/skojaku/cidre (also on PyPI as `cidre`).
- **Stated limitations:**
  - no ground truth beyond JCR;
  - the 159 new groups are unvalidated;
  - non-malicious causes such as geography or editorial preference;
  - manual inspection is costly;
  - MAG parsing errors;
  - the threshold θ = 0.15 was chosen to match JCR.
- **Future work they suggest:** author–journal networks.

## Other relevant work (verified DOIs)
| Ref | DOI | Relevance |
|---|---|---|
| Liu et al. (2022), Deep Graph Learning for Anomalous Citation Detection, *IEEE TNNLS* | 10.1109/tnnls.2022.3145092 | Paper-level anomalous citations (GNN plus text); not journal groups |
| Liu et al. (2024), Anomalous citations detection in academic networks, *AI Review* | 10.1007/s10462-023-10655-5 | Paper-level "unreasonable citations" (cited paper not relevant to the citing paper); ACTION framework |
| Liu et al. (2026), Designing a Computational Framework for Identifying Suspicious Citation Groups in Heterogeneous Academic Networks, *Inf. Syst. Frontiers* | 10.1007/s10796-026-10770-y | Group-level graph learning. **Abstract not available; read the full text before claiming novelty** |
| Daly et al. (2026), OntoTrack: linked open data … mutual citation networks, *Frontiers in Computer Science* | 10.3389/fcomp.2026.1636097 | Ontology and linked-open-data architecture for unnatural citations; a system paper, apparently without a JCR validation (TODO(verify) the full text) |
| Łyko & Kozierkiewicz (2026), Detecting Citation Cartels: A Preliminary Review, *LNCS* | 10.1007/978-3-032-36871-3_3 | Review; read it for the method landscape |
| Ibrahim et al. (2025), Citation manipulation through citation mills and pre-print servers, *Scientific Reports* | 10.1038/s41598-025-88709-7 | Author-level citation mills |
| Besançon et al. (2024), Sneaked references, *JASIST* | 10.1002/asi.24896 | Fabricated reference metadata; relevant to data-quality caveats |
| Di Scala et al. (2025), Screening Crossref for integrity issues, *JCDL 2025* | 10.1109/jcdl67857.2025.00023 | Large-scale integrity screening on open metadata |
| Secchi (2023), A Simple Model of Citation Cartels, *Springer Proc. Complexity* | 10.1007/978-3-031-34920-1_3 | Simulation model |

Still to add (TODO): Clarivate suppression policy documents; classic coercive-citation and journal self-citation papers (e.g., Wilhite & Fong 2012; Chorus & Waltman 2016). Find and verify each before citing.

## Gate C1 result (2026-10-28): the original Project C is NOT novel

Journal-level detection of stacking groups validated against JCR suspensions was done by CIDRE (2021), with recall of about 55%. Our planned Leiden-CPM step is exactly the kind of community detection CIDRE found useless for this task.

### Gaps that remain (candidate new angles)
1. **Out-of-sample, open-data replication.**
   - MAG, CIDRE's data source, was retired at the end of 2021. CIDRE's validation stops at groups in 2019.
   - With OpenCitations (Jan 2024), we can run CIDRE on fully open data and test it on suspensions **after** its paper (JCR years about 2020–2022), which it never saw.
   - Question: does it still find about half of them, and do the results depend on the data source (MAG vs. OpenCitations coverage)?
2. **Paper-level anatomy of stacking.**
   - Which citing papers carry the within-group citations?
   - Are they concentrated in a few papers (editorials, special issues, reviews)?
   - Are they topically weaker than normal citations between the same fields? This can use title-embedding similarity, the thesis feature f6, since `_pubs` has titles.
   - This links the journal-level (CIDRE) and paper-level (Liu et al.) lines, which neither paper covers, and it reuses the author's thesis features.
3. **Early warning:** how many years before suspension the open-data signal appears (CIDRE reports 10 groups earlier than JCR, on MAG).

### Recommended revised C
Combine 1 and 2: *"Citation stacking on open data: an out-of-sample test of CIDRE on OpenCitations and the citing papers behind it."*
- The data plan is unchanged.
- The Leiden-CPM step is dropped in favor of CIDRE plus a paper-level analysis.
- Before committing, read the full texts of Liu et al. (2026, ISF) and Daly et al. (2026).

## Full-text checks of the two 2026 papers (2026-10-28)
- **Daly et al. (2026, OntoTrack)**, read in full via Frontiers (open access):
  - an ontology and system paper; the proof-of-concept data comes from Connected Papers, and OpenCitations is used only as an ontology (OCO);
  - the rules cover keyword overlap and author self-citation, not journal stacking;
  - validation is a manual sample plus synthetic cases; **no JCR suppressions**.
  - **No overlap** with revised C.
- **Liu, Cheng, Wei & Wang (2026, ISF)**: the full text is paywalled. Read only via a press summary (bioengineer.org, Sept 2026):
  - a heterogeneous graph of journals and papers;
  - "underlying data available from the authors upon request";
  - no JCR-suppression validation is mentioned; the June 2024 suppressions appear only as motivation.
  - **Partial overlap** (journal + paper level). Cite it and differentiate: C uses fully open data, a public method (CIDRE), an out-of-sample JCR test, and title-embedding similarity of within-group citations. TODO(verify) against the full text when it can be accessed.
- **Gupta, Udandarao & Bandi (2026)**, Trust-Aware Citation Cartel Ranking in Scholarly Knowledge Graphs, arXiv:2607.06528 (abstract read on arXiv; DOI 10.48550/arXiv.2607.06528, TODO(verify) through DataCite):
  - paper-level communities on a DBLP graph (500k papers);
  - LLM and SciBERT citation intent;
  - **no JCR validation**.
  - Relevant to angle 3 (semantic signal); cite it.

**Gate C1 status:** passed for the revised C. The novelty claim rests on three points:
1. an out-of-sample test of CIDRE on fully open data against post-2019 JCR suspensions;
2. sensitivity to the data source;
3. paper-level anatomy (concentration and title-semantic similarity) of within-group citations in suspended and detected groups.

Residual risk: the full text of Liu et al. (2026).

## Literature check 2 (2026-10-31): after the C10/C12 results
Raw search results are in `searches_20261031/`: OpenAlex queries, the 53 works citing CIDRE (`cidre_citers.json`), abstracts of candidates (`abstracts_candidates.json`) and the CIDRE full text from Europe PMC (`cidre_fulltext.xml`). Every DOI below was returned by OpenAlex on 2026-10-31. Crossref verification of each one before it goes into the .bib: TODO(verify).

### Questions and answers
1. **Is CIDRE's large-donor blind spot known? Not in anything found.**
   - The CIDRE paper (full text) removes a journal when *both* its donor and recipient scores are < θ. It justifies θ = 0.15 on the recipient side only: "all recipient journals suspended from JCR received at least 15% of their incoming citations from donor journals". It explains its missed JCR groups by missing within-group citations in MAG (unparsed or retracted papers), not by donor size.
   - None of the 53 citing works (titles, and abstracts where available) analyses CIDRE's peeling. **The finding appears new; residual risk: Zhang (2026), below.**
2. **Has detection on open data been validated against Clarivate's lists? Yes, at least once, concurrently.**
   - **Zhang, Q. (2026). *Detecting Citation Stacking with OpenAlex Open Data*. ScienceDB dataset, doi:10.57760/sciencedb.014qs (CC BY-ND 4.0, posted 2026-10-05).** From the DataCite abstract: a full OpenAlex snapshot; 1,057 journals in chemistry, materials science and nanoscience (5.747 M papers, 145 M citations); **16 Clarivate citation-stacking pairs from the 2018–2025 lists as positives**; 15 detection methods (single-signal and combined) compared at equal false-positive rates; simulated evasion attacks.
   - No paper or preprint is indexed yet. The method list is not public, so whether CIDRE is among the 15 is unknown: TODO(verify) when the paper appears.
   - **Differences from C:** OpenCitations rather than OpenAlex; all fields rather than three; a fidelity check against Clarivate's published *numbers* (self-citation and stacking); a coverage audit (missing reference lists, the `dataset` artifact); the mechanism behind CIDRE's misses and a fix; CIDRE's sensitivity to the partition. Cite it as concurrent work.
   - **Consequence for C:** Clarivate's 2018–2025 lists contain at least 16 stacking pairs in those three fields alone. `data/suppressions.csv` has only the JCR 2020, 2022 and 2023 lists, so **expanding the labels to every year we can source** is the most valuable data step left.
   - Barnes et al. (2026), *Citation distance matters*, Scientometrics, doi:10.1007/s11192-026-05586-1: journals flagged for anomalous citation in JCR have shorter incoming citation distances. A different question (a metric), but it uses JCR flags as validation; cite it.
   - Jolly et al. (2020), *Unsupervised Anomaly Detection in Journal-Level Citation Networks*, JCDL, doi:10.1145/3383583.3398531: journal-level anomaly detection; read whether it validates against JCR (TODO).
3. **Coverage of OpenCitations is studied, but not its effect on integrity detection.**
   - Martín-Martín et al. (2021), Scientometrics, doi:10.1007/s11192-020-03690-4: coverage of COCI vs GS, MA, Scopus, Dimensions and WoS.
   - Visser, van Eck & Waltman (2021), QSS, doi:10.1162/qss_a_00112: large-scale comparison of Scopus, WoS, Dimensions, Crossref and MAG.
   - Heibi, Peroni & Shotton (2019), Scientometrics, doi:10.1007/s11192-019-03217-6: COCI.
   - Peroni & Shotton (2020), QSS, doi:10.1162/qss_a_00023: OpenCitations.
   - Massari et al. (2024), QSS, doi:10.1162/qss_a_00292: OpenCitations Meta (our venue source).
   - Culbert et al. (2025), Scientometrics, doi:10.1007/s11192-025-05293-3: reference coverage of OpenAlex vs WoS and Scopus.
   - Recent studies of Italian institutions' coverage in OpenCitations (Scientometrics 2026, doi:10.1007/s11192-026-05540-1 and 10.1007/s11192-026-05788-7).
   - None of these links coverage gaps to detecting citation manipulation. **This angle of C is open.**
   - DataCite citations in OpenCitations ("DOCI", OpenCitations blog 2022, doi:10.59350/e58ta-ah134) are a plausible source of the `dataset`-typed citing items. **TODO(verify) on sampled OMIDs** before stating it.
4. **Background on suppressions and self-citation** (for the Introduction):
   - Moussa (2022), Accountability in Research, doi:10.1080/08989621.2022.2071154: journals suppressed three or more times, all for self-citation.
   - Erfanmanesh et al. (2019), doi:10.30481/lis.2019.58392: 225 suppressed journals, 2010–2014.
   - Taşkın et al. (2021), JOI, doi:10.1016/j.joi.2021.101221: self-citation patterns in JCR.
   - Heneberg (2016), PLoS ONE, doi:10.1371/journal.pone.0153730: from excessive self-cites to citation stacking.
   - Fister et al. (2016), Frontiers in Physics, doi:10.3389/fphy.2016.00049: citation cartels.
   - Van Noorden (2013), Nature, doi:10.1038/500510a: the Brazilian citation scheme.
   - Zeppelini et al. (2020), Nat Ecol Evol, doi:10.1038/s41559-020-01359-y: self-citation in taxonomy. This is relevant to the taxonomy journals behind the `dataset` artifact.
   - Chakraborty et al. (2018), arXiv:1807.10804: anomalous journal citation patterns in CS.
   - Spanakis et al. (2026), arXiv:2605.11930: author-level citation cliques.

### Novelty statement for C (revised 2026-10-31)
An audit of journal-level citation-manipulation detection on fully open data (OpenCitations, all fields) against Clarivate's published suppression numbers. Its contributions:
1. fidelity of open data to Clarivate's published numbers, and the cases open data cannot see (journals whose references are missing; a DataCite-type artifact);
2. a structural blind spot in CIDRE: peeling applies the recipient-motivated threshold θ to donors as well, so it cannot express a large journal feeding a small one;
3. a recipient-centric variant using CIDRE's own test and parameters, which flags listed journals above chance and sometimes years early;
4. how far CIDRE's input partition varies between runs.
**Risks:** Zhang (2026) may cover part of point 1 for three fields, and Liu et al. (2026, ISF) is still unread in full.
