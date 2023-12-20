import argparse
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tqdm.auto import tqdm

from srt_reader import SrtReader

RGB_COLOR = (255, 255, 255)
OSD_SCALE = 3
LINE_STYLE = cv2.LINE_AA
OSD_FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_THICKNESS = 8

font_path = "Arial Unicode.ttf"
font = ImageFont.truetype(font_path, size=150)


def check_srt_file(filepath):
    mp4_name, mp4_extension = os.path.splitext(filepath)
    srt_path = mp4_name + '.srt'

    return srt_path if os.path.exists(srt_path) else None


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


def write_osd_to_frame(frame, frame_osd):
    # Convert the frame to a PIL image
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_frame = Image.fromarray(frame)

    # Use PIL's ImageDraw to write text on the frame
    draw = ImageDraw.Draw(pil_frame)
    home_distance = f"{frame_osd.home_distance} m".ljust(6)
    drone_speed = f"{frame_osd.speed} km/h".ljust(8)
    drone_alt = f"{frame_osd.height} m".ljust(5)
    text = f"⌂{home_distance}   →{drone_speed}   ↨{drone_alt}   ⌚{frame_osd.iso_time.strftime('%H:%M')}"
    draw.text((676, 0), text, fill=RGB_COLOR, font=font, stroke_width=3, stroke_fill=(0, 0, 0))

    # Convert the PIL image back to a NumPy array
    frame_with_text = np.array(pil_frame)
    frame_with_text = cv2.cvtColor(frame_with_text, cv2.COLOR_RGB2BGR)
    return frame_with_text


def write_osd_to_file(file_list):
    cap = cv2.VideoCapture(file_list[0])

    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    video_fps = cap.get(5)
    cap.release()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    output_filename = get_output_file_name(file_list)
    print(f"Output file = {output_filename}")

    out = cv2.VideoWriter(output_filename, fourcc, video_fps, (frame_width, frame_height))
    srt_files = [check_srt_file(file_name) for file_name in file_list]
    if not all(srt_files):
        raise RuntimeError("SRT file not found!")

    osd_data = SrtReader(srt_files).frame_details_new()
    for frame in read_frames(file_list):
        out.write(write_osd_to_frame(frame, next(osd_data)))

    out.release()


def check_osd(video_file):
    from srt_reader import FrameOsd
    from datetime import datetime
    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        print("Failed to open file")
        exit(-1)

    ret, frame = cap.read()
    if ret:
        osd_data = FrameOsd(height=120, speed=15, home_distance=1,
                            lat="N49 58'01.91''", long="E19 46'12.64''", iso_time=datetime.now())
        frame_with_text = write_osd_to_frame(frame, osd_data)
        cv2.imshow('Frame', frame_with_text)
        while cv2.waitKey(25) & 0xFF != ord('q'):
            pass
        cv2.imwrite("test_frame.png", frame_with_text)
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Write OSD data into video')
    parser.add_argument('files', metavar='file', type=str, nargs='+',
                        help='a list of files to process (MP4 only)')
    parser.add_argument('--preview', action=argparse.BooleanOptionalAction, help='display only one frame as preview')
    args = parser.parse_args()

    if args.preview:
        check_osd(args.files[0])
    else:
        write_osd_to_file(args.files)
