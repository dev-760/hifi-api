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
