#!/usr/bin/env bash
# Upload original vendor archives + your filtered CSV bundle (no re-tar of audio).
#
# Usage:
#   export REMOTE='user@host:/path/to/German_Audios/'
#   ./upload_raw_archives_and_filtered_csvs.sh
#
# Or one-liner:
#   REMOTE='zhengbolin@172.16.0.1:/home/jovyan/work/.../German_Audios/' ./upload_raw_archives_and_filtered_csvs.sh
#
# Requires: rsync on this machine and on the remote host.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

REMOTE="${REMOTE:?Set REMOTE, e.g. export REMOTE='user@host:/path/German_Audios/'}"

# Local directory of filtered CSVs (override if your report id differs).
FILTERED_SRC="${FILTERED_SRC:-$PROJECT_ROOT/report/20260430-115818/filtered_csvs}"
# Remote folder name for that directory (basename of parent report + filtered_csvs).
FILTERED_REMOTE_NAME="${FILTERED_REMOTE_NAME:-filtered_csvs_20260430-115818}"

# Ensure REMOTE ends with /
case "$REMOTE" in
  */) ;;
  *) REMOTE="${REMOTE}/" ;;
esac

echo "[project] $PROJECT_ROOT"
echo "[remote]  $REMOTE"
echo "[filtered] $FILTERED_SRC -> ${REMOTE}${FILTERED_REMOTE_NAME}/"

echo ""
echo "==> Raw archives (large; resumable with rsync)"
/usr/bin/rsync -avh --partial --inplace --progress \
  "$PROJECT_ROOT/Mozilla/Common Voice Scripted Speech 25.0 - German.tar.gz" \
  "$PROJECT_ROOT/Mozilla/Common Voice Spontaneous Speech 3.0 - German.tar.gz" \
  "$PROJECT_ROOT/openslr/thorsten-de_v02.tgz" \
  "$PROJECT_ROOT/kaggle/archive.zip" \
  "$REMOTE"

echo ""
echo "==> Filtered CSVs"
/usr/bin/rsync -avh --partial --inplace --progress \
  "$FILTERED_SRC/" \
  "${REMOTE}${FILTERED_REMOTE_NAME}/"

echo ""
echo "[done] On the server you can:"
echo "  - Extract each archive under a layout that matches your CSV path column"
echo "  - Join / filter using files in ${FILTERED_REMOTE_NAME}/"
