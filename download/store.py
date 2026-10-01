"""Filesystem layout and safe path handling for downloaded audio.

Files are written to a base directory using a template that mirrors tiddl's
common ``{artist}/{album}/{number}. {title}`` layout. Every path component is
derived from upstream metadata, so each one is sanitised before it is joined -
a title of ``../../etc`` must never escape the download root.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

# Characters that are illegal on Windows, awkward on POSIX, or that break
# shell tooling downstream. Replaced with a space and collapsed.
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Reserved device names on Windows; a file called "CON.flac" cannot be created.
_WINDOWS_RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)

MAX_COMPONENT_LENGTH = 120
DEFAULT_TEMPLATE = "{artist}/{album}/{number:02d}. {title}"

# When a whole path would exceed this, drop the album component and retry, then
# the artist component. Keeps deeply nested templates from tripping over the
# Windows MAX_PATH limit.
MAX_PATH_LENGTH = 240


def sanitize_component(value: Optional[str], fallback: str = "Unknown") -> str:
    """Reduce arbitrary metadata to a single safe path component."""
    if value is None:
        return fallback

    # Normalise so visually identical names collide predictably.
    text = unicodedata.normalize("NFC", str(value))
    text = _ILLEGAL_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Collapse dot runs so that neither ".." nor hidden ".foo" survives. A path
    # component consisting only of dots would otherwise traverse or vanish.
    # Bare dots left behind by stripped separators ("AC/DC" -> "AC DC" is fine,
    # but "../../x" -> "  .. x") are dropped to keep filenames readable.
    text = re.sub(r"(?<!\S)\.{2,}", " ", text)
    text = re.sub(r"\.{2,}", ".", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    if text in ("", "."):
        return fallback

    if text.lower() in _WINDOWS_RESERVED:
        text = f"{text}_"

    if len(text) > MAX_COMPONENT_LENGTH:
        text = text[:MAX_COMPONENT_LENGTH].rstrip().strip(".")
        # Truncation can re-expose a trailing dot run.
        text = re.sub(r"\.{2,}", ".", text).strip()

    return text or fallback


def render_template(template: str, fields: dict) -> str:
    """Render a path template, sanitising every produced component.

    The template is split on ``/`` and each segment is formatted independently so
    that no single metadata value can introduce extra directory levels.
    """
    parts: Iterable[str] = template.split(
        "/") if template else [DEFAULT_TEMPLATE]

    rendered: list[str] = []
    for part in parts:
        if not part.strip():
            continue
        try:
            value = str(part).format(**fields)
        except (KeyError, IndexError, ValueError) as exc:
            raise KeyError(
                f"Template segment {part!r} is invalid for fields "
                f"{sorted(fields)}: {exc}"
            ) from exc
        rendered.append(sanitize_component(value))

    if not rendered:
        rendered = [sanitize_component(DEFAULT_TEMPLATE.format(**fields))]
    return "/".join(rendered)


def build_track_path(
    base_dir: Path,
    *,
    template: str = DEFAULT_TEMPLATE,
    extension: str,
    **fields,
) -> Path:
    """Return the absolute path a track should be written to.

    ``fields`` supplies the template variables (``title``, ``artist``, ``album``,
    ``number``, and any others a custom template may reference). Every rendered
    component is sanitised, so no field can introduce traversal.
    """
    relative = render_template(template, fields)

    # Build the filename by string concatenation rather than Path.with_suffix().
    # A rendered name like "01. One More Time" has ". One More Time" as its
    # "suffix" as far as pathlib is concerned, so with_suffix() would silently
    # discard the title and produce "01.flac". Plain concatenation appends the
    # extension without interpreting dots in the metadata.
    filename = relative + extension
    candidate = base_dir / filename

    # Shed directory levels until the path fits the platform limit.
    segments = candidate.parts
    while (
        len(str(candidate)) > MAX_PATH_LENGTH
        and len(segments) > len(base_dir.parts) + 1
    ):
        candidate = Path(*segments[1:])
        segments = candidate.parts

    return candidate


async def atomic_write_stream(path: Path, chunks) -> int:
    """Write an async stream of chunks to `path` atomically.

    The data is staged in a sibling ``.part`` file and moved into place with
    ``os.replace`` only once the stream completes, so a cancelled or failed
    download never leaves a truncated file that looks finished.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_name(f".{path.name}.part")
    written = 0
    try:
        with open(tmp, "wb") as handle:
            async for chunk in chunks:
                handle.write(chunk)
                written += len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    return written


def ensure_inside(base_dir: Path, candidate: Path) -> Path:
    """Assert that `candidate` resolves inside `base_dir`.

    Guards against a sanitisation bug allowing writes outside the root.
    """
    base = base_dir.resolve()
    target = candidate.resolve()

    if base != target and base not in target.parents:
        raise ValueError(f"Refusing path outside download root: {candidate}")

    return target
