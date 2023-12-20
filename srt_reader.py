from datetime import datetime
from statistics import mean
from math import radians, sin, cos, sqrt, atan2
import re
from collections import namedtuple
from itertools import chain

FrameSrt = namedtuple("FrameSrt", "id time_range time_diff iso_time gps iso shutter")
FrameOsd = namedtuple("FrameOsd", "height speed home_distance lat long iso_time")
R = 6371000
GPS_RE = re.compile(r".*latitude: (.*?)].*longitude: (.*?)].*altitude: (.*?)].*")
DIFF_TIME_RE = re.compile(r".*DiffTime: (\d{1,2}?)ms")
ISO_RE = re.compile(r"\[iso : (.*?)\]")
SHUTTER_RE = re.compile(r"\[shutter : (.*?)\]")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def get_gps_coordinate(gps_str):
    return tuple(float(x) for x in GPS_RE.findall(gps_str)[0])


def get_iso(details_line):
    return ISO_RE.findall(details_line)[0]


def get_shutter(details_line):
    return SHUTTER_RE.findall(details_line)[0]


def get_home(filename):
    data = SrtReader.read_frame_srt(filename)
    return next(data).gps


def deg_to_dms(deg, coordinate=None, ndp=1):
    m, s = divmod(abs(deg) * 3600, 60)
    d, m = divmod(m, 60)
    if deg < 0:
        d = -d
    d, m = int(d), int(m)

    if coordinate == 'latitude':
        hemi = 'N' if d >= 0 else 'S'
    elif coordinate == 'longitude':
        hemi = 'E' if d >= 0 else 'W'
    else:
        hemi = '?'

    return '{d:d}\u00b0{m:d}′{s:.{ndp:d}f}″{hemi:1s}'.format(d=abs(d), m=m, s=s, hemi=hemi, ndp=ndp)


class SrtReader:
    def __init__(self, filename, fix_alt=True, shift=None):
        self.file_name = filename
        self.home = get_home(filename[0])
        self.fix_alt = fix_alt
        self.shift = shift
        self.current_osd = None

    @staticmethod
    def calculate_distance(coord1, coord2):
        # Convert latitude and longitude to radians
        lat1, lon1, alt1 = map(radians, coord1)
        lat2, lon2, alt2 = map(radians, coord2)

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c

        # Calculate altitude difference
        alt_diff = abs(alt2 - alt1) * 10

        # Calculate the total distance
        return sqrt(distance ** 2 + alt_diff ** 2)

    def fix_altitude(self, alt):
        if not self.fix_alt:
            return alt
        if self.shift is None:
            self.shift = alt
        return (alt - self.shift) * 10.

    @staticmethod
    def read_frame_srt(file_name):
        with open(file_name) as file:
            while file.readable():
                line = file.readline()
                if not line:
                    break
                elif len(line.strip()) == 0:
                    continue
                sub_id = int(line.rstrip())
                time_range = file.readline().rstrip()
                time_diff = int(DIFF_TIME_RE.findall(file.readline().rstrip())[0]) / 1000.
                iso_time = datetime.strptime(file.readline().rstrip(), DATETIME_FORMAT)
                details_line = file.readline().rstrip()
                iso = get_iso(details_line)
                shutter = get_shutter(details_line)
                gps_coordinates = get_gps_coordinate(details_line)
                yield FrameSrt(sub_id, time_range, time_diff, iso_time, gps_coordinates, iso, shutter)

    def get_avg_from_buff(self, buffer):
        distance = [self.calculate_distance(buffer[k].gps, buffer[k + 1].gps) for k in range(len(buffer) - 1)]
        time_difference = [b.time_diff for b in buffer[1::]]
        speed = int(mean([m / n for m, n in zip(distance, time_difference)] if len(distance) != 0 else [0]) * 3.6)
        home_distance = int(self.calculate_distance(buffer[-1].gps, self.home))
        altitude = int(mean([self.fix_altitude(b.gps[2]) for b in buffer]))
        latitude = deg_to_dms(mean([b.gps[0] for b in buffer]), coordinate="latitude")
        longitude = deg_to_dms(mean([b.gps[1] for b in buffer]), coordinate="longitude")

        self.current_osd = FrameOsd(altitude, speed, home_distance, latitude, longitude, buffer[-1].iso_time)

    def frame_details_new(self):
        buffer = []
        srt_frames = chain(*(self.read_frame_srt(file) for file in self.file_name))
        for idx, fr in enumerate(srt_frames):
            buffer.append(fr)
            if len(buffer) > 30:
                buffer.pop(0)

            if idx % 30 == 0:
                self.get_avg_from_buff(buffer)

            yield self.current_osd

        while True:  # srt data not always match frames count
            yield self.current_osd
