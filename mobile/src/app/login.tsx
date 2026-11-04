import { Stack, useRouter } from 'expo-router';
import { useState } from 'react';

import { Button, ErrorText, Field, Screen } from '../components/ui';
import { useLocale } from '../i18n';
import { useAuth } from '../lib/auth';

export default function Login() {
  const { t: tr } = useLocale();
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.replace('/');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Stack.Screen options={{ title: tr('login') }} />
      <Field label={tr('email')} value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" />
      <Field label={tr('password')} value={password} onChangeText={setPassword} secureTextEntry autoComplete="password" onSubmitEditing={submit} />
      <ErrorText error={error} />
      <Button title={tr('login')} onPress={submit} loading={busy} disabled={!email || !password} />
      <Button title={tr('no_account')} variant="ghost" onPress={() => router.replace('/welcome')} />
    </Screen>
  );
}
