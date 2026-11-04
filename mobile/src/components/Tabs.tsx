import { Ionicons } from '@expo/vector-icons';
import { Redirect, Tabs } from 'expo-router';

import { useLocale, TKey } from '../i18n';
import { useAuth } from '../lib/auth';
import type { Role } from '../lib/types';
import { useTheme } from './theme';
import { Loading } from './ui';

export interface TabDef {
  name: string;
  title: TKey;
  icon: keyof typeof Ionicons.glyphMap;
}

export function RoleTabs({ role, tabs }: { role: Role; tabs: TabDef[] }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Redirect href="/welcome" />;
  if (user.role !== role) return <Redirect href="/" />;
  return (
    <Tabs screenOptions={{
      tabBarActiveTintColor: t.primary,
      tabBarInactiveTintColor: t.muted,
      tabBarStyle: { backgroundColor: t.card, borderTopColor: t.border },
      headerStyle: { backgroundColor: t.card },
      headerTintColor: t.text,
      headerTitleStyle: { fontWeight: '700' },
    }}>
      {tabs.map((tab) => (
        <Tabs.Screen key={tab.name} name={tab.name} options={{
          title: tr(tab.title),
          tabBarIcon: ({ color, size }) => <Ionicons name={tab.icon} color={color as string} size={size} />,
        }} />
      ))}
    </Tabs>
  );
}
