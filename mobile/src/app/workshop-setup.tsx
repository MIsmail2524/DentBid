import { Stack, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { useTheme } from '../components/theme';
import { Button, Card, Chip, ErrorText, Field, H2, P, Row, Screen } from '../components/ui';
import { DocumentsCard, VerificationBanner } from '../components/Verification';
import { TKey, useLocale } from '../i18n';
import { api, ApiError } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { DamageType, Workshop } from '../lib/types';

const SERVICES: DamageType[] = ['dent', 'scratch', 'crack', 'glass_shatter', 'lamp_broken', 'tire_flat'];
const RADII = [10, 25, 50, 100];

export default function WorkshopSetup() {
  const t = useTheme();
  const { t: tr, place, locate, country } = useLocale();
  const { user, refresh } = useAuth();
  const router = useRouter();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [about, setAbout] = useState('');
  const [services, setServices] = useState<DamageType[]>(['dent', 'scratch']);
  const [radius, setRadius] = useState(25);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [existing, setExisting] = useState<Workshop | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.myWorkshop().then((w) => {
      setExisting(w);
      setName(w.name); setPhone(w.phone ?? ''); setAddress(w.address ?? ''); setCity(w.city ?? '');
      setAbout(w.about ?? ''); setServices(w.services); setRadius(w.service_radius_km); setCoords({ lat: w.lat, lng: w.lng });
    }).catch((e) => {
      if (!(e instanceof ApiError && e.status === 404)) setError(e);
    });
  }, []);

  useEffect(() => {
    if (!coords && place) {
      setCoords({ lat: place.lat, lng: place.lng });
      if (place.city) setCity((c) => c || place.city!);
    }
  }, [place, coords]);

  const useLocation = async () => {
    const p = await locate();
    if (p) {
      setCoords({ lat: p.lat, lng: p.lng });
      if (p.city) setCity(p.city);
    }
  };

  const toggle = (s: DamageType) => setServices((ss) => (ss.includes(s) ? ss.filter((x) => x !== s) : [...ss, s]));

  const save = async () => {
    if (!coords) return;
    setBusy(true);
    setError(null);
    try {
      await api.saveWorkshop({
        name: name.trim(), phone: phone.trim() || null, address: address.trim() || null, city: city.trim() || null,
        country_code: place?.country ?? country, lat: coords.lat, lng: coords.lng,
        service_radius_km: radius, services, about: about.trim() || null,
      });
      await refresh();
      if (existing) router.replace('/workshop');
      else setExisting(await api.myWorkshop());
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Stack.Screen options={{ title: tr('setup_title') }} />
      <P muted>{tr('setup_sub')}</P>
      {existing && <VerificationBanner status={existing.verification_status} reason={existing.rejection_reason} />}
      <Card>
        <Field label={tr('shop_name')} value={name} onChangeText={setName} />
        <Field label={tr('phone')} value={phone} onChangeText={setPhone} keyboardType="phone-pad" />
        <Field label={tr('address')} value={address} onChangeText={setAddress} />
        <Field label={tr('city')} value={city} onChangeText={setCity} />
        <Field label={tr('about')} value={about} onChangeText={setAbout} multiline />
      </Card>
      <Card>
        <H2>{tr('services')}</H2>
        <Row wrap>{SERVICES.map((s) => <Chip key={s} label={tr(`dmg_${s}` as TKey)} active={services.includes(s)} onPress={() => toggle(s)} />)}</Row>
      </Card>
      <Card>
        <H2>{tr('location')}</H2>
        <P style={{ color: coords ? t.success : t.muted }}>
          {coords ? tr('location_set', { lat: coords.lat.toFixed(4), lng: coords.lng.toFixed(4) }) : tr('location_detecting')}
        </P>
        <Button title={tr('use_my_location')} icon="locate" variant="secondary" onPress={useLocation} />
        <P muted>{tr('service_radius')}</P>
        <Row wrap>{RADII.map((r) => <Chip key={r} label={tr('km', { n: r })} active={radius === r} onPress={() => setRadius(r)} />)}</Row>
      </Card>
      {existing && <DocumentsCard />}
      <ErrorText error={error} />
      <View>
        <Button title={tr('save')} loading={busy} disabled={name.trim().length < 2 || !coords} onPress={save} />
      </View>
    </Screen>
  );
}
