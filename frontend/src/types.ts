export type User = {
  id: string;
  email: string;
};

export type Workspace = {
  id: string;
  name: string;
  target_role: string | null;
  created_at: string;
};

export type Document = {
  id: string;
  original_name: string;
  category: "resume" | "project" | "other";
  current_version: number;
  size_bytes: number;
  sha256: string;
  status: string;
  index_error: string | null;
  indexed_at: string | null;
  chunk_count: number;
  created_at: string;
};

export type DocumentVersion = {
  id: string;
  version: number;
  original_name: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  status: string;
  index_error: string | null;
  indexed_at: string | null;
  chunk_count: number;
  created_at: string;
};

export type Citation = {
  label: string;
  chunk_id: string;
  document_id: string;
  original_name: string;
  page_number: number | null;
  position: number;
  content: string;
  score: number;
};

export type RagAnswer = {
  answer: string;
  citations: Citation[];
};

export type Job = {
  id: string;
  workspace_id: string;
  company: string;
  title: string;
  raw_text: string;
  status: string;
  coverage_score: number | null;
  analysis_error: string | null;
  analyzed_at: string | null;
  created_at: string;
};

export type JobEvidence = {
  chunk_id: string | null;
  document_id: string | null;
  original_name: string | null;
  page_number: number | null;
  content: string | null;
  score: number;
  support_level: string;
  explanation: string;
};

export type JobRequirement = {
  id: string;
  competency: string;
  category: string;
  requirement_type: string;
  importance: number;
  raw_evidence: string;
  coverage: string;
  confidence: number;
  explanation: string;
  priority: number;
  evidence: JobEvidence[];
};

export type JobAnalysis = {
  job: Job;
  requirements: JobRequirement[];
};

export type JobComparisonItem = {
  competency: string;
  jobs: Record<string, string>;
};

export type JobComparison = {
  jobs: Job[];
  common: JobComparisonItem[];
  differences: JobComparisonItem[];
};

export type CompetencyGap = {
  competency: string;
  category: string;
  worst_coverage: string;
  max_importance: number;
  priority: number;
  job_count: number;
};

export type InterviewTurn = {
  id: string;
  competency_name: string;
  research_question_id: string | null;
  source_type: string;
  source_url: string | null;
  sequence: number;
  question: string;
  answer: string | null;
  is_follow_up: boolean;
  answered_at: string | null;
  created_at: string;
};

export type InterviewScore = {
  id: string;
  competency_name: string;
  score: number;
  rubric: string;
  evidence: string[];
  strengths: string[];
  issues: string[];
  suggestion: string;
};

export type Interview = {
  id: string;
  workspace_id: string;
  job_description_id: string | null;
  job_name: string | null;
  interview_type: string;
  question_limit: number;
  question_source_mode: "all_real" | "mixed" | "no_search";
  status: string;
  overall_score: number | null;
  report_summary: string | null;
  report_strengths: string[];
  report_issues: string[];
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  turns: InterviewTurn[];
  scores: InterviewScore[];
};

export type CompetencyMemory = {
  id: string;
  workspace_id: string;
  source_session_id: string | null;
  competency_name: string;
  mastery_score: number;
  confidence: number;
  evidence_summary: string;
  error_count: number;
  confirmed: boolean;
  updated_at: string;
  created_at: string;
};
