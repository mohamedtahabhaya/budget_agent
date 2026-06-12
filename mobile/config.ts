// Configuration for the Budget Agent Mobile client
import { Platform } from 'react-native';
import Constants from 'expo-constants';

const getApiUrl = () => {
  // Web client dynamic discovery
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined' && window.location) {
      return `http://${window.location.hostname}:8000`;
    }
    return 'http://localhost:8000';
  }

  // Native mobile (Expo Go) dynamic host discovery
  try {
    const hostUri = Constants.expoConfig?.hostUri; // e.g. "192.168.11.19:8081"
    if (hostUri) {
      const ip = hostUri.split(':')[0];
      if (ip) {
        return `http://${ip}:8000`;
      }
    }
  } catch (error) {
    console.warn('Failed to dynamically determine API URL, using fallback:', error);
  }

  // Safe fallback for emulators
  return Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
};

export const API_URL = getApiUrl();
console.log('[API_URL Configured]', API_URL);

export const DEFAULT_WORKSPACE_ID = 'workspace_coloc_taha_mohamed';
export const DEFAULT_USER_ID = 'user_mohamed';
