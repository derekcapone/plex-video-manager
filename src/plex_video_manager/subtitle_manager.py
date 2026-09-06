import pysrt

SRT_FILE = "/home/derek/Projects/plex-video-manager/src/plex_video_manager/resources/Futurama.S13E07.1080p.WEB.H264-ETHEL.srt"


def print_subtitles(file_name: str) -> pysrt.SubRipFile:
    subtitles = pysrt.open(file_name)
    
    for sub in subtitles:
        print(sub.start)
        print(sub.end)
        print(sub.text + "\n\n")


if __name__ == "__main__":
    srt_file = SRT_FILE
    print_subtitles(srt_file)
