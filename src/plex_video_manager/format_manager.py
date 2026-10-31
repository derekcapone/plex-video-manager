import subprocess
import json
from typing import Any, Dict
from pathlib import Path


def get_mkv_information(mkv_file: str) -> Dict[str, Any]:
    result = subprocess.run(
        ["mkvmerge", "-J", mkv_file],
        capture_output=True,
        text=True,
        check=True
    )

    info = json.loads(result.stdout)
    return info


def is_audio_format_required(video_file: str) -> bool:
    """Use ffprobe (ffmpeg tool) to determine whether the provided video file requires its audio
        to be converted. 

    Args:
        video_file (str): path of video file to check

    Returns:
        bool: True if conversion required, False otherwise
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            str(video_file),
        ],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    for stream in info["streams"]:
        # TODO: Handle multiple audio streams in an mkv file
        # Only downmix surround audio; mono/stereo is left alone.
        if stream["codec_type"] == "audio" and stream.get("channels", 2) > 2:
            print(stream["codec_type"], stream.get("codec_name"))
            return True

    return False 


def convert_audio_to_aac(video_file: str) -> Path:
    input_file = Path(video_file)
    output_file = f"{str(input_file.parent)}/{input_file.stem}-converted{input_file.suffix}"
    
    command = [
        "ffmpeg",
        "-n",  # Never overwrite (and never prompt, which would hang the qBittorrent hook)
        "-i", video_file,
        "-map", "0:v",
        "-map", "0:a:0",
        "-map", "0:s?",  # Keep subtitle tracks if there are any
        "-c:v", "copy",
        "-c:s", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        output_file,
    ]

    # Raises exception if error occurred. No stdin so ffmpeg can never wait for input.
    subprocess.run(command, check=True, stdin=subprocess.DEVNULL)
    return Path(output_file)


def process_audio_track(mkv_file: Path) -> Path:
    # TODO: finish implementing audio manipulation functionality
    return mkv_file  # TODO remove this when fully implemented
    
    if not is_audio_format_required(str(mkv_file)):
        return mkv_file
    
    working_file = convert_audio_to_aac(str(mkv_file))
    mkv_file.unlink()  # No longer need the original, get rid of it
    return working_file

