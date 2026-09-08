import subprocess
import json
import argparse
from typing import Any, Dict
from pathlib import Path
import re


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
        if stream["codec_type"] == "audio" and stream["channels"] != 2: 
            print(stream["codec_type"], stream.get("codec_name"))
            return True

    return False 


def convert_audio_to_aac(video_file: str) -> None:
    input_file = Path(video_file)
    output_file = f"{str(input_file.parent)}/{input_file.stem}-converted{input_file.suffix}"
    
    command = [
        "ffmpeg",
        "-i", video_file,
        "-map", "0:v",
        "-map", "0:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        output_file,
    ]

    subprocess.run(command, check=True)


def handle_new_download(content_path: str, category: str, tag: str|None = None):
    # Handle movies and TV shows differently
    if category == "Movie":
        print(f"Handling newly downloaded movie. Root path: {content_path}")

        # TODO: Handle movies here
    else:
        if tag is None:
            raise ValueError("Must provide tag when downloading a show.")

        handle_tv_show_download(content_path, tag)


def handle_tv_show_download(content_path: str, tag: str):
    print(f"Handling newly downloaded TV show. Root path: '{content_path}', tag: '{tag}'")
    content = Path(content_path)

    if content.is_file():
        # First make base directory (if doesn't already exist)
        base_show_directory = Path(f"{str(content.parent)}/{tag}/")
        base_show_directory.mkdir(parents=True, exist_ok=True)
        
        # Find season and episode number, then rename file and place into show directory 
        formatted_file_name = rename_tv_show_episode(tag, content)
        new_file_dest = base_show_directory / formatted_file_name
        content.rename(new_file_dest)

        # Now we can perform audio conversion on the file.
        # TODO: Convert audio on file.

    elif content.is_dir():
        print("Handle dir")
        # TODO handle directory



        
    else:
        raise ValueError(f"Content is not file or directory at path '{content_path}'")


def rename_tv_show_episode(show_name: str, original_file: Path) -> Path:
    match = re.search(r"S(\d{2})E(\d{2})", original_file.name, re.IGNORECASE)
    if not match: 
        raise ValueError(f"Can't determine season/episode from content path: {original_file.name}")

    episode_identifier = match.group(0)
    return Path(f"{show_name}-{episode_identifier}{original_file.suffix}")


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Format manager functionality.")
    # parser.add_argument("file", type=str, help="File path for video file to format.")
    # args = parser.parse_args()

    # video_file = args.file  
    video_file = "/home/derek/Desktop/Projects/plex-video-manager/src/plex_video_manager/resources/FuturamaS10E03.mkv"
    tag = "Futurama"

    handle_tv_show_download(video_file, tag)

