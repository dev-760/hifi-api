// Quick Start Template for Expo + hifi-api Integration
// Copy these files into your Expo project structure

// ==================== FILE 1: src/config/api.js ====================
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


// ==================== FILE 2: src/services/hifiApi.js ====================
import axios from 'axios';
import { API_CONFIG } from '../config/api';

const api = axios.create(API_CONFIG);

export default api;


// ==================== FILE 3: src/services/musicApi.js ====================
import api from './hifiApi';

export const searchTracks = async (query, limit = 25) => {
  const response = await api.get(`/search/`, {
    params: { s: query, limit }
  });
  return response.data;
};

export const getTrackInfo = async (trackId) => {
  const response = await api.get(`/info/`, {
    params: { id: trackId }
  });
  return response.data;
};

export const getTrackPlayback = async (trackId, quality = 'HI_RES_LOSSLESS') => {
  const response = await api.get(`/track/`, {
    params: { id: trackId, quality }
  });
  return response.data;
};

export const getAlbum = async (albumId, limit = 100) => {
  const response = await api.get(`/album/`, {
    params: { id: albumId, limit }
  });
  return response.data;
};

export const getArtist = async (artistId) => {
  const response = await api.get(`/artist/`, {
    params: { id: artistId }
  });
  return response.data;
};


// ==================== FILE 4: App.js (Simple Version) ====================
import React, { useState } from 'react';
import { View, Text, TextInput, FlatList, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { searchTracks, getTrackInfo, getTrackPlayback } from './src/services/musicApi';

export default function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedTrack, setSelectedTrack] = useState(null);

  const handleSearch = async () => {
    if (!query) return;
    setLoading(true);
    try {
      const response = await searchTracks(query);
      setResults(response.data?.items || []);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTrackPress = async (trackId) => {
    setLoading(true);
    try {
      const [info, playback] = await Promise.all([
        getTrackInfo(trackId),
        getTrackPlayback(trackId)
      ]);
      setSelectedTrack({ info: info.data, playback: playback.data });
    } catch (error) {
      console.error('Track details error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (selectedTrack) {
    return (
      <View style={styles.container}>
        <TouchableOpacity onPress={() => setSelectedTrack(null)} style={styles.backButton}>
          <Text style={styles.backButtonText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>{selectedTrack.info.title}</Text>
        <Text style={styles.subtitle}>{selectedTrack.info.artist?.name}</Text>
        <Text style={styles.detail}>Album: {selectedTrack.info.album?.title}</Text>
        <Text style={styles.detail}>Duration: {Math.floor(selectedTrack.info.duration / 60)}:{(selectedTrack.info.duration % 60).toString().padStart(2, '0')}</Text>
        <Text style={styles.detail}>Quality: {selectedTrack.info.audioQuality}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Music Search</Text>
      <TextInput
        style={styles.input}
        placeholder="Search for tracks..."
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={handleSearch}
      />
      <TouchableOpacity style={styles.button} onPress={handleSearch}>
        <Text style={styles.buttonText}>Search</Text>
      </TouchableOpacity>
      
      {loading ? (
        <ActivityIndicator size="large" color="#007AFF" />
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => (
            <TouchableOpacity 
              style={styles.trackItem}
              onPress={() => handleTrackPress(item.id)}
            >
              <Text style={styles.trackTitle}>{item.title}</Text>
              <Text style={styles.artistName}>{item.artist?.name}</Text>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  header: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    textAlign: 'center',
  },
  input: {
    height: 50,
    borderColor: '#ddd',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 15,
    marginBottom: 15,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#007AFF',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 20,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  trackItem: {
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  trackTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 5,
  },
  artistName: {
    fontSize: 14,
    color: '#666',
  },
  backButton: {
    marginBottom: 20,
  },
  backButtonText: {
    fontSize: 16,
    color: '#007AFF',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  subtitle: {
    fontSize: 18,
    color: '#666',
    marginBottom: 20,
  },
  detail: {
    fontSize: 16,
    marginBottom: 10,
  },
});


// ==================== INSTALL COMMANDS ====================
// Run these in your Expo project:

// 1. Install dependencies
// npm install axios
// npx expo install expo-av

// 2. Install navigation (if using the full version)
// npm install @react-navigation/native @react-navigation/stack
// npx expo install react-native-screens react-native-safe-area-context

// 3. Start your app
// npx expo start
