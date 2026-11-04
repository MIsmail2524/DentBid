import { useRouter } from 'expo-router';
import { View } from 'react-native';

import type { AdminWorkshop, VerificationStatus } from '../lib/types';
import { Theme, useTheme } from './theme';
import { Badge, Card, H2, P, Row } from './ui';

export const verificationColor = (t: Theme, s: VerificationStatus) =>
  ({ pending: t.warning, approved: t.success, rejected: t.danger, suspended: t.danger })[s];

export function AdminWorkshopRow({ w }: { w: AdminWorkshop }) {
  const t = useTheme();
  const router = useRouter();
  return (
    <Card onPress={() => router.push({ pathname: '/review/[id]', params: { id: String(w.id) } })}>
      <Row style={{ justifyContent: 'space-between' }}>
        <View style={{ flex: 1 }}>
          <H2 style={{ fontSize: 16 }}>{w.name}</H2>
          <P muted style={{ fontSize: 13 }}>{w.owner_name} · {w.owner_email}</P>
        </View>
        <Badge label={w.verification_status} color={verificationColor(t, w.verification_status)} />
      </Row>
      <P muted style={{ fontSize: 13 }}>
        {[w.city, w.phone, `${w.document_count} document(s)`, `since ${new Date(w.created_at).toLocaleDateString()}`]
          .filter(Boolean).join(' · ')}
      </P>
    </Card>
  );
}
