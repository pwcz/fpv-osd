# DJI FPV OSD Data Writer for Videos

This script, `fpv_osd.py`, is tailored for files captured from DJI FPV drones. It enables the embedding of On-Screen Display (OSD) data onto videos, enhancing them with information such as home distance, drone speed, altitude, and timestamp.

## Requirements

- Python 3.10 or later (recommended)
- OpenCV (`cv2`)
- NumPy
- Pillow (`PIL`)
- tqdm

## Installation

1. **Clone Repository**
   git clone [https://github.com/your_repository.git](https://github.com/pwcz/fpv-osd.git)

2. **Install Dependencies**
   pip install -r requirements.txt

3. **Font Configuration**
   Ensure the `Arial Unicode.ttf` font file is available or configure the `font_path` variable in the script to the appropriate font path.

## Usage

### Writing OSD to Videos

Run the script and provide the list of MP4 files captured by DJI FPV, following the naming convention `DJI_0001.MP4`, `DJI_0002.MP4`, and so on:

```bash
python3.10 fpv_osd.py DJI_0001.MP4 DJI_0002.MP4 ...
```

This will embed OSD details onto the specified videos, generating new MP4 files with OSD information.

### Preview OSD on Single Frame

To preview OSD details on a single frame without processing the entire video:

```bash
python3.10 fpv_osd.py DJI_0001.MP4 --preview
```

This will display a frame with OSD data overlaid. Press 'q' to exit the preview.

## Additional Information

- **OSD Content**: OSD content is defined within the script and can be customized by modifying the `write_osd_to_frame` function.
- **Font and Styling**: OSD text font, color, size, and positioning can be adjusted by modifying variables like `OSD_FONT`, `RGB_COLOR`, `FONT_THICKNESS`, etc., within the script.
