# Project C VM runbook (TODO item 6)

One Azure VM, used for one job: turn the two Data Bank files into small journal-level tables, fit the dcSBM blocks, copy the results back, then delete everything. Everything after that runs on the laptop.

## Cost (Azure retail price API, eastus, Linux, pay-as-you-go, read 2026-10-28)

| Item | Price | Bills when |
|---|---|---|
| E8s_v5 (8 vCPU, 64 GB) | $0.504/h | running only |
| E16s_v5 (128 GB), fallback | $1.008/h | running only |
| 256 GB Premium SSD (P15) | $38.01/month ≈ $1.25/day | until the disk is deleted, also when deallocated |
| 256 GB Standard SSD (E15) | $19.20/month ≈ $0.63/day | same |

Estimate: 10–20 VM hours (≈ $5–10) plus the disk for the days it exists. Expect roughly $15–30 in all. The run times are extrapolated from the samples: TODO(verify) on the VM.

**Cost guards built in:**
- `vmctl.sh stop` **deallocates**. `sudo shutdown` inside the VM does not stop compute billing.
- Daily auto-shutdown (deallocate) at `AUTO_SHUTDOWN_UTC`, a safety net if you forget.
- `run_all.sh` deallocates the VM itself when the run ends, success or failure (`AUTO_DEALLOCATE=1`). It uses the VM's managed identity, which may only manage this one VM.
- Stages are resumable. After an auto-shutdown or a failure, rerun the same run ID and finished stages are skipped.
- Only the small outputs come back: the analysis years, the aggregated network, the blocks and the coverage tables. Big intermediates stay on the VM disk.
- `vmctl.sh hours` sums the logged sessions. The exact bill is in the portal under Cost Management.
- SSH is open only from your current IP.

## Steps

On the **laptop**, from `C_citation_stacking/`:
1. `cp vm/vm.env.example vm/vm.env`, then check the size, disk type and region.
2. `az login` if needed, then `vm/vmctl.sh create`. This takes about 3 minutes, and **billing starts here**.
3. `vm/vmctl.sh push`, then `vm/vmctl.sh ssh`.

On the **VM**:

4. `bash ~/c/vm/setup_vm.sh` (about 5–10 min). It installs micromamba and the environment with graph-tool, then runs three self-tests: the graph-tool planted blocks, the synthetic pipeline test and the CIDRE toy check. **Stop if any of them fails.** (Done 2026-10-29: all three pass with graph-tool 3.9; see `vm/setup_vm_20261029.log` and `vm/environment.lock.yml`.)
5. **Download (needs you; the Data Bank blocks scripted downloads):**
   - In your laptop browser, open the Data Bank page and start downloading `open_citations_jan2024_iid_el.csv.gz`. In DevTools → Network, right-click the request → Copy → **Copy as cURL**, paste it into `~/curl_edges.txt` on the laptop, and cancel the browser download.
   - Do the same for `open_citations_jan2024_pubs.csv.gz` → `~/curl_pubs.txt`.
   - The commands carry your session cookies: they are secrets.
6. On the laptop: `vm/vmctl.sh start`, then `vm/vmctl.sh sendcurl` (copies them to the VM and deletes the local copies), then `vm/vmctl.sh download`.
   - `download.sh` resumes if cut, checks the exact byte sizes (14,309,784,846 and 9,064,662,339), tests the gzip and records sha256.
   - If every attempt fails, the session has expired: copy fresh cURL commands.
7. `vm/vmctl.sh run c6_full_<YYYYMMDD>_01`: starts `run_all.sh` in tmux on the VM. The VM deallocates itself at the end.

On the **laptop**:

8. Next day: `vm/vmctl.sh start`, then `vm/vmctl.sh ssh` and `tail ~/c/vm/run_all_<run_id>.log`, to check that it finished.
9. `vm/vmctl.sh fetch <run_id>` copies the run folder back and verifies `SHA256SUMS`. Also copy `~/c/vm/run_all_<run_id>.log` and `~/c/vm/environment.lock.yml`.
10. `vm/vmctl.sh stop`. When the results are checked and logged in `RESULTS_LOG.md`: `vm/vmctl.sh delete`.
    - Optionally keep the disk a few days for C13, which needs `edges.parquet` again, but every day costs about $1.25.

## If something goes wrong
- **graph-tool runs out of memory or is too slow:** rerun only the blocks, either with `c6_blocks.py --run-id <id> --min-strength 10 --tag minstr10` (and report the restriction) or after resizing to E16s_v5. To resize: `az vm deallocate`, then `az vm resize --size Standard_E16s_v5`, then start.
- **DuckDB runs out of memory:** lower `C_MEM` in `~/c/vm/vm.env` (spilling goes to disk, up to `C_MAX_TEMP`) and rerun the same run ID.
- **The run stopped (auto-shutdown or a crash):** start the VM and rerun step 7 with the same run ID.

## Tested locally (2026-10-28)
- `test_c6_synthetic.py`: hand-built gzip inputs with known answers; all checks pass.
- `run_all.sh` on gzipped prefix samples with small limits: the pipeline completed. The block fit failed as expected because there is no graph-tool on the laptop, and the failure path ran once with no deallocation. Resuming the same run ID skipped all 8 stages.
- `vmctl.sh hours` cost arithmetic.
- **Not testable locally:** `vmctl.sh create/start/stop/delete`, `setup_vm.sh`, `download.sh`, `self_deallocate.sh`, and graph-tool itself (its download was not approved on the laptop). They are covered by the self-tests in step 4, before any data is touched.
