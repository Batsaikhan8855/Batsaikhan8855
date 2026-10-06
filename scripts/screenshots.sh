#!/usr/bin/env bash
# Refresh live-site screenshots used by the projects card. Needs a Chrome/Chromium binary.
set -euo pipefail
cd "$(dirname "$0")/.."
CHROME="${CHROME:-google-chrome}"
shoot() {
  local name="$1" url="$2" tmp
  tmp="$(mktemp -d)"
  "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars --virtual-time-budget=10000 \
    --window-size=1280,800 --screenshot="$tmp/shot.png" "$url" >/dev/null 2>&1 || return 0
  python3 -c "
import sys
from PIL import Image
Image.open(sys.argv[1]).convert('RGB').resize((800, 500), Image.LANCZOS).save(sys.argv[2], quality=78, optimize=True)
" "$tmp/shot.png" "assets/shots/$name.jpg"
}
shoot 100ail https://100ail.vercel.app
shoot sporthub https://sporthub-eight.vercel.app
