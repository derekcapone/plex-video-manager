#!/bin/bash
# Called by qBittorrent on torrent completion. Configure it as:
#   /home/derek/Desktop/Projects/plex-video-manager/test-torrent-script.sh "%F" "%L" "%G"
PROJECT_DIR="/home/derek/Desktop/Projects/plex-video-manager"
LOG="/home/derek/logs/qbittorrent-postprocess.log"
mkdir -p "$(dirname "$LOG")"

DOWNLOAD_PATH="$1"
CATEGORY="$2"
TAGS="$3"

{
    echo "===== $(date) ====="
    echo "Processing: $DOWNLOAD_PATH"
    echo "Category: $CATEGORY"
    echo "Tags: $TAGS"
} >> "$LOG"

# cd so the tool finds .env; flock so two finishing torrents are processed one at a time.
cd "$PROJECT_DIR" || exit 1
flock /tmp/plex-video-manager.lock \
    "$PROJECT_DIR/.venv/bin/plex_video_manager" "$DOWNLOAD_PATH" --category "$CATEGORY" --tags "$TAGS" \
    >> "$LOG" 2>&1
STATUS=$?

echo "Exit status: $STATUS" >> "$LOG"
exit $STATUS
