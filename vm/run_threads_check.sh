#!/usr/bin/env bash
# Run ON THE VM inside tmux:  tmux new -s t1 'bash ~/c/vm/run_threads_check.sh RUN_ID RULE SEED'
# TODO 6c: c6_blockstab_20261031_01 found that the same seed gives different partitions with 8
# OMP threads. Test whether one thread makes the fit reproducible: two fits with C_GT_THREADS=1,
# the same seed, run side by side (tags RULE_sSEED_t1a, RULE_sSEED_t1b; each fit uses one thread,
# so running them together does not change either). Skips finished fits. With AUTO_DEALLOCATE=1
# the VM deallocates itself at the end.
set -uo pipefail
RUN_ID="${1:?usage: run_threads_check.sh RUN_ID RULE SEED}"; RULE="${2:?rule}"; SEED="${3:?seed}"
C=~/c
set -a; source "$C/vm/vm.env"; set +a
export C_GT_THREADS=1
PY=~/mamba/envs/c-gt/bin/python
cd "$C/experiments/c01_journal_graph"
LOG="$C/vm/run_threads_check_$RUN_ID.log"
finish() {
  echo "$(date -u +%FT%TZ) run_threads_check exit code $1" | tee -a "$LOG"
  if [ "${AUTO_DEALLOCATE:-0}" = "1" ]; then bash "$C/vm/self_deallocate.sh"; fi
  exit "$1"
}
one() {
  tag="${RULE}_s${SEED}_t1$1"
  if [ -f "runs/$RUN_ID/stage_blocks_$tag.json" ]; then echo "$tag: done, skipped"; return 0; fi
  echo "$(date -u +%FT%TZ) $tag: start"
  /usr/bin/time -v "$PY" c6_blocks.py --run-id "$RUN_ID" --journal-rule "$RULE" --seed "$SEED" --tag "$tag" \
    > "$C/vm/run_threads_check_${RUN_ID}_$1.out" 2>&1
  rc=$?; echo "$(date -u +%FT%TZ) $tag: done, exit $rc"; return $rc
}
{
  echo "$(date -u +%FT%TZ) start $RUN_ID rule $RULE seed $SEED; gt threads $C_GT_THREADS; two fits side by side"
  one a & pa=$!
  one b & pb=$!
  wait $pa; ra=$?; wait $pb; rb=$?
  [ $ra -eq 0 ] && [ $rb -eq 0 ] || exit 1
  echo "$(date -u +%FT%TZ) all done"
} 2>&1 | tee -a "$LOG"
finish "${PIPESTATUS[0]}"
