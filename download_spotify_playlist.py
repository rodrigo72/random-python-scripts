import os
import spotipy
import requests
from spotipy.oauth2 import SpotifyClientCredentials
from pytube import YouTube, Search
import logging
from pathvalidate import sanitize_filename
from mutagen.id3 import (ID3, APIC, TIT2, TPE1, TALB, TRCK, TPOS, TCON, TDRC, TCOM, TPUB, TBPM, TSRC, TCOP, TENC,
                         USLT)
from pydub import AudioSegment

PLAYLIST_ID = '-----'
START = 0

# spotify credentials
client_id = '-----'
client_secret = '-----'
client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)


def get_playlist_tracks(playlist_id):
    results = sp.playlist(playlist_id)
    playlist_name = results['name']
    playlist_tracks = results['tracks']
    playlist_items = playlist_tracks['items']

    while playlist_tracks['next']:
        playlist_tracks = sp.next(playlist_tracks)
        playlist_items.extend(playlist_tracks['items'])

    return playlist_name, playlist_items


def download_cover_image(url, output_path):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded cover image to {output_path}")
            return output_path
        else:
            print(f"Failed to download cover image from {url}")
            return None
    except Exception as err:
        print(f"Error downloading cover image: {err}")
        return None


def convert_to_mp3(input_path, output_path):
    try:
        audio = AudioSegment.from_file(input_path)
        audio.export(output_path, format="mp3")
        print(f"Converted {input_path} to MP3: {output_path}")
        return True
    except Exception as err:
        print(f"Failed to convert {input_path} to MP3: {err}")
        return False


def add_metadata(file_path, track_name, artist_name, album_name=None, cover_path=None, track_number=None,
                 disc_number=None, genre=None, year=None, lyrics=None, bpm=None, composer=None, publisher=None,
                 isrc=None, copyright_info=None):
    try:
        audio_file = ID3(file_path)
        audio_file['TIT2'] = TIT2(encoding=3, text=track_name)  # Title
        audio_file['TPE1'] = TPE1(encoding=3, text=artist_name)  # Artist

        if album_name:
            audio_file['TALB'] = TALB(encoding=3, text=album_name)  # Album
        if track_number:
            audio_file['TRCK'] = TRCK(encoding=3, text=str(track_number))  # Track number
        if disc_number:
            audio_file['TPOS'] = TPOS(encoding=3, text=str(disc_number))  # Disc number
        if genre:
            audio_file['TCON'] = TCON(encoding=3, text=genre)  # Genre
        if year:
            audio_file['TDRC'] = TDRC(encoding=3, text=str(year))  # Year
        if lyrics:
            audio_file['USLT'] = USLT(encoding=3, text=lyrics)  # Lyrics
        if bpm:
            audio_file['TBPM'] = TBPM(encoding=3, text=str(bpm))  # BPM (tempo)
        if composer:
            audio_file['TCOM'] = TCOM(encoding=3, text=composer)  # Composer
        if publisher:
            audio_file['TPUB'] = TPUB(encoding=3, text=publisher)  # Publisher
        if isrc:
            audio_file['TSRC'] = TSRC(encoding=3, text=isrc)  # ISRC
        if copyright_info:
            audio_file['TCOP'] = TCOP(encoding=3, text=copyright_info)  # Copyright
        audio_file['TENC'] = TENC(encoding=3, text="Python Script with Mutagen")  # Encoded by

        if cover_path:
            with open(cover_path, 'rb') as album_art:
                audio_file.add(
                    APIC(
                        mime='image/jpeg',
                        type=3,
                        desc=u'Cover',
                        data=album_art.read()
                    )
                )

        audio_file.save()
        print(f"Metadata added for {track_name} by {artist_name}")
    except Exception as err:
        print(f"Failed to add metadata for {track_name} by {artist_name}: {err}")


if __name__ == "__main__":

    pytube_logger = logging.getLogger('pytube')
    pytube_logger.setLevel(logging.ERROR)

    name, tracks = get_playlist_tracks(PLAYLIST_ID)
    print(f"Playlist: {name}")
    print(f"Number of tracks: {len(tracks)}")

    playlist_dir = sanitize_filename(name)
    if not os.path.exists(playlist_dir):
        os.makedirs(playlist_dir)

    failed_downloads = []
    failed_downloads_count = 0

    tracks = tracks[START:]

    for i, item in enumerate(tracks):

        if item['track'] is None:
            print(f"\n{i + 1}: No track found")
            failed_downloads_count += 1
            continue

        track = item['track']

        if 'name' not in track:
            print(f"\n{i + 1}: No track name found")
            failed_downloads_count += 1
            continue

        track_name = track['name'] if 'name' in track else None
        track_number = track['track_number'] if 'track_number' in track else None
        track_album = track['album'] if 'album' in track else None
        bpm = track['tempo'] if 'tempo' in track else None

        if track_album and 'name' in track_album:
            album_name = track_album['name']
        else:
            album_name = None

        if track_album and 'release_date' in track_album and isinstance(track_album['release_date'], str) and len(
                track_album['release_date']) >= 4:
            year = track_album['release_date'][:4]
        else:
            year = None

        if track_album and 'label' in track_album:
            publisher = track_album['label']
        else:
            publisher = None

        if 'artists' in track and len(track['artists']) > 0 and 'name' in track['artists'][0]:
            artist_name = track['artists'][0]['name']
        else:
            artist_name = None

        if track_album and 'images' in track_album and len(track_album['images']) > 0 and 'url' in \
                track_album['images'][0]:
            cover_url = track_album['images'][0]['url']
        else:
            cover_url = None

        print(f"\n{i + 1}: {track_name} by {artist_name}")

        s = Search(f"{track_name} {artist_name}")
        result = None
        for video in s.results:
            if hasattr(video, 'video_id'):
                result = video
                break

        if result:
            entry = result.title
            print(entry, result.watch_url)
            yt = YouTube(result.watch_url)
            try:
                audio_stream = yt.streams.filter(only_audio=True).first()
                if audio_stream:
                    raw_filename = sanitize_filename(f"{track_name} - {artist_name}")
                    raw_file_path = os.path.join(playlist_dir, f"{raw_filename}.webm")
                    audio_stream.download(output_path=playlist_dir, filename=f"{raw_filename}.webm")

                    mp3_file_path = os.path.join(playlist_dir, f"{raw_filename}.mp3")
                    if convert_to_mp3(raw_file_path, mp3_file_path):
                        cover_image_path = None
                        if cover_url:
                            cover_image_path = download_cover_image(
                                cover_url, os.path.join(playlist_dir, f"{raw_filename}_cover.jpg")
                            )
                        add_metadata(
                            mp3_file_path, track_name, artist_name, album_name, cover_image_path,
                            track_number, None, None, year, None, bpm, None, publisher,
                            None, None
                        )
                        if cover_image_path:
                            os.remove(cover_image_path)
                    os.remove(raw_file_path)
                else:
                    print(f"No audio stream found for {track_name} by {artist_name}")
            except Exception as e:
                failed_downloads.append((track_name, artist_name))
                failed_downloads_count += 1
                print(f"Failed to download audio for {track_name} by {artist_name}: {e}")
        else:
            print(f"No valid result found for {track_name} by {artist_name}")

    print(f"\n{failed_downloads_count} Failed downloads:")
    for failed_download in failed_downloads:
        print(f" - Failed to download audio for {failed_download[0]} by {failed_download[1]}")


"""
Modified regex (cypher.py -> get_throttling_function_name) (might not work in the future):
function_patterns = [
        # https://github.com/ytdl-org/youtube-dl/issues/29326#issuecomment-865985377
        # https://github.com/yt-dlp/yt-dlp/commit/48416bc4a8f1d5ff07d5977659cb8ece7640dcd8
        # var Bpa = [iha];
        # ...
        # a.C && (b = a.get("n")) && (b = Bpa[0](b), a.set("n", b),
        # Bpa.length || iha("")) }};
        # In the above case, `iha` is the relevant function name
        r'a\.[a-zA-Z]\s*&&\s*\([a-z]\s*=\s*a\.get\("n"\)\)\s*&&.*?\|\|\s*([a-z]+)',
        r'\([a-z]\s*=\s*([a-zA-Z0-9$]+)(\[\d+\])?\([a-z]\)',
        r'\([a-z]\s*=\s*([a-zA-Z0-9$]+)(\[\d+\])\([a-z]\)',
    ]
"""
