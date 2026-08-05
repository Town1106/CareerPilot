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
