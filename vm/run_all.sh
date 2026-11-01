#!/usr/bin/env bash
# Run ON THE VM inside tmux:  tmux new -s run 'bash ~/c/vm/run_all.sh c6_full_YYYYMMDD_01'
# Full pipeline, then the dcSBM block fit. Resumable: rerunning the same RUN_ID skips finished
# stages (edges.parquet etc. stay in ~/c/data/work for later passes). With AUTO_DEALLOCATE=1 the VM deallocates itself at the end, success or failure.
set -uo pipefail
RUN_ID="${1:?usage: run_all.sh RUN_ID}"
# Overrides for a local test only: C_DIR, C_PY, C_RAW, C_ENV_FILE.
C=${C_DIR:-~/c}
# shellcheck disable=SC1090
set -a; source "${C_ENV_FILE:-$C/vm/vm.env}"; set +a
export C_TEMP_DIR=$C/data/work/$RUN_ID/duckdb_tmp
PY=${C_PY:-~/mamba/envs/c-gt/bin/python}
RAW=${C_RAW:-$C/data/raw}
cd "$C/experiments/c01_journal_graph"
LOG="$C/vm/run_all_$RUN_ID.log"
finish() {
  echo "$(date -u +%FT%TZ) run_all exit code $1" | tee -a "$LOG"
  df -h ~ | tail -1 | tee -a "$LOG"
  if [ "${AUTO_DEALLOCATE:-0}" = "1" ]; then bash "$C/vm/self_deallocate.sh"; fi
  exit "$1"
}
{
  echo "$(date -u +%FT%TZ) start $RUN_ID; threads $C_THREADS, mem $C_MEM, gt threads $C_GT_THREADS"
  resume=""; [ -d "runs/$RUN_ID" ] && resume="--resume"
  # OpenCitations Meta dump (download_meta.sh) is the journal source since 2026-10-31; required.
  [ -f "$RAW/meta_csv/.ok" ] || { echo "missing $RAW/meta_csv (run vm/download_meta.sh)"; exit 1; }
  /usr/bin/time -v "$PY" c6_full_run.py --run-id "$RUN_ID" $resume \
    --edges "$RAW/open_citations_jan2024_iid_el.csv.gz" --pubs "$RAW/open_citations_jan2024_pubs.csv.gz" \
    --meta "$RAW/meta_csv" || exit $?
  [ -f "runs/$RUN_ID/stage_blocks.json" ] || /usr/bin/time -v "$PY" c6_blocks.py --run-id "$RUN_ID" || exit $?
  echo "$(date -u +%FT%TZ) all done. On the laptop: vm/vmctl.sh fetch $RUN_ID"
} 2>&1 | tee -a "$LOG"
finish "${PIPESTATUS[0]}"
