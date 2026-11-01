#!/usr/bin/env bash
# print-signal-seeker.sh: fetch today's Signal Seeker print PDF and send it to a printer, duplex.
#
# Works on macOS and Linux (both ship CUPS `lp`). It installs nothing; it needs only curl,
# lp and python3 (or plutil on macOS) to read the JSON.
#
#   PRINTER=HP_OfficeJet ./print-signal-seeker.sh      # a named CUPS queue (see `lpstat -p`)
#   ./print-signal-seeker.sh                           # the system default printer
#   DRY_RUN=1 ./print-signal-seeker.sh                 # fetch and check it, but don't print
#   FORCE=1 ./print-signal-seeker.sh                   # print even if today's was already printed
#
# Safe to run more than once a day: it remembers the last date it printed and skips repeats.
# If today's edition isn't published yet it exits 0 without printing (status "not-yet"),
# so a launchd/cron job can retry later without spamming the printer.
set -euo pipefail

BASE="${SIGNAL_SEEKER_BASE:-https://chrisjamesmedia.github.io/MediaBot/signal-seeker/latest}"
PRINTER="${PRINTER:-}"                  # empty = system default printer
MEDIA="${MEDIA:-Letter}"                # Letter or A4
SIDES="${SIDES:-two-sided-long-edge}"   # one-sided if the printer has no duplexer
STATE_DIR="${STATE_DIR:-$HOME/.signal-seeker}"
ALLOW_STALE="${ALLOW_STALE:-0}"         # 1 = print the latest edition even if it isn't today's
DRY_RUN="${DRY_RUN:-0}"
FORCE="${FORCE:-0}"

mkdir -p "$STATE_DIR"
LOG="$STATE_DIR/print.log"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG"; }

today="$(date +%Y-%m-%d)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# 1. Which edition is latest? (cache-busting query so a CDN never hands back yesterday's file)
if ! curl -fsSL --retry 3 --max-time 30 -o "$tmp/latest.json" "$BASE/latest.json?t=$(date +%s)"; then
  log "error: could not fetch $BASE/latest.json"; exit 1
fi
json_get() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import json,sys
v=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): v=v.get(k,"") if isinstance(v,dict) else ""
print(v)' "$tmp/latest.json" "$1"
  else
    plutil -extract "$1" raw -o - "$tmp/latest.json"
  fi
}
edition_date="$(json_get date)"
pages="$(json_get pages.print)"

if [ "$edition_date" != "$today" ] && [ "$ALLOW_STALE" != "1" ]; then
  log "not-yet: latest edition is $edition_date, today is $today; nothing printed"; exit 0
fi
if [ "$FORCE" != "1" ] && [ -f "$STATE_DIR/last-printed" ] && [ "$(cat "$STATE_DIR/last-printed")" = "$edition_date" ]; then
  log "skip: $edition_date already printed"; exit 0
fi

# 2. Download and sanity-check the PDF
curl -fsSL --retry 3 --max-time 60 -o "$tmp/signal-seeker.pdf" "$BASE/print.pdf?t=$(date +%s)" \
  || { log "error: could not fetch $BASE/print.pdf"; exit 1; }
if [ "$(head -c 5 "$tmp/signal-seeker.pdf")" != "%PDF-" ]; then
  log "error: print.pdf is not a PDF"; exit 1
fi
cp "$tmp/signal-seeker.pdf" "$STATE_DIR/signal-seeker-$edition_date.pdf"

# 3. Print (duplex, long-edge) and remember the date only after the job was accepted
args=(-o "sides=$SIDES" -o "media=$MEDIA" -o fit-to-page -t "Signal Seeker $edition_date")
[ -n "$PRINTER" ] && args=(-d "$PRINTER" "${args[@]}")
if [ "$DRY_RUN" = "1" ]; then
  log "dry-run: would run: lp ${args[*]} $STATE_DIR/signal-seeker-$edition_date.pdf ($pages pages)"; exit 0
fi
if job="$(lp "${args[@]}" "$STATE_DIR/signal-seeker-$edition_date.pdf" 2>&1)"; then
  echo "$edition_date" > "$STATE_DIR/last-printed"
  log "printed: $edition_date ($pages pages) -> ${PRINTER:-default printer}: $job"
else
  log "error: lp failed: $job"; exit 1
fi
