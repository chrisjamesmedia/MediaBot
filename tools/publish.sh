#!/usr/bin/env bash
# Daily publish: build one edition (public + local private copy), refresh indexes,
# scan for secrets, commit, and push. GitHub Actions (.github/workflows/pages.yml)
# then deploys site/ to https://chrisjamesmedia.github.io/mediabot/.
#
#   tools/publish.sh                       # signal-seeker, today's date (America/New_York)
#   tools/publish.sh signal-seeker 2026-10-31 [--weather]
#   NO_PUSH=1 tools/publish.sh ...         # build + commit only
#
# Pushing uses whatever git credential is already set up on this machine
# (e.g. `gh auth login` done by Chris, then `gh auth setup-git`). This script never
# reads, stores, or prints tokens.
set -euo pipefail
cd "$(dirname "$0")/.."
SLUG="${1:-signal-seeker}"
DATE="${2:-$(TZ=America/New_York date +%F)}"
shift $(( $# > 2 ? 2 : $# )) || true

.venv/bin/python build.py "$SLUG" "$DATE" "$@"
.venv/bin/python build.py --index

# Guards: the private copy must never be tracked; no secrets in what we commit.
if git ls-files --error-unmatch site-private >/dev/null 2>&1; then
  echo "site-private/ is tracked - refusing to publish" >&2; exit 1; fi
tools/secret_scan.sh

git add -A
git diff --cached --quiet && { echo "nothing new to publish"; exit 0; }
git commit -q -m "edition: $SLUG $DATE"
[ "${NO_PUSH:-}" = 1 ] && { echo "committed (NO_PUSH=1, not pushed)"; exit 0; }
git push origin main
echo "pushed. Live in ~1 min: https://chrisjamesmedia.github.io/mediabot/$SLUG/$DATE/"
