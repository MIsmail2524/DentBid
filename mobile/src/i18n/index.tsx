import { getLocales } from 'expo-localization';
import * as Location from 'expo-location';
import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Platform } from 'react-native';

import { api } from '../lib/api';
import { getItem, setItem } from '../lib/storage';
import ar from './ar';
import en, { Strings } from './en';
import es from './es';
import hi from './hi';
import ur from './ur';

export const LANGUAGES = { en: 'English', ur: 'اردو', ar: 'العربية', hi: 'हिन्दी', es: 'Español' } as const;
export type Lang = keyof typeof LANGUAGES;
const DICTS: Record<Lang, Strings> = { en, ur, ar, hi, es };
const RTL: Lang[] = ['ur', 'ar'];
const STORE_KEY = 'dentbid.locale';

export type TKey = keyof Strings;

export interface Place {
  lat: number;
  lng: number;
  city?: string;
  country?: string;
}

interface LocaleState {
  language: Lang;
  currency: string;
  country: string;
  decimals: number;
  detectedFrom: string;
  manual: boolean;
}

interface LocaleCtx extends LocaleState {
  ready: boolean;
  rtl: boolean;
  place: Place | null;
  locationDenied: boolean;
  t: (key: TKey, vars?: Record<string, string | number>) => string;
  money: (amount: string | number | null | undefined, currency?: string) => string;
  setLanguage: (lang: Lang) => void;
  locate: () => Promise<Place | null>;
}

const Ctx = createContext<LocaleCtx | null>(null);

const isLang = (l: string | null | undefined): l is Lang => !!l && l in DICTS;

function deviceDefaults(): LocaleState {
  const d = getLocales()[0];
  const lang = isLang(d?.languageCode) ? d.languageCode : 'en';
  return {
    language: lang,
    currency: d?.currencyCode ?? 'USD',
    country: d?.regionCode ?? 'US',
    decimals: 2,
    detectedFrom: 'device',
    manual: false,
  };
}

async function currentPlace(): Promise<{ place: Place | null; denied: boolean }> {
  try {
    const perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status !== 'granted') return { place: null, denied: true };
    const pos = (await Location.getLastKnownPositionAsync({ maxAge: 10 * 60 * 1000 }))
      ?? (await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }));
    const place: Place = { lat: pos.coords.latitude, lng: pos.coords.longitude };
    if (Platform.OS !== 'web') {
      try {
        const [addr] = await Location.reverseGeocodeAsync({ latitude: place.lat, longitude: place.lng });
        place.city = addr?.city ?? addr?.subregion ?? addr?.region ?? undefined;
        place.country = addr?.isoCountryCode ?? undefined;
      } catch {
        // geocoder unavailable: keep coordinates only
      }
    }
    return { place, denied: false };
  } catch {
    return { place: null, denied: true };
  }
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LocaleState>(deviceDefaults);
  const [ready, setReady] = useState(false);
  const [place, setPlace] = useState<Place | null>(null);
  const [locationDenied, setLocationDenied] = useState(false);

  const locate = useCallback(async () => {
    const r = await currentPlace();
    setLocationDenied(r.denied);
    if (r.place) setPlace(r.place);
    return r.place;
  }, []);

  useEffect(() => {
    (async () => {
      let saved: LocaleState | null = null;
      try {
        const raw = await getItem(STORE_KEY);
        saved = raw ? JSON.parse(raw) : null;
      } catch {
        saved = null;
      }
      if (saved) setState(saved);
      // Show the UI right away with saved/device settings, then refine from GPS.
      setReady(true);

      const p = await locate();
      try {
        const info = await api.locale(p?.country ?? null);
        setState((prev) => {
          const next: LocaleState = {
            // a language the user picked by hand wins over the detected one
            language: prev.manual ? prev.language : isLang(info.language) ? info.language : 'en',
            currency: info.currency,
            country: info.country_code,
            decimals: info.currency_decimals,
            detectedFrom: info.detected_from,
            manual: prev.manual,
          };
          setItem(STORE_KEY, JSON.stringify(next));
          return next;
        });
      } catch {
        // offline: keep saved/device settings
      }
    })();
  }, [locate]);

  const setLanguage = useCallback((language: Lang) => {
    setState((prev) => {
      const next = { ...prev, language, manual: true };
      setItem(STORE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const value = useMemo<LocaleCtx>(() => {
    const dict = DICTS[state.language];
    const t = (key: TKey, vars?: Record<string, string | number>) => {
      let s: string = dict[key] ?? en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
      return s;
    };
    const money = (amount: string | number | null | undefined, currency?: string) => {
      if (amount === null || amount === undefined || amount === '') return '-';
      const cur = currency ?? state.currency;
      const n = typeof amount === 'string' ? Number(amount) : amount;
      const decimals = Number.isInteger(n) ? 0 : state.decimals;
      try {
        return new Intl.NumberFormat(`${state.language}-${state.country}`, {
          style: 'currency', currency: cur, maximumFractionDigits: decimals, minimumFractionDigits: 0,
        }).format(n);
      } catch {
        return `${cur} ${n.toLocaleString()}`;
      }
    };
    return { ...state, ready, rtl: RTL.includes(state.language), place, locationDenied, t, money, setLanguage, locate };
  }, [state, ready, place, locationDenied, setLanguage, locate]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLocale(): LocaleCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useLocale must be used inside LocaleProvider');
  return c;
}
