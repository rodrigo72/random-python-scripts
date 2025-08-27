import os
import re
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
import requests
from pathlib import Path

SPOTIFY_CLIENT_ID = '--'
SPOTIFY_CLIENT_SECRET = '--'
PLAYLIST_URL = 'https://open.spotify.com/playlist/--'
OUTPUT_DIR = Path('downloads')
START_INDEX = 0

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_filename(name, max_length=200):
    name = name.strip()
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name)
    if len(name) > max_length:
        name = name[:max_length].rstrip()
    return name

def existing_file_for(safe_title, safe_artist):
    base = f"{safe_title} - {safe_artist}"
    preferred_exts = ['.mp3', '.m4a', '.webm', '.opus', '.wav', '.flac', '.aac']
    for ext in preferred_exts:
        p = OUTPUT_DIR / (base + ext)
        if p.exists():
            return p
    matches = sorted(OUTPUT_DIR.glob(f"{base}*"))
    for m in matches:
        if m.suffix in ('.part', '.tmp'):
            return m
        if m.is_file():
            return m
    return None

def find_downloaded_file(safe_title, safe_artist):
    return existing_file_for(safe_title, safe_artist)

def get_playlist_tracks(playlist_url):
    playlist_id = playlist_url.split('/')[-1].split('?')[0]
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def download_from_youtube(query, out_template):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch1:{query}"])

def set_metadata(file_path: Path, title, artist, album, year, cover_url):
    if not file_path.exists():
        raise FileNotFoundError(f"Cannot tag - file not found: {file_path}")
    audio = EasyID3(str(file_path))
    audio['title'] = title
    audio['artist'] = artist
    audio['album'] = album
    audio['date'] = year
    audio.save()
    try:
        img_data = requests.get(cover_url, timeout=15).content
        audio_id3 = ID3(str(file_path))
        audio_id3.add(APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc='Cover',
            data=img_data
        ))
        audio_id3.save()
    except Exception as e:
        print(f"Warning: failed to download/set cover art: {e}")

def main():
    tracks = get_playlist_tracks(PLAYLIST_URL)
    print(f"Found {len(tracks)} tracks in playlist.")
    for i, item in enumerate(tracks[START_INDEX:], start=START_INDEX):
        track = item['track']
        if track is None:
            print(f"Skipping unavailable track at index {i+1}")
            continue
        title = track['name']
        artist = track['artists'][0]['name']
        album = track['album']['name']
        year = track['album']['release_date'].split('-')[0]
        cover_url = track['album']['images'][0]['url'] if track['album']['images'] else None
        safe_title = sanitize_filename(title)
        safe_artist = sanitize_filename(artist)
        base_filename = f"{safe_title} - {safe_artist}"
        out_template = str(OUTPUT_DIR / (base_filename + ".%(ext)s"))
        existing = existing_file_for(safe_title, safe_artist)
        if existing:
            print(f"Skipping already present file for '{title} - {artist}': {existing.name}")
            continue
        query = f"{title} {artist} audio"
        print(f"Downloading ({i+1}/{len(tracks)}): {query}")
        try:
            download_from_youtube(query, out_template)
            downloaded_path = find_downloaded_file(safe_title, safe_artist)
            if not downloaded_path or not downloaded_path.exists():
                raise FileNotFoundError("Download finished but file not found (unexpected filename/extension)")
            set_metadata(downloaded_path, title, artist, album, year, cover_url)
            print(f"Downloaded and tagged: {downloaded_path.name}")
        except Exception as e:
            print(f"Failed to download {title} - {artist}: {e}")

if __name__ == '__main__':
    main()
