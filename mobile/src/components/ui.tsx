import { Ionicons } from '@expo/vector-icons';
import { ReactNode } from 'react';
import {
  ActivityIndicator, Pressable, ScrollView, StyleProp, StyleSheet, Text, TextInput, TextInputProps,
  TextStyle, View, ViewStyle,
} from 'react-native';

import { useLocale } from '../i18n';
import { ApiError } from '../lib/api';
import { radius, severityColor, space, useTheme } from './theme';

export function Screen({ children, scroll = true, style }: { children: ReactNode; scroll?: boolean; style?: StyleProp<ViewStyle> }) {
  const t = useTheme();
  const inner = <View style={[{ padding: space(4), gap: space(3), maxWidth: 760, width: '100%', alignSelf: 'center' }, style]}>{children}</View>;
  if (!scroll) return <View style={{ flex: 1, backgroundColor: t.bg }}>{inner}</View>;
  return (
    <ScrollView style={{ flex: 1, backgroundColor: t.bg }} contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled">
      {inner}
    </ScrollView>
  );
}

export function H1({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  const t = useTheme();
  return <Text style={[{ fontSize: 26, fontWeight: '800', color: t.text }, style]}>{children}</Text>;
}

export function H2({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  const t = useTheme();
  return <Text style={[{ fontSize: 18, fontWeight: '700', color: t.text }, style]}>{children}</Text>;
}

export function P({ children, muted, style, numberOfLines }: { children: ReactNode; muted?: boolean; style?: StyleProp<TextStyle>; numberOfLines?: number }) {
  const t = useTheme();
  return <Text numberOfLines={numberOfLines} style={[{ fontSize: 15, color: muted ? t.muted : t.text, lineHeight: 21 }, style]}>{children}</Text>;
}

export function Card({ children, style, onPress }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void }) {
  const t = useTheme();
  const s = [{ backgroundColor: t.card, borderRadius: radius, padding: space(4), gap: space(2), borderWidth: StyleSheet.hairlineWidth, borderColor: t.border }, style];
  if (onPress) {
    return <Pressable onPress={onPress} style={({ pressed }) => [s, pressed && { opacity: 0.85 }]}>{children}</Pressable>;
  }
  return <View style={s}>{children}</View>;
}

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'accent';

export function Button({ title, onPress, variant = 'primary', loading, disabled, icon, style }: {
  title: string; onPress: () => void; variant?: Variant; loading?: boolean; disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap; style?: StyleProp<ViewStyle>;
}) {
  const t = useTheme();
  const bg = { primary: t.primary, accent: t.accent, danger: t.danger, secondary: t.chip, ghost: 'transparent' }[variant];
  const fg = variant === 'secondary' || variant === 'ghost' ? t.primary : t.primaryText;
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [{
        backgroundColor: bg, borderRadius: radius, paddingVertical: 14, paddingHorizontal: 18,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
        opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
      }, style]}>
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={18} color={fg} /> : null}
      <Text style={{ color: fg, fontWeight: '700', fontSize: 16 }}>{title}</Text>
    </Pressable>
  );
}

export function Field({ label, hint, error, ...props }: TextInputProps & { label: string; hint?: string; error?: string }) {
  const t = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ color: t.text, fontWeight: '600' }}>{label}</Text>
      <TextInput
        placeholderTextColor={t.muted}
        {...props}
        style={[{
          backgroundColor: t.inputBg, borderColor: error ? t.danger : t.border, borderWidth: 1, borderRadius: radius,
          paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: t.text,
        }, props.multiline && { minHeight: 90, textAlignVertical: 'top' }, props.style]}
      />
      {error ? <Text style={{ color: t.danger }}>{error}</Text> : hint ? <Text style={{ color: t.muted, fontSize: 13 }}>{hint}</Text> : null}
    </View>
  );
}

export function Chip({ label, active, onPress, color }: { label: string; active?: boolean; onPress?: () => void; color?: string }) {
  const t = useTheme();
  const c = color ?? t.primary;
  return (
    <Pressable onPress={onPress} disabled={!onPress}
      style={{ paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, backgroundColor: active ? c : t.chip, borderWidth: 1, borderColor: active ? c : t.border }}>
      <Text style={{ color: active ? '#fff' : t.text, fontWeight: '600', fontSize: 13 }}>{label}</Text>
    </Pressable>
  );
}

export function Row({ children, style, wrap }: { children: ReactNode; style?: StyleProp<ViewStyle>; wrap?: boolean }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 8 }, wrap && { flexWrap: 'wrap' }, style]}>{children}</View>;
}

export function Badge({ label, color }: { label: string; color: string }) {
  return (
    <View style={{ backgroundColor: color + '22', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' }}>
      <Text style={{ color, fontWeight: '700', fontSize: 12 }}>{label}</Text>
    </View>
  );
}

export function SeverityBadge({ severity, score }: { severity?: string | null; score?: number | null }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  if (!severity) return null;
  const key = `sev_${severity}` as const;
  const label = tr(key as Parameters<typeof tr>[0]) + (score != null && severity !== 'none' ? ` · ${Math.round(score)}` : '');
  return <Badge label={label} color={severityColor(t, severity)} />;
}

export function Loading() {
  const t = useTheme();
  return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40, backgroundColor: t.bg }}><ActivityIndicator size="large" color={t.primary} /></View>;
}

export function Empty({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const t = useTheme();
  return (
    <View style={{ alignItems: 'center', padding: 32, gap: 12 }}>
      <Ionicons name={icon} size={48} color={t.muted} />
      <P muted style={{ textAlign: 'center' }}>{text}</P>
    </View>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  const t = useTheme();
  const { t: tr } = useLocale();
  if (!error) return null;
  const msg = error instanceof ApiError ? (error.status === 0 ? tr('error_network') : error.message) : tr('error_generic');
  return <Text style={{ color: t.danger }}>{msg}</Text>;
}

export function Stat({ label, value }: { label: string; value: string }) {
  const t = useTheme();
  return (
    <View style={{ flexGrow: 1, flexBasis: '45%', backgroundColor: t.chip, borderRadius: 10, padding: 10 }}>
      <Text style={{ color: t.muted, fontSize: 12 }}>{label}</Text>
      <Text style={{ color: t.text, fontWeight: '700', fontSize: 15 }}>{value}</Text>
    </View>
  );
}
