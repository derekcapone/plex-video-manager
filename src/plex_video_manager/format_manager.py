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


def convert_audio_to_aac(video_file: str) -> Path:
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

    subprocess.run(command, check=True)  # Raises exception if error occurred. 
    return Path(output_file)


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

    if content.is_file() and content.suffix == ".mkv":
        # First do the audio conversion if necessary
        if is_audio_format_required(content_path):
            working_file = convert_audio_to_aac(content_path)
            content.unlink()  # No longer need the original, get rid of it
        else:
            # No audio conversion occurred, keep using original file
            working_file = content

        # make base directory (if doesn't already exist)
        base_show_directory = Path(f"{str(working_file.parent)}/{tag}/")
        base_show_directory.mkdir(parents=True, exist_ok=True)
        
        # Find season and episode number, then rename file and place into show directory 
        formatted_file_name = rename_tv_show_episode(tag, working_file)
        new_file_dest = base_show_directory / formatted_file_name
        working_file.rename(new_file_dest)

    elif content.is_dir():
        base_dir = content
        base_show_directory = Path(base_dir.parent / Path(tag) / base_dir.name)
        base_show_directory.mkdir(parents=True, exist_ok=True)
        base_dir.rename(base_show_directory)
        print(f"Base show dir: {base_show_directory}")

        for mkv_file in base_show_directory.rglob('*.mkv'):
            print(f"Processing file: {str(mkv_file.name)}")
            if is_audio_format_required(str(mkv_file)):
                working_file = convert_audio_to_aac(str(mkv_file))
                mkv_file.unlink()  # No longer need the original, get rid of it
            else:
                # No audio conversion occurred, keep using original file
                working_file = mkv_file

            formatted_file_name = rename_tv_show_episode(tag, working_file)
            new_file_dest = base_show_directory / formatted_file_name
            working_file.rename(new_file_dest)
        
    else:
        raise ValueError(f"Content is not file or directory at path '{content_path}'")


def rename_tv_show_episode(show_name: str, original_file: Path) -> Path:
    match = re.search(r"S(\d{2})E(\d{2})", original_file.name, re.IGNORECASE)
    if not match: 
        print(f"Can't determine season/episode from content path: {original_file.name}. Ignoring rename.")
        return original_file

    episode_identifier = match.group(0)
    return Path(f"{show_name}-{episode_identifier}{original_file.suffix}")


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Format manager functionality.")
    # parser.add_argument("file", type=str, help="File path for video file to format.")
    # args = parser.parse_args()

    # video_file = args.file  
    video_file = "/home/derek/Desktop/Projects/plex-video-manager/src/plex_video_manager/resources/FuturamaS03-DownloadedDir/"
    tag = "Futurama"

    handle_tv_show_download(video_file, tag)

