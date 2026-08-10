export interface User {
  id: string;
  name: string;
  email: string;
  is_demo: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  demo_mode: boolean;
}

export interface DashboardStats {
  opportunities_found: number;
  strong_matches: number;
  applications: number;
  under_review: number;
  approved: number;
  agent_active: boolean;
  last_scan: string | null;
  next_scan: string | null;
  demo_mode: boolean;
  student_name: string;
  onboarding_completed?: boolean;
  documents_count?: number;
  country_focus?: string;
}

export interface Profile {
  id: string;
  user_id: string;
  degree: string | null;
  field_of_study: string | null;
  institution: string | null;
  gpa: number | null;
  graduation_year: number | null;
  country: string | null;
  state: string | null;
  city: string | null;
  skills: string[];
  interests: string[];
  career_goals: string[];
  education_level: string | null;
  category: string | null;
  additional_profile_data: Record<string, unknown>;
  agent_active: boolean;
  onboarding_completed?: boolean;
  last_agent_scan_at: string | null;
  next_agent_scan_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Opportunity {
  id: string;
  title: string;
  provider: string;
  opportunity_type: string;
  description: string;
  amount: number | null;
  currency: string;
  deadline: string | null;
  application_start_date: string | null;
  location: string | null;
  eligibility_text: string | null;
  required_documents: string[];
  official_source_url: string;
  application_url: string | null;
  source_name: string;
  source_verified: boolean;
  last_verified_at: string | null;
  status: string;
  eligibility_structured: Record<string, unknown>;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface Match {
  id: string;
  student_id: string;
  opportunity_id: string;
  eligibility_status: string;
  eligibility_score: number;
  application_readiness_score: number;
  ranking_score: number;
  reasoning: string;
  missing_requirements: string[];
  matched_requirements: string[];
  failed_requirements: string[];
  score_breakdown: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  opportunity?: Opportunity;
}

export interface Application {
  id: string;
  student_id: string;
  opportunity_id: string;
  status: string;
  submitted_at: string | null;
  last_status_update: string | null;
  notes: string | null;
  timeline: TimelineEntry[];
  created_at: string;
  updated_at: string;
  opportunity?: Opportunity;
}

export interface TimelineEntry {
  status: string;
  at: string;
  note: string;
}

export interface Document {
  id: string;
  student_id: string;
  document_type: string;
  file_name: string;
  file_url: string;
  verified: boolean;
  uploaded_at: string;
  expiration_date: string | null;
  metadata_json: Record<string, unknown>;
}

export interface Notification {
  id: string;
  student_id: string;
  type: string;
  title: string;
  message: string;
  priority: string;
  read: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AgentRun {
  id: string;
  student_id: string | null;
  agent_name: string;
  run_type: string;
  status: string;
  input_summary: string | null;
  output_summary: string | null;
  started_at: string;
  completed_at: string | null;
  metadata_json: Record<string, unknown>;
  parent_run_id: string | null;
  steps: AgentStep[];
}

export interface AgentStep {
  name?: string;
  agent?: string;
  status?: string;
  message?: string;
  output?: string;
  duration_ms?: number;
}

export interface DiscoverResponse {
  run_id: string;
  status: string;
  summary: Record<string, unknown>;
  steps: AgentStep[];
}

export interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  event_type: string;
  opportunity_id?: string;
  application_id?: string;
  priority: string;
  description: string;
}

export interface CareerRoadmap {
  career_goal: string;
  years: Array<{
    year: number;
    title: string;
    milestones: string[];
    skills_to_develop: string[];
  }>;
  linked_opportunity_ids: string[];
  summary: string;
}

export interface ChatResponse {
  reply: string;
  tools_used: string[];
  requires_confirmation: boolean;
  confirmation_prompt: string | null;
  data: Record<string, unknown>;
}

export interface AnalysisResult {
  overall_score: number;
  dimensions: Record<string, number>;
  strengths: string[];
  improvements: string[];
  suggestions: string[];
  ai_generated_draft: string | null;
  disclaimer: string;
}

export interface ApiError {
  detail: string | { requires_confirmation?: boolean; confirmation_prompt?: string; [key: string]: unknown };
}
