import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import { TKey, useLocale } from '../i18n';
import { api } from '../lib/api';
import type { VerificationStatus, WorkshopDocument } from '../lib/types';
import { AuthImage } from './AuthImage';
import { useTheme } from './theme';
import { Button, Card, Chip, ErrorText, H2, P, Row } from './ui';

const KINDS: WorkshopDocument['kind'][] = ['shop_front', 'trade_license', 'owner_id', 'other'];

export function VerificationBanner({ status, reason }: { status: VerificationStatus | null; reason?: string | null }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  const router = useRouter();
  if (!status || status === 'approved') return null;
  const color = status === 'pending' ? t.warning : t.danger;
  const title = status === 'pending' ? tr('verify_pending_title')
    : status === 'rejected' ? tr('verify_rejected_title') : tr('verify_suspended_title');
  return (
    <Card style={{ borderColor: color, borderWidth: 2 }}>
      <Row>
        <Ionicons name={status === 'pending' ? 'time-outline' : 'alert-circle-outline'} size={22} color={color} />
        <H2 style={{ flex: 1 }}>{title}</H2>
      </Row>
      {status === 'pending' ? <P>{tr('verify_pending_body')}</P> : null}
      {reason ? <P style={{ fontWeight: '600' }}>{reason}</P> : null}
      {status !== 'suspended' && (
        <Button title={tr('edit_workshop')} variant="secondary" icon="document-attach-outline"
          onPress={() => router.push('/workshop-setup')} />
      )}
    </Card>
  );
}

export function DocumentsCard() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const [docs, setDocs] = useState<WorkshopDocument[]>([]);
  const [kind, setKind] = useState<WorkshopDocument['kind']>('shop_front');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = () => api.myDocuments().then(setDocs).catch(() => undefined);
  useEffect(() => {
    load();
  }, []);

  const upload = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85 });
    if (r.canceled) return;
    const a = r.assets[0] as ImagePicker.ImagePickerAsset & { file?: File };
    setBusy(true);
    setError(null);
    try {
      await api.uploadDocument(kind, { uri: a.uri, mimeType: a.mimeType, fileName: a.fileName, file: a.file });
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.deleteDocument(id);
      await load();
    } catch (e) {
      setError(e);
    }
  };

  return (
    <Card>
      <H2>{tr('documents')}</H2>
      <P muted style={{ fontSize: 13 }}>{tr('documents_hint')}</P>
      <Row wrap>
        {docs.map((d) => (
          <View key={d.id} style={{ gap: 4 }}>
            <AuthImage url={d.url} style={{ width: 110, height: 82, borderRadius: 8 }} />
            <Row style={{ justifyContent: 'space-between' }}>
              <P style={{ fontSize: 12 }}>{tr(`doc_${d.kind}` as TKey)}</P>
              <Pressable onPress={() => remove(d.id)} accessibilityLabel="delete document">
                <Ionicons name="trash-outline" size={16} color={t.danger} />
              </Pressable>
            </Row>
          </View>
        ))}
      </Row>
      <Row wrap>{KINDS.map((k) => <Chip key={k} label={tr(`doc_${k}` as TKey)} active={kind === k} onPress={() => setKind(k)} />)}</Row>
      <ErrorText error={error} />
      <Button title={tr('upload_document')} icon="cloud-upload-outline" variant="secondary" loading={busy} onPress={upload} />
    </Card>
  );
}
