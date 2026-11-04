import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * API base URL, in priority order:
 *  1. EXPO_PUBLIC_API_URL env var (set this for production builds)
 *  2. in development, the dev machine's LAN IP taken from the Metro host, so a
 *     phone on the same Wi-Fi reaches the backend on port 8000
 *  3. app.json extra.apiUrl
 */
function resolveApiUrl(): string {
  const env = process.env.EXPO_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, '');
  const fallback = (Constants.expoConfig?.extra?.apiUrl as string | undefined) ?? 'http://localhost:8000';
  if (__DEV__ && Platform.OS !== 'web') {
    const host = Constants.expoConfig?.hostUri?.split(':')[0];
    if (host) return `http://${host}:8000`;
  }
  return fallback.replace(/\/$/, '');
}

export const API_URL = resolveApiUrl();
export const WS_URL = API_URL.replace(/^http/, 'ws');
