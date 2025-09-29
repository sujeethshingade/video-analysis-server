import os
import math
import tempfile
import shutil
import logging
from typing import List, Tuple

import ffmpeg

logger = logging.getLogger("video-analysis.video")


def get_video_duration_seconds(input_path: str) -> float:
    probe = ffmpeg.probe(input_path)
    dur = float(probe["format"]["duration"])  # seconds
    return dur


def hms(seconds: float) -> str:
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


def extract_keyframes_every_n_seconds(input_path: str, n: int = 30) -> List[Tuple[str, int]]:
    duration = get_video_duration_seconds(input_path)
    video_id = os.path.splitext(os.path.basename(input_path))[0]
    out_dir = os.path.join(tempfile.gettempdir(), video_id)
    os.makedirs(out_dir, exist_ok=True)

    timestamps = list(range(0, int(math.ceil(duration)), n))
    outputs: List[Tuple[str, int]] = []

    for ts in timestamps:
        out_file = os.path.join(out_dir, f"frame_{ts}.jpg")
        (
            ffmpeg
            .input(input_path, ss=ts)
            .output(out_file, vframes=1, format='image2', vcodec='mjpeg', loglevel='error')
            .overwrite_output()
            .run()
        )
        if os.path.exists(out_file):
            outputs.append((out_file, ts))

    return outputs


def temp_output_dir_for(input_path: str) -> str:
    video_id = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(tempfile.gettempdir(), video_id)


def cleanup_temp_artifacts(input_path: str) -> None:
    try:
        out_dir = temp_output_dir_for(input_path)
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir, ignore_errors=False)
            logger.info(f"Deleted temp frames directory: {out_dir}")
    except Exception as ex:
        logger.warning(f"Failed to delete frames directory for {input_path}: {ex}")

    try:
        if os.path.exists(input_path):
            os.remove(input_path)
            logger.info(f"Deleted temp video file: {input_path}")
    except Exception as ex:
        logger.warning(f"Failed to delete temp video file {input_path}: {ex}")
