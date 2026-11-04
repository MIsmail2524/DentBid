import { Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, Text, View } from 'react-native';

import { verificationColor } from '../../components/AdminWorkshopRow';
import { AuthImage } from '../../components/AuthImage';
import { useTheme } from '../../components/theme';
import { Badge, Button, Card, ErrorText, Field, H2, Loading, P, Row, Screen, Stat } from '../../components/ui';
import { api } from '../../lib/api';
import { useLoader } from '../../lib/useLoader';

/** Admin review of one workshop: details, documents, approve / reject / suspend. */
export default function ReviewWorkshop() {
  const t = useTheme();
  const { id } = useLocalSearchParams<{ id: string }>();
  const wid = Number(id);
  const { data: w, error, reload } = useLoader(() => api.admin.workshop(wid));
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setActionError(null);
    try {
      await fn();
      setReason('');
      await reload();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(null);
    }
  };

  if (!w) return error ? <Screen><ErrorText error={error} /></Screen> : <Loading />;
  const reasonOk = reason.trim().length >= 3;

  return (
    <Screen>
      <Stack.Screen options={{ title: w.name }} />
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <H2>{w.name}</H2>
          <Badge label={w.verification_status} color={verificationColor(t, w.verification_status)} />
        </Row>
        {w.rejection_reason ? <P style={{ color: t.danger }}>Reason: {w.rejection_reason}</P> : null}
        <Row wrap>
          <Stat label="Owner" value={w.owner_name} />
          <Stat label="Owner email" value={w.owner_email} />
          <Stat label="Shop phone" value={w.phone ?? '-'} />
          <Stat label="Owner phone" value={w.owner_phone ?? '-'} />
          <Stat label="City" value={[w.city, w.country_code].filter(Boolean).join(', ') || '-'} />
          <Stat label="Service radius" value={`${w.service_radius_km} km`} />
          <Stat label="Repairs" value={w.services.join(', ') || 'all'} />
          <Stat label="Owner account" value={w.owner_active ? 'active' : 'disabled'} />
        </Row>
        {w.address ? <P>{w.address}</P> : null}
        {w.about ? <P muted>{w.about}</P> : null}
        <Button title={`Check location on map (${w.lat.toFixed(4)}, ${w.lng.toFixed(4)})`} icon="map-outline" variant="secondary"
          onPress={() => Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${w.lat},${w.lng}`)} />
      </Card>

      <Card>
        <H2>Documents ({w.documents.length})</H2>
        {w.documents.length === 0 && <P muted>No documents uploaded. Ask the workshop for a shop-front photo and licence before approving.</P>}
        <Row wrap>
          {w.documents.map((d) => (
            <View key={d.id} style={{ gap: 4 }}>
              <AuthImage url={d.url} style={{ width: 260, height: 195, borderRadius: 10 }} />
              <Text style={{ color: t.muted }}>{d.kind.replace('_', ' ')}</Text>
            </View>
          ))}
        </Row>
      </Card>

      <Card>
        <H2>Decision</H2>
        <Field label="Reason (required to reject or suspend; the workshop sees it)" value={reason} onChangeText={setReason} multiline />
        <ErrorText error={actionError} />
        <Row wrap>
          {w.verification_status !== 'approved' && (
            <Button title="Approve" icon="checkmark-circle" loading={busy === 'approve'} disabled={!w.owner_active}
              onPress={() => act('approve', () => api.admin.approve(w.id))} />
          )}
          {w.verification_status !== 'rejected' && w.verification_status !== 'approved' && (
            <Button title="Reject" variant="danger" icon="close-circle" loading={busy === 'reject'} disabled={!reasonOk}
              onPress={() => act('reject', () => api.admin.reject(w.id, reason.trim()))} />
          )}
          {w.verification_status === 'approved' && (
            <Button title="Suspend" variant="danger" icon="ban" loading={busy === 'suspend'} disabled={!reasonOk}
              onPress={() => act('suspend', () => api.admin.suspend(w.id, reason.trim()))} />
          )}
        </Row>
        {w.verified_at ? <P muted style={{ fontSize: 13 }}>Verified {new Date(w.verified_at).toLocaleString()}</P> : null}
      </Card>
    </Screen>
  );
}
