#!/usr/bin/env bash
# Run ON THE VM inside tmux:  tmux new -s blocks 'bash ~/c/vm/run_blocks.sh RUN_ID RULE [RULE ...]'
# Journal flags (c6_journal_set.py) once, then one dcSBM fit per journal rule in config.yaml
# (c6_blocks.py --journal-rule, tag = rule name). Skips finished steps. With AUTO_DEALLOCATE=1 the
# VM deallocates itself at the end, success or failure.
set -uo pipefail
RUN_ID="${1:?usage: run_blocks.sh RUN_ID RULE [RULE ...]}"; shift
[ $# -ge 1 ] || { echo "give at least one journal rule"; exit 1; }
C=~/c
set -a; source "$C/vm/vm.env"; set +a
export C_WORK=$C/data/work/$RUN_ID
PY=~/mamba/envs/c-gt/bin/python
cd "$C/experiments/c01_journal_graph"
LOG="$C/vm/run_blocks_$RUN_ID.log"
finish() {
  echo "$(date -u +%FT%TZ) run_blocks exit code $1" | tee -a "$LOG"
  if [ "${AUTO_DEALLOCATE:-0}" = "1" ]; then bash "$C/vm/self_deallocate.sh"; fi
  exit "$1"
}
{
  echo "$(date -u +%FT%TZ) start $RUN_ID rules: $*; gt threads $C_GT_THREADS"
  [ -f "runs/$RUN_ID/stage_journal_flags.json" ] || "$PY" c6_journal_set.py --run-id "$RUN_ID" || exit $?
  for rule in "$@"; do
    if [ -f "runs/$RUN_ID/stage_blocks_$rule.json" ]; then echo "blocks $rule: done, skipped"; continue; fi
    echo "$(date -u +%FT%TZ) blocks $rule: start"
    /usr/bin/time -v "$PY" c6_blocks.py --run-id "$RUN_ID" --journal-rule "$rule" || exit $?
    echo "$(date -u +%FT%TZ) blocks $rule: done"
  done
  echo "$(date -u +%FT%TZ) all done. On the laptop: vm/vmctl.sh fetch is not usable (run exists locally); copy the new files"
} 2>&1 | tee -a "$LOG"
finish "${PIPESTATUS[0]}"
