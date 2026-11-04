import { useState } from 'react';
import { Switch, Text, View } from 'react-native';

import { useLocale } from '../i18n';
import { api } from '../lib/api';
import type { DamageRequest } from '../lib/types';
import { useTheme } from './theme';
import { Button, Card, ErrorText, Field, H2, P, Row } from './ui';

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  const t = useTheme();
  return (
    <Row style={{ justifyContent: 'space-between' }}>
      <Text style={{ color: t.text, flex: 1 }}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: t.primary }} />
    </Row>
  );
}

/** Workshop's quote form: create or revise. */
export function QuoteForm({ req, onSaved }: { req: DamageRequest; onSaved: () => void }) {
  const { t: tr, money } = useLocale();
  const q = req.my_quote;
  const [amount, setAmount] = useState(q ? String(Number(q.amount)) : '');
  const [eta, setEta] = useState(String(q?.eta_days ?? 1));
  const [warranty, setWarranty] = useState(String(q?.warranty_months ?? 3));
  const [parts, setParts] = useState(q?.includes_parts ?? true);
  const [pickup, setPickup] = useState(q?.pickup_available ?? false);
  const [notes, setNotes] = useState(q?.notes ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [sent, setSent] = useState(false);

  const submit = async (value: number) => {
    setBusy(true);
    setError(null);
    try {
      await api.submitQuote(req.id, {
        amount: value, eta_days: Number(eta) || 0, warranty_months: Number(warranty) || 0,
        includes_parts: parts, pickup_available: pickup, notes: notes.trim() || undefined,
      });
      setSent(true);
      onSaved();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <H2>{q ? tr('your_quote') : tr('send_quote')}</H2>
      {req.customer_offer && (
        <View style={{ gap: 8 }}>
          <P>{tr('customer_offers', { amount: money(req.customer_offer, req.currency) })}</P>
          <Button title={tr('accept_offer')} variant="accent" loading={busy}
            onPress={() => submit(Number(req.customer_offer))} />
        </View>
      )}
      <Field label={`${tr('quote_amount')} (${req.currency})`} keyboardType="numeric" value={amount} onChangeText={setAmount} />
      <Row>
        <View style={{ flex: 1 }}><Field label={tr('eta_days')} keyboardType="number-pad" value={eta} onChangeText={setEta} /></View>
        <View style={{ flex: 1 }}><Field label={tr('warranty_months')} keyboardType="number-pad" value={warranty} onChangeText={setWarranty} /></View>
      </Row>
      <Toggle label={tr('includes_parts')} value={parts} onChange={setParts} />
      <Toggle label={tr('pickup_available')} value={pickup} onChange={setPickup} />
      <Field label={tr('notes')} multiline value={notes} onChangeText={setNotes} />
      <ErrorText error={error} />
      {sent && !error && <P style={{ fontWeight: '600' }}>{tr('quote_sent')}</P>}
      <Button title={q ? tr('update_quote') : tr('send_quote')} loading={busy} disabled={!Number(amount)}
        onPress={() => submit(Number(amount))} />
    </Card>
  );
}
