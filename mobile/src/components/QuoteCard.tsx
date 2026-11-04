import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, Linking, Platform, Text, View } from 'react-native';

import { TKey, useLocale } from '../i18n';
import { api } from '../lib/api';
import type { DamageRequest, Quote } from '../lib/types';
import { useTheme } from './theme';
import { Badge, Button, Card, ErrorText, Field, H2, P, Row } from './ui';

export function confirm(message: string, onYes: () => void) {
  if (Platform.OS === 'web') {
    if (globalThis.confirm?.(message)) onYes();
    return;
  }
  Alert.alert('DentBid', message, [{ text: 'No', style: 'cancel' }, { text: 'Yes', onPress: onYes }]);
}

export function QuoteCard({ quote, req, onChange }: { quote: Quote; req: DamageRequest; onChange: () => void }) {
  const t = useTheme();
  const { t: tr, money } = useLocale();
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [counterOpen, setCounterOpen] = useState(false);
  const [counter, setCounter] = useState('');
  const w = quote.workshop!;
  const open = req.status === 'open' && (quote.status === 'pending' || quote.status === 'countered');
  const booked = req.accepted_quote_id === quote.id;
  const amount = money(quote.amount, quote.currency);

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      onChange();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card style={booked ? { borderColor: t.accent, borderWidth: 2 } : undefined}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View style={{ flex: 1, gap: 2 }}>
          <Row>
            <H2 style={{ fontSize: 17 }}>{w.name}</H2>
            {w.verified && <Ionicons name="checkmark-circle" size={16} color={t.primary} />}
          </Row>
          <P muted style={{ fontSize: 13 }}>
            ★ {w.rating_avg ? w.rating_avg.toFixed(1) : '-'} ({w.rating_count}) · {tr('jobs_done', { n: w.jobs_completed })}
            {w.distance_km != null ? ` · ${tr('km', { n: w.distance_km })}` : ''}
          </P>
        </View>
        <Text style={{ fontSize: 22, fontWeight: '800', color: t.text }}>{amount}</Text>
      </Row>

      <Row wrap>
        <Badge label={tr(`quote_${quote.status}` as TKey)} color={quote.status === 'accepted' ? t.success : t.muted} />
        <Badge label={tr('ready_in', { n: quote.eta_days })} color={t.primary} />
        {quote.warranty_months > 0 && <Badge label={tr('warranty', { n: quote.warranty_months })} color={t.success} />}
        {quote.includes_parts && <Badge label={tr('parts_included')} color={t.primary} />}
        {quote.pickup_available && <Badge label={tr('pickup')} color={t.accent} />}
      </Row>
      {quote.notes ? <P>{quote.notes}</P> : null}
      {quote.breakdown?.map((b, i) => (
        <Row key={i} style={{ justifyContent: 'space-between' }}>
          <P muted style={{ fontSize: 14 }}>{b.item}</P>
          <P style={{ fontSize: 14 }}>{money(b.amount, quote.currency)}</P>
        </Row>
      ))}
      {quote.status === 'countered' && quote.counter_amount && (
        <P style={{ color: t.accent, fontWeight: '600' }}>{tr('counter_sent', { amount: money(quote.counter_amount, quote.currency) })}</P>
      )}

      {booked && w.phone && (
        <Row wrap>
          <Button title={tr('call')} icon="call" variant="secondary" onPress={() => Linking.openURL(`tel:${w.phone}`)} />
          {w.lat != null && w.lng != null && (
            <Button title={tr('directions')} icon="navigate" variant="secondary"
              onPress={() => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${w.lat},${w.lng}`)} />
          )}
        </Row>
      )}

      {counterOpen && (
        <Row style={{ alignItems: 'flex-end' }}>
          <View style={{ flex: 1 }}>
            <Field label={tr('counter_prompt')} keyboardType="numeric" value={counter} onChangeText={setCounter} />
          </View>
          <Button title={tr('send')} loading={busy === 'counter'} disabled={!Number(counter)}
            onPress={() => run('counter', async () => {
              await api.counterQuote(quote.id, Number(counter));
              setCounterOpen(false);
            })} />
        </Row>
      )}

      <ErrorText error={error} />
      <Row wrap>
        {open && (
          <>
            <Button title={tr('accept')} icon="checkmark" loading={busy === 'accept'}
              onPress={() => confirm(tr('confirm_accept', { amount, name: w.name }),
                () => run('accept', () => api.acceptQuote(quote.id)))} />
            <Button title={tr('counter')} variant="secondary" onPress={() => setCounterOpen((v) => !v)} />
            <Button title={tr('reject')} variant="ghost" loading={busy === 'reject'}
              onPress={() => run('reject', () => api.rejectQuote(quote.id))} />
          </>
        )}
        {(open || booked) && (
          <Button title={tr('chat')} icon="chatbubbles-outline" variant="secondary"
            onPress={() => router.push({ pathname: '/chat/[quoteId]', params: { quoteId: String(quote.id), title: w.name } })} />
        )}
      </Row>
    </Card>
  );
}
