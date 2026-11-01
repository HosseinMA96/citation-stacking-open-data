#!/usr/bin/env bash
# Run ON THE VM:  bash ~/c/vm/download.sh
# The Data Bank blocks scripted downloads, so this uses "Copy as cURL" commands that the USER copies
# from their own browser session (they carry cookies: treat as secrets). Paste each into
# ~/curl_edges.txt and ~/curl_pubs.txt. Downloads resume (-C -) if cut; sizes are checked against
# the Data Bank's listed byte sizes, then gzip-tested and checksummed; the cURL files are deleted.
set -euo pipefail
RAW=~/c/data/raw
mkdir -p "$RAW"
fetch() {  # $1 = curl file, $2 = output name, $3 = expected bytes (Data Bank listing, 2026-10-29)
  [ -f "$RAW/$2.ok" ] && { echo "$2 already downloaded and tested"; return; }
  [ -f "$1" ] || { echo "missing $1"; exit 1; }
  cmd=$(sed -e 's/\\$//' "$1" | tr '\n' ' ')
  case "$cmd" in
    curl\ *) ;;
    http*) cmd="curl '${cmd%% }'" ;;   # a bare URL, e.g. the final (signed) link from the browser's downloads page
    *) echo "$1 is neither a curl command nor a URL"; exit 1;;
  esac
  cmd=${cmd//--compressed/}           # the file is already gzip; keep the bytes as they are
  echo "downloading $2 ($3 bytes) ..."
  for i in 1 2 3 4 5; do
    eval "$cmd -sS -L --fail -C - --retry 5 --retry-delay 15 -o '$RAW/$2'" && break
    echo "attempt $i failed; retrying in 30 s (if every attempt fails, the session has expired: copy a fresh cURL)"
    sleep 30
  done
  got=$(stat -c %s "$RAW/$2")
  [ "$got" = "$3" ] || { echo "SIZE MISMATCH for $2: got $got, expected $3"; exit 1; }
  echo "testing gzip integrity of $2 ..."
  pigz -t "$RAW/$2"
  sha256sum "$RAW/$2" > "$RAW/$2.sha256"
  touch "$RAW/$2.ok"
}
fetch ~/curl_edges.txt open_citations_jan2024_iid_el.csv.gz 14309784846
fetch ~/curl_pubs.txt  open_citations_jan2024_pubs.csv.gz  9064662339
shred -u ~/curl_edges.txt ~/curl_pubs.txt 2>/dev/null || rm -f ~/curl_edges.txt ~/curl_pubs.txt
cat "$RAW"/*.sha256
df -h ~ | tail -1
echo "Next: tmux new -s run 'bash ~/c/vm/run_all.sh <run_id>'"
