import os
import random
from PIL import Image


def map_directory_images(directory, images_paths):
    for filename in os.listdir(directory):
        if filename.lower().endswith((".jpg", ".png", ".jpeg")):
            images_paths.append(os.path.join(directory, filename))
        elif os.path.isdir(os.path.join(directory, filename)):
            map_directory_images(os.path.join(directory, filename), images_paths)


def open_random_images(images_paths, num_images=3):
    selected_paths = random.sample(images_paths, min(num_images, len(images_paths)))

    for image_path in selected_paths:
        image = Image.open(image_path)
        image.show()


if __name__ == "__main__":
    image_paths = []
    path = ""

    map_directory_images(path, image_paths)
    number_of_images_to_open = 1

    while True:
        user_input = input("Press enter to open " + str(number_of_images_to_open) + " random image(s) or 'q' to quit: ")
        if user_input.lower() == 'q':
            break
        open_random_images(image_paths, number_of_images_to_open)

    print("Program terminated.")
