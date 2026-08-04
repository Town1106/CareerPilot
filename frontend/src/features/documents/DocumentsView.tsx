import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import type { Document, Workspace } from "../../types";

const CATEGORY_NAMES = { resume: "简历", project: "项目资料", other: "其他资料" };

export function DocumentsView({ workspace, onBack }: { workspace: Workspace; onBack: () => void }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<Document["category"]>("resume");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const url = `/api/v1/workspaces/${workspace.id}/documents`;

  const loadDocuments = useCallback(async () => {
    try {
      setDocuments(await api<Document[]>(url));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载文档失败");
    } finally {
      setLoading(false);
    }
  }, [url]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    const form = event.currentTarget;
    const body = new FormData();
    body.append("file", file);
    body.append("category", category);
    setUploading(true);
    setError("");
    try {
      const document = await api<Document>(url, { method: "POST", body });
      setDocuments((items) => [document, ...items]);
      setFile(null);
      form.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function remove(document: Document) {
    if (!window.confirm(`确定删除“${document.original_name}”吗？`)) return;
    try {
      await api<void>(`${url}/${document.id}`, { method: "DELETE" });
      setDocuments((items) => items.filter((item) => item.id !== document.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除失败");
    }
  }

  return (
    <section className="knowledge-shell">
      <button className="text-button back-button" onClick={onBack}>← 返回工作空间</button>
      <div className="knowledge-header">
        <div>
          <p className="eyebrow">KNOWLEDGE BASE · {workspace.target_role || "未设置岗位"}</p>
          <h1>{workspace.name}</h1>
          <p className="muted">上传简历和项目资料，为后续证据检索建立可靠来源。</p>
        </div>
        <div className="status-pill"><span /> 数据库已连接</div>
      </div>

      <div className="knowledge-grid">
        <form className="upload-card" onSubmit={upload}>
          <p className="eyebrow">ADD SOURCE</p>
          <h2>上传求职资料</h2>
          <label>
            文档类型
            <select value={category} onChange={(event) => setCategory(event.target.value as Document["category"])}>
              <option value="resume">简历</option>
              <option value="project">项目资料</option>
              <option value="other">其他资料</option>
            </select>
          </label>
          <label>
            文件
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              required
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
          </label>
          <p className="hint">支持 PDF、DOCX、TXT、Markdown，单文件不超过 10 MB。</p>
          <button className="primary" disabled={uploading || !file}>
            {uploading ? "正在解析…" : "上传并解析"}
          </button>
        </form>

        <div className="documents-card">
          <div className="documents-title">
            <div>
              <p className="eyebrow">SOURCES</p>
              <h2>已解析文档</h2>
            </div>
            <strong>{documents.length}</strong>
          </div>
          {loading ? (
            <p className="muted">正在加载文档…</p>
          ) : documents.length === 0 ? (
            <div className="documents-empty">上传第一份资料后，解析结果会显示在这里。</div>
          ) : (
            <div className="document-list">
              {documents.map((document) => (
                <article className="document-row" key={document.id}>
                  <div className="file-badge">{document.original_name.split(".").pop()?.toUpperCase()}</div>
                  <div className="document-info">
                    <h3>{document.original_name}</h3>
                    <p>
                      {CATEGORY_NAMES[document.category]}
                      {" · "}{(document.size_bytes / 1024).toFixed(1)} KB
                      {" · "}{document.chunk_count} 个文本块
                    </p>
                  </div>
                  <span className="ready">已解析</span>
                  <button className="danger" onClick={() => remove(document)}>删除</button>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
      {error && <div className="toast" role="alert">{error}</div>}
    </section>
  );
}
