from pymkv import MKVFile
import subprocess
import json


mkv_file = "/home/derek/Projects/plex-video-manager/src/plex_video_manager/resources/FuturamaS13E09TheTroubleWithTruffles1080p.mkv"

result = subprocess.run(
    ["mkvmerge", "-J", mkv_file],
    capture_output=True,
    text=True,
    check=True
)

info = json.loads(result.stdout)

for track in info["tracks"]:
    if track["type"] == "subtitles":
        print(track)
