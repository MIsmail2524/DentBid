import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Text, View } from 'react-native';

import { LanguagePicker } from '../components/LanguagePicker';
import { useTheme } from '../components/theme';
import { Button, Card, H1, P, Row, Screen } from '../components/ui';
import { useLocale } from '../i18n';

export default function Welcome() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const router = useRouter();
  return (
    <Screen style={{ paddingTop: 64, gap: 20 }}>
      <View style={{ alignItems: 'center', gap: 12 }}>
        <View style={{ width: 84, height: 84, borderRadius: 24, backgroundColor: t.primary, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="car-sport" size={48} color="#fff" />
        </View>
        <H1>{tr('appName')}</H1>
        <P muted style={{ textAlign: 'center' }}>{tr('tagline')}</P>
      </View>

      <Card onPress={() => router.push({ pathname: '/register', params: { role: 'customer' } })}>
        <Row>
          <Ionicons name="camera" size={28} color={t.primary} />
          <View style={{ flex: 1 }}>
            <Text style={{ color: t.text, fontSize: 18, fontWeight: '700' }}>{tr('i_am_customer')}</Text>
            <P muted>{tr('i_am_customer_sub')}</P>
          </View>
        </Row>
      </Card>
      <Card onPress={() => router.push({ pathname: '/register', params: { role: 'workshop' } })}>
        <Row>
          <Ionicons name="construct" size={28} color={t.accent} />
          <View style={{ flex: 1 }}>
            <Text style={{ color: t.text, fontSize: 18, fontWeight: '700' }}>{tr('i_am_workshop')}</Text>
            <P muted>{tr('i_am_workshop_sub')}</P>
          </View>
        </Row>
      </Card>

      <Button title={tr('have_account')} variant="ghost" onPress={() => router.push('/login')} />
      <LanguagePicker />
    </Screen>
  );
}
