#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  swap-domain.sh — Replace Netlify preview URL with production domain
#
#  Usage:
#    ./swap-domain.sh <new-domain>
#    ./swap-domain.sh tayloredmortgages.com
#
#  What it updates:
#    - All .html files (canonical, OG, twitter, schema JSON-LD, href links)
#    - sitemap.xml
#    - robots.txt
#    - llms.txt
#
#  It will show you a dry-run diff first and ask for confirmation.
# ─────────────────────────────────────────────────────────────

set -euo pipefail

OLD="subtle-manatee-efc18b.netlify.app"
NEW="${1:-}"

if [[ -z "$NEW" ]]; then
  echo "Usage: ./swap-domain.sh <new-domain>"
  echo "Example: ./swap-domain.sh tayloredmortgages.com"
  exit 1
fi

# Strip any protocol prefix the user might have passed
NEW="${NEW#https://}"
NEW="${NEW#http://}"
NEW="${NEW%/}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FILES=$(find . \
  -not -path "./.git/*" \
  -not -path "./.claude/*" \
  -not -name "swap-domain.sh" \
  \( -name "*.html" -o -name "*.xml" -o -name "*.txt" -o -name "*.md" \) \
  | sort)

# ── Dry run ──────────────────────────────────────────────────
echo ""
echo "  Domain swap: $OLD → $NEW"
echo "  ──────────────────────────────────────────────"
MATCH_COUNT=0
for f in $FILES; do
  COUNT=$(grep -c "$OLD" "$f" 2>/dev/null || true)
  if [[ "$COUNT" -gt 0 ]]; then
    echo "  $f  ($COUNT occurrence(s))"
    MATCH_COUNT=$((MATCH_COUNT + COUNT))
  fi
done

if [[ "$MATCH_COUNT" -eq 0 ]]; then
  echo "  No occurrences of '$OLD' found. Nothing to do."
  exit 0
fi

echo ""
echo "  Total replacements: $MATCH_COUNT"
echo ""
read -p "  Proceed? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "  Aborted."
  exit 0
fi

# ── Apply ────────────────────────────────────────────────────
for f in $FILES; do
  if grep -q "$OLD" "$f" 2>/dev/null; then
    # macOS-compatible in-place sed
    sed -i '' "s|$OLD|$NEW|g" "$f"
    echo "  ✓ $f"
  fi
done

echo ""
echo "  Done. Review the changes with: git diff"
echo ""
echo "  Next steps:"
echo "  1. Verify pages look correct in the browser"
echo "  2. Update Netlify custom domain settings"
echo "  3. Commit: git add -A && git commit -m 'Switch domain to $NEW'"
echo "  4. Push and confirm Netlify deploy"
