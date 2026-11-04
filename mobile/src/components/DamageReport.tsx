import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { ActivityIndicator, Image, Pressable, ScrollView, Text, View } from 'react-native';

import { TKey, useLocale } from '../i18n';
import type { Damage, DamageRequest, Photo } from '../lib/types';
import { severityColor, useTheme } from './theme';
import { Badge, Card, Chip, H2, P, Row, SeverityBadge, Stat } from './ui';

function depthLabel(d: number | null): TKey | null {
  if (d == null) return null;
  return d < 0.35 ? 'depth_shallow' : d < 0.65 ? 'depth_medium' : 'depth_deep';
}

export function PhotoViewer({ photos }: { photos: Photo[] }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  const [index, setIndex] = useState(0);
  const [marked, setMarked] = useState(true);
  const photo = photos[index];
  if (!photo) return null;
  const hasMarked = !!photo.annotated_url;
  const uri = marked && hasMarked ? photo.annotated_url! : photo.url;
  const ratio = photo.width && photo.height ? photo.width / photo.height : 4 / 3;
  return (
    <View style={{ gap: 8 }}>
      <Image source={{ uri }} style={{ width: '100%', aspectRatio: ratio, borderRadius: 12, backgroundColor: t.chip }}
        resizeMode="contain" accessibilityLabel="damage photo" />
      <Row wrap>
        {hasMarked && (
          <>
            <Chip label={tr('show_marked')} active={marked} onPress={() => setMarked(true)} />
            <Chip label={tr('show_original')} active={!marked} onPress={() => setMarked(false)} />
          </>
        )}
      </Row>
      {photos.length > 1 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
          {photos.map((p, i) => (
            <Pressable key={p.id} onPress={() => setIndex(i)} accessibilityRole="button"
              style={{ borderWidth: 2, borderColor: i === index ? t.primary : 'transparent', borderRadius: 10 }}>
              <Image source={{ uri: p.annotated_url ?? p.url }} style={{ width: 72, height: 54, borderRadius: 8 }} />
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

function DamageItem({ d }: { d: Damage }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  const m = d.measurements;
  const stats: [string, string][] = [];
  if ((d.type === 'scratch' || d.type === 'crack') && m.length_cm != null) {
    stats.push([tr('length'), `${m.length_cm.toFixed(0)} cm`]);
  } else if (m.width_cm != null && m.height_cm != null) {
    stats.push([tr('size'), `${m.width_cm.toFixed(0)} × ${m.height_cm.toFixed(0)} cm`]);
  }
  if (m.area_cm2 != null) stats.push([tr('area'), `${m.area_cm2.toFixed(0)} cm²`]);
  const dl = depthLabel(m.depth_index);
  if (dl) stats.push([tr('depth'), tr(dl)]);
  if (m.paint_layer) stats.push([tr('paint_layer'), tr(`layer_${m.paint_layer}` as TKey)]);
  stats.push([tr('confidence'), `${Math.round(d.confidence * 100)}%`]);

  return (
    <View style={{ gap: 8, paddingVertical: 10, borderTopWidth: 1, borderTopColor: t.border }}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Row>
          <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: severityColor(t, d.severity) }} />
          <Text style={{ color: t.text, fontWeight: '700', fontSize: 16 }}>
            #{d.id} {tr(`dmg_${d.type}` as TKey)}{d.part_label ? ` · ${d.part_label}` : ''}
          </Text>
        </Row>
        <SeverityBadge severity={d.severity} score={d.severity_score} />
      </Row>
      <Row wrap>{stats.map(([k, v]) => <Stat key={k} label={k} value={v} />)}</Row>
      <Row style={{ alignItems: 'flex-start' }}>
        <Ionicons name="construct-outline" size={16} color={t.muted} />
        <P muted style={{ flex: 1, fontSize: 14 }}>{tr('suggested_repair')}: {d.repair_notes} ({d.labor_hours[0]}-{d.labor_hours[1]} h)</P>
      </Row>
    </View>
  );
}

export function DamageReport({ req }: { req: DamageRequest }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  const a = req.analysis;

  if (req.status === 'analyzing' || !a) {
    return (
      <Card>
        <Row><ActivityIndicator color={t.primary} /><P>{tr('analysing_wait')}</P></Row>
      </Card>
    );
  }
  if (a.status === 'unavailable') {
    return <Card><Row><Ionicons name="information-circle-outline" size={20} color={t.muted} /><P muted style={{ flex: 1 }}>{tr('ai_unavailable')}</P></Row></Card>;
  }

  const damages = req.photos.flatMap((p) => p.analysis?.damages ?? []);
  const issues = Array.from(new Set(req.photos.flatMap((p) => p.analysis?.quality?.issues ?? [])));

  return (
    <Card>
      <Row style={{ justifyContent: 'space-between' }}>
        <H2>{tr('ai_report')}</H2>
        <SeverityBadge severity={a.overall_severity} score={a.overall_score} />
      </Row>
      {a.summary ? <P>{a.summary}</P> : null}
      {a.labor_hours && damages.length > 0 && (
        <P muted>{tr('labour_estimate', { a: a.labor_hours[0], b: a.labor_hours[1] })}</P>
      )}
      {issues.length > 0 && (
        <Row style={{ backgroundColor: t.warning + '22', padding: 10, borderRadius: 10 }}>
          <Ionicons name="camera-outline" size={18} color={t.warning} />
          <P style={{ flex: 1, fontSize: 14 }}>
            {tr('quality_warning', { issues: issues.map((i) => tr(`issue_${i}` as TKey)).join(', ') })}
          </P>
        </Row>
      )}
      {a.parts && a.parts.length > 0 && (
        <View style={{ gap: 6 }}>
          <Text style={{ color: t.muted, fontWeight: '600' }}>{tr('parts_affected')}</Text>
          {a.parts.map((p) => (
            <Row key={p.part} style={{ justifyContent: 'space-between' }}>
              <P style={{ flex: 1 }}>{p.part_label} · {p.damage_types.map((d) => tr(`dmg_${d}` as TKey)).join(', ')}</P>
              <Badge label={tr(`rec_${p.recommendation}` as TKey)} color={severityColor(t, p.severity)} />
            </Row>
          ))}
        </View>
      )}
      {damages.length > 0 && (
        <View>
          <Text style={{ color: t.muted, fontWeight: '600', marginBottom: 4 }}>{tr('damages_found')}</Text>
          {damages.map((d, i) => <DamageItem key={`${i}-${d.id}`} d={d} />)}
        </View>
      )}
    </Card>
  );
}
