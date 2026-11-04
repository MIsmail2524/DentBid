import { useEffect, useState } from 'react';
import { ActivityIndicator, Image, ImageStyle, Platform, StyleProp, View } from 'react-native';

import { getAuthToken } from '../lib/api';
import { absoluteUrl } from '../lib/config';
import { useTheme } from './theme';

/**
 * Image behind an authenticated endpoint (verification documents).
 * Native <Image> can send headers; on web we fetch with the token and show a blob URL.
 */
export function AuthImage({ url, style }: { url: string; style?: StyleProp<ImageStyle> }) {
  const t = useTheme();
  const full = absoluteUrl(url) ?? '';
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (Platform.OS !== 'web') return;
    let revoked = false;
    let made: string | null = null;
    fetch(full, { headers: { Authorization: `Bearer ${getAuthToken()}` } })
      .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
      .then((b) => {
        if (revoked) return;
        made = URL.createObjectURL(b);
        setBlobUrl(made);
      })
      .catch(() => undefined);
    return () => {
      revoked = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [full]);

  if (Platform.OS !== 'web') {
    return <Image source={{ uri: full, headers: { Authorization: `Bearer ${getAuthToken()}` } }} style={style} resizeMode="cover" />;
  }
  if (!blobUrl) {
    return <View style={[{ alignItems: 'center', justifyContent: 'center', backgroundColor: t.chip }, style]}><ActivityIndicator /></View>;
  }
  return <Image source={{ uri: blobUrl }} style={style} resizeMode="cover" />;
}
