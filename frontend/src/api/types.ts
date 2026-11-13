// Mirrors backend/fms/schemas.py. Decimal values arrive as strings (e.g. "180.00").

export type PayScheme = 'cutting' | 'loading';
export type RateComponent = 'cutting' | 'loading' | 'unloading';
export type Language = 'en' | 'hi';
export type PayPeriod = 'half_month' | 'month';
export type Decimal = string;
export type ISODate = string; // YYYY-MM-DD

export interface WorkerType {
  id: string;
  code: string;
  name_en: string;
  name_hi: string | null;
  pay_scheme: PayScheme;
  is_active: boolean;
}

export interface Worker {
  id: string;
  name_en: string;
  name_hi: string | null;
  worker_type_id: string;
  worker_type: WorkerType;
  phone: string | null;
  joined_on: ISODate | null;
  notes: string | null;
  archived_at: string | null;
  is_archived: boolean;
}

export interface WorkerInput {
  name_en: string;
  name_hi?: string | null;
  worker_type_id: string;
  phone?: string | null;
  joined_on?: ISODate | null;
  notes?: string | null;
  allow_duplicate_name?: boolean;
}

export interface Rate {
  id: string;
  worker_type_id: string;
  component: RateComponent;
  rate_per_sqft: Decimal;
  effective_from: ISODate;
  note: string | null;
}

export interface CurrentRate {
  worker_type_id: string;
  component: RateComponent;
  rate_per_sqft: Decimal | null;
  effective_from: ISODate | null;
}

export interface WageLine {
  component: RateComponent;
  effective_area_sqft: Decimal;
  rate_per_sqft: Decimal;
  amount: Decimal;
}

export interface ProductionEntry {
  id: string;
  worker_id: string;
  worker_type_id: string;
  entry_date: ISODate;
  length_ft: Decimal;
  width_ft: Decimal;
  cuts: number;
  quantity: number;
  notes: string | null;
  area_sqft: Decimal;
  wage: Decimal | null;
  wage_lines: WageLine[];
  missing_rates: RateComponent[];
}

export interface ProductionInput {
  worker_id: string;
  entry_date: ISODate;
  length_ft: string;
  width_ft: string;
  cuts: number;
  quantity: number;
  notes?: string | null;
}

export interface WagePreview {
  area_sqft: Decimal;
  wage: Decimal | null;
  wage_lines: WageLine[];
  missing_rates: RateComponent[];
}

export interface WorkerWages {
  worker_id: string;
  name_en: string;
  name_hi: string | null;
  worker_type_name_en: string;
  worker_type_name_hi: string | null;
  is_archived: boolean;
  entry_count: number;
  total_quantity: number;
  total_area_sqft: Decimal;
  total_cuts: number;
  total_wage: Decimal;
  missing_rate_entries: number;
  entries: ProductionEntry[] | null;
}

export interface WagesReport {
  start: ISODate;
  end: ISODate;
  workers: WorkerWages[];
  total_wage: Decimal;
  total_area_sqft: Decimal;
  missing_rate_entries: number;
}

export interface AppSettings {
  factory_name_en: string;
  factory_name_hi: string;
  factory_address: string;
  ui_language: Language;
  print_language: Language;
  pay_period: PayPeriod;
}
