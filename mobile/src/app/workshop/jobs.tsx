import { useRouter } from 'expo-router';
import { FlatList, RefreshControl } from 'react-native';

import { RequestCardView } from '../../components/RequestCardView';
import { useTheme } from '../../components/theme';
import { Empty, ErrorText, Loading } from '../../components/ui';
import { useLocale } from '../../i18n';
import { api } from '../../lib/api';
import { useRealtime } from '../../lib/realtime';
import { useLoader } from '../../lib/useLoader';

export default function Jobs() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const router = useRouter();
  const { data, error, refreshing, reload } = useLoader(api.myJobs);
  useRealtime((e) => {
    if (e.type.startsWith('quote.') || e.type.startsWith('request.')) reload();
  });
  if (!data && !error) return <Loading />;
  return (
    <FlatList
      style={{ backgroundColor: t.bg }}
      contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 760, width: '100%', alignSelf: 'center' }}
      data={data ?? []}
      keyExtractor={(r) => String(r.id)}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}
      ListHeaderComponent={<ErrorText error={error} />}
      ListEmptyComponent={<Empty icon="pricetags-outline" text={tr('quotes_empty')} />}
      renderItem={({ item }) => (
        <RequestCardView card={item} workshop
          onPress={() => router.push({ pathname: '/request/[id]', params: { id: String(item.id) } })} />
      )}
    />
  );
}
