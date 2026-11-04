import { Redirect } from 'expo-router';

import { Loading } from '../components/ui';
import { useAuth } from '../lib/auth';

export default function Index() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Redirect href="/welcome" />;
  if (user.role === 'admin') return <Redirect href="/admin" />;
  if (user.role === 'workshop') return <Redirect href={user.has_workshop ? '/workshop' : '/workshop-setup'} />;
  return <Redirect href="/customer" />;
}
