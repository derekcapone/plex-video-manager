#!/bin/bash
LOG="/home/derek/logs/qbittorrent-postprocess.log"
echo "===== $(date) =====" >> "$LOG"

DOWNLOAD_PATH="$1"
CATEGORY="$2"
TAG="$3"
echo "Processing: $DOWNLOAD_PATH" >> "$LOG"
echo "Category: $CATEGORY" >> "$LOG"
echo "PATH: $PATH" >> "$LOG"

# TODO: Call the python tool to handle the functionality with download path and categories as arguments.

