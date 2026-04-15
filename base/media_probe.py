import json
import platform
import shutil
import subprocess
from datetime import timedelta
from fractions import Fraction
from pathlib import Path

from django.conf import settings
from django.utils import timezone


IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _candidate_ffprobe_paths():
    base_dir = Path(settings.BASE_DIR) / "electron_app" / "node_modules" / "ffprobe-static" / "bin"

    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        platform_dir = "win32"
        binary_name = "ffprobe.exe"
    elif system == "darwin":
        platform_dir = "darwin"
        binary_name = "ffprobe"
    else:
        platform_dir = "linux"
        binary_name = "ffprobe"

    if machine in {"amd64", "x86_64"}:
        arch_dir = "x64"
    elif machine in {"arm64", "aarch64"}:
        arch_dir = "arm64"
    elif machine in {"i386", "i686", "x86"}:
        arch_dir = "ia32"
    else:
        arch_dir = machine

    return [
        base_dir / platform_dir / arch_dir / binary_name,
        base_dir / binary_name,
    ]


def resolve_ffprobe_path(explicit_path=None):
    candidates = []

    if explicit_path:
        candidates.append(Path(explicit_path))

    candidates.extend(_candidate_ffprobe_paths())

    which_ffprobe = shutil.which("ffprobe")
    if which_ffprobe:
        candidates.append(Path(which_ffprobe))

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)

    raise FileNotFoundError("Unable to locate an ffprobe binary.")


def _parse_fraction(value):
    if not value or value in {"0/0", "N/A"}:
        return None

    try:
        if "/" in str(value):
            return round(float(Fraction(value)), 3)
        return round(float(value), 3)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _parse_int(value):
    try:
        if value in (None, "", "N/A"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_duration(value):
    try:
        if value in (None, "", "N/A"):
            return None
        seconds = float(value)
        if seconds < 0:
            return None
        return timedelta(seconds=seconds)
    except (TypeError, ValueError):
        return None


def _detect_file_type(file_path, streams):
    suffix = Path(file_path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"

    stream_types = [stream.get("codec_type") for stream in streams]
    if "video" in stream_types:
        return "video"
    if "audio" in stream_types:
        return "audio"
    return suffix.lstrip(".") or "unknown"


def _detect_hdr(stream):
    color_transfer = (stream.get("color_transfer") or "").lower()
    color_primaries = (stream.get("color_primaries") or "").lower()

    if color_transfer in {"smpte2084", "arib-std-b67"}:
        return True
    if "bt2020" in color_primaries:
        return True
    if color_transfer or color_primaries:
        return False
    return None


def probe_media_file(file_path, ffprobe_path=None):
    ffprobe_binary = resolve_ffprobe_path(ffprobe_path)

    cmd = [
        ffprobe_binary,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    format_info = payload.get("format") or {}

    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]

    primary_stream = video_streams[0] if video_streams else audio_streams[0] if audio_streams else (streams[0] if streams else {})

    return {
        "file_type": _detect_file_type(file_path, streams),
        "file_size": _parse_int(format_info.get("size")),
        "imported_at": timezone.now(),
        "hdr": _detect_hdr(primary_stream),
        "frame_rate": _parse_fraction(primary_stream.get("avg_frame_rate") or primary_stream.get("r_frame_rate")),
        "codec": primary_stream.get("codec_name") or format_info.get("format_name") or "",
        "duration": _parse_duration(primary_stream.get("duration") or format_info.get("duration")),
        "width": _parse_int(primary_stream.get("width")),
        "height": _parse_int(primary_stream.get("height")),
        "aspect_ratio": primary_stream.get("display_aspect_ratio") if primary_stream.get("display_aspect_ratio") not in {None, "", "N/A"} else "",
        "color_space": primary_stream.get("color_space") or "",
        "bit_rate": _parse_int(primary_stream.get("bit_rate") or format_info.get("bit_rate")),
    }
