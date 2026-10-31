#!/bin/sh
# Headless screenshots of the local site (serve site/ on :8765 first). Usage: tools/screenshots.sh [slug] [date]
SLUG=${1:-signal-seeker}; DATE=${2:-2026-10-31}; B=http://localhost:8765; O=$(dirname "$0")/../screenshots
shot(){ google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --virtual-time-budget=6000 \
  --window-size=$2 --screenshot="$O/$1.png" "$3" 2>/dev/null; }
shot root 1440,900 $B/
shot paper 1440,900 $B/$SLUG/
shot edition-1440 1440,2200 $B/$SLUG/$DATE/
shot edition-1440-full 1440,9000 $B/$SLUG/$DATE/
shot edition-390 390,1600 $B/$SLUG/$DATE/
shot edition-390-full 390,16000 $B/$SLUG/$DATE/
P=$(dirname "$0")/../site/$SLUG/$DATE/$SLUG-$DATE
pdftoppm -r 80 -png "$P-print.pdf" "$O/print"
pdftoppm -r 80 -png "$P-digital.pdf" "$O/digital"
