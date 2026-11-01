#!/usr/bin/env bash
# Run ON THE VM inside tmux:  tmux new -s seeds 'bash ~/c/vm/run_seeds.sh RUN_ID RULE SEED [SEED ...]'
# TODO item 6b: refit one journal rule with other seeds (tag RULE_sSEED) to measure how much the
# dcSBM partition depends on the stochastic search. A seed equal to config.yaml's seed is a
# repeat of the existing fit (tag RULE_sSEED_rep), to test run-to-run reproducibility.
# Skips finished fits. With AUTO_DEALLOCATE=1 the VM deallocates itself at the end.
set -uo pipefail
RUN_ID="${1:?usage: run_seeds.sh RUN_ID RULE SEED [SEED ...]}"; RULE="${2:?rule}"; shift 2
C=~/c
set -a; source "$C/vm/vm.env"; set +a
PY=~/mamba/envs/c-gt/bin/python
cd "$C/experiments/c01_journal_graph"
CFG_SEED=$(grep -E '^seed:' config.yaml | awk '{print $2}')
LOG="$C/vm/run_seeds_$RUN_ID.log"
finish() {
  echo "$(date -u +%FT%TZ) run_seeds exit code $1" | tee -a "$LOG"
  if [ "${AUTO_DEALLOCATE:-0}" = "1" ]; then bash "$C/vm/self_deallocate.sh"; fi
  exit "$1"
}
{
  echo "$(date -u +%FT%TZ) start $RUN_ID rule $RULE seeds: $*; gt threads $C_GT_THREADS"
  for s in "$@"; do
    tag="${RULE}_s$s"; [ "$s" = "$CFG_SEED" ] && tag="${tag}_rep"
    if [ -f "runs/$RUN_ID/stage_blocks_$tag.json" ]; then echo "$tag: done, skipped"; continue; fi
    echo "$(date -u +%FT%TZ) $tag: start"
    /usr/bin/time -v "$PY" c6_blocks.py --run-id "$RUN_ID" --journal-rule "$RULE" --seed "$s" --tag "$tag" || exit $?
    echo "$(date -u +%FT%TZ) $tag: done"
  done
  echo "$(date -u +%FT%TZ) all done"
} 2>&1 | tee -a "$LOG"
finish "${PIPESTATUS[0]}"
