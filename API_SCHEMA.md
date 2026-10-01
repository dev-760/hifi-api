# Download API Schema

Reference for the download endpoints added to `hifi-api`. For the rest of the
API see the [main README](README.md); for client wiring see
[EXPO_INTEGRATION.md](EXPO_INTEGRATION.md).

Machine-readable schema is always available at `GET /openapi.json` on a running
server, with browsable docs at `/docs`.

> ⚠️ **Live deployment status.** `https://hifi-api00.vercel.app` runs an older
> build: its `/download/resolve/` returns `500` because the DASH parser could not
> read Tidal's malformed manifests. That is fixed locally but **not yet
> redeployed**. Verify against a local or Docker instance until a new Vercel
> deployment ships. See [Known upstream quirks](#known-upstream-quirks).

## Contents

- [Base URL](#base-url)
- [Quality vocabulary](#quality-vocabulary)
- [The two download modes](#the-two-download-modes)
- [`GET /download/resolve/`](#get-downloadresolve)
- [`POST /download/track/`](#post-downloadtrack)
- [`GET /download/requests/{request_id}`](#get-downloadrequestsrequest_id)
- [Job lifecycle and polling](#job-lifecycle-and-polling)
- [Errors](#errors)
- [Known upstream quirks](#known-upstream-quirks)
- [Notes](#notes)

## Base URL

| Deployment | Base URL | Downloads to disk |
| --- | --- | --- |
| Live (Vercel) | `https://hifi-api00.vercel.app` | **no** (`501`) |
| Local | `http://localhost:8000` | yes |
| Docker | `http://localhost:8000` | yes |

`GET /download/resolve/` works on every deployment, including Vercel.

## Quality vocabulary

| Value | Meaning | Container |
| --- | --- | --- |
| `LOW` | 96 kbps AAC | `.m4a` |
| `HIGH` | 320 kbps AAC | `.m4a` |
| `LOSSLESS` | 16-bit / 44.1 kHz FLAC | `.flac` |
| `HI_RES_LOSSLESS` | up to 24-bit / 192 kHz | `.m4a` (FLAC-in-MP4) |

Aliases are accepted and normalised to the names above:

| Alias | Resolves to |
| --- | --- |
| `low` | `LOW` |
| `normal` | `HIGH` |
| `lossless` | `LOSSLESS` |
| `max`, `hires`, `hires_lossless` | `HI_RES_LOSSLESS` |

Separators and case are ignored, so `HI-RES-LOSSLESS`, `hires_lossless` and
`max` all work.

> ⚠️ `high` maps to Tidal's `HIGH` (320 kbps AAC), **not** lossless. This
> differs from tiddl, where `high` means 16-bit FLAC. Use `lossless` for the
> lossless tier.

## The two download modes

**Resolve only.** Returns short-lived CDN URLs; the client fetches them. No
filesystem access, no credentials burned on a long transfer, works on Vercel.
This is the recommended default.

**To disk.** The server writes the audio and returns a path. Requires
`ENABLE_DOWNLOADS=True` and a persistent filesystem. It is the only mode that
is refused on Vercel.

Both modes require a **playback credential**. Only the manifest lookup is
authenticated; segment transfers hit the CDN unauthenticated.

## `GET /download/resolve/`

Resolve a track's segment URLs without transferring audio.

### Query parameters

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | int | *required* | Tidal track ID |
| `quality` | string | `HI_RES_LOSSLESS` | See above |
| `immersiveaudio` | bool | `false` | Request Dolby Atmos |

### Responses

**200 OK** — resolved successfully. May instead be `202` if all playback
accounts are busy; see [Job lifecycle](#job-lifecycle-and-polling).

```json
{
  "version": "2.10",
  "trackId": 194567102,
  "requestedQuality": "LOSSLESS",
  "urlCount": 2,
  "codecs": "flac",
  "mimeType": "application/vnd.tidal.bts",
  "encryptionType": "NONE",
  "audioMode": "STEREO",
  "audioQuality": "LOSSLESS",
  "bitDepth": 16,
  "sampleRate": 44100,
  "fileExtension": ".flac",
  "needsFlacExtraction": false,
  "urls": [
    "https://resources.tidal.com/.../0.mp4",
    "https://resources.tidal.com/.../1.mp4"
  ]
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `urls` | string[] | Fetch these **in order** and concatenate |
| `urlCount` | int | `urls.length` |
| `codecs` | string | `flac`, `mp4a.40.2`, `eac3`, … |
| `mimeType` | string | `application/vnd.tidal.bts` or `application/dash+xml` |
| `encryptionType` | string | Always `NONE`; anything else is rejected |
| `fileExtension` | string | Extension the assembled file should have |
| `needsFlacExtraction` | bool | `true` when FLAC is wrapped in MP4 |
| `bitDepth`, `sampleRate` | int \| null | Absent for lossy tiers |
| `audioMode` | string | `STEREO` or `DOLBY_ATMOS` |

**Segment URLs expire and are effectively single-use.** Fetch them promptly and
do not cache them across sessions.

### Example

```bash
curl "http://localhost:8000/download/resolve/?id=194567102&quality=max"
```

## `POST /download/track/`

Download one track to the server's download directory.

### Query parameters

| Name | Type | Default | Notes |
| --- | --- | --- | --- |
| `id` | int | *required* | Tidal track ID |
| `quality` | string | `HI_RES_LOSSLESS` | See above |

### Responses

**200 OK** — downloaded, or already present.

```json
{
  "version": "2.10",
  "trackId": 194567102,
  "status": "downloaded",
  "path": "/data/downloads/Daft Punk/Discovery/01. One More Time.flac",
  "bytes": 34567890,
  "requestedQuality": "LOSSLESS",
  "audioQuality": "LOSSLESS",
  "audioMode": "STEREO",
  "codecs": "flac",
  "bitDepth": 16,
  "sampleRate": 44100
}
```

`status` is one of:

| Value | Meaning |
| --- | --- |
| `downloaded` | Newly written |
| `exists` | Skipped; `DOWNLOAD_SKIP_EXISTING=True` and the file was present |

**202 Accepted** — all playback accounts busy. Body and headers as described in
[job lifecycle](#job-lifecycle-and-polling). Poll the status URL.

**501 Not Implemented** — running on Vercel or another serverless platform.

**503 Service Unavailable** — `ENABLE_DOWNLOADS` is not enabled.

**413** — the track exceeded `DOWNLOAD_MAX_BYTES`; the partial file is deleted.

### Example

```bash
curl -X POST "http://localhost:8000/download/track/?id=194567102&quality=max"
```

### Notes on the written file

- **Paths are sanitised.** A title of `../../etc/passwd` cannot escape
  `DOWNLOAD_DIR`. Every template component is cleaned and the resolved path is
  re-checked against the root.
- **Writes are atomic.** Data is staged in a `.part` sibling and moved into
  place with `os.replace`, so an interrupted download never leaves a truncated
  file that looks complete.
- **`HI_RES_LOSSLESS` needs ffmpeg** to remux FLAC-in-MP4 into a true `.flac`.
  Without it the download still succeeds and returns the `.m4a`. The Docker
  image bundles ffmpeg.

## `GET /download/requests/{request_id}`

Poll a queued request. Shares the playback job store, so this is equivalent to
`GET /playback/requests/{id}`.

### Path parameters

| Name | Type | Notes |
|---|---|---|
| `request_id` | string | `requestId` from the `202` body |

### Responses

**200 OK** — the request completed; body is the endpoint's normal result.

**202 Accepted** — still pending or processing:

```json
{
  "status": "pending",
  "requestId": "a1b2c3d4e5f6...",
  "queuePosition": 1,
  "statusUrl": "/download/requests/a1b2c3d4e5f6...",
  "cancelUrl": "/download/requests/a1b2c3d4e5f6...",
  "playbackAccounts": 1,
  "activePlaybackRequests": 1
}
```

Response headers on the original `202` are useful too:

| Header | Notes |
| --- | --- |
| `Location` | Status URL to poll |
| `Retry-After` | Suggested seconds to wait (`1`) |
| `X-Playback-Queue-Position` | Queue position |
| `X-Playback-Request-Id` | The job ID |

**404** — unknown or expired. Jobs are pruned 300 s after completion.

**410** — the job was cancelled.

**4xx/5xx** — the job failed; body carries `detail`.

Cancel with `DELETE /download/requests/{request_id}`.

## Job lifecycle and polling

Any endpoint that needs a playback credential can return `202` when every
account is leased. The contract is identical across playback and download:

```
GET  /track/            ┐
POST /download/track/   ├─► 202 + Location header
GET /download/resolve/  ┘        │
                                     ▼
                        poll statusUrl every Retry-After seconds
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
           200 OK               202 (pending)          4xx/5xx (failed)
```

Implementation sketch:

```javascript
async function resolveWithPolling(params) {
  let res = await api.get('/download/resolve/', { params });

  while (res.status === 202) {
    const wait = Number(res.headers['retry-after'] || 1);
    await new Promise((r) => setTimeout(r, wait * 1000));
    res = await api.get(res.headers.location);
  }

  if (res.status !== 200) throw new Error(res.data?.detail || 'Request failed');
  return res.data;
}
```

## Errors

| Status | Meaning |
| --- | --- |
| `400` | Missing required parameter (e.g. neither `id` nor `q`) |
| `401` | Credential rejected by Tidal; re-run `tidal_auth` |
| `404` | Unknown track, or unknown/expired job |
| `410` | Job was cancelled |
| `413` | Exceeded `DOWNLOAD_MAX_BYTES` |
| `422` | Invalid `quality`; body lists the accepted values |
| `429` | Upstream rate limited (auto-retried internally) |
| `501` | Disk downloads unsupported on this deployment |
| `503` | `ENABLE_DOWNLOADS=False`, or no working proxy |

Error bodies are FastAPI's standard shape:

```json
{ "detail": "Unsupported quality 'ultra'; expected one of [...]" }
```

## Known upstream quirks

Tidal's v1 DASH manifests are **not valid XML**. A live `LOSSLESS` manifest has
four independent defects:

1. `segmentAlignment="true"` is repeated on the same start tag.
2. `<Representation>` sits directly under `<MPD>`, with no `<Period>` or
   `<AdaptationSet>` wrapper.
3. The `initialization` attribute is **never terminated** — its value, a base64
   `Policy`/`Signature` blob, runs directly into `</AdaptationSet>`.
4. The document closes with `</MAP>` instead of `</MPD>`.

Any conforming XML parser rejects this. `download/manifest.py` therefore
extracts the few attributes it needs with targeted patterns instead of parsing
the document, and `tests/test_manifest.py` pins the behaviour against a real
captured manifest.

Two payload layouts occur upstream:

| Layout | Attributes | Segments |
| --- | --- | --- |
| Single file | `initialization` only, no `SegmentTimeline` | 1 |
| Segmented | `media` template + `SegmentTimeline` with `$Number$` | timeline count |

`encryptionType` is validated, not acted upon: the v1 path is unencrypted, and
anything else fails loudly rather than writing unplayable bytes.

DASH segment numbering starts at **1** unless `startNumber` says otherwise.

## Notes

- **Downloads are off by default** (`ENABLE_DOWNLOADS=False`). Fetching full
  audio is far more detectable by Tidal than streaming and is a common cause of
  account suspension. Enable deliberately.
- **Do not expose this API without authentication.** Both `/widevine` and the
  download endpoints act on your Tidal account; an open download endpoint is an
  unlimited give-me-everything oracle. There is currently no auth middleware.
- Segment URLs are time-limited. Do not persist them for later playback.
