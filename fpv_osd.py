import argparse
import os
import glob
import platform
import fnmatch

import cv2
import staticmaps
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tqdm.auto import tqdm
from dynamic_map import altitude_mapping, apply_intermediate_zoom_pil

from srt_reader import SrtReader

RGB_COLOR = (255, 255, 255)
OSD_SCALE = 3
LINE_STYLE = cv2.LINE_AA
OSD_FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_THICKNESS = 8


def get_system_font(size=50):
    system = platform.system()
    if system == "Windows":
        font_path = "C:/Windows/Fonts/arialuni.ttf"
    elif system == "Darwin":  # macOS
        font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    else:  # Linux
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Fallback
    return ImageFont.truetype(font_path, size=size)


font = get_system_font()

tile_provider_OpenTopoMap = staticmaps.TileProvider(
    "opentopomap",
    url_pattern="https://$s.tile.opentopomap.org/$z/$x/$y.png",
    shards=["a", "b", "c"],
    max_zoom=17,
)

tile_provider_GoogleImages = staticmaps.TileProvider(
    "googleImages",
    url_pattern="https://mt0.google.com/vt/lyrs=s&hl=en&x=$x&y=$y&z=$z",
    max_zoom=17,
)

tile_provider_thunderforest = staticmaps.TileProvider(
    "opencycle_outdoors",
    url_pattern=f"https://tile.thunderforest.com/outdoors/$z/$x/$y.png?apikey={os.getenv('THUNDERFOREST_API_KEY')}",
    max_zoom=17,
)

tile_provider_thunderforest_landscape = staticmaps.TileProvider(
    "opencycle_landscape",
    url_pattern=f"https://tile.thunderforest.com/landscape/$z/$x/$y.png?apikey={os.getenv('THUNDERFOREST_API_KEY')}",
    max_zoom=17,
)

tile_context = staticmaps.Context()
tile_context.set_zoom(17)


def get_output_file_name(filenames):
    extension = os.path.splitext(filenames[0])[1]
    names = [os.path.splitext(os.path.basename(file))[0].split("_")[1] for file in filenames]
    return "DJI_" + "_".join(names) + "_OSD" + extension


def read_frames(mp4_file_list):
    for file in mp4_file_list:
        cap = cv2.VideoCapture(file)
        frame_number = int(cap.get(7))
        pbar = tqdm(total=frame_number, desc=f"file: {file}")
        while cap.isOpened():
            ret, frame = cap.read()
            pbar.update(1)
            if ret:
                yield frame
            else:
                break

        cap.release()


def write_osd_to_frame(frame, frame_osd, osd_direction):
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_frame = Image.fromarray(frame)

    draw = ImageDraw.Draw(pil_frame)
    drone_speed = f"{frame_osd.speed} m/s".ljust(7)
    drone_alt = f"{frame_osd.height} m".ljust(5)
    frame_direction = osd_direction

    draw.text((3610, 610-50), f"↨{drone_alt}", fill=RGB_COLOR, font=font, stroke_width=3, stroke_fill=(0, 0, 0))
    draw.text((3160, 610-50), f"→{drone_speed}", fill=RGB_COLOR, font=font, stroke_width=3, stroke_fill=(0, 0, 0))

    # Add map
    map_r = 250
    map_x, map_y = (3230, 110)
    tile_context.set_center(staticmaps.create_latlng(frame_osd.lat, frame_osd.long))
    zoom_level, intermediate_scale = altitude_mapping(frame_osd.rt_height)
    tile_context.set_zoom(zoom_level)
    image = tile_context.render_pillow(map_r*2, map_r*2)
    map_image = apply_intermediate_zoom_pil(image, intermediate_scale)
    map_image = map_image.rotate(frame_direction + 180)

    # Create a linear gradient mask
    mask = Image.new("L", map_image.size, 0)
    eclipse_draw = ImageDraw.Draw(mask)
    eclipse_draw.ellipse(((0, 0), (map_r*2, map_r*2)), fill=255)
    map_image.putalpha(mask)

    pil_frame = pil_frame.convert("RGBA")
    pil_frame = pil_frame.convert(map_image.mode)
    pil_frame.alpha_composite(map_image, (map_x, map_y))
    frame_with_text = np.array(pil_frame)

    # cursor acting like drone position
    cx, cy = (map_x + map_r, map_y + map_r)
    size_y = 40
    size_x = 30
    border_inner = 4

    triangle_points = np.array([
        (cx, cy - size_y),
        (cx - size_x, cy + size_y),
        (cx, cy + size_y/2),
        (cx + size_x, cy + size_y)
    ], np.int32)

    cv2.fillPoly(frame_with_text, [triangle_points], color=(255, 255, 255))
    white_border = triangle_points + [[0, border_inner],
                                      [border_inner, -border_inner],
                                      [0, -border_inner],
                                      [-border_inner, -border_inner]]
    cv2.fillPoly(frame_with_text, [white_border], color=(0, 0, 0))

    # white circle around map
    cv2.circle(frame_with_text, (map_x+map_r, map_y+map_r), map_r, (255, 255, 255), 3)

    return cv2.cvtColor(frame_with_text, cv2.COLOR_RGB2BGR)


def write_osd_to_file(mp4_list, srt_list):
    cap = cv2.VideoCapture(mp4_list[0])

    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    video_fps = cap.get(5)
    cap.release()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    output_filename = get_output_file_name(mp4_list)
    print(f"Output file = {output_filename}")

    out = cv2.VideoWriter(output_filename, fourcc, video_fps, (frame_width, frame_height))

    osd_directions = SrtReader(srt_list).get_smooth_direction_array()
    osd_data = SrtReader(srt_list).frame_details_new()
    for frame, osd_text, osd_direction in zip(read_frames(mp4_list), osd_data, osd_directions):
        out.write(write_osd_to_frame(frame, osd_text, osd_direction))

    out.release()


def check_osd(video_file):
    from srt_reader import FrameOsd
    from datetime import datetime
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        raise FileNotFoundError("Failed to read video")

    ret, frame = cap.read()
    if ret:
        osd_data = FrameOsd(height=120, rt_height=12.3, speed=25, home_distance=1,
                            lat=50.041159, long=20.809571, iso_time=datetime.now(), direction_vector=[90])
        frame_with_text = write_osd_to_frame(frame, osd_data, 90)
        cv2.imshow('Frame', frame_with_text)
        while cv2.waitKey(25) & 0xFF != ord('q'):
            pass
        cv2.imwrite("test_frame.png", frame_with_text)
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Write OSD data into video')
    parser.add_argument('--files', metavar='file', type=str, nargs='+', default=None,
                        help='a list of files to process (MP4 only)')
    parser.add_argument('--subtitles', metavar='srt', type=str, nargs='+',
                        default=None,
                        help='a list of subtitle files to process (SRT only)')

    parser.add_argument('--autodetect', action='store_true',
                        help='automatically detect video and subtitle files in the "data" folder')

    parser.add_argument('--tile-provider', type=str,
                        choices=['opentopomap', 'google', 'thunderforest', 'thunderforest_landscape'],
                        default='thunderforest_landscape',
                        help='Choose tile provider (default: thunderforest_landscape)')

    parser.add_argument('--preview', action=argparse.BooleanOptionalAction, help='display only one frame as preview')
    args = parser.parse_args()

    tile_providers = {
        'opentopomap': tile_provider_OpenTopoMap,
        'google': tile_provider_GoogleImages,
        'thunderforest': tile_provider_thunderforest,
        'thunderforest_landscape': tile_provider_thunderforest_landscape,
    }
    tile_context.set_tile_provider(tile_providers[args.tile_provider])

    if args.autodetect:
        video_files = sorted([
            os.path.join("data", f)
            for f in os.listdir("data")
            if fnmatch.fnmatch(f.lower(), "*.mp4")
        ])
        srt_files = glob.glob(os.path.join("data", '*.SRT'))
        video_files.sort()
        srt_files.sort()
    elif args.files and args.srt:
        video_files = args.files
        srt_files = args.srt
    else:
        parser.error("You must provide either --files or --autodetect.")

    if args.preview:
        check_osd(srt_files)
    else:
        write_osd_to_file(video_files, srt_files)
