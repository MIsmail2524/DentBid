import { useRouter } from 'expo-router';
import { FlatList, RefreshControl } from 'react-native';

import { RequestCardView } from '../../components/RequestCardView';
import { useTheme } from '../../components/theme';
import { Button, Empty, ErrorText, Loading } from '../../components/ui';
import { useLocale } from '../../i18n';
import { api } from '../../lib/api';
import { useRealtime } from '../../lib/realtime';
import { useLoader } from '../../lib/useLoader';

export default function MyRequests() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const router = useRouter();
  const { data, error, refreshing, reload } = useLoader(api.myRequests);
  useRealtime((e) => {
    if (e.type.startsWith('quote.') || e.type.startsWith('request.') || e.type.startsWith('job.')) reload();
  });

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
        <Button title={tr('tab_new')} icon="camera" variant="accent" onPress={() => router.push('/customer/new')} />
      </>}
      ListEmptyComponent={<Empty icon="car-outline" text={tr('tagline')} />}
      renderItem={({ item }) => (
        <RequestCardView card={item} onPress={() => router.push({ pathname: '/request/[id]', params: { id: String(item.id) } })} />
      )}
    />
  );
}
