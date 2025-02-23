import staticmaps
import cv2
import numpy as np
from PIL import Image


def altitude_mapping(altitude):
    max_zoom = 17
    min_zoom = 13
    if altitude <= 5:
        return max_zoom, 1
    if altitude >= 120:
        return min_zoom, 1
    a = (min_zoom - max_zoom) / 115
    b = max_zoom - 5 * a
    val = a * altitude + b
    return int(val), (val % 1)*-.5 + 1.


def render_image(context, image_width, image_height):
    return np.array(context.render_pillow(image_width, image_height))


# Function to add zoom level text to the image
def add_zoom_level_text(image, height, zoom_level, intermediate_scale):
    font = cv2.FONT_HERSHEY_SIMPLEX
    text = f"h: {height} (z: {zoom_level}, s: {intermediate_scale})"
    position = (10, 30)  # Top-left corner
    font_scale = 1
    font_color = (0, 0, 255)  # Red color
    thickness = 2
    cv2.putText(image, text, position, font, font_scale, font_color, thickness)
    return image


def apply_intermediate_zoom_pil(image, scale):
    if scale == 1.0:
        return image  # No scaling needed

    # Get the original dimensions of the image
    width, height = image.size

    # Calculate the new dimensions after scaling
    new_width = int(width / scale)
    new_height = int(height / scale)

    # Resize the image to the new dimensions using Pillow
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Calculate the crop area to maintain the original image size
    start_x = max(0, (new_width - width) // 2)
    start_y = max(0, (new_height - height) // 2)
    end_x = start_x + width
    end_y = start_y + height

    # Ensure the crop area does not exceed the resized image dimensions
    end_x = min(end_x, new_width)
    end_y = min(end_y, new_height)

    # Crop the image to the original size
    cropped_image = resized_image.crop((start_x, start_y, end_x, end_y))
    return cropped_image


def apply_intermediate_zoom(image, scale):
    if scale == 1.0:
        return image  # No scaling needed

    height, width = image.shape[:2]
    # Calculate the new dimensions after scaling
    new_width = int(width / scale)
    new_height = int(height / scale)

    # Resize the image to the new dimensions
    resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

    # Calculate the crop area to maintain the original image size
    start_x = max(0, (new_width - width) // 2)
    start_y = max(0, (new_height - height) // 2)
    end_x = start_x + width
    end_y = start_y + height

    # Ensure the crop area does not exceed the resized image dimensions
    end_x = min(end_x, new_width)
    end_y = min(end_y, new_height)

    # Crop the image to the original size
    cropped_image = resized_image[start_y:end_y, start_x:end_x]
    return cropped_image


def map_test():
    import os

    # Set GPS coordinates and download OSM data
    latitude = 50.041159
    longitude = 20.809571

    tile_provider_OpenTopoMap = staticmaps.TileProvider(
        "opentopomap",
        url_pattern="https://$s.tile.opentopomap.org/$z/$x/$y.png",
        shards=["a", "b", "c"],
        max_zoom=17,
    )

    tile_provider_Outdoor = staticmaps.TileProvider(
        "maptiler_outdoor",
        url_pattern="https://tile.openstreetmap.org/$z/$x/$y.png",
        max_zoom=16
    )

    tile_provider_GoogleImages = staticmaps.TileProvider(
        "googleImages_t",
        url_pattern="https://mt0.google.com/vt/lyrs=t&hl=en&x=$x&y=$y&z=$z",
        max_zoom=17,
    )

    tile_provider_thunderstrike = staticmaps.TileProvider(
        "opencycle_cycle",
        url_pattern=f"https://tile.thunderforest.com/cycle/$z/$x/$y.png?apikey={os.getenv('THUNDERFOREST_API_KEY')}",
        max_zoom=17,
    )

    context = staticmaps.Context()
    context.set_tile_provider(tile_provider_thunderstrike)

    p1 = staticmaps.create_latlng(latitude, longitude)
    context.set_center(p1)

    # Initial zoom level
    zoom_level = 17
    context.set_zoom(zoom_level)

    # Intermediate zoom scaling factor
    intermediate_scale = 1.0  # Start with no scaling

    # Fixed image size
    image_width, image_height = 800, 800

    height = 0
    image = render_image(context, image_width, image_height)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    image = apply_intermediate_zoom(image, intermediate_scale)
    image = add_zoom_level_text(image, height, zoom_level, intermediate_scale)

    cv2.imshow("Map", image)
    re_render = False
    while True:
        key = cv2.waitKey(0) & 0xFF
        # Check if the key is 'q' to quit
        if key == ord('q'):
            break
        elif key == ord('+'):
            re_render = True
            if height < 120:
                height += 1
                re_render = True
        elif key == ord('-'):
            re_render = True
            if height > 0:
                height -= 1
        if re_render:
            zoom_level, intermediate_scale = altitude_mapping(height)
            context.set_zoom(zoom_level)
            image = render_image(context, image_width, image_height)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            image = apply_intermediate_zoom(image, intermediate_scale)
            image = add_zoom_level_text(image, height, zoom_level, intermediate_scale)
            cv2.imshow("Map", image)
            re_render = False

    cv2.destroyAllWindows()


if __name__ == "__main__":
    map_test()
