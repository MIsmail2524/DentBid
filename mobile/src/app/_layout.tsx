import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { useTheme } from '../components/theme';
import { Loading } from '../components/ui';
import { LocaleProvider, useLocale } from '../i18n';
import { AuthProvider } from '../lib/auth';

function Root() {
  const t = useTheme();
  const { ready, rtl } = useLocale();
  if (!ready) return <Loading />;
  return (
    // Yoga applies `direction` to all children, so switching to Urdu/Arabic
    // flips the layout immediately without restarting the app.
    <View style={{ flex: 1, direction: rtl ? 'rtl' : 'ltr', backgroundColor: t.bg }}
      {...(Platform.OS === 'web' ? { dir: rtl ? 'rtl' : 'ltr' } : {})}>
      <StatusBar style="auto" />
      <Stack screenOptions={{
        headerStyle: { backgroundColor: t.card },
        headerTintColor: t.text,
        headerTitleStyle: { fontWeight: '700' },
        contentStyle: { backgroundColor: t.bg },
      }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="welcome" options={{ headerShown: false }} />
        <Stack.Screen name="customer" options={{ headerShown: false }} />
        <Stack.Screen name="workshop" options={{ headerShown: false }} />
      </Stack>
    </View>
  );
}

export default function Layout() {
  return (
    <SafeAreaProvider>
      <LocaleProvider>
        <AuthProvider>
          <Root />
        </AuthProvider>
      </LocaleProvider>
    </SafeAreaProvider>
  );
}
