from dataclasses import dataclass, field
import math
import collections
from datetime import datetime
from statistics import mean
from math import radians, sin, cos, sqrt, atan2
import re
from collections import namedtuple
from itertools import chain
from scipy.signal import savgol_filter
import numpy as np

FrameSrt = namedtuple("FrameSrt", "id time_range time_diff iso_time gps iso shutter")
R = 6371000
GPS_RE = re.compile(r".*latitude: (.*?)].*longitude: (.*?)].*altitude: (.*?)].*")
DIFF_TIME_RE = re.compile(r".*DiffTime: (\d{1,2}?)ms")
ISO_RE = re.compile(r"\[iso : (.*?)\]")
SHUTTER_RE = re.compile(r"\[shutter : (.*?)\]")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def range_between(start, stop):
    if stop - start > 180:
        step = (start + 360 - stop)/5.
        for x in range(4):
            start -= step
            if start < 0:
                start += 360
            yield start
    else:
        step = (stop-start)/5.
        for x in range(4):
            start += step
            yield start
    yield stop


@dataclass
class FrameOsd:
    height: int = 0
    rt_height: float = .0
    speed: int = 0
    home_distance: int = 0
    lat: float = 0.0
    long: float = 0.0
    iso_time: datetime = 0.0
    direction_vector: list = field(default_factory=lambda: [180.]*30)

    @property
    def direction(self):
        return self.direction_vector.pop(0)


def get_gps_coordinate(gps_str):
    return tuple(float(x) for x in GPS_RE.findall(gps_str)[0])


def get_iso(details_line):
    return ISO_RE.findall(details_line)[0]


def get_shutter(details_line):
    return SHUTTER_RE.findall(details_line)[0]


def get_home(filename):
    data = SrtReader.read_frame_srt(filename)
    return next(data).gps


def calculate_initial_compass_bearing(point_a, point_b):
    """
    Calculates the bearing between two points.
    The formulae used is the following:
        θ = atan2(sin(Δlong).cos(lat2),
                  cos(lat1).sin(lat2) − sin(lat1).cos(lat2).cos(Δlong))
    :Parameters:
      - `pointA: The tuple representing the latitude/longitude for the
        first point. Latitude and longitude must be in decimal degrees
      - `pointB: The tuple representing the latitude/longitude for the
        second point. Latitude and longitude must be in decimal degrees
    :Returns:
      The bearing in degrees
    :Returns Type:
      float
    """
    if not isinstance(point_a, tuple) or not isinstance(point_b, tuple):
        raise TypeError("Only tuples are supported as arguments")

    lat1 = math.radians(point_a[0])
    lat2 = math.radians(point_b[0])

    diff_long = math.radians(point_b[1] - point_a[1])

    x = math.sin(diff_long) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diff_long))

    initial_bearing = math.atan2(x, y)

    # Now we have the initial bearing but math.atan2 return values
    # from -180° to + 180° which is not what we want for a compass bearing
    # The solution is to normalize the initial bearing as shown below
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing


class SrtReader:
    def __init__(self, filename, fix_alt=True, shift=None, offset=0):
        self.direction = 180
        self.file_name = filename
        self.home = get_home(filename[0])
        self.fix_alt = fix_alt
        self.shift = shift
        self.current_osd = FrameOsd()
        self.offset = offset

    @staticmethod
    def calculate_distance(coord1, coord2):
        # Convert latitude and longitude to radians
        lat1, lon1, alt1 = map(radians, coord1)
        lat2, lon2, alt2 = map(radians, coord2)

        # Haversine formula
        d_lat = lat2 - lat1
        d_lon = lon2 - lon1
        a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
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
        return (alt - self.shift) * 10. + (self.offset if self.offset else 0.)

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

    def get_avg_from_buff(self, buffer, idx):
        # updates always
        self.current_osd.lat = buffer[-1].gps[0]
        self.current_osd.long = buffer[-1].gps[1]
        self.current_osd.iso_time = buffer[-1].iso_time
        self.current_osd.rt_height = mean([self.fix_altitude(b.gps[2]) for b in buffer])

        if idx % 30 == 0 and idx >= 30:
            distance = [self.calculate_distance(buffer[k].gps, buffer[k + 1].gps) for k in range(len(buffer) - 1)]
            time_difference = [b.time_diff for b in list(buffer)[1::]]
            self.current_osd.speed = int(mean([m / n for m, n in zip(distance, time_difference)]
                                              if len(distance) != 0 else [0]))  # m/s
            self.current_osd.home_distance = int(self.calculate_distance(buffer[-1].gps, self.home))
            self.current_osd.height = int(self.current_osd.rt_height)

        if idx % 5 == 0 and idx >= 30:
            directions = []

            if self.current_osd.speed >= 16:
                direction_slices = ((15, 18), (19, 22), (23, 26), (27, 29))
            elif self.current_osd.speed >= 8:
                direction_slices = ((15, 19), (20, 24), (25, 29))
            else:
                direction_slices = ((15, 22), (23, 29))

            for point_a, point_b in ((buffer[i], buffer[j]) for i, j in direction_slices):
                direction = calculate_initial_compass_bearing((point_b.gps[0], point_b.gps[1]),
                                                              (point_a.gps[0], point_a.gps[1]))
                if direction != 0.0:  # ignore zeroes
                    directions.append(direction)

            if len(directions) == 0:
                directions = [180.]

            new_direction = mean(directions)
            if new_direction > self.direction:
                self.current_osd.direction_vector = list(range_between(self.direction, new_direction))
            else:
                self.current_osd.direction_vector = list(range_between(new_direction, self.direction))

            self.direction = new_direction

    def frame_details_new(self, infinite_yield=True):
        buffer = collections.deque(maxlen=30)

        srt_frames = chain(*(self.read_frame_srt(file) for file in self.file_name))
        for idx, fr in enumerate(srt_frames):
            buffer.append(fr)
            self.get_avg_from_buff(buffer, idx)
            yield self.current_osd

        while infinite_yield:  # srt data not always match frames count
            yield self.current_osd

    def get_smooth_direction_array(self):
        directions = []
        for srt_frame in self.frame_details_new():
            try:
                directions.append(srt_frame.direction)
            except IndexError:
                break
        return savgol_filter(np.array(directions), 31, 3)


def main():
    import os
    import glob

    # Use glob to find all .srt files
    srt_files = glob.glob(os.path.join("data", '*.SRT'))

    # Sort the files by name
    srt_files.sort()
    osd_data = SrtReader(srt_files).frame_details_new(infinite_yield=False)
    print(list(osd_data)[-1])


if __name__ == "__main__":
    main()
