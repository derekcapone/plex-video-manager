from pathlib import Path

import pytest

from plex_video_manager.download_handler import (
    Episode,
    handle_tv_show_download,
    normalize_category,
    parse_episode,
    show_name_from_tags,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Futurama.S03E04.Parasites.Lost.1080p.WEBRip.mkv", Episode(3, 4)),
        ("show.s03e04.mkv", Episode(3, 4)),
        ("Show S1E1.mkv", Episode(1, 1)),
        ("FuturamaS10E03-original.mkv", Episode(10, 3)),
        ("One.Piece.S01E100.mkv", Episode(1, 100)),
        ("Show.S01E01E02.mkv", Episode(1, 1, 2)),
        ("Show.S01E01-E02.mkv", Episode(1, 1, 2)),
        ("Show.S01E01-02.mkv", Episode(1, 1, 2)),
        ("Show.S01E01-720p.mkv", Episode(1, 1)),
        ("Show.1x05.mkv", Episode(1, 5)),
        ("Show.1920x1080.mkv", None),
        ("Futurama-1999-S03 1080p WEBRip 10bit EAC3 2 0 x265-iVy.mkv", None),
    ],
)
def test_parse_episode(name, expected):
    assert parse_episode(name) == expected


def test_episode_identifier():
    assert Episode(3, 4).identifier() == "S03E04"
    assert Episode(1, 1, 2).identifier() == "S01E01-E02"


@pytest.mark.parametrize("category", ["TVShows", "TV Shows", "tv", "Shows"])
def test_tv_categories(category):
    assert normalize_category(category) == "tv"


@pytest.mark.parametrize("category", ["Movies", "movie"])
def test_movie_categories(category):
    assert normalize_category(category) == "movie"


def test_unknown_category():
    with pytest.raises(ValueError):
        normalize_category("Music")


def test_show_name_from_tags():
    assert show_name_from_tags("Futurama (1999), other") == "Futurama (1999)"
    with pytest.raises(ValueError):
        show_name_from_tags("")


def make_files(root: Path, names: list[str]) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)


def tree(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_season_pack_directory(tmp_path):
    tv = tmp_path / "TVShows"
    download = tv / "FuturamaS03-DownloadedDir"
    make_files(download, [
        "Futurama.S03E02.War.Is.the.H-Word.1080p.WEBRip.mkv",
        "Futurama.S03E03.The.Cryonic.Woman.1080p.WEBRip.mkv",
        "Futurama.S03E03.The.Cryonic.Woman.1080p.WEBRip.en.srt",
        "Futurama.S03E04.Parasites.Lost.1080p.WEBRip.mkv.nfo",
        "Torrent Downloaded From     UIndex.org      .txt",
        "Sample/futurama.s03e02.sample.mkv",
    ])

    show_dir = handle_tv_show_download(download, "Futurama")

    assert show_dir == tv / "Futurama"
    assert tree(tv) == {
        "Futurama/Season 03/Futurama - S03E02.mkv",
        "Futurama/Season 03/Futurama - S03E03.mkv",
        "Futurama/Season 03/Futurama - S03E03.en.srt",
    }


def test_unmatched_video_keeps_torrent_directory(tmp_path):
    tv = tmp_path / "TVShows"
    download = tv / "Pack"
    make_files(download, ["Futurama.S03E02.mkv", "Futurama-1999-S03 1080p.mkv", "info.nfo"])

    handle_tv_show_download(download, "Futurama")

    assert tree(tv) == {
        "Futurama/Season 03/Futurama - S03E02.mkv",
        "Pack/Futurama-1999-S03 1080p.mkv",
        "Pack/info.nfo",
    }


def test_single_file(tmp_path):
    tv = tmp_path / "TVShows"
    make_files(tv, ["FuturamaS10E03-original.mkv"])

    handle_tv_show_download(tv / "FuturamaS10E03-original.mkv", "Futurama")

    assert tree(tv) == {"Futurama/Season 10/Futurama - S10E03.mkv"}


def test_directory_named_like_show(tmp_path):
    tv = tmp_path / "TVShows"
    make_files(tv / "Futurama", ["Futurama.S01E01.mkv", "readme.txt"])

    handle_tv_show_download(tv / "Futurama", "Futurama")

    # The show directory itself must never be deleted.
    assert tree(tv) == {"Futurama/Season 01/Futurama - S01E01.mkv", "Futurama/readme.txt"}


def test_existing_show_and_no_overwrite(tmp_path):
    tv = tmp_path / "TVShows"
    make_files(tv, ["Futurama/Season 01/Futurama - S01E01.mkv"])
    make_files(tv / "Pack", ["Futurama.S01E01.mkv", "Futurama.S02E01.mkv"])

    handle_tv_show_download(tv / "Pack", "Futurama")

    assert tree(tv) == {
        "Futurama/Season 01/Futurama - S01E01.mkv",
        "Futurama/Season 02/Futurama - S02E01.mkv",
        "Pack/Futurama.S01E01.mkv",  # duplicate left alone instead of overwriting
    }
    assert (tv / "Futurama/Season 01/Futurama - S01E01.mkv").read_text() == "Futurama/Season 01/Futurama - S01E01.mkv"


def test_dry_run_changes_nothing(tmp_path):
    tv = tmp_path / "TVShows"
    make_files(tv / "Pack", ["Futurama.S01E01.mkv", "info.nfo"])
    before = tree(tv)

    handle_tv_show_download(tv / "Pack", "Futurama", dry_run=True)

    assert tree(tv) == before
