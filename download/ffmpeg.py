"""Thin, safe wrappers around ffmpeg/ffprobe.

ffmpeg is optional. When it is missing the helpers degrade gracefully rather
than failing the download: callers keep the MP4 container Tidal actually served
and the response reports that FLAC extraction was skipped.

Every command is built as a fixed argv list and executed without a shell, so
media filenames (which may contain quotes, semicolons or unicode) can never be
interpreted as anything but a path.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Generous ceiling; stream copy on a single track is fast, but a cold or
# overloaded host can be slow. Prevents a hung subprocess from pinning a slot.
FFMPEG_TIMEOUT_SECONDS = 300


class FFmpegError(RuntimeError):
    """Raised when an ffmpeg/ffprobe invocation fails."""


def is_ffmpeg_installed() -> bool:
    """True when both ffmpeg and ffprobe are available on PATH."""
    return bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegError(f"{cmd[0]} is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(
            f"{cmd[0]} timed out after {FFMPEG_TIMEOUT_SECONDS}s") from exc

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise FFmpegError(
            f"{cmd[0]} failed (rc={result.returncode}): {stderr[:500]}")

    return result


def probe_audio_codec(source: Path) -> str:
    """Return the first audio stream's codec name, or "" if undeterminable."""
    if not is_ffmpeg_installed():
        return ""
    try:
        result = _run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source),
            ]
        )
        return result.stdout.strip()
    except FFmpegError as exc:
        logger.debug("ffprobe failed for %s: %s", source, exc)
        return ""


def extract_flac(source: Path) -> Path:
    """Extract a FLAC stream from an MP4 container.

    Tidal serves AAC-in-MP4 for tracks with no lossless master, so the input is
    probed first: if it is not actually FLAC the file is simply renamed to
    ``.m4a`` and returned untouched.
    """
    codec = probe_audio_codec(source)

    if codec and codec != "flac":
        target = source.with_suffix(".m4a")
        if target != source:
            source.replace(target)
        return target

    target = source.with_suffix(".flac")
    tmp = source.with_suffix(".tmp.flac")

    _run(["ffmpeg", "-y", "-i", str(source), "-c", "copy", str(tmp)])

    tmp.replace(target)
    if source != target and source.exists():
        source.unlink()

    return target


def convert_to_mp4(source: Path) -> Path:
    """Remux a downloaded video segment chain into a playable MP4."""
    target = source.with_suffix(".mp4")
    tmp = source.with_suffix(".tmp.mp4")

    _run(["ffmpeg", "-y", "-i", str(source), "-c", "copy", str(tmp)])

    tmp.replace(target)
    if source != target and source.exists():
        source.unlink()

    return target
