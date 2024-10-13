import os
from pytube import Playlist, YouTube
import re


def download_playlist_videos(url, max_videos=10):
    playlist = Playlist(url)
    playlist._video_regex = re.compile(r"\"url\":\"(/watch\?v=[\w-]*)")

    os.makedirs('downloads', exist_ok=True)

    downloaded_count = 0
    for video_url in playlist.video_urls:
        try:
            if downloaded_count >= max_videos:
                break

            yt = YouTube(video_url)
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if stream:
                print(f"Downloading video: {yt.title}...")
                stream.download(output_path='downloads/')
                downloaded_count += 1
                print("Download completed.")
            else:
                print(f"No downloadable stream found for video: {yt.title}")
        except Exception as e:
            print(f"Error downloading video: {str(e)}")


if __name__ == "__main__":
    playlist_url = input("Enter the URL of the YouTube playlist: ")
    download_playlist_videos(playlist_url, max_videos=10)
