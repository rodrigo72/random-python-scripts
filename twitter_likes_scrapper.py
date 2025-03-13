from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import requests
import os

TWITTER_USER = ''

driver = webdriver.Firefox()

driver.get("https://x.com/login")
print("Please log in to your account in the opened browser window, then press Enter here.")
input("Press Enter after you have logged in...")

driver.get(f"https://x.com/{TWITTER_USER}/likes")
time.sleep(5)

downloaded_urls = set()
download_folder = "downloaded_images"
os.makedirs(download_folder, exist_ok=True)

SCROLL_PAUSE_TIME = 2
last_height = driver.execute_script("return document.body.scrollHeight")

while True:
    images = driver.find_elements(By.CLASS_NAME, "css-9pa8cd")
    print(f"Found {len(images)} images on the page.")
    
    for img in images:
        src = img.get_attribute("src")
        if src and "pbs.twimg.com/media" in src:
            high_res_src = src.split("&name=")[0] + "&name=orig"
            if high_res_src not in downloaded_urls:
                downloaded_urls.add(high_res_src)
                print(f"Downloading image: {high_res_src}")
                try:
                    response = requests.get(high_res_src)
                    if response.status_code == 200:
                        filename = os.path.join(download_folder, high_res_src.split("/")[-1].split("?")[0] + ".jpg")
                        with open(filename, "wb") as file:
                            file.write(response.content)
                    else:
                        print(f"Failed to download image, status code: {response.status_code}")
                except Exception as e:
                    print(f"Error downloading {high_res_src}: {e}")
    
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(SCROLL_PAUSE_TIME)
    new_height = driver.execute_script("return document.body.scrollHeight")
    
    if new_height == last_height:
        print("No more content to load.")
        break
    last_height = new_height

driver.quit()
print("Download complete! Images are saved in the folder:", download_folder)
