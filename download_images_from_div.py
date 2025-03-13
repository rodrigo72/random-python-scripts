import os
import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def download_images_from_div(url, div_id, output_folder):
    try:
        response = requests.get(url)
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return

    if response.status_code != 200:
        print(f"Failed to retrieve page. Status code: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    container = soup.find("div", {"id": div_id})
    if not container:
        print(f"No div found with ID: {div_id}")
        return

    images = container.find_all("img")
    if not images:
        print("No images found in the selected div.")
        return

    os.makedirs(output_folder, exist_ok=True)

    for i, img in enumerate(images, start=1):
        src = img.get("src")
        if not src:
            print("Skipping an image with no src attribute.")
            continue

        img_url = urljoin(url, src)
        
        file_name = os.path.basename(img_url)
        if not file_name or '.' not in file_name:
            file_name = f"image_{i}.jpg"
        file_path = os.path.join(output_folder, file_name)
        
        print(f"Downloading {img_url} as {file_name}...")
        try:
            img_data = requests.get(img_url).content
        except Exception as e:
            print(f"Failed to download {img_url}: {e}")
            continue

        with open(file_path, "wb") as f:
            f.write(img_data)
    
    print("Download complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download images from a specific div of a webpage."
    )
    parser.add_argument("url", help="The URL of the website to scrape.")
    parser.add_argument("div_id", help="The ID of the target div.")
    parser.add_argument(
        "--output",
        default="images",
        help="Folder where images will be saved (default: images)."
    )
    args = parser.parse_args()

    download_images_from_div(args.url, args.div_id, args.output)
