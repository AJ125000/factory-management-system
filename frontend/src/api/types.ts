// Mirrors backend/fms/schemas.py. Decimal values arrive as strings (e.g. "180.00").

export type Role = 'operator' | 'loader';
export type MachineKind =
  | 'block_cutting'
  | 'double_edge'
  | 'table_polish'
  | 'single_cutting'
  | 'block_cutter'; // paid per shift (not the splitting machine, block_cutting)
export type Shift = 'day' | 'night';
/** 'cutting', 'loading', 'unloading', or 'polish_N' for table polish with N batti. */
export type RateComponent = string;
export type Unit = 'sqft' | 'rft' | 'shift';
export type Language = 'en' | 'hi';
export type PayPeriod = 'half_month' | 'month';
export type Decimal = string;
export type ISODate = string; // YYYY-MM-DD

export interface WorkerType {
  id: string;
  code: string;
  name_en: string;
  name_hi: string | null;
  role: Role;
  is_active: boolean;
}

export interface Machine {
  id: string;
  code: string;
  kind: MachineKind;
  name_en: string;
  name_hi: string | null;
  sort_order: number;
  is_active: boolean;
}

/** A standard size and what one piece counts for, shared by every machine of the type.
 * Feet on double edge, inches on single cutting. */
export interface MachineSize {
  id: string;
  kind: MachineKind;
  length: Decimal;
  width: Decimal;
  rft: Decimal;
  sqft: Decimal;
}

/** Who loads at a machine from a date onwards (worker_id null = no loader). */
export interface LoaderAssignment {
  id: string;
  machine_id: string;
  worker_id: string | null;
  effective_from: ISODate;
  note: string | null;
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

/** A rate of a machine type: every machine of the type is paid at it. */
export interface Rate {
  id: string;
  kind: MachineKind;
  component: RateComponent;
  unit: Unit;
  rate: Decimal;
  effective_from: ISODate;
  note: string | null;
}

export interface CurrentRate {
  kind: MachineKind;
  component: RateComponent;
  unit: Unit;
  rate: Decimal | null;
  effective_from: ISODate | null;
}

export interface WageLine {
  component: RateComponent;
  basis: Decimal; // the sq ft or running ft the rate is multiplied by
  unit: Unit;
  rate: Decimal;
  amount: Decimal;
}

export interface ProductionEntry {
  id: string;
  worker_id: string;
  worker_type_id: string;
  machine_id: string;
  entry_date: ISODate;
  length_ft: Decimal | null;
  width_ft: Decimal | null;
  size_id: string | null;
  size_label: string | null;
  piece_sqft: Decimal;
  piece_rft: Decimal | null;
  cuts: number;
  batti: number | null;
  shift: Shift | null; // block cutter: the shift worked (the entry is one shift)
  quantity: number;
  loader_id: string | null; // only when someone filled in on this entry
  notes: string | null;
  area_sqft: Decimal;
  rft_total: Decimal | null;
  /** Splitting machine: sq ft the operator's cutting and the loader's unloading are paid on. */
  cutting_sqft: Decimal | null;
  unloading_sqft: Decimal | null;
  /** The pay of paid_worker_id as paid_as (the operator, except on a loader's wage slip). */
  paid_as: Role;
  paid_worker_id: string | null;
  wage: Decimal | null;
  wage_lines: WageLine[];
  missing_rates: RateComponent[];
  loader_worker_id: string | null;
  loader_wage: Decimal | null;
  loader_wage_lines: WageLine[];
  loader_missing_rates: RateComponent[];
  no_loader: boolean;
}

export interface ProductionInput {
  worker_id: string;
  machine_id: string;
  entry_date: ISODate;
  length_ft: string | null;
  width_ft: string | null;
  size_id: string | null;
  cuts: number;
  batti: number | null;
  shift: Shift | null;
  quantity: number;
  loader_id: string | null;
  notes?: string | null;
}

export interface WagePreview {
  area_sqft: Decimal;
  rft_total: Decimal | null;
  cutting_sqft: Decimal | null;
  unloading_sqft: Decimal | null;
  piece_sqft: Decimal;
  piece_rft: Decimal | null;
  wage: Decimal | null;
  wage_lines: WageLine[];
  missing_rates: RateComponent[];
  loader_worker_id: string | null;
  loader_wage: Decimal | null;
  loader_wage_lines: WageLine[];
  loader_missing_rates: RateComponent[];
  no_loader: boolean;
}

export interface WorkerWages {
  worker_id: string;
  name_en: string;
  name_hi: string | null;
  worker_type_name_en: string;
  worker_type_name_hi: string | null;
  role: Role;
  is_archived: boolean;
  entry_count: number;
  total_quantity: number;
  total_area_sqft: Decimal;
  total_rft: Decimal;
  total_cuts: number;
  total_shifts: number; // block cutter shifts
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
  no_loader_entries: number;
}

export interface AppSettings {
  factory_name_en: string;
  factory_name_hi: string;
  factory_address: string;
  ui_language: Language;
  print_language: Language;
  pay_period: PayPeriod;
  phone_url: string;
  backup_copy_dir: string;
}

export type GroupBy = 'day' | 'month' | 'year';

export interface ProductionBucket {
  period: string; // "2026-11-05", "2026-11" or "2026"
  entry_count: number;
  total_quantity: number;
  total_area_sqft: Decimal;
  total_rft: Decimal;
  total_cuts: number;
  total_shifts: number; // block cutter shifts
  total_wage: Decimal;
  missing_rate_entries: number;
}

export interface ProductionSummary {
  start: ISODate;
  end: ISODate;
  group_by: GroupBy;
  buckets: ProductionBucket[];
  totals: ProductionBucket;
}

export interface ConnectInfo {
  tailscale_installed: boolean;
  tailscale_running: boolean;
  detected_url: string | null;
  phone_url: string | null;
  hub_port: number;
}

export interface DeviceInfo {
  id: string;
  name: string;
  created_at: string;
  last_seen_at: string;
  current: boolean;
}

export interface AuthStatus {
  setup_required: boolean;
  logged_in: boolean;
  device: DeviceInfo | null;
}

export interface BackupInfo {
  name: string;
  size: number;
  created_at: string;
  kind: 'auto' | 'manual' | 'before-restore';
}

export interface BackupStatus {
  backups: BackupInfo[];
  last_backup_at: string | null;
  copy_dir: string;
  copy_dir_ok: boolean | null;
  last_error: string | null;
}
