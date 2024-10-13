import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import csv
from collections import defaultdict

client_id = '<id>'
client_secret = '<id>'
client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
playlist_id = '<id>'
csv_filename = 'example.csv'


def get_all_playlist_items(p_id):
    results = sp.playlist_items(p_id)
    items = results['items']
    while results['next']:
        results = sp.next(results)
        items.extend(results['items'])
    return items


def store_playlist_items(all_tracks, file_name):

    with open(file_name, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ['Song Name', 'Artist(s)', 'Album', 'Release Date', 'Duration (ms)', 'Popularity', 'Track ID',
                      'Album Image URL']
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()

        for item in all_tracks:
            if item['track'] is not None:
                track = item['track']
                song_name = track['name']
                artists = ', '.join([artist['name'] for artist in track['artists']])
                album_name = track['album']['name']
                release_date = track['album']['release_date']
                duration_ms = track['duration_ms']
                popularity = track['popularity']
                track_id = track['id']
                album_image_url = track['album']['images'][0]['url'] if track['album']['images'] else ''
                writer.writerow({'Song Name': song_name, 'Artist(s)': artists, 'Album': album_name,
                                 'Release Date': release_date, 'Duration (ms)': duration_ms, 'Popularity': popularity,
                                 'Track ID': track_id, 'Album Image URL': album_image_url})


def main():
    """
    all_tracks = get_all_playlist_items(playlist_id)
    store_playlist_items(all_tracks, csv_filename)
    """

    interval = 10
    dist = defaultdict(list)
    data_size = 0

    with open(csv_filename, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['Release Date'] == '':
                continue
            data_size += 1
            release_year = int(row['Release Date'][:4])
            dist[(release_year // interval) * interval].append(row)

    for year, songs in sorted(dist.items()):
        print(f'{year}-{year + interval - 1}: {len(songs) / data_size * 100:.2f}% ({len(songs)})')


if __name__ == '__main__':
    main()
