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
  size_bytes: number;
  status: string;
  chunk_count: number;
  created_at: string;
};
