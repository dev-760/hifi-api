# hifi-api

A Python FastAPI proxy for Tidal music streaming service, providing access to high-fidelity audio streaming with multi-account management and request queuing.

## ⚠️ Important Warnings

- **Account Blocking Risk**: Tidal actively blocks accounts using this API. Use at your own risk. The download feature in particular is readily detected.
- **Educational Use Only**: Intended for personal homelab use with valid Tidal accounts.
- **No Public Hosting**: Do not host on the open internet to minimize detection risk.
- **IP Exposure**: Your IP may be exposed to Tidal when using this service.

## Features

- 🎵 **High-Fidelity Audio**: Support for LOSSLESS, HI_RES_LOSSLESS, and Dolby Atmos
- 🔐 **Multi-Account Support**: Separate playback and catalog credentials
- 📊 **Request Queuing**: Built-in queue system for concurrent playback requests
- 🔄 **Automatic Token Refresh**: Handles Tidal OAuth token refresh automatically
- 🌐 **Proxy Support**: Optional proxy rotation for IP protection
- 🚀 **Multiple Deployments**: Support for local, Docker, and Vercel deployment

## Quick Start

### Prerequisites

- Python 3.9+
- Valid Tidal account
- (Optional) Vercel account for cloud deployment

### Installation

1. **Clone the repository** (if not already done):

```bash
cd hifi-api
```

1. **Install dependencies**:

```bash
pip install -r requirements.txt
```

1. **Set up Tidal authentication**:

```bash
cd tidal_auth
pip install -r requirements.txt
python tidal_auth.py
```

**Authentication Process:**

- The script will display a URL (e.g., `link.tidal.com/XXXXX`)
- Open the URL in your browser
- Log in to your Tidal account
- Click "Authorize" when prompted
- The script will automatically save your credentials to `token.json`

1. **Configure environment variables** (optional):

```bash
cp .env.example .env
# Edit .env with your preferences
```

1. **Run the server**:

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## Testing Your Setup

After starting the server, test it with these commands:

```bash
# Test basic endpoint
curl http://localhost:8000/

# Test track information
curl "http://localhost:8000/info/?id=194567102"

# Test search
curl "http://localhost:8000/search/?s=daft+punk"
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Tidal Configuration
COUNTRY_CODE=US

# Proxy Configuration (Optional)
USE_PROXIES=False
ROTATE_PROXIES_ON_REFRESH=False
PROXIES_FILE=proxies.txt
MAX_RETRIES=2
FALLBACK_TO_DIRECT_CONNECTION=False

# Development
DEV_MODE=True  # Enable verbose logging
```

### Multi-Account Setup

You can configure multiple Tidal accounts in `token.json`:

```json
[
  {
    "client_ID": "...",
    "client_secret": "...",
    "refresh_token": "playback-account-1-refresh-token",
    "userID": "..."
  },
  {
    "client_ID": "...",
    "client_secret": "...",
    "refresh_token": "playback-account-2-refresh-token",
    "userID": "..."
  },
  {
    "role": "catalog",
    "client_ID": "...",
    "client_secret": "...",
    "refresh_token": "catalog-account-refresh-token",
    "userID": "..."
  }
]
```

- **Playback accounts**: Used for streaming audio (limited concurrent requests)
- **Catalog accounts**: Used for metadata/search (unrestricted, no subscription needed)

## API Endpoints

### Metadata Endpoints

- `GET /` - API version and repository info
- `GET /info/?id={track_id}` - Track information
- `GET /search/?s={query}` - Search tracks
- `GET /search/?a={query}` - Search artists
- `GET /search/?al={query}` - Search albums
- `GET /search/?v={query}` - Search videos
- `GET /search/?p={query}` - Search playlists
- `GET /album/?id={album_id}` - Album details with tracks
- `GET /artist/?id={artist_id}` - Artist information
- `GET /artist/?f={artist_id}` - Artist discography with tracks
- `GET /playlist/?id={playlist_id}` - Playlist information
- `GET /mix/?id={mix_id}` - Mix details
- `GET /recommendations/?id={track_id}` - Track recommendations
- `GET /lyrics/?id={track_id}` - Track lyrics
- `GET /cover/?id={track_id}` - Album cover art URLs
- `GET /cover/?q={query}` - Search cover art

### Playback Endpoints

- `GET /track/?id={track_id}&quality={quality}` - Track streaming URLs
  - Quality options: `HI_RES_LOSSLESS`, `LOSSLESS`, `HIGH`, `LOW`
- `GET /trackManifests/?id={track_id}` - Advanced manifest streaming (Dolby Atmos support)
- `GET/POST /widevine` - DRM license proxy
- `GET /video/?id={video_id}` - Video streaming

### Management Endpoints

- `GET /playback/requests/{request_id}` - Poll queued playback requests
- `DELETE /playback/requests/{request_id}` - Cancel queued requests

### Download Endpoints

Downloads resolve a track's CDN segment URLs and (optionally) write the audio to
disk. The manifest handling follows the approach used by
[tiddl](https://github.com/oskvr37/tiddl) (Apache-2.0).

- `GET /download/resolve/?id={track_id}&quality={quality}` - Return segment URLs
  without downloading. Stateless, works on Vercel.
- `POST /download/track/?id={track_id}&quality={quality}` - Download one track to
  disk. Returns a 202 job reference when all playback accounts are busy.
- `GET /download/requests/{request_id}` - Poll a download job

Quality accepts Tidal's native names (`LOW`, `HIGH`, `LOSSLESS`,
`HI_RES_LOSSLESS`) plus the aliases `low`, `normal`, `lossless`, `max`.

> ⚠️ **Downloading is high risk.** Fetching full audio is far more detectable by
> Tidal than ordinary streaming and is a common cause of account suspension.
> Downloads are therefore **disabled by default** — set `ENABLE_DOWNLOADS=True`
> to opt in, and consider proxy rotation.

#### Two ways to download

**Resolve only (recommended default).** Returns short-lived CDN URLs; the client
fetches them. Costs you no bandwidth and works on serverless:

```bash
curl "http://localhost:8000/download/resolve/?id=194567102&quality=max"
```

**To disk.** Requires `ENABLE_DOWNLOADS=True` and a persistent filesystem.
Refused with `501` on Vercel:

```bash
curl -X POST "http://localhost:8000/download/track/?id=194567102&quality=max"
```

#### How it works

The v1 `playbackinfopaywall` manifest is **not** encrypted, unlike the v2
manifests served by `/trackManifests/`. There are two shapes:

| `manifestMimeType` | Format | Qualities |
| --- | --- | --- |
| `application/vnd.tidal.bts` | JSON with a `urls` array | LOW, HIGH, LOSSLESS |
| `application/dash+xml` | MPEG-DASH MPD, `SegmentTemplate` | HI_RES_LOSSLESS, Atmos |

Segments are fetched from `resources.tidal.com` without a credential, so the
playback account is only held for the brief manifest call. Encrypted manifests
are rejected rather than written to disk.

`HI_RES_LOSSLESS` is served as FLAC-in-MP4 and needs `ffmpeg` to remux into a
true `.flac`. Without ffmpeg the download still succeeds and returns the `.m4a`.
Install it with `winget install Gyan.FFmpeg`, or use the Docker image (which
includes it).

#### Download configuration

```bash
ENABLE_DOWNLOADS=True
DOWNLOAD_DIR=downloads
DOWNLOAD_TEMPLATE={artist}/{album}/{number:02d}. {title}
DOWNLOAD_QUALITY=HI_RES_LOSSLESS
DOWNLOAD_SKIP_EXISTING=True
DOWNLOAD_MAX_BYTES=2147483648
```

Every path component in `DOWNLOAD_TEMPLATE` is sanitised, so a track titled
`../../etc/passwd` cannot escape `DOWNLOAD_DIR`. Files are written to a `.part`
sibling and moved into place atomically, so an interrupted download never
leaves a truncated file.

## Deployment

### Local Development

```bash
python main.py
```

### Docker Deployment

#### Prerequisites

1. **Create .env file** with your Tidal credentials:

```bash
cp .env.example .env
# Edit .env and add your credentials from token.json
```

1. **Your .env file should contain:**

```bash
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
USER_ID=your_user_id
REFRESH_TOKEN=your_refresh_token
COUNTRY_CODE=US

USE_PROXIES=False
DEV_MODE=False
```

#### Using Docker Compose (Recommended)

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

#### Using Docker directly

```bash
# Build the image
docker build -t hifi-api .

# Run the container with environment variables
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  --name hifi-api \
  hifi-api

# View logs
docker logs -f hifi-api

# Stop the container
docker stop hifi-api
docker rm hifi-api
```

#### Docker Features

- **Security**: Runs as non-root user
- **Environment Variables**: Credentials loaded from .env file
- **Health Checks**: Automatic health monitoring
- **Volume Mounts**: Log management
- **Auto-restart**: Container restarts on failure
- **Optimized Caching**: Efficient layer caching for faster builds

### Vercel Deployment

#### Prerequisites

- Vercel CLI installed: `npm install -g vercel`
- Vercel account
- Configured `token.json` with valid credentials

#### Deployment Steps

1. **Install Vercel CLI** (if not already installed):

```bash
npm install -g vercel
```

1. **Login to Vercel**:

```bash
vercel login
```

1. **Deploy**:

```bash
vercel
```

Follow the prompts:

- Set up and deploy: `Yes`
- Select your account scope
- Project name: `hifi-api` (or your preferred name)
- Directory: `./` (current directory)

1. **Set Environment Variables**:

```bash
vercel env add COUNTRY_CODE
# Enter: US

vercel env add DEV_MODE
# Enter: False
```

1. **Handle token.json for Vercel**:

**Option A - Environment Variables (Recommended):**
Extract values from your `token.json` and set them as individual environment variables:

```bash
vercel env add CLIENT_ID
vercel env add CLIENT_SECRET
vercel env add REFRESH_TOKEN
vercel env add USER_ID
```

**Option B - Include token.json (Less Secure):**

- Temporarily remove `token.json` from `.vercelignore`
- Redeploy with `vercel --prod`
- Add `token.json` back to `.vercelignore`

1. **Production Deployment**:

```bash
vercel --prod
```

#### Vercel Considerations

- **Execution Time Limits**: Hobby (10s), Pro (60s)
- **Cold Starts**: First request will be slower
- **Stateless**: Each request is independent
- **Memory Limits**: May affect concurrent request handling

## Architecture

### Credential Management

- **Playback Pool**: Each playback account handles one request at a time
- **Request Queuing**: Returns HTTP 202 when all accounts are occupied
- **Job Tracking**: Pollable status endpoints for queued requests
- **Automatic Refresh**: Tokens are refreshed automatically with per-credential locking

### Proxy Support

- **Rotation**: Automatic proxy rotation on token refresh
- **Testing**: Concurrent proxy testing for fastest working proxy
- **Failover**: Configurable retry logic with fallback options
- **IP Protection**: Helps hide your host IP from Tidal

## Troubleshooting

### Authentication Issues

**Problem**: Token refresh fails
**Solution**: Run the authentication script again to get fresh credentials

**Problem**: Account blocked by Tidal
**Solution**: This is a known risk. Consider using proxy rotation and limiting request frequency.

### API Issues

**Problem**: 429 Too Many Requests
**Solution**: The API has built-in retry logic. Consider reducing request frequency.

**Problem**: 401 Unauthorized
**Solution**: Your token may have expired. The API should auto-refresh, but check your credentials.

### Deployment Issues

**Problem**: Vercel deployment fails
**Solution**: Check that `requirements-vercel.txt` includes all dependencies and `api/index.py` exists.

**Problem**: Timeouts on Vercel
**Solution**: Large album track fetching may timeout. Consider pagination or upgrading to Vercel Pro.

## Security Recommendations

1. **Never commit** `.env` or `token.json` to version control
2. **Use environment variables** for sensitive data in production
3. **Restrict CORS** origins in production (currently open to all)
4. **Consider adding API authentication** for additional security
5. **Monitor account status** for any blocking activity
6. **Use proxy rotation** to minimize IP exposure
7. **Keep `ENABLE_DOWNLOADS=False`** unless you accept the account-ban risk;
   if you enable it, add API authentication first

### Testing

The offline suite covers manifest parsing, path sanitisation and the download
endpoints. It needs no Tidal credentials and makes no network calls:

```bash
python -m pytest tests/test_manifest.py tests/test_download_api.py -q
```

`tests/local_e2e.py` runs the complete download pipeline against a **fake Tidal
and fake CDN** served on localhost. It makes real HTTP requests and real file
writes, but never contacts Tidal and never uses your credentials, so it is safe
to run any time:

```bash
python tests/local_e2e.py
```

It verifies manifest parsing for both BTS and DASH, the extension mapping,
segment concatenation, filename templating, skip-existing behaviour, atomic
writes, and the disabled/serverless gates.

`tests/test_endpoints.py` is a separate live smoke test against a running
server: `python tests/test_endpoints.py`.

## Project Structure

```
hifi-api/
├── api/
│   └── index.py              # Vercel entry point
├── download/
│   ├── manifest.py           # BTS + DASH manifest parsing (pure, no I/O)
│   ├── service.py            # Tidal calls, quality mapping, segment fetching
│   ├── store.py              # Path templating, sanitisation, atomic writes
│   └── ffmpeg.py             # Optional remuxing, degrades if ffmpeg absent
├── tests/
│   ├── test_manifest.py      # Offline parser + path safety tests
│   └── test_download_api.py  # Endpoint tests with stubbed network
├── tidal_auth/
│   ├── tidal_auth.py         # OAuth authentication script
│   └── requirements.txt      # Auth dependencies
├── main.py                   # Main FastAPI application
├── requirements.txt          # All dependencies
├── requirements-vercel.txt   # Vercel-specific dependencies
├── token.json                # Tidal credentials (auto-generated)
├── .env.example              # Environment variable template
├── .env                      # Your environment variables (create this)
├── .vercelignore             # Files to exclude from Vercel
├── .dockerignore             # Files to exclude from Docker
├── vercel.json               # Vercel configuration
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Docker configuration
├── logs/                     # Log directory (created by Docker)
└── README.md                 # This file
```

## API Response Format

All endpoints return JSON in the following format:

```json
{
  "version": "2.10",
  "data": { ... }
}
```

## Contributing

This project is forked from [sachinsenal0x64/hifi](https://github.com/sachinsenal0x64/hifi). Please respect the original project's license and terms.

## License

See LICENSE file for details.

## Disclaimer

This project is for educational purposes only. Music piracy is illegal in most countries. The authors are not responsible for any misuse of this software or any consequences resulting from its use. Always respect copyright laws and terms of service of music streaming platforms.

## Support

For issues related to:

- **Tidal API**: Check Tidal's official documentation
- **Deployment**: Refer to deployment guides above
- **Authentication**: Re-run the tidal_auth script
- **Account Blocking**: This is a known risk with no guaranteed solution
