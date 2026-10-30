from dotenv import load_dotenv
import os
import requests
from plex_video_manager.format_manager import *


PLEX_HOST = "http://127.0.0.1:32400"


def get_plex_token() -> str:
    load_dotenv()
    plex_token = os.getenv("PLEX_TOKEN")

    if plex_token is None:
        raise Exception("Can't retrieve Plex token")

    return plex_token


def scan_plex_library(plex_token: str):
    requests.get(
        f"{PLEX_HOST}/library/sections/all/refresh", params={"X-Plex-Token": plex_token}, timeout=10,
    ).raise_for_status()


if __name__ == "__main__":
    # plex_token = get_plex_token()

    # scan_plex_library(plex_token)
    print("Testing that this works")
