#!/usr/bin/env bash
# Run ON THE VM:  bash ~/c/vm/download_meta.sh
# OpenCitations Meta CSV dump, Figshare 10.6084/m9.figshare.21747461.v7 (published 2024-02-16, CC0),
# the journal source for each article (decision 2026-10-31, RESULTS_LOG). Public Figshare API download.
# Checks the size and MD5 listed by the Figshare API, records sha256, then extracts the CSVs.
set -euo pipefail
RAW=~/c/data/raw
OUT=$RAW/meta_csv_dump.zip
URL=https://ndownloader.figshare.com/files/44571631
SIZE=11342656708
MD5=91d9b2f0a6b15959d92ef236c00b19e2
mkdir -p "$RAW"
if [ ! -f "$OUT.ok" ]; then
  echo "downloading meta_csv_dump.zip ($SIZE bytes) ..."
  for i in 1 2 3 4 5; do
    curl -sS -L --fail -C - --retry 5 --retry-delay 15 -o "$OUT" "$URL" && break
    echo "attempt $i failed; retrying in 30 s"; sleep 30
  done
  got=$(stat -c %s "$OUT")
  [ "$got" = "$SIZE" ] || { echo "SIZE MISMATCH: got $got, expected $SIZE"; exit 1; }
  echo "checking md5 ..."
  [ "$(md5sum "$OUT" | cut -d' ' -f1)" = "$MD5" ] || { echo "MD5 MISMATCH"; exit 1; }
  sha256sum "$OUT" > "$OUT.sha256"
  touch "$OUT.ok"
fi
if [ ! -f "$RAW/meta_csv/.ok" ]; then
  echo "extracting ..."
  rm -rf "$RAW/meta_csv"; mkdir -p "$RAW/meta_csv"
  unzip -q "$OUT" -d "$RAW/meta_csv"
  find "$RAW/meta_csv" -type f | wc -l > "$RAW/meta_csv/.ok"
fi
echo "files: $(cat "$RAW/meta_csv/.ok")"; du -sh "$RAW/meta_csv"; cat "$OUT.sha256"; df -h ~ | tail -1
