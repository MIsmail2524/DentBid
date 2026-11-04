import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';

import { Button, Chip, ErrorText, Field, Row, Screen } from '../components/ui';
import { useLocale } from '../i18n';
import { useAuth } from '../lib/auth';

export default function Register() {
  const { t: tr, country, language } = useLocale();
  const { register } = useAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ role?: string }>();
  const [role, setRole] = useState<'customer' | 'workshop'>(params.role === 'workshop' ? 'workshop' : 'customer');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const u = await register({ name: name.trim(), email: email.trim(), password, phone: phone.trim() || undefined,
        role, country_code: country, language });
      router.replace(u.role === 'workshop' ? '/workshop-setup' : '/');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Stack.Screen options={{ title: tr('register') }} />
      <Row wrap>
        <Chip label={tr('i_am_customer')} active={role === 'customer'} onPress={() => setRole('customer')} />
        <Chip label={tr('i_am_workshop')} active={role === 'workshop'} onPress={() => setRole('workshop')} />
      </Row>
      <Field label={tr('name')} value={name} onChangeText={setName} autoComplete="name" />
      <Field label={tr('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label={tr('phone')} value={phone} onChangeText={setPhone} keyboardType="phone-pad" autoComplete="tel" />
      <Field label={tr('password')} hint={tr('password_hint')} value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" />
      <ErrorText error={error} />
      <Button title={tr('register')} onPress={submit} loading={busy} disabled={name.length < 2 || !email || password.length < 8} />
      <Button title={tr('have_account')} variant="ghost" onPress={() => router.replace('/login')} />
    </Screen>
  );
}
