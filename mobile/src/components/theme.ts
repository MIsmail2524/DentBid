import { useColorScheme } from 'react-native';

const light = {
  bg: '#F4F6FA',
  card: '#FFFFFF',
  text: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
  primary: '#0B3D91',
  primaryText: '#FFFFFF',
  accent: '#FF6B2C',
  success: '#16A34A',
  warning: '#D97706',
  danger: '#DC2626',
  chip: '#EEF2FF',
  inputBg: '#FFFFFF',
};

const dark: typeof light = {
  bg: '#0B1220',
  card: '#131C2E',
  text: '#E2E8F0',
  muted: '#94A3B8',
  border: '#24324A',
  primary: '#4F8BFF',
  primaryText: '#FFFFFF',
  accent: '#FF8A50',
  success: '#22C55E',
  warning: '#F59E0B',
  danger: '#F87171',
  chip: '#1E2A44',
  inputBg: '#0F1828',
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? dark : light;
}

export const severityColor = (t: Theme, s?: string | null) =>
  s === 'severe' ? t.danger : s === 'moderate' ? t.warning : s === 'minor' ? t.success : t.muted;

export const radius = 14;
export const space = (n: number) => n * 4;
