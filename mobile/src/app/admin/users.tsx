import { useState } from 'react';
import { FlatList, RefreshControl, TextInput, View } from 'react-native';

import { confirm } from '../../components/QuoteCard';
import { radius, useTheme } from '../../components/theme';
import { Badge, Button, Card, Empty, ErrorText, H2, Loading, P, Row } from '../../components/ui';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { useLoader } from '../../lib/useLoader';

export default function Users() {
  const t = useTheme();
  const { user: me } = useAuth();
  const [q, setQ] = useState('');
  const [actionError, setActionError] = useState<unknown>(null);
  const { data, error, refreshing, reload } = useLoader(() => api.admin.users(q.trim()));

  const act = async (fn: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setActionError(e);
    }
  };

  if (!data && !error) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 900, width: '100%', alignSelf: 'center' }}
      data={data ?? []}
      keyExtractor={(u) => String(u.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
      ListHeaderComponent={<>
        <TextInput value={q} onChangeText={setQ} onSubmitEditing={reload} placeholder="Search name, email, phone"
          placeholderTextColor={t.muted} returnKeyType="search"
          style={{ backgroundColor: t.inputBg, color: t.text, borderColor: t.border, borderWidth: 1, borderRadius: radius, padding: 12 }} />
        <ErrorText error={error ?? actionError} />
      </>}
      ListEmptyComponent={<Empty icon="people-outline" text="No users match." />}
      renderItem={({ item: u }) => (
        <Card>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}>
              <H2 style={{ fontSize: 16 }}>{u.name}</H2>
              <P muted style={{ fontSize: 13 }}>{u.email}{u.phone ? ` · ${u.phone}` : ''}{u.country_code ? ` · ${u.country_code}` : ''}</P>
            </View>
            <Row>
              <Badge label={u.role} color={t.primary} />
              {!u.is_active && <Badge label="disabled" color={t.danger} />}
            </Row>
          </Row>
          {u.id !== me?.id && (u.is_active ? (
            <Button title="Disable account" variant="ghost" icon="ban-outline"
              onPress={() => confirm(`Disable ${u.email}? They are signed out everywhere.`,
                () => act(() => api.admin.deactivate(u.id, 'Disabled by admin')))} />
          ) : (
            <Button title="Enable account" variant="secondary" onPress={() => act(() => api.admin.activate(u.id))} />
          ))}
        </Card>
      )}
    />
  );
}
