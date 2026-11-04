import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Image, Platform, Pressable, View } from 'react-native';

import { useTheme } from '../../components/theme';
import { Button, Card, Chip, ErrorText, Field, H2, P, Row, Screen } from '../../components/ui';
import { useLocale } from '../../i18n';
import { api } from '../../lib/api';

const MAX_PHOTOS = 8;
const RADII = [10, 25, 50];
type Asset = ImagePicker.ImagePickerAsset;

export default function NewRequest() {
  const t = useTheme();
  const { t: tr, place, locate, locationDenied, currency, country } = useLocale();
  const router = useRouter();
  const [photos, setPhotos] = useState<Asset[]>([]);
  const [make, setMake] = useState('');
  const [model, setModel] = useState('');
  const [year, setYear] = useState('');
  const [color, setColor] = useState('');
  const [description, setDescription] = useState('');
  const [offer, setOffer] = useState('');
  const [radius, setRadius] = useState(25);
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const add = (assets: Asset[]) => setPhotos((prev) => [...prev, ...assets].slice(0, MAX_PHOTOS));

  const fromCamera = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return;
    const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.85 });
    if (!r.canceled) add(r.assets);
  };

  const fromGallery = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'], allowsMultipleSelection: true, selectionLimit: MAX_PHOTOS - photos.length, quality: 0.85,
    });
    if (!r.canceled) add(r.assets);
  };

  const refreshLocation = async () => {
    setLocating(true);
    await locate();
    setLocating(false);
  };

  const submit = async () => {
    setFormError(null);
    if (!photos.length) return setFormError(tr('need_photo'));
    const p = place ?? (await locate());
    if (!p) return setFormError(tr('location_denied'));
    setBusy(true);
    setError(null);
    try {
      const req = await api.createRequest({
        photos: photos.map((a) => ({ uri: a.uri, mimeType: a.mimeType, fileName: a.fileName, file: (a as Asset & { file?: File }).file })),
        lat: p.lat, lng: p.lng, city: p.city, country_code: p.country ?? country,
        car_make: make.trim(), car_model: model.trim(), car_year: year.trim(), car_color: color.trim(),
        description: description.trim(), customer_offer: offer.trim(), search_radius_km: radius,
      });
      setPhotos([]);
      setOffer('');
      setDescription('');
      router.push({ pathname: '/request/[id]', params: { id: String(req.id) } });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Card>
        <H2>{tr('new_title')}</H2>
        <P muted style={{ fontSize: 14 }}>{tr('new_photos_hint')}</P>
        <Row wrap>
          {photos.map((a, i) => (
            <View key={`${a.uri}-${i}`}>
              <Image source={{ uri: a.uri }} style={{ width: 96, height: 96, borderRadius: 10 }} />
              <Pressable onPress={() => setPhotos((ps) => ps.filter((_, j) => j !== i))} accessibilityLabel="remove photo"
                style={{ position: 'absolute', top: 4, end: 4, backgroundColor: '#0009', borderRadius: 12 }}>
                <Ionicons name="close" size={20} color="#fff" />
              </Pressable>
            </View>
          ))}
        </Row>
        {photos.length < MAX_PHOTOS && (
          <Row>
            {Platform.OS !== 'web' && <Button title={tr('take_photo')} icon="camera" onPress={fromCamera} style={{ flex: 1 }} />}
            <Button title={tr('pick_photos')} icon="images" variant="secondary" onPress={fromGallery} style={{ flex: 1 }} />
          </Row>
        )}
      </Card>

      <Card>
        <Row>
          <View style={{ flex: 1 }}><Field label={tr('car_make')} value={make} onChangeText={setMake} /></View>
          <View style={{ flex: 1 }}><Field label={tr('car_model')} value={model} onChangeText={setModel} /></View>
        </Row>
        <Row>
          <View style={{ flex: 1 }}><Field label={tr('car_year')} value={year} onChangeText={setYear} keyboardType="number-pad" maxLength={4} /></View>
          <View style={{ flex: 1 }}><Field label={tr('car_color')} value={color} onChangeText={setColor} /></View>
        </Row>
        <Field label={tr('description')} value={description} onChangeText={setDescription} multiline />
        <Field label={`${tr('your_offer')} (${currency})`} hint={tr('your_offer_hint')} value={offer}
          onChangeText={setOffer} keyboardType="numeric" />
      </Card>

      <Card>
        <H2>{tr('location')}</H2>
        <Row>
          {locating ? <ActivityIndicator color={t.primary} /> : <Ionicons name="location" size={18} color={place ? t.success : t.muted} />}
          <P style={{ flex: 1 }}>
            {place ? `${place.city ?? ''} (${place.lat.toFixed(3)}, ${place.lng.toFixed(3)})`
              : locationDenied ? tr('location_denied') : tr('location_detecting')}
          </P>
          <Button title="" icon="refresh" variant="ghost" onPress={refreshLocation} />
        </Row>
        <P muted>{tr('radius')}</P>
        <Row>{RADII.map((r) => <Chip key={r} label={tr('km', { n: r })} active={radius === r} onPress={() => setRadius(r)} />)}</Row>
      </Card>

      {formError && <P style={{ color: t.danger }}>{formError}</P>}
      <ErrorText error={error} />
      <Button title={busy ? tr('uploading') : tr('submit_request')} icon="sparkles" variant="accent" loading={busy} onPress={submit} />
    </Screen>
  );
}
