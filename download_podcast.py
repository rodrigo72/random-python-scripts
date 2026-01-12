import feedparser
import requests
import os
import re


def download_podcast(rss_url, export_folder="downloads"):
    feed = feedparser.parse(rss_url)
    podcast_title = feed.feed.title
    print(f"Starting download for: {podcast_title}")

    safe_podcast_title = re.sub(r'[\\/*?:"<>|]', "", podcast_title)
    full_path = os.path.join(export_folder, safe_podcast_title)

    if not os.path.exists(full_path):
        os.makedirs(full_path)
        print(f"Created folder: {full_path}")

    for entry in feed.entries:
        audio_url = None
        for link in entry.enclosures:
            if link.type.startswith('audio'):
                audio_url = link.href
                break
        
        if not audio_url:
            continue

        ep_title = re.sub(r'[\\/*?:"<>|]', "", entry.title)
        file_extension = audio_url.split('.')[-1].split('?')[0]
        filename = f"{ep_title}.{file_extension}"
        filepath = os.path.join(full_path, filename)

        if os.path.exists(filepath):
            print(f"Skipping: {ep_title} (Already exists)")
            continue

        print(f"Downloading: {ep_title}...")
        try:
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"Failed to download {ep_title}: {e}")

    print("All downloads complete")


rss_link = ""
download_podcast(rss_link, export_folder="")
