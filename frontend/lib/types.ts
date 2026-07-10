export type Offer = {
  id: number;
  company: string;
  role: string;
  offer_url: string;
  detection_date: string;
  score_grade: string;
  score_value: number;
  status: string;
  send_date: string | null;
  contacts: string;
  notes: string;
  cv_path: string;
  cover_letter_path: string;
  prep_sheet_path: string;
  follow_up_date: string | null;
  description: string;
  portal: string;
};

export type ParsedDescription = {
  mission?: string;
  profil?: string;
  stack?: string;
  avantages?: string;
  contrat?: string;
  salaire?: string;
};

export type OffersResponse = {
  offers: Offer[];
  followup_ids: number[];
  statuses: string[];
};

export type OfferDetailResponse = {
  offer: Offer;
  description: ParsedDescription;
};

export type ScanResult = {
  inserted: number;
  skipped: number;
  found: number;
  scored: number;
  abandoned: number;
  error: string;
};

export type ScanStatusResponse = {
  status: "idle" | "running" | "done" | "error";
  result: ScanResult;
};

export type PrepareStatusResponse = {
  status: "idle" | "running" | "done" | "error";
  stage: string;
  error: string;
};

export type FunnelStep = {
  status: string;
  count: number;
  rate: number | null;
};

export type ExitStep = {
  status: string;
  count: number;
};

export type Stats = {
  total: number;
  response_rate: number;
  interview_count: number;
  stale_count: number;
  by_status: Record<string, number>;
};

export type StatsResponse = {
  stats: Stats;
  funnel: FunnelStep[];
  exits: ExitStep[];
  max_count: number;
  latest_report_html: string | null;
  latest_report_date: string | null;
};

export type ProfileContact = {
  name: string;
  title: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
};

export type ProfileInfo = {
  contact: ProfileContact;
  profile_md: string;
};

export type CvExperience = {
  id: number;
  title: string;
  company: string;
  type: string;
  period: string;
  sort_order: number;
  bullets: string[];
};

export type CvSkill = {
  id: number;
  category: string;
  skill: string;
  sort_order: number;
};

export type CvCertification = {
  id: number;
  name: string;
  issuer: string;
  year: number | null;
};

export type CvEducation = {
  id: number;
  degree: string;
  school: string;
  year: number | null;
};

export type CvProject = {
  id: number;
  name: string;
  stack: string[];
  desc: string;
  sort_order: number;
};

export type CvLanguage = {
  id: number;
  name: string;
  sort_order: number;
};

export type CvHobby = {
  id: number;
  name: string;
  sort_order: number;
};

export type Cv = {
  meta: { summary: string };
  experience: CvExperience[];
  skills: CvSkill[];
  certifications: CvCertification[];
  education: CvEducation[];
  projects: CvProject[];
  languages: CvLanguage[];
  hobbies: CvHobby[];
};

export type OnboardingState = {
  is_complete: boolean;
  profile_complete: boolean;
  search_complete: boolean;
  hf_token_complete: boolean;
};

export type ProfileResponse = {
  profile: ProfileInfo;
  cv: Cv;
  cv_en: Cv;
  onboarding: OnboardingState;
};

export type Settings = {
  keywords: string[];
  enabled_portals: string[];
  location: string;
  contract: string;
  experience_max_years: number;
  salary_min: number;
  salary_max: number;
  target_companies: string[];
  follow_up_days: number;
};

export type AtsTarget = {
  id: number;
  name: string;
  careers_url: string;
};

export type Portal = {
  id: string;
  name: string;
  status: string;
};

export type SettingsResponse = {
  settings: Settings;
  ats_targets: AtsTarget[];
  hf_token_set: boolean;
  onboarding: OnboardingState;
  available_portals: Portal[];
};
