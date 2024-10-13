import instaloader
from instaloader import Profile
import os

TARGET = ''
OUTPUT_DIR = ''

MAX_POSTS = 15000


def main():
    output_dir = os.path.join(OUTPUT_DIR, TARGET)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    loader = instaloader.Instaloader(
        dirname_pattern=output_dir,
        download_videos=False,
        download_video_thumbnails=False,
        post_metadata_txt_pattern='',
        save_metadata=False,
        download_geotags=False,
        download_comments=False,
        storyitem_metadata_txt_pattern='',
    )

    profile = Profile.from_username(loader.context, TARGET)
    post_iterator = profile.get_posts()
    max_posts = MAX_POSTS

    try:
        for post in post_iterator:
            if not post.is_video:
                if max_posts == 0:
                    break
                max_posts -= 1
                loader.download_post(post, target=profile.username)
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return

    loader.context.session.close()


if __name__ == '__main__':
    main()
