import { useState } from 'react';
import { FlatList, RefreshControl, TextInput } from 'react-native';

import { AdminWorkshopRow } from '../../components/AdminWorkshopRow';
import { radius, useTheme } from '../../components/theme';
import { Chip, Empty, ErrorText, Loading, Row } from '../../components/ui';
import { api } from '../../lib/api';
import type { VerificationStatus } from '../../lib/types';
import { useLoader } from '../../lib/useLoader';

const FILTERS: (VerificationStatus | '')[] = ['', 'pending', 'approved', 'rejected', 'suspended'];

export default function AllWorkshops() {
  const t = useTheme();
  const [status, setStatus] = useState<VerificationStatus | ''>('');
  const [q, setQ] = useState('');
  const { data, error, refreshing, reload } = useLoader(() => api.admin.workshops(status, q.trim()));
  const pick = (s: VerificationStatus | '') => {
    setStatus(s);
    setTimeout(reload, 0);
  };
  if (!data && !error) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 900, width: '100%', alignSelf: 'center' }}
      data={data ?? []}
      keyExtractor={(w) => String(w.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
      ListHeaderComponent={<>
        <TextInput value={q} onChangeText={setQ} onSubmitEditing={reload} placeholder="Search name, city, email, phone"
          placeholderTextColor={t.muted} returnKeyType="search"
          style={{ backgroundColor: t.inputBg, color: t.text, borderColor: t.border, borderWidth: 1, borderRadius: radius, padding: 12 }} />
        <Row wrap>{FILTERS.map((f) => <Chip key={f || 'all'} label={f || 'all'} active={status === f} onPress={() => pick(f)} />)}</Row>
        <ErrorText error={error} />
      </>}
      ListEmptyComponent={<Empty icon="construct-outline" text="No workshops match." />}
      renderItem={({ item }) => <AdminWorkshopRow w={item} />}
    />
  );
}
