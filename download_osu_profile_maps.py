import requests

PROFILE_ID = ''


def download_single_beatmap(beatmap_id, song_title):
    response: requests.Response = requests.get(f"https://beatconnect.io/b/{beatmap_id}?n=1", allow_redirects=True)

    if response.status_code == 200:
        with open(f"{beatmap_id} - {song_title}.osz", "wb") as osx:
            osx.write(response.content)
        return response.status_code
    else:
        print(f"Failed to download {beatmap_id}, {song_title}" )
        return beatmap_id 


def download_beatmaps(beatmaps: list[dict]):
    progress = 0 
    failed_downloads = []
    try:
        for beatmap in beatmaps:
            beatmapset_id = beatmap["beatmap"]["beatmapset_id"] 
            song_title = beatmap["beatmapset"]["title"]
            print(f"Downloading {beatmapset_id} - {song_title}.") 
            is_success = download_single_beatmap(beatmapset_id, song_title)
            if is_success == 0:
                progress += 100/len(beatmaps)
                print(f"Progress: {progress}%")
            else:
                failed_downloads.append(is_success)
    except:
        print(f"Error downloading beatmaps")
    finally:
        with open("failed_downloads1.txt", "wb") as failed_downloads_txt:
            for failed_download in failed_downloads:
                failed_downloads_txt.write(failed_download)
            failed_downloads_txt.flush()


def retrieve_most_played_beatmaps(user_id:str, limit:int, offs:int = 0) -> list[dict]:
    '''
    user_id = Osu! User ID \n
    limit = number of entries 
    '''
    beatmaps: list[dict] = [] 
    offset = offs

    for offset in range(offs , limit, 10):
        try:
            response: requests.Response = requests.get(url=f"https://osu.ppy.sh/users/{user_id}/beatmapsets/most_played?limit=10&offset={offset}")
            if response.status_code != 200:
                print(f"encountered status code: {response.status_code}")
                continue
            beatmaps.extend(response.json())
            download_beatmaps(response.json())
        except:
            print(f"Error encountered at beatmaps {offset} - {offset + 10}")


def main():
     retrieve_most_played_beatmaps(PROFILE_ID, 1037, 12)


if __name__ == "__main__":
    main()
