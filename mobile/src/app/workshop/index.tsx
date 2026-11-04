import { useRouter } from 'expo-router';
import { useState } from 'react';
import { FlatList, RefreshControl, ScrollView } from 'react-native';

import { RequestCardView } from '../../components/RequestCardView';
import { useTheme } from '../../components/theme';
import { Chip, Empty, ErrorText, Loading, Row } from '../../components/ui';
import { useLocale } from '../../i18n';
import { api } from '../../lib/api';
import { useRealtime } from '../../lib/realtime';
import { useLoader } from '../../lib/useLoader';

const SEVERITIES = ['', 'minor', 'moderate', 'severe'] as const;
const SORTS = ['distance', 'newest', 'severity'] as const;

export default function Feed() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const router = useRouter();
  const [severity, setSeverity] = useState<(typeof SEVERITIES)[number]>('');
  const [sort, setSort] = useState<(typeof SORTS)[number]>('distance');
  const { data, error, refreshing, reload } = useLoader(() => api.feed({ severity, sort }));
  useRealtime((e) => {
    if (e.type.startsWith('request.') || e.type.startsWith('quote.')) reload();
  });

  const change = (fn: () => void) => {
    fn();
    setTimeout(reload, 0);
  };

  if (!data && !error) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 760, width: '100%', alignSelf: 'center' }}
      data={data ?? []}
      keyExtractor={(r) => String(r.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
      ListHeaderComponent={<>
        <ErrorText error={error} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <Row>
            {SEVERITIES.map((s) => (
              <Chip key={s || 'all'} label={s ? tr(`sev_${s}`) : tr('filter_all')} active={severity === s}
                onPress={() => change(() => setSeverity(s))} />
            ))}
            {SORTS.map((s) => (
              <Chip key={s} label={tr(`sort_${s}`)} active={sort === s} color={t.accent} onPress={() => change(() => setSort(s))} />
            ))}
          </Row>
        </ScrollView>
      </>}
      ListEmptyComponent={<Empty icon="map-outline" text={tr('feed_empty')} />}
      renderItem={({ item }) => (
        <RequestCardView card={item} workshop
          onPress={() => router.push({ pathname: '/request/[id]', params: { id: String(item.id) } })} />
      )}
    />
  );
}
