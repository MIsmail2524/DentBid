import { FlatList, RefreshControl } from 'react-native';

import { AdminWorkshopRow } from '../../components/AdminWorkshopRow';
import { useTheme } from '../../components/theme';
import { Card, Empty, ErrorText, H2, Loading, P, Row, Stat } from '../../components/ui';
import { api } from '../../lib/api';
import { useRealtime } from '../../lib/realtime';
import { useLoader } from '../../lib/useLoader';

export default function VerificationQueue() {
  const t = useTheme();
  const { data, error, refreshing, reload } = useLoader(async () => {
    const [stats, pending] = await Promise.all([api.admin.stats(), api.admin.workshops('pending')]);
    return { stats, pending };
  });
  useRealtime((e) => {
    if (e.type === 'admin.workshop_pending') reload();
  });
  if (!data && !error) return <Loading />;
  const s = data?.stats;
  return (
    <FlatList
      style={{ backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 900, width: '100%', alignSelf: 'center' }}
      data={data?.pending ?? []}
      keyExtractor={(w) => String(w.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
      ListHeaderComponent={<>
        <ErrorText error={error} />
        {s && (
          <Card>
            <Row wrap>
              <Stat label="Pending workshops" value={String(s.workshops.pending ?? 0)} />
              <Stat label="Verified workshops" value={String(s.workshops.approved ?? 0)} />
              <Stat label="Customers" value={String(s.users.customer ?? 0)} />
              <Stat label="Open requests" value={String(s.open_requests)} />
              <Stat label="Quotes sent" value={String(s.quotes_total)} />
              <Stat label="Jobs booked" value={String(s.jobs_booked)} />
            </Row>
            <P muted style={{ fontSize: 13, color: s.analyzer.available ? t.success : t.warning }}>
              AI analyzer: {s.analyzer.available ? `running (${s.analyzer.model_version})` : `not available${s.analyzer.error ? ` - ${s.analyzer.error}` : ''}`}
            </P>
          </Card>
        )}
        <H2>Waiting for verification ({data?.pending.length ?? 0})</H2>
      </>}
      ListEmptyComponent={<Empty icon="checkmark-done-outline" text="No workshops waiting. You're all caught up." />}
      renderItem={({ item }) => <AdminWorkshopRow w={item} />}
    />
  );
}
