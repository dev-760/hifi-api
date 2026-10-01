# Expo App Integration Guide for hifi-api

## Step 1: Set Up Your Expo Project

If you don't have an Expo project yet:

```bash
npx create-expo-app my-music-app
cd my-music-app
```

## Step 2: Install Required Dependencies

```bash
# For API calls
npm install axios

# For audio playback (optional)
npx expo install expo-av

# For state management (optional)
npm install @react-native-async-storage/async-storage
```

## Step 3: Create API Configuration

Create a file `src/config/api.js`:

```javascript
// src/config/api.js
const API_BASE_URL = __DEV__ 
  ? 'http://localhost:8000'  // Local development
  : 'https://your-vercel-app.vercel.app';  // Production

export const API_CONFIG = {
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
};

export default API_CONFIG;
```

## Step 4: Create API Service Layer

Create `src/services/hifiApi.js`:

```javascript
// src/services/hifiApi.js
import axios from 'axios';
import { API_CONFIG } from '../config/api';

const api = axios.create(API_CONFIG);

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
```

## Step 5: Create API Functions

Create `src/services/musicApi.js`:

```javascript
// src/services/musicApi.js
import api from './hifiApi';

// Track Info
export const getTrackInfo = async (trackId) => {
  try {
    const response = await api.get(`/info/`, {
      params: { id: trackId }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Track Playback URL
export const getTrackPlayback = async (trackId, quality = 'HI_RES_LOSSLESS') => {
  try {
    const response = await api.get(`/track/`, {
      params: { 
        id: trackId, 
        quality 
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Search
export const searchTracks = async (query, limit = 25) => {
  try {
    const response = await api.get(`/search/`, {
      params: { 
        s: query, 
        limit 
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const searchArtists = async (query, limit = 25) => {
  try {
    const response = await api.get(`/search/`, {
      params: { 
        a: query, 
        limit 
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const searchAlbums = async (query, limit = 25) => {
  try {
    const response = await api.get(`/search/`, {
      params: { 
        al: query, 
        limit 
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Album Details
export const getAlbum = async (albumId, limit = 100) => {
  try {
    const response = await api.get(`/album/`, {
      params: { 
        id: albumId, 
        limit 
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Artist Details
export const getArtist = async (artistId) => {
  try {
    const response = await api.get(`/artist/`, {
      params: { id: artistId }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const getArtistAlbums = async (artistId, skipTracks = false) => {
  try {
    const response = await api.get(`/artist/`, {
      params: { 
        f: artistId,
        skip_tracks: skipTracks
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Playlist
export const getPlaylist = async (playlistId, limit = 100) => {
  try {
    const response = await api.get(`/playlist/`, {
      params: { 
        id: playlistId, 
        limit 
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Cover Art
export const getCover = async (trackId) => {
  try {
    const response = await api.get(`/cover/`, {
      params: { id: trackId }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Recommendations
export const getRecommendations = async (trackId) => {
  try {
    const response = await api.get(`/recommendations/`, {
      params: { id: trackId }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

// Track Manifests (for advanced streaming)
export const getTrackManifests = async (trackId, formats = ['FLAC', 'FLAC_HIRES']) => {
  try {
    const response = await api.get(`/trackManifests/`, {
      params: { 
        id: trackId,
        formats: formats
      }
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};
```

## Step 6: Create React Hooks

Create `src/hooks/useMusicApi.js`:

```javascript
// src/hooks/useMusicApi.js
import { useState, useEffect } from 'react';
import { searchTracks, getTrackInfo, getTrackPlayback } from '../services/musicApi';

export const useSearch = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = async (query) => {
    if (!query) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await searchTracks(query);
      setResults(response.data?.items || []);
    } catch (err) {
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return { results, loading, error, search };
};

export const useTrack = (trackId) => {
  const [track, setTrack] = useState(null);
  const [playbackUrl, setPlaybackUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!trackId) return;

    const fetchTrack = async () => {
      setLoading(true);
      setError(null);

      try {
        const [infoData, playbackData] = await Promise.all([
          getTrackInfo(trackId),
          getTrackPlayback(trackId)
        ]);
        
        setTrack(infoData.data);
        setPlaybackUrl(playbackData.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTrack();
  }, [trackId]);

  return { track, playbackUrl, loading, error };
};
```

## Step 7: Create UI Components

### Search Screen

Create `src/screens/SearchScreen.js`:

```javascript
// src/screens/SearchScreen.js
import React, { useState } from 'react';
import { 
  View, 
  Text, 
  TextInput, 
  FlatList, 
  TouchableOpacity, 
  Image, 
  ActivityIndicator 
} from 'react-native';
import { useSearch } from '../hooks/useMusicApi';

const SearchScreen = ({ navigation }) => {
  const [query, setQuery] = useState('');
  const { results, loading, error, search } = useSearch();

  const handleSearch = () => {
    search(query);
  };

  const renderTrack = ({ item }) => {
    const coverUrl = item.album?.cover 
      ? `https://resources.tidal.com/images/${item.album.cover.replace('-', '/')}/320x320.jpg`
      : null;

    return (
      <TouchableOpacity 
        style={styles.trackItem}
        onPress={() => navigation.navigate('TrackDetail', { trackId: item.id })}
      >
        {coverUrl && (
          <Image 
            source={{ uri: coverUrl }} 
            style={styles.coverImage}
            defaultSource={require('../assets/placeholder.png')}
          />
        )}
        <View style={styles.trackInfo}>
          <Text style={styles.trackTitle}>{item.title}</Text>
          <Text style={styles.artistName}>{item.artist?.name}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.searchInput}
        placeholder="Search tracks..."
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={handleSearch}
        returnKeyType="search"
      />
      
      {loading && <ActivityIndicator size="large" color="#0000ff" />}
      
      {error && <Text style={styles.errorText}>{error}</Text>}
      
      <FlatList
        data={results}
        renderItem={renderTrack}
        keyExtractor={(item) => item.id.toString()}
        style={styles.resultsList}
      />
    </View>
  );
};

const styles = {
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#fff',
  },
  searchInput: {
    height: 50,
    borderColor: '#ddd',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 16,
    marginBottom: 16,
    fontSize: 16,
  },
  trackItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  coverImage: {
    width: 50,
    height: 50,
    borderRadius: 4,
    marginRight: 12,
  },
  trackInfo: {
    flex: 1,
  },
  trackTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  artistName: {
    fontSize: 14,
    color: '#666',
  },
  errorText: {
    color: 'red',
    textAlign: 'center',
    marginBottom: 16,
  },
  resultsList: {
    flex: 1,
  },
};

export default SearchScreen;
```

### Track Detail Screen

Create `src/screens/TrackDetailScreen.js`:

```javascript
// src/screens/TrackDetailScreen.js
import React from 'react';
import { View, Text, Image, ScrollView, ActivityIndicator, TouchableOpacity } from 'react-native';
import { useTrack } from '../hooks/useMusicApi';
import { Audio } from 'expo-av';

const TrackDetailScreen = ({ route }) => {
  const { trackId } = route.params;
  const { track, playbackUrl, loading, error } = useTrack(trackId);
  const [sound, setSound] = React.useState(null);
  const [isPlaying, setIsPlaying] = React.useState(false);

  const playSound = async () => {
    if (!playbackUrl?.manifest) return;

    try {
      // Decode the manifest (base64 encoded JSON)
      const manifestData = JSON.parse(atob(playbackUrl.manifest));
      const streamUrl = manifestData.urls[0];

      const { sound } = await Audio.Sound.createAsync(
        { uri: streamUrl },
        { shouldPlay: true }
      );
      
      setSound(sound);
      setIsPlaying(true);
      
      sound.setOnAudioPlaybackStatusUpdate((status) => {
        if (status.didJustFinish) {
          setIsPlaying(false);
        }
      });
    } catch (err) {
      console.error('Error playing sound:', err);
    }
  };

  const stopSound = async () => {
    if (sound) {
      await sound.stopAsync();
      await sound.unloadAsync();
      setSound(null);
      setIsPlaying(false);
    }
  };

  React.useEffect(() => {
    return () => {
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, [sound]);

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#0000ff" />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Error: {error}</Text>
      </View>
    );
  }

  if (!track) {
    return (
      <View style={styles.centerContainer}>
        <Text>Track not found</Text>
      </View>
    );
  }

  const coverUrl = track.album?.cover
    ? `https://resources.tidal.com/images/${track.album.cover.replace('-', '/')}/640x640.jpg`
    : null;

  return (
    <ScrollView style={styles.container}>
      {coverUrl && (
        <Image 
          source={{ uri: coverUrl }} 
          style={styles.coverImage}
          defaultSource={require('../assets/placeholder.png')}
        />
      )}
      
      <View style={styles.infoContainer}>
        <Text style={styles.trackTitle}>{track.title}</Text>
        <Text style={styles.artistName}>{track.artist?.name}</Text>
        <Text style={styles.albumName}>{track.album?.title}</Text>
        
        <View style={styles.metadata}>
          <Text style={styles.metadataText}>Duration: {Math.floor(track.duration / 60)}:{(track.duration % 60).toString().padStart(2, '0')}</Text>
          <Text style={styles.metadataText}>Quality: {track.audioQuality}</Text>
        </View>

        <TouchableOpacity 
          style={styles.playButton}
          onPress={isPlaying ? stopSound : playSound}
        >
          <Text style={styles.playButtonText}>
            {isPlaying ? 'Stop' : 'Play'}
          </Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = {
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  coverImage: {
    width: '100%',
    height: 400,
    resizeMode: 'cover',
  },
  infoContainer: {
    padding: 20,
  },
  trackTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  artistName: {
    fontSize: 18,
    color: '#666',
    marginBottom: 4,
  },
  albumName: {
    fontSize: 16,
    color: '#888',
    marginBottom: 16,
  },
  metadata: {
    marginBottom: 24,
  },
  metadataText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  playButton: {
    backgroundColor: '#007AFF',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  playButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '600',
  },
  errorText: {
    color: 'red',
    fontSize: 16,
  },
};

export default TrackDetailScreen;
```

## Step 8: Set Up Navigation

Update your `App.js`:

```javascript
// App.js
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import SearchScreen from './src/screens/SearchScreen';
import TrackDetailScreen from './src/screens/TrackDetailScreen';

const Stack = createStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Search">
        <Stack.Screen 
          name="Search" 
          component={SearchScreen}
          options={{ title: 'Music Search' }}
        />
        <Stack.Screen 
          name="TrackDetail" 
          component={TrackDetailScreen}
          options={{ title: 'Track Details' }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
```

## Step 9: Install Navigation Dependencies

```bash
npm install @react-navigation/native @react-navigation/stack
npx expo install react-native-screens react-native-safe-area-context
```

## Step 10: Test Your Integration

1. **Start your local API** (if testing locally):

   ```bash
   python main.py
   ```

2. **Start your Expo app**:

   ```bash
   npx expo start
   ```

3. **Test on your device** using the Expo Go app

## Step 11: Update for Production

When you deploy your API to Vercel, update `src/config/api.js`:

```javascript
// src/config/api.js
const API_BASE_URL = 'https://your-vercel-app.vercel.app';

export const API_CONFIG = {
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
};

export default API_CONFIG;
```

## Common Issues and Solutions

### CORS Issues

If you encounter CORS errors, ensure your API's CORS middleware is configured correctly. The hifi-api already has CORS enabled with `allow_origins=["*"]`.

### Network Security

For production, consider:

- Adding authentication to your API
- Using HTTPS only
- Implementing rate limiting
- Adding error handling for network issues

### Audio Playback

For better audio handling, consider using:

- `expo-av` for basic playback
- `react-native-track-player` for advanced features
- Background audio support for music apps

### Performance

- Implement caching for frequently accessed data
- Use pagination for large result sets
- Optimize image loading with caching

## Next Steps

1. **Add more screens**: Album details, artist pages, playlists
2. **Implement user authentication**: If you want user-specific features
3. **Add offline support**: Cache tracks and metadata
4. **Implement state management**: Use Redux or Context API for complex state
5. **Add analytics**: Track user behavior and API usage

This integration provides a solid foundation for your music app connected to the hifi-api!

---

# Offline Downloads

Optional section for caching hi-res audio on-device. See
[API_SCHEMA.md](API_SCHEMA.md) for the exact request and response contracts.

## How it works

There are two ways to get audio onto the device, and the right choice depends
on whether the API is running where you can reach a filesystem.

> ⚠️ The live deployment at `https://hifi-api00.vercel.app` currently returns
> `500` from `/download/resolve/` because it runs a build from before the DASH
> parser was fixed. Run the API locally or with Docker while testing, and see
> [API_SCHEMA.md](API_SCHEMA.md#known-upstream-quirks) for details.

### Option A — Resolve, then fetch on-device (recommended)

The API returns short-lived CDN URLs; the app downloads and concatenates them.
Nothing is written to the API host, so this works even against a Vercel
deployment.

```
GET /download/resolve/  ──►  [seg0, seg1, seg2]
        │
        └─ app fetches each URL, concatenates, writes to disk
```

**Prefer this when** the API is on Vercel, you want per-user storage, or you
would rather not have audio pass through the server twice.

### Option B — Ask the server to write the file

```
POST /download/track/  ──►  { status: "downloaded", path: "..." }
```

The file lands on the **API host**, not on the phone. This is only useful if
you also mount that directory over a network share, or run the API on the same
LAN as a desktop player. On Vercel it returns `501` — there is no persistent
filesystem.

For a phone app, Option A is almost always what you want.

## Step 1: Install the extra dependencies

```bash
npx expo install expo-file-system
npx expo install expo-media-library   # save into the user's music library
```

`expo-file-system` differs by SDK generation. This guide uses the **new**
(async) API, which requires Expo SDK 52+:

```bash
npx expo install expo@latest
```

If you are on an older SDK, see [Legacy API](#legacy-file-system-api) below.

## Step 2: Add the download service

Create `src/services/downloadService.js`:

```javascript
// src/services/downloadService.js
import { API_BASE_URL } from '../config/api';
import { File, Directory, Paths } from 'expo-file-system';
import * as MediaLibrary from 'expo-media-library';

// Tracks currently downloading, so the UI can show progress and dedupe calls.
const active = new Map();

/**
 * Handles the 202 queue response that any playback-credential endpoint may
 * return when every account is busy.
 */
async function resolveOrPoll(path, params = {}, attempt = 0) {
  const query = new URLSearchParams(params).toString();
  const url = `${API_BASE_URL}${path}${query ? `?${query}` : ''}`;

  const res = await fetch(url);

  if (res.status === 202) {
    if (attempt > 60) throw new Error('Timed out waiting for a free account');

    const wait = Number(res.headers.get('retry-after') || 1);
    const location = res.headers.get('location');
    await new Promise((r) => setTimeout(r, wait * 1000));
    return resolveOrPoll(location, {}, attempt + 1);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  return res.json();
}

/** Step 1: ask the API for segment URLs. */
export async function resolveTrack(trackId, quality = 'HI_RES_LOSSLESS') {
  return resolveOrPoll('/download/resolve/', { id: trackId, quality });
}

/**
 * Step 2: fetch every segment and concatenate them into one file.
 *
 * Segments are fetched in order. The output is written incrementally via a
 * FileHandle in Append mode so a 24-bit/192 kHz track never has to be held in
 * memory in one piece.
 */
export async function downloadTrack(trackId, options = {}) {
  const { quality = 'HI_RES_LOSSLESS', onProgress, filename } = options;

  if (active.has(trackId)) return active.get(trackId);

  const task = (async () => {
    const manifest = await resolveTrack(trackId, quality);

    // Strip characters that are illegal in filenames on any platform.
    const safeName = (filename || String(manifest.trackId))
      .replace(/[/\\?%*:|"<>]/g, '_')
      .slice(0, 120);

    const dir = new Directory(Paths.document, 'tidal');
    if (!dir.exists) dir.create({ intermediates: true });

    const out = new File(dir, `${safeName}${manifest.fileExtension}`);
    if (out.exists) out.delete();

    const handle = out.open(FileMode.Append);
    try {
      for (let i = 0; i < manifest.urls.length; i += 1) {
        // Download to cache first; downloadFileAsync needs a File/Directory.
        const segment = await File.downloadFileAsync(
          manifest.urls[i],
          new Directory(Paths.cache),
        );

        // Append the segment's bytes to the output file.
        const bytes = await segment.bytes();
        handle.writeBytes(bytes);
        segment.delete();

        if (onProgress) {
          onProgress({
            stage: 'downloading',
            done: i + 1,
            total: manifest.urls.length,
            bytesWritten: out.size,
          });
        }
      }
    } finally {
      handle.close();
    }

    if (onProgress) onProgress({ stage: 'done', uri: out.uri });

    return {
      uri: out.uri,
      size: out.size,
      quality,
      extension: manifest.fileExtension,
      needsFlacExtraction: manifest.needsFlacExtraction,
    };
  })();

  active.set(trackId, task);
  try {
    return await task;
  } finally {
    active.delete(trackId);
  }
}

/** Save into the user's visible music library. */
export async function saveToLibrary(uri, title, artist, album) {
  const perm = await MediaLibrary.requestPermissionsAsync();
  if (!perm.granted) throw new Error('Media library permission denied');

  await MediaLibrary.saveToLibraryAsync(uri, title, artist, album);
}

/** Remove a previously downloaded file. */
export async function deleteDownload(uri) {
  const file = new File(uri);
  if (file.exists) file.delete();
}
```

> **Note:** the download is driven by the server's `/download/resolve/`
> response, so no Tidal credentials ever reach the device.

## Step 3: Download hook

Create `src/hooks/useDownload.js`:

```javascript
// src/hooks/useDownload.js
import { useState, useCallback } from 'react';
import { downloadTrack, deleteDownload } from '../services/downloadService';

export const useDownload = () => {
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [downloaded, setDownloaded] = useState(null);

  const download = useCallback(async (trackId, options = {}) => {
    setError(null);
    setDownloaded(null);

    try {
      const result = await downloadTrack(trackId, {
        ...options,
        onProgress: setProgress,
      });
      setProgress(null);
      setDownloaded(result);
      return result;
    } catch (err) {
      setError(err.message);
      setProgress(null);
      throw err;
    }
  }, []);

  const remove = useCallback(async (uri) => {
    await deleteDownload(uri);
    setDownloaded(null);
  }, []);

  return { progress, error, downloaded, download, remove };
};
```

## Step 4: Wire it into a component

```javascript
// src/components/DownloadButton.js
import React from 'react';
import { Pressable, Text, View, StyleSheet, Alert } from 'react-native';
import { useDownload } from '../hooks/useDownload';
import { saveToLibrary } from '../services/downloadService';

export const DownloadButton = ({ track, quality = 'HI_RES_LOSSLESS' }) => {
  const { progress, error, downloaded, download } = useDownload();

  const onPress = async () => {
    try {
      const result = await download(track.id, {
        quality,
        // Avoid characters that are illegal in filenames.
        filename: `${track.trackNumber ?? 0}. ${track.title}`,
      });

      // Optional: also drop it into the user's music library.
      await saveToLibrary(
        result.uri,
        track.title,
        track.artists?.[0]?.name ?? track.artist?.name,
        track.album?.title,
      );

      Alert.alert('Downloaded', `Saved ${track.title}`);
    } catch (err) {
      Alert.alert('Download failed', err.message);
    }
  };

  const busy = progress?.stage === 'downloading';

  return (
    <View>
      <Pressable onPress={onPress} disabled={busy}>
        <Text>{downloaded ? 'Downloaded' : busy ? 'Downloading...' : 'Download'}</Text>
      </Pressable>

      {busy && (
        <Text style={styles.progress}>
          {progress.segment ?? 0}/{progress.total} segments
        </Text>
      )}

      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
};

const styles = StyleSheet.create({
  progress: { fontSize: 12, color: '#666' },
  error: { fontSize: 12, color: 'crimson' },
});
```

## Step 5: Enable network access

On Android emulators and physical devices, `localhost` refers to the device
itself, not your machine. Use your LAN IP instead:

```javascript
// src/config/api.js
import { Platform } from 'react-native';

const DEV_HOST = Platform.OS === 'android' ? '192.168.1.100' : 'localhost';

export const API_BASE_URL = __DEV__
  ? `http://${DEV_HOST}:8000`
  : 'https://your-vercel-app.vercel.app';
```

On Android cleartext HTTP is blocked by default in release builds. For a local
LAN build add a network security config, or use HTTPS.

## Troubleshooting

### Segments 403 or fail mid-download

The URLs are short-lived and effectively single-use. Resolve and fetch in one
pass — do not cache `manifest.urls` between sessions.

### `422 Unsupported quality`

Use `LOW`, `HIGH`, `LOSSLESS`, `HI_RES_LOSSLESS`, or the aliases `low`,
`normal`, `lossless`, `max`. Note `high` means 320 kbps AAC here, not lossless.

### `503 Downloads are disabled`

Expected — downloads are opt-in. Set `ENABLE_DOWNLOADS=True` on the API host.
Remember this only affects Option B; Option A works regardless.

### `501` from `POST /download/track/`

The API is on a serverless platform with no writable disk. Use Option A.

### Concatenated file will not play

Check the extension matches `manifest.fileExtension`. For
`HI_RES_LOSSLESS` the server-side result is `.m4a` containing FLAC; some
players need `.m4a` and others need a remux, which is why the API reports
`needsFlacExtraction`.

## Legacy file-system API

On Expo SDK < 52, replace the file operations in `downloadService.js`:

```javascript
import * as FileSystem from 'expo-file-system';

const directory = `${FileSystem.documentDirectory}tidal/`;
await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
const target = `${directory}${safeName}${manifest.fileExtension}`;

const result = await FileSystem.createDownloadResumable(
  manifest.urls[0],
  target,
  {},
  (e) => { /* onProgress */ },
).downloadAsync();

// Legacy API cannot concatenate segments, so it only supports
// single-segment (LOW/HIGH) results. For multi-segment tracks, fetch each
// segment with fetch() and append with a legacy write.
```

Prefer upgrading to the current SDK if you need multi-segment hi-res.

## Security

The hifi-api has **no authentication**. Anyone who can reach it can spend your
Tidal account's playback quota, and if `ENABLE_DOWNLOADS=True` they can pull
audio through your IP. Do not expose it to the public internet without putting
authentication in front of it.
