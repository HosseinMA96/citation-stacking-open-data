#!/usr/bin/env bash
# Claude Code Stop hook for the Project C VM job (configured in PAPER/.claude/settings.local.json).
# Reads vm/JOB_STATE: first line = state, rest = note.
#   working     -> block the stop: Claude must check the job, retry failed steps and continue
#   waiting     -> allow (a background watcher will wake Claude when the VM run changes)
#   needs-user  -> allow (something only the user can do)
#   done / no file -> allow
# Runaway guard: after 100 consecutive blocks the stop is allowed.
HERE="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="$HERE/JOB_STATE"
COUNT_FILE="$HERE/.stop_hook_blocks"
cat > /dev/null   # hook input (unused)
[ -f "$STATE_FILE" ] || exit 0
state=$(head -n1 "$STATE_FILE" | tr -d '[:space:]')
note=$(tail -n +2 "$STATE_FILE" | tr '\n' ' ' | cut -c1-400)
case "$state" in
  working)
    n=$(( $(cat "$COUNT_FILE" 2>/dev/null || echo 0) + 1 ))
    echo "$n" > "$COUNT_FILE"
    if [ "$n" -gt 100 ]; then
      echo '{"systemMessage": "Project C stop hook: 100 consecutive blocks, allowing stop (runaway guard)."}'
      exit 0
    fi
    reason="Project C VM job is not finished (JOB_STATE=working, block $n/100). Note: $note. Check the job (vm/vmctl.sh status; ssh and tail ~/c/vm/run_all_*.log), retry any failed step, and continue the workflow in vm/README.md. While a long step runs, start a background watcher and set JOB_STATE to 'waiting'; set 'needs-user' if only the user can unblock it, and 'done' when the run is fetched, verified, logged and the VM is deallocated."
    REASON="$reason" /usr/bin/python3 -c 'import json,os; print(json.dumps({"decision": "block", "reason": os.environ["REASON"]}))'
    ;;
  *)
    rm -f "$COUNT_FILE"
    exit 0
    ;;
esac
