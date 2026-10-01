"""Download support for hifi-api.

The package is split so that each piece is independently testable:

``manifest``
    Pure parsing of Tidal playback manifests. No network, no filesystem.
``store``
    Path templating, sanitisation and atomic writes.
``ffmpeg``
    Optional remuxing helpers that degrade gracefully when ffmpeg is absent.
``service``
    Bridges the existing credential pool and HTTP client to manifest parsing.
"""

from .manifest import ManifestError, ParsedManifest, parse_manifest

__all__ = ["ManifestError", "ParsedManifest", "parse_manifest"]
