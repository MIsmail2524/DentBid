import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * API base URL, in priority order:
 *  1. EXPO_PUBLIC_API_URL env var (set this for production builds)
 *  2. production web build: the page's own origin (the API serves the web app)
 *  3. in development, the dev machine's LAN IP taken from the Metro host, so a
 *     phone on the same Wi-Fi reaches the backend on port 8000
 *  4. app.json extra.apiUrl
 */
function resolveApiUrl(): string {
  const env = process.env.EXPO_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, '');
  const fallback = (Constants.expoConfig?.extra?.apiUrl as string | undefined) ?? 'http://localhost:8000';
  // the production web build is served by the API itself: talk to the same origin
  if (!__DEV__ && Platform.OS === 'web' && typeof window !== 'undefined') return window.location.origin;
  if (__DEV__ && Platform.OS !== 'web') {
    const host = Constants.expoConfig?.hostUri?.split(':')[0];
    if (host) return `http://${host}:8000`;
  }
  return fallback.replace(/\/$/, '');
}

export const API_URL = resolveApiUrl();
export const WS_URL = API_URL.replace(/^http/, 'ws');

/** Turns a server path ("/media/...", "/api/...") into an absolute URL for <Image>. */
export function absoluteUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return /^https?:\/\//.test(url) ? url : `${API_URL}${url}`;
}
