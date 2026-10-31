"""Entry point called by qBittorrent (via test-torrent-script.sh) when a download finishes.

Organizes the downloaded content into a Plex-friendly layout and triggers a Plex scan:

    TVShows/<Show>/Season 03/<Show> - S03E04.mkv
"""

import argparse
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv

from plex_video_manager.format_manager import process_audio_track

log = logging.getLogger("plex_video_manager")

DEFAULT_PLEX_HOST = "http://127.0.0.1:32400"

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx"}
# Files that are safe to delete together with the leftover torrent directory.
JUNK_EXTENSIONS = {".nfo", ".txt", ".sfv", ".url", ".jpg", ".jpeg", ".png", ".exe", ".md5"}

MOVIE_CATEGORY = "Movies"
TV_CATEGORY = "TV"

# S01E02, s1e2, S01.E02, S01E100, multi-episode S01E01E02 / S01E01-E02 / S01E01-02
SXXEYY_PATTERN = re.compile(
    r"s(\d{1,2})[ ._-]?e(\d{1,3})(?!\d)(?:-?e(\d{1,3})(?!\d)|-(\d{1,3})(?!\d))?",
    re.IGNORECASE,
)
# 1x02 (the digit lookarounds keep resolutions like 1920x1080 from matching)
NXNN_PATTERN = re.compile(r"(?<!\d)(\d{1,2})x(\d{2,3})(?!\d)", re.IGNORECASE)
SAMPLE_PATTERN = re.compile(r"(?:^|[ ._-])sample(?:$|[ ._-])", re.IGNORECASE)
# Trailing subtitle qualifiers to keep, e.g. ".en", ".eng", ".forced", ".sdh"
SUBTITLE_QUALIFIER_PATTERN = re.compile(r"\.([a-z]{2,3}|forced|sdh|cc)$", re.IGNORECASE)


@dataclass(frozen=True)
class Episode:
    season: int
    episode: int
    end_episode: int | None = None

    def identifier(self) -> str:
        ident = f"S{self.season:02}E{self.episode:02}"
        if self.end_episode is not None:
            ident += f"-E{self.end_episode:02}"
        return ident


# ---------------------------------------------------------------------------
# Parsing / naming
# ---------------------------------------------------------------------------

def parse_episode(name: str) -> Episode | None:
    """Extract season/episode numbers from a file name, or None if not found."""
    match = SXXEYY_PATTERN.search(name)
    if match:
        season, episode = int(match.group(1)), int(match.group(2))
        end = match.group(3) or match.group(4)
        end_episode = int(end) if end else None
        # Guard against things like "S01E01-720p" being read as a range.
        if end_episode is not None and not (episode < end_episode <= episode + 20):
            end_episode = None
        return Episode(season, episode, end_episode)

    match = NXNN_PATTERN.search(name)
    if match:
        return Episode(int(match.group(1)), int(match.group(2)))

    return None


def build_episode_name(show_name: str, episode: Episode, suffix: str) -> str:
    return f"{show_name} - {episode.identifier()}{suffix}"


def subtitle_suffix(subtitle_file: Path) -> str:
    """Keep language/forced qualifiers: 'x.S01E01.en.srt' -> '.en.srt'."""
    match = SUBTITLE_QUALIFIER_PATTERN.search(subtitle_file.stem)
    qualifier = f".{match.group(1).lower()}" if match else ""
    return f"{qualifier}{subtitle_file.suffix.lower()}"


def is_sample(file: Path) -> bool:
    return bool(SAMPLE_PATTERN.search(file.stem))


def show_name_from_tags(tags: str | None) -> str:
    """qBittorrent passes tags comma separated (%G); use the first one as the show name."""
    names = [t.strip() for t in (tags or "").split(",") if t.strip()]
    if not names:
        raise ValueError("A tag with the show name is required for TV downloads.")
    # A path separator in the tag would create nested directories.
    return names[0].replace("/", "-")


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------

def move_file(src: Path, dest: Path, dry_run: bool) -> bool:
    """Move src to dest without ever overwriting. Returns True if moved (or would be)."""
    if src.resolve() == dest.resolve():
        return True
    if dest.exists():
        log.warning("Destination already exists, leaving '%s' in place: %s", src.name, dest)
        return False

    log.info("%sMove '%s' -> '%s'", "[dry-run] " if dry_run else "", src, dest)
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dest)
    return True


def files_with_extensions(root: Path, extensions: set[str]) -> list[Path]:
    # Materialize the list up front: we move files while iterating.
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def organize_tv_file(file: Path, show_dir: Path, show_name: str, dry_run: bool) -> bool:
    """Move one video or subtitle file into show_dir/Season XX/. Returns True on success."""
    episode = parse_episode(file.name)
    if episode is None:
        log.warning("Can't determine season/episode for '%s', leaving it in place.", file)
        return False

    is_video = file.suffix.lower() in VIDEO_EXTENSIONS
    if is_video and not dry_run:
        file = process_audio_track(file)

    suffix = file.suffix.lower() if is_video else subtitle_suffix(file)
    dest = show_dir / f"Season {episode.season:02}" / build_episode_name(show_name, episode, suffix)
    return move_file(file, dest, dry_run)


def remove_leftovers(directory: Path, moved: set[Path], dry_run: bool) -> None:
    """Delete the torrent directory if only junk (nfo/txt/samples/empty dirs) remains."""
    remaining = [p for p in directory.rglob("*") if p.is_file() and p not in moved]
    keep = [p for p in remaining if p.suffix.lower() not in JUNK_EXTENSIONS and not is_sample(p)]
    if keep:
        log.warning(
            "Not removing '%s', it still contains: %s", directory, ", ".join(p.name for p in keep)
        )
        return

    log.info("%sRemove leftover directory '%s'", "[dry-run] " if dry_run else "", directory)
    if not dry_run:
        shutil.rmtree(directory)


def handle_tv_show_download(content_path: Path, show_name: str, dry_run: bool = False) -> Path:
    """Organize a finished TV download. Returns the show directory."""
    log.info("Handling TV show download '%s' (show: '%s')", content_path, show_name)
    show_dir = content_path.parent / show_name

    if content_path.is_file():
        if content_path.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError(f"Not a video file: '{content_path}'")
        organize_tv_file(content_path, show_dir, show_name, dry_run)

    elif content_path.is_dir():
        # A torrent directory named after the show (TVShows/Futurama) *is* the show directory.
        if content_path.resolve() == show_dir.resolve():
            show_dir = content_path

        moved: set[Path] = set()
        for file in files_with_extensions(content_path, VIDEO_EXTENSIONS | SUBTITLE_EXTENSIONS):
            if is_sample(file):
                log.info("Skipping sample '%s'", file.name)
                continue
            if organize_tv_file(file, show_dir, show_name, dry_run):
                moved.add(file)

        if content_path != show_dir:
            remove_leftovers(content_path, moved, dry_run)

    else:
        raise ValueError(f"Content is not a file or directory: '{content_path}'")

    return show_dir


# ---------------------------------------------------------------------------
# Plex
# ---------------------------------------------------------------------------

def get_plex_config() -> tuple[str, str]:
    load_dotenv()
    plex_token = os.getenv("PLEX_TOKEN")
    if not plex_token:
        raise RuntimeError("PLEX_TOKEN is not set (add it to .env).")
    return os.getenv("PLEX_HOST", DEFAULT_PLEX_HOST), plex_token


def find_library_section(host: str, token: str, path: Path) -> str | None:
    """Return the key of the Plex library section whose folder contains path."""
    response = requests.get(
        f"{host}/library/sections",
        headers={"X-Plex-Token": token, "Accept": "application/json"},
        timeout=10,
    )
    response.raise_for_status()
    for section in response.json()["MediaContainer"].get("Directory", []):
        for location in section.get("Location", []):
            if path.is_relative_to(location["path"]):
                return section["key"]
    return None


def scan_plex_library(path: Path) -> None:
    """Partial scan of just `path` if a matching library is found, else scan everything."""
    host, token = get_plex_config()
    path = path.resolve()
    headers = {"X-Plex-Token": token}

    section = find_library_section(host, token, path)
    if section is None:
        log.warning("No Plex library contains '%s', refreshing all libraries.", path)
        url, params = f"{host}/library/sections/all/refresh", {}
    else:
        log.info("Scanning Plex library section %s for '%s'", section, path)
        url, params = f"{host}/library/sections/{section}/refresh", {"path": str(path)}

    requests.get(url, headers=headers, params=params, timeout=10).raise_for_status()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def handle_new_download(content_path: Path, category: str, tags: str | None, dry_run: bool) -> None:
    if category == MOVIE_CATEGORY:
        # TODO: rename to "Title (Year)/Title (Year).ext". For now just make it show up in Plex.
        log.info("Handling movie download '%s' (no renaming yet)", content_path)
        scan_path = content_path.parent
    else:
        scan_path = handle_tv_show_download(content_path, show_name_from_tags(tags), dry_run)

    if dry_run:
        log.info("[dry-run] Would scan Plex for '%s'", scan_path)
    else:
        scan_plex_library(scan_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize a finished qBittorrent download for Plex.")
    parser.add_argument("content_path", type=Path, help="Content path of the download (qBittorrent %%F).")
    parser.add_argument("--category", required=True, help="qBittorrent category (%%L), e.g. Movies or TVShows.")
    parser.add_argument("--tags", default=None, help="qBittorrent tags (%%G); the first is the show name.")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be done.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)

    try:
        handle_new_download(args.content_path, args.category, args.tags, args.dry_run)
    except Exception:
        log.exception("Failed to handle download '%s'", args.content_path)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
