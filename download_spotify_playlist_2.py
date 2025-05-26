import os
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
import requests
from pathlib import Path

SPOTIFY_CLIENT_ID = '---'
SPOTIFY_CLIENT_SECRET = '---'
PLAYLIST_URL = 'https://open.spotify.com/playlist/---'
OUTPUT_DIR = 'downloads'

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_playlist_tracks(playlist_url):
    playlist_id = playlist_url.split('/')[-1].split('?')[0]
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']

    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def download_from_youtube(query, filename):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch1:{query}"])

def set_metadata(file_path, title, artist, album, year, cover_url):
    audio = EasyID3(file_path)
    audio['title'] = title
    audio['artist'] = artist
    audio['album'] = album
    audio['date'] = year
    audio.save()

    # Add cover art
    img_data = requests.get(cover_url).content
    audio = ID3(file_path)
    audio.add(APIC(
        encoding=3,
        mime='image/jpeg',
        type=3,  # Cover (front)
        desc='Cover',
        data=img_data
    ))
    audio.save()

def main():
    tracks = get_playlist_tracks(PLAYLIST_URL)
    print(f"Found {len(tracks)} tracks in playlist.")

    for item in tracks:
        track = item['track']
        title = track['name']
        artist = track['artists'][0]['name']
        album = track['album']['name']
        year = track['album']['release_date'].split('-')[0]
        cover_url = track['album']['images'][0]['url']

        query = f"{title} {artist} audio"
        filename = Path(OUTPUT_DIR) / f"{title} - {artist}.%(ext)s"
        output_path = Path(OUTPUT_DIR) / f"{title} - {artist}.mp3"

        if output_path.exists():
            print(f"Skipping already downloaded: {title} - {artist}")
            continue

        print(f"Downloading: {query}")
        try:
            download_from_youtube(query, str(filename))
            set_metadata(str(output_path), title, artist, album, year, cover_url)
            print(f"Downloaded and tagged: {output_path}")
        except Exception as e:
            print(f"Failed to download {title} - {artist}: {e}")


if __name__ == '__main__':
    main()
