import { Image, View } from 'react-native';

import { TKey, useLocale } from '../i18n';
import { absoluteUrl } from '../lib/config';
import type { RequestCard, RequestStatus } from '../lib/types';
import { Theme, useTheme } from './theme';
import { Badge, Card, H2, P, Row, SeverityBadge } from './ui';

export const statusColor = (t: Theme, s: RequestStatus) =>
  ({ analyzing: t.muted, open: t.primary, booked: t.accent, in_progress: t.warning,
     completed: t.success, cancelled: t.muted, expired: t.muted })[s];

export function StatusBadge({ status }: { status: RequestStatus }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  return <Badge label={tr(`status_${status}` as TKey)} color={statusColor(t, status)} />;
}

export function RequestCardView({ card, onPress, workshop }: { card: RequestCard; onPress: () => void; workshop?: boolean }) {
  const t = useTheme();
  const { t: tr, money } = useLocale();
  return (
    <Card onPress={onPress} style={{ flexDirection: 'row', gap: 12 }}>
      {card.thumbnail_url ? (
        <Image source={{ uri: absoluteUrl(card.thumbnail_url) ?? '' }} style={{ width: 92, height: 92, borderRadius: 10, backgroundColor: t.chip }} />
      ) : (
        <View style={{ width: 92, height: 92, borderRadius: 10, backgroundColor: t.chip }} />
      )}
      <View style={{ flex: 1, gap: 4 }}>
        <H2 style={{ fontSize: 16 }}>{card.title}</H2>
        <Row wrap>
          <StatusBadge status={card.status} />
          <SeverityBadge severity={card.overall_severity} score={card.overall_score} />
        </Row>
        <P muted numberOfLines={1} style={{ fontSize: 13 }}>
          {card.damage_types.map((d) => tr(`dmg_${d}` as TKey)).join(', ')}
          {card.distance_km != null ? ` · ${tr('km', { n: card.distance_km })}` : card.city ? ` · ${card.city}` : ''}
        </P>
        <P style={{ fontSize: 13 }}>
          {workshop && card.customer_offer ? tr('customer_offers', { amount: money(card.customer_offer, card.currency) }) + ' · ' : ''}
          {tr('n_quotes', { n: card.quote_count })}
          {card.lowest_quote ? ` · ${tr('lowest', { amount: money(card.lowest_quote, card.currency) })}` : ''}
        </P>
        {workshop && card.my_quote_status && <Badge label={tr(`quote_${card.my_quote_status}` as TKey)} color={t.accent} />}
      </View>
    </Card>
  );
}
