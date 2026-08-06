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

export type StudyTask = {
  id: string;
  competency_name: string | null;
  title: string;
  description: string;
  scheduled_date: string;
  duration_minutes: number;
  priority: number;
  status: string;
  created_at: string;
};

export type StudyPlan = {
  id: string;
  workspace_id: string;
  goal: string;
  start_date: string;
  end_date: string;
  version: number;
  status: string;
  created_at: string;
  tasks: StudyTask[];
  total_tasks: number;
  completed_tasks: number;
  coverage: number;
};

export type RunStep = {
  id: string;
  run_id: string;
  step_name: string;
  status: string;
  input_summary: string | null;
  output_summary: string | null;
  retrieved_chunks: string | null;
  latency_ms: number;
  error_code: string | null;
  started_at: string;
  completed_at: string | null;
};

export type Run = {
  id: string;
  workspace_id: string;
  run_type: string;
  skill_name: string | null;
  skill_version: string | null;
  status: string;
  model_id: string | null;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  error_code: string | null;
  started_at: string;
  completed_at: string | null;
};

export type RunDetail = Run & {
  steps: RunStep[];
};

export type RunList = {
  runs: Run[];
  total: number;
};

export type SkillItem = {
  id: string;
  name: string;
  version: string;
  description: string;
  manifest_path: string;
  risk_level: string;
  status: string;
  created_at: string;
};

export type SkillDetail = SkillItem & {
  triggers: string[];
  required_inputs: string[];
  allowed_tools: string[];
};

export type ToolItem = {
  id: string;
  name: string;
  version: string;
  description: string;
  manifest_path: string;
  risk_level: string;
  status: string;
  created_at: string;
};

export type ToolDetail = ToolItem & {
  input_schema: string | null;
  output_schema: string | null;
  require_approval: boolean;
  approval_prompt: string | null;
  max_per_session: number | null;
};

export type ApprovalItem = {
  id: string;
  workspace_id: string;
  tool_name: string;
  run_id: string | null;
  requested_by_skill: string | null;
  payload_summary: string;
  status: string;
  created_at: string;
  decided_at: string | null;
};

export type MCPStatus = {
  provider: string;
  connected: boolean;
  message: string;
};

export type RepoSummary = {
  name: string;
  full_name: string;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  updated_at: string;
  html_url: string;
};

export type RepoDetail = RepoSummary & {
  topics: string[];
  default_branch: string;
  open_issues_count: number;
  created_at: string;
};

export type CommitItem = {
  sha: string;
  message: string;
  author: string;
  date: string;
};

export type FactItem = {
  id: string;
  workspace_id: string;
  repo_full_name: string;
  extracted_tech_stack: string[] | null;
  extracted_summary: string | null;
  extracted_role: string | null;
  commit_count: number;
  created_at: string;
};

export type ConsistencyReport = {
  id: string;
  workspace_id: string;
  repo_full_name: string;
  matched_items: { item: string; source: string }[] | null;
  missing_in_resume: { item: string; evidence: string }[] | null;
  conflicts: { claim: string; reality: string; severity: string }[] | null;
  overall_score: number;
  created_at: string;
};
