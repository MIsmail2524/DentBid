export type Role = 'customer' | 'workshop' | 'admin';
export type Severity = 'minor' | 'moderate' | 'severe' | 'none';
export type RequestStatus = 'analyzing' | 'open' | 'booked' | 'in_progress' | 'completed' | 'cancelled' | 'expired';
export type QuoteStatus = 'pending' | 'countered' | 'accepted' | 'rejected' | 'withdrawn';
export type DamageType = 'dent' | 'scratch' | 'crack' | 'glass_shatter' | 'lamp_broken' | 'tire_flat';

export interface User {
  id: number;
  role: Role;
  name: string;
  email: string;
  phone: string | null;
  country_code: string | null;
  currency: string | null;
  language: string | null;
  has_workshop: boolean;
  workshop_status: VerificationStatus | null;
}

export type VerificationStatus = 'pending' | 'approved' | 'rejected' | 'suspended';

export interface WorkshopDocument {
  id: number;
  kind: 'shop_front' | 'trade_license' | 'owner_id' | 'other';
  url: string;
  created_at: string;
}

export interface AdminWorkshop extends Workshop {
  owner_id: number;
  owner_name: string;
  owner_email: string;
  owner_phone: string | null;
  owner_active: boolean;
  document_count: number;
  created_at: string;
  verified_at: string | null;
  documents: WorkshopDocument[];
}

export interface AdminUser {
  id: number;
  role: Role;
  name: string;
  email: string;
  phone: string | null;
  country_code: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AdminStats {
  users: Record<string, number>;
  workshops: Record<string, number>;
  requests: Record<string, number>;
  quotes_total: number;
  jobs_booked: number;
  open_requests: number;
  analyzer: { available: boolean; model_version: string | null; error: string | null };
}

export interface LocaleInfo {
  country_code: string;
  currency: string;
  language: string;
  rtl: boolean;
  currency_decimals: number;
  supported_languages: string[];
  detected_from: string;
}

export interface Workshop {
  id: number;
  name: string;
  phone: string | null;
  address: string | null;
  city: string | null;
  country_code: string | null;
  lat: number;
  lng: number;
  service_radius_km: number;
  services: DamageType[];
  about: string | null;
  verified: boolean;
  verification_status: VerificationStatus;
  rejection_reason: string | null;
  rating_avg: number;
  rating_count: number;
  jobs_completed: number;
  distance_km?: number | null;
}

export interface WorkshopPublic {
  id: number;
  name: string;
  city: string | null;
  verified: boolean;
  rating_avg: number;
  rating_count: number;
  jobs_completed: number;
  distance_km: number | null;
  phone: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
}

export interface Measurements {
  area_px: number;
  area_ratio_part: number | null;
  area_ratio_car: number | null;
  area_ratio_image: number;
  width_cm: number | null;
  height_cm: number | null;
  area_cm2: number | null;
  length_cm: number | null;
  mean_width_cm: number | null;
  paint_contrast: number | null;
  paint_layer: 'clear_coat' | 'base_coat' | 'primer_or_metal' | null;
  scale_source: string | null;
}

export interface Damage {
  id: number;
  type: DamageType;
  label: string;
  confidence: number;
  bbox: number[];
  part: string | null;
  part_label: string | null;
  measurements: Measurements;
  severity_score: number;
  severity: Severity;
  repair_method: string;
  repair_notes: string;
  labor_hours: [number, number];
}

export interface PhotoAnalysis {
  quality?: { ok: boolean; issues: string[]; sharpness: number; brightness: number };
  damages?: Damage[];
  summary?: string;
  overall_severity?: Severity;
  warnings?: string[];
  error?: string;
}

export interface Photo {
  id: number;
  url: string;
  annotated_url: string | null;
  width: number | null;
  height: number | null;
  analysis: PhotoAnalysis | null;
}

export interface PartSummary {
  part: string;
  part_label: string;
  damage_count: number;
  damage_types: DamageType[];
  severity_score: number;
  severity: Severity;
  recommendation: 'repair' | 'repaint' | 'replace';
}

export interface Report {
  status: 'done' | 'failed' | 'unavailable';
  reason?: string;
  overall_score?: number;
  overall_severity?: Severity;
  damage_types: DamageType[];
  damage_count?: number;
  parts?: PartSummary[];
  labor_hours?: [number, number];
  photos_analyzed: number;
  photos_with_quality_issues?: number;
  summary?: string;
  model_version?: string;
}

export interface Quote {
  id: number;
  request_id: number;
  status: QuoteStatus;
  amount: string;
  currency: string;
  counter_amount: string | null;
  eta_days: number;
  warranty_months: number;
  includes_parts: boolean;
  pickup_available: boolean;
  notes: string | null;
  breakdown: { item: string; amount: number }[] | null;
  created_at: string;
  updated_at: string;
  workshop: WorkshopPublic | null;
}

export interface DamageRequest {
  id: number;
  status: RequestStatus;
  car_make: string | null;
  car_model: string | null;
  car_year: number | null;
  car_color: string | null;
  description: string | null;
  city: string | null;
  country_code: string | null;
  currency: string;
  customer_offer: string | null;
  search_radius_km: number;
  lat: number;
  lng: number;
  analysis: Report | null;
  overall_severity: Severity | null;
  overall_score: number | null;
  photos: Photo[];
  quote_count: number;
  lowest_quote: string | null;
  accepted_quote_id: number | null;
  created_at: string;
  expires_at: string;
  distance_km: number | null;
  my_quote: Quote | null;
  customer_name: string | null;
  customer_phone: string | null;
}

export interface RequestCard {
  id: number;
  status: RequestStatus;
  title: string;
  thumbnail_url: string | null;
  city: string | null;
  currency: string;
  customer_offer: string | null;
  overall_severity: Severity | null;
  overall_score: number | null;
  damage_types: DamageType[];
  quote_count: number;
  lowest_quote: string | null;
  created_at: string;
  expires_at: string;
  distance_km: number | null;
  my_quote_status: QuoteStatus | null;
}

export interface Message {
  id: number;
  quote_id: number;
  sender_id: number;
  body: string;
  created_at: string;
}

export interface RealtimeEvent {
  type: string;
  request_id?: number;
  quote_id?: number;
  message?: Message;
}
