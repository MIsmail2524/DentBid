import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, RefreshControl, ScrollView, Text, View } from 'react-native';

import { DamageReport, PhotoViewer } from '../../components/DamageReport';
import { QuoteCard, confirm } from '../../components/QuoteCard';
import { QuoteForm } from '../../components/QuoteForm';
import { StatusBadge } from '../../components/RequestCardView';
import { useTheme } from '../../components/theme';
import { Badge, Button, Card, Chip, Empty, ErrorText, Field, H2, Loading, P, Row } from '../../components/ui';
import { TKey, useLocale } from '../../i18n';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { useRealtime } from '../../lib/realtime';
import type { DamageRequest, Quote } from '../../lib/types';
import { useLoader } from '../../lib/useLoader';

function hoursLeft(iso: string) {
  return Math.max(0, Math.round((new Date(iso).getTime() - Date.now()) / 3600000));
}

function CustomerPanel({ req, quotes, reload }: { req: DamageRequest; quotes: Quote[]; reload: () => void }) {
  const { t: tr, money } = useLocale();
  const router = useRouter();
  const [offerOpen, setOfferOpen] = useState(false);
  const [offer, setOffer] = useState(req.customer_offer ? String(Number(req.customer_offer)) : '');
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const visible = quotes.filter((q) => q.status !== 'rejected' || req.accepted_quote_id === q.id);
  const accepted = quotes.find((q) => q.id === req.accepted_quote_id);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setError(e);
    }
  };

  return (
    <View style={{ gap: 12 }}>
      {accepted?.workshop && <H2>{tr('booked_with', { name: accepted.workshop.name })}</H2>}
      {req.status === 'open' && (
        <Card>
          <Row style={{ justifyContent: 'space-between' }}>
            <P>{req.customer_offer ? tr('my_offer', { amount: money(req.customer_offer, req.currency) }) : tr('your_offer')}</P>
            <Button title={tr('update_offer')} variant="ghost" onPress={() => setOfferOpen((v) => !v)} />
          </Row>
          {offerOpen && (
            <Row style={{ alignItems: 'flex-end' }}>
              <View style={{ flex: 1 }}><Field label={req.currency} keyboardType="numeric" value={offer} onChangeText={setOffer} /></View>
              <Button title={tr('save')} disabled={!Number(offer)}
                onPress={() => act(async () => { await api.updateOffer(req.id, Number(offer)); setOfferOpen(false); })} />
            </Row>
          )}
          <P muted style={{ fontSize: 13 }}>{tr('expires_in', { h: hoursLeft(req.expires_at) })}</P>
        </Card>
      )}

      <H2>{tr('quotes')} ({visible.length})</H2>
      {visible.length === 0 && req.status === 'open' && <Empty icon="time-outline" text={tr('no_quotes_yet')} />}
      {visible.map((q) => <QuoteCard key={q.id} quote={q} req={req} onChange={reload} />)}

      {req.status === 'completed' && !reviewed && (
        <Card>
          <H2>{tr('rate_workshop')}</H2>
          <Row>{[1, 2, 3, 4, 5].map((n) => <Chip key={n} label={'★'.repeat(n)} active={rating === n} onPress={() => setRating(n)} />)}</Row>
          <Field label={tr('notes')} value={comment} onChangeText={setComment} multiline />
          <Button title={tr('send')} disabled={!rating}
            onPress={() => act(async () => { await api.review(req.id, rating, comment || undefined); setReviewed(true); })} />
        </Card>
      )}
      {reviewed && <P>{tr('thanks_review')}</P>}
      <ErrorText error={error} />
      {['analyzing', 'open', 'booked'].includes(req.status) && (
        <Button title={tr('cancel_request')} variant="ghost"
          onPress={() => confirm(tr('confirm_cancel'), () => act(async () => { await api.cancelRequest(req.id); router.back(); }))} />
      )}
    </View>
  );
}

function WorkshopPanel({ req, reload }: { req: DamageRequest; reload: () => void }) {
  const t = useTheme();
  const { t: tr, money } = useLocale();
  const router = useRouter();
  const [error, setError] = useState<unknown>(null);
  const q = req.my_quote;
  const bookedWithMe = q && req.accepted_quote_id === q.id;

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setError(e);
    }
  };

  return (
    <View style={{ gap: 12 }}>
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <H2>{tr('customer')}: {req.customer_name}</H2>
          {req.distance_km != null && <Badge label={tr('km', { n: req.distance_km })} color={t.primary} />}
        </Row>
        {req.description ? <P>{req.description}</P> : null}
        {bookedWithMe && req.customer_phone && (
          <Row wrap>
            <Button title={tr('call')} icon="call" variant="secondary" onPress={() => Linking.openURL(`tel:${req.customer_phone}`)} />
            <Button title={tr('directions')} icon="navigate" variant="secondary"
              onPress={() => Linking.openURL(`https://www.google.com/maps/dir/?api=1&destination=${req.lat},${req.lng}`)} />
          </Row>
        )}
      </Card>

      {q && (
        <Card>
          <Row style={{ justifyContent: 'space-between' }}>
            <H2>{tr('your_quote')}: {money(q.amount, q.currency)}</H2>
            <Badge label={tr(`quote_${q.status}` as TKey)} color={q.status === 'accepted' ? t.success : t.accent} />
          </Row>
          {q.status === 'countered' && q.counter_amount && (
            <>
              <P style={{ color: t.accent, fontWeight: '600' }}>{tr('counter_sent', { amount: money(q.counter_amount, q.currency) })}</P>
              <Button title={tr('accept_counter', { amount: money(q.counter_amount, q.currency) })} variant="accent"
                onPress={() => act(() => api.acceptCounter(q.id))} />
            </>
          )}
          <Row wrap>
            {['pending', 'countered', 'accepted'].includes(q.status) && (
              <Button title={tr('chat')} icon="chatbubbles-outline" variant="secondary"
                onPress={() => router.push({ pathname: '/chat/[quoteId]', params: { quoteId: String(q.id), title: req.customer_name ?? '' } })} />
            )}
            {['pending', 'countered'].includes(q.status) && (
              <Button title={tr('withdraw')} variant="ghost" onPress={() => act(() => api.withdrawQuote(q.id))} />
            )}
          </Row>
          {bookedWithMe && req.status === 'booked' && (
            <Button title={tr('start_job')} icon="play" onPress={() => act(() => api.setJobStatus(req.id, 'in_progress'))} />
          )}
          {bookedWithMe && (req.status === 'booked' || req.status === 'in_progress') && (
            <Button title={tr('complete_job')} icon="checkmark-done" variant="accent"
              onPress={() => act(() => api.setJobStatus(req.id, 'completed'))} />
          )}
        </Card>
      )}
      <ErrorText error={error} />
      {req.status === 'open' && (!q || q.status === 'pending' || q.status === 'countered') && (
        <QuoteForm key={q?.updated_at ?? 'new'} req={req} onSaved={reload} />
      )}
    </View>
  );
}

export default function RequestDetail() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const { user } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();
  const rid = Number(id);
  const isOwner = user?.role !== 'workshop';
  const { data, error, refreshing, reload } = useLoader(async () => {
    const [req, quotes] = await Promise.all([api.getRequest(rid), isOwner ? api.quotes(rid) : Promise.resolve([] as Quote[])]);
    return { req, quotes };
  });

  useRealtime((e) => {
    if (e.request_id === rid && e.type !== 'message.new' && e.type !== 'message.push') reload();
  });

  // fallback polling while the AI report is being prepared
  useEffect(() => {
    if (data?.req.status !== 'analyzing') return;
    const h = setInterval(reload, 3000);
    return () => clearInterval(h);
  }, [data?.req.status, reload]);

  if (!data) return error ? <View style={{ padding: 16 }}><ErrorText error={error} /></View> : <Loading />;
  const { req, quotes } = data;
  const title = [req.car_year, req.car_make, req.car_model].filter(Boolean).join(' ') || tr('appName');

  return (
    <ScrollView style={{ backgroundColor: t.bg }} contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={{ padding: 16, gap: 12, maxWidth: 760, width: '100%', alignSelf: 'center' }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={reload} />}>
      <Stack.Screen options={{ title }} />
      <Row wrap>
        <StatusBadge status={req.status} />
        {req.car_color ? <Text style={{ color: t.muted }}>{req.car_color}</Text> : null}
        {req.city ? <Text style={{ color: t.muted }}>· {req.city}</Text> : null}
      </Row>
      <PhotoViewer photos={req.photos} />
      <DamageReport req={req} />
      {isOwner ? <CustomerPanel req={req} quotes={quotes} reload={reload} /> : <WorkshopPanel req={req} reload={reload} />}
    </ScrollView>
  );
}
