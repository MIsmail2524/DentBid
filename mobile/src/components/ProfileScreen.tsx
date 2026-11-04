import { useRouter } from 'expo-router';

import { TKey, useLocale } from '../i18n';
import { useAuth } from '../lib/auth';
import { LanguagePicker } from './LanguagePicker';
import { Button, Card, H2, P, Row, Screen, Stat } from './ui';

export function ProfileScreen() {
  const { t: tr, currency, country, detectedFrom } = useLocale();
  const { user, logout } = useAuth();
  const router = useRouter();
  if (!user) return null;
  const src = (['gps', 'ip', 'accept_language', 'default'].includes(detectedFrom) ? `src_${detectedFrom}` : 'src_default') as TKey;
  return (
    <Screen>
      <Card>
        <H2>{user.name}</H2>
        <P muted>{user.email}{user.phone ? ` · ${user.phone}` : ''}</P>
      </Card>
      <Card>
        <Row wrap>
          <Stat label={tr('country')} value={country} />
          <Stat label={tr('currency')} value={currency} />
        </Row>
        <P muted style={{ fontSize: 13 }}>{tr('detected_by', { source: tr(src) })}</P>
      </Card>
      <Card>
        <H2>{tr('language')}</H2>
        <LanguagePicker />
      </Card>
      {user.role === 'workshop' && (
        <Button title={tr('edit_workshop')} variant="secondary" icon="construct" onPress={() => router.push('/workshop-setup')} />
      )}
      <Button title={tr('logout')} variant="danger" icon="log-out-outline"
        onPress={async () => { await logout(); router.replace('/welcome'); }} />
    </Screen>
  );
}
