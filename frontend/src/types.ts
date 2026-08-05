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
