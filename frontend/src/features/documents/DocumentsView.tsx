import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import type { Document, RagAnswer, Workspace } from "../../types";

const CATEGORY_NAMES = { resume: "简历", project: "项目资料", other: "其他资料" };
const STATUS_NAMES: Record<string, string> = {
  parsed: "待索引",
  indexing: "索引中",
  indexed: "已索引",
  failed: "索引失败",
};

export function DocumentsView({ workspace, onBack }: { workspace: Workspace; onBack: () => void }) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<Document["category"]>("resume");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [indexingId, setIndexingId] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState<RagAnswer | null>(null);
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

  async function index(document: Document) {
    setIndexingId(document.id);
    setError("");
    try {
      const updated = await api<Document>(`${url}/${document.id}/index`, { method: "POST" });
      setDocuments((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "建立索引失败");
    } finally {
      setIndexingId(null);
    }
  }

  async function reindexAll() {
    setReindexing(true);
    setError("");
    try {
      setDocuments(await api<Document[]>(`/api/v1/workspaces/${workspace.id}/rag/reindex`, {
        method: "POST",
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重建索引失败");
    } finally {
      setReindexing(false);
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (text.length < 2) return;
    setAsking(true);
    setError("");
    try {
      setResult(await api<RagAnswer>(`/api/v1/workspaces/${workspace.id}/rag/ask`, {
        method: "POST",
        body: JSON.stringify({ question: text }),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "知识库问答失败");
    } finally {
      setAsking(false);
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
        <div>
          <button
            className="ghost"
            disabled={reindexing || documents.length === 0}
            onClick={() => void reindexAll()}
          >
            {reindexing ? "正在重建…" : "重建全部索引"}
          </button>
        </div>
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
                  <span className={`document-status ${document.status}`}>
                    {STATUS_NAMES[document.status] || document.status}
                  </span>
                  <div className="document-actions">
                    {document.status !== "indexed" && (
                      <button
                        className="ghost"
                        disabled={indexingId === document.id}
                        onClick={() => void index(document)}
                      >
                        {indexingId === document.id ? "索引中…" : document.status === "failed" ? "重试" : "建立索引"}
                      </button>
                    )}
                    <button className="danger" onClick={() => void remove(document)}>删除</button>
                  </div>
                  {document.index_error && <p className="index-error">{document.index_error}</p>}
                </article>
              ))}
            </div>
          )}
        </div>
      </div>

      <section className="rag-card">
        <div>
          <p className="eyebrow">EVIDENCE Q&amp;A</p>
          <h2>向知识库提问</h2>
          <p className="muted">回答仅基于当前工作空间中已索引的资料，并附上引用原文。</p>
        </div>
        <form className="rag-form" onSubmit={ask}>
          <textarea
            value={question}
            minLength={2}
            maxLength={1000}
            required
            placeholder="例如：我的项目中使用了哪些技术，它们分别解决了什么问题？"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button className="primary" disabled={asking || !documents.some((item) => item.status === "indexed")}>
            {asking ? "正在检索并生成…" : "基于资料回答"}
          </button>
        </form>
        {result && (
          <div className="rag-result">
            <h3>回答</h3>
            <p className="answer-text">{result.answer}</p>
            {result.citations.length > 0 && (
              <div className="citations">
                <h3>引用证据</h3>
                {result.citations.map((citation) => (
                  <details key={citation.chunk_id}>
                    <summary>
                      [{citation.label}] {citation.original_name}
                      {citation.page_number ? ` · 第 ${citation.page_number} 页` : ""}
                    </summary>
                    <p>{citation.content}</p>
                  </details>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
      {error && <div className="toast" role="alert">{error}</div>}
    </section>
  );
}
