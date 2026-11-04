import { Platform } from 'react-native';

import { API_URL } from './config';
import type {
  AdminStats, AdminUser, AdminWorkshop, DamageRequest, LocaleInfo, Message, Quote, RequestCard, User,
  VerificationStatus, Workshop, WorkshopDocument,
} from './types';

let authToken: string | null = null;
export const getAuthToken = () => authToken;
export function setAuthToken(token: string | null) {
  authToken = token;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...(init.headers as Record<string, string>) };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, 'network');
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === 'string' ? body.detail : body.detail?.[0]?.msg ?? msg;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, msg);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

const get = <T>(p: string) => request<T>(p);
const post = <T>(p: string, body?: unknown) => request<T>(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
const put = <T>(p: string, body: unknown) => request<T>(p, { method: 'PUT', body: JSON.stringify(body) });
const patch = <T>(p: string, body: unknown) => request<T>(p, { method: 'PATCH', body: JSON.stringify(body) });

export interface AuthResult { access_token: string; user: User }

export interface NewRequestInput {
  photos: { uri: string; mimeType?: string | null; fileName?: string | null; file?: File }[];
  lat: number;
  lng: number;
  city?: string;
  country_code?: string;
  car_make?: string;
  car_model?: string;
  car_year?: string;
  car_color?: string;
  description?: string;
  customer_offer?: string;
  search_radius_km?: number;
}

export interface QuoteInput {
  amount: number;
  eta_days: number;
  warranty_months: number;
  includes_parts: boolean;
  pickup_available: boolean;
  notes?: string;
  breakdown?: { item: string; amount: number }[];
}

export const api = {
  locale: (country?: string | null, lang?: string | null) => {
    const q = new URLSearchParams();
    if (country) q.set('country', country);
    if (lang) q.set('lang', lang);
    return get<LocaleInfo>(`/locale?${q}`);
  },
  health: () => get<{ status: string; analyzer: { available: boolean; model_version: string | null } }>('/health'),

  register: (body: { name: string; email: string; password: string; phone?: string; role: string; country_code?: string; language?: string }) =>
    post<AuthResult>('/auth/register', body),
  login: (email: string, password: string) => post<AuthResult>('/auth/login', { email, password }),
  me: () => get<User>('/auth/me'),
  updateMe: (body: Partial<Pick<User, 'name' | 'phone' | 'country_code' | 'currency' | 'language'>> & { push_token?: string }) =>
    patch<User>('/auth/me', body),

  myWorkshop: () => get<Workshop>('/workshops/me'),
  saveWorkshop: (body: Omit<Workshop, 'id' | 'verified' | 'verification_status' | 'rejection_reason' | 'rating_avg'
    | 'rating_count' | 'jobs_completed' | 'distance_km'>) => put<Workshop>('/workshops/me', body),
  myDocuments: () => get<WorkshopDocument[]>('/workshops/me/documents'),
  uploadDocument: async (kind: string, photo: { uri: string; mimeType?: string | null; fileName?: string | null; file?: File }) => {
    const fd = new FormData();
    fd.append('kind', kind);
    const name = photo.fileName ?? `${kind}.jpg`;
    if (Platform.OS === 'web') {
      fd.append('file', photo.file ?? (await (await fetch(photo.uri)).blob()), name);
    } else {
      fd.append('file', { uri: photo.uri, name, type: photo.mimeType ?? 'image/jpeg' } as unknown as Blob);
    }
    return request<WorkshopDocument>('/workshops/me/documents', { method: 'POST', body: fd });
  },
  deleteDocument: (id: number) => request<void>(`/workshops/me/documents/${id}`, { method: 'DELETE' }),
  logoutAll: () => post<void>('/auth/logout-all'),

  admin: {
    stats: () => get<AdminStats>('/admin/stats'),
    workshops: (status?: VerificationStatus | '', q?: string) => {
      const p = new URLSearchParams();
      if (status) p.set('status', status);
      if (q) p.set('q', q);
      return get<AdminWorkshop[]>(`/admin/workshops?${p}`);
    },
    workshop: (id: number) => get<AdminWorkshop>(`/admin/workshops/${id}`),
    approve: (id: number) => post<AdminWorkshop>(`/admin/workshops/${id}/approve`),
    reject: (id: number, reason: string) => post<AdminWorkshop>(`/admin/workshops/${id}/reject`, { reason }),
    suspend: (id: number, reason: string) => post<AdminWorkshop>(`/admin/workshops/${id}/suspend`, { reason }),
    users: (q?: string) => get<AdminUser[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ''}`),
    deactivate: (id: number, reason: string) => post<AdminUser>(`/admin/users/${id}/deactivate`, { reason }),
    activate: (id: number) => post<AdminUser>(`/admin/users/${id}/activate`),
  },

  createRequest: async (input: NewRequestInput) => {
    const fd = new FormData();
    input.photos.forEach((p, i) => {
      const name = p.fileName ?? `photo_${i}.jpg`;
      if (Platform.OS === 'web') {
        // web: the picker gives a File object (or a blob: URI we fetch)
        if (p.file) fd.append('photos', p.file, name);
      } else {
        fd.append('photos', { uri: p.uri, name, type: p.mimeType ?? 'image/jpeg' } as unknown as Blob);
      }
    });
    if (Platform.OS === 'web') {
      for (const [i, p] of input.photos.entries()) {
        if (!p.file) {
          const blob = await (await fetch(p.uri)).blob();
          fd.append('photos', blob, p.fileName ?? `photo_${i}.jpg`);
        }
      }
    }
    const fields: (keyof NewRequestInput)[] = ['lat', 'lng', 'city', 'country_code', 'car_make', 'car_model',
      'car_year', 'car_color', 'description', 'customer_offer', 'search_radius_km'];
    for (const k of fields) {
      const v = input[k];
      if (v !== undefined && v !== null && v !== '') fd.append(k, String(v));
    }
    return request<DamageRequest>('/requests', { method: 'POST', body: fd });
  },
  myRequests: () => get<RequestCard[]>('/requests/mine'),
  feed: (params: { severity?: string; damage_type?: string; sort?: string } = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]);
    return get<RequestCard[]>(`/requests/feed?${q}`);
  },
  getRequest: (id: number) => get<DamageRequest>(`/requests/${id}`),
  cancelRequest: (id: number) => post<DamageRequest>(`/requests/${id}/cancel`),
  updateOffer: (id: number, amount: number) => patch<DamageRequest>(`/requests/${id}/offer`, { amount }),
  setJobStatus: (id: number, status: 'in_progress' | 'completed') => post<DamageRequest>(`/requests/${id}/status`, { status }),
  review: (id: number, rating: number, comment?: string) => post(`/requests/${id}/review`, { rating, comment }),

  quotes: (requestId: number) => get<Quote[]>(`/requests/${requestId}/quotes`),
  submitQuote: (requestId: number, body: QuoteInput) => post<Quote>(`/requests/${requestId}/quotes`, body),
  myJobs: () => get<RequestCard[]>('/quotes/mine'),
  acceptQuote: (id: number) => post<Quote>(`/quotes/${id}/accept`),
  rejectQuote: (id: number) => post<Quote>(`/quotes/${id}/reject`),
  counterQuote: (id: number, amount: number) => post<Quote>(`/quotes/${id}/counter`, { amount }),
  acceptCounter: (id: number) => post<Quote>(`/quotes/${id}/accept-counter`),
  withdrawQuote: (id: number) => post<Quote>(`/quotes/${id}/withdraw`),
  messages: (quoteId: number) => get<Message[]>(`/quotes/${quoteId}/messages`),
  sendMessage: (quoteId: number, body: string) => post<Message>(`/quotes/${quoteId}/messages`, { body }),
};
