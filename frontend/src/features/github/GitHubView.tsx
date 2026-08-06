import { useEffect, useState } from "react";

import { api } from "../../api";
import type { CommitItem, RepoDetail, RepoSummary, Workspace } from "../../types";

export function GitHubView({ workspace, onBack }: { workspace: Workspace; onBack: () => void }) {
  const [connected, setConnected] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [repos, setRepos] = useState<RepoSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedRepo, setSelectedRepo] = useState<RepoDetail | null>(null);
  const [readme, setReadme] = useState("");
  const [commits, setCommits] = useState<CommitItem[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  async function connect() {
    setLoading(true);
    setError("");
    try {
      const data = await api<{ provider: string; connected: boolean; message: string }>(
        "/api/v1/mcp/github/connect",
        { method: "POST" }
      );
      setConnected(data.connected);
      setStatusMsg(data.message);
      if (data.connected) {
        await loadRepos();
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "连接失败");
    } finally {
      setLoading(false);
    }
  }

  async function disconnect() {
    setError("");
    try {
      await api<{ provider: string; connected: boolean; message: string }>(
        "/api/v1/mcp/github/disconnect",
        { method: "POST" }
      );
      setConnected(false);
      setRepos([]);
      setSelectedRepo(null);
      setStatusMsg("已断开");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "断开失败");
    }
  }

  async function loadRepos() {
    setLoading(true);
    try {
      const data = await api<{ repos: RepoSummary[] }>("/api/v1/mcp/github/repos");
      setRepos(data.repos);
      setConnected(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载仓库失败");
    } finally {
      setLoading(false);
    }
  }

  async function openRepo(owner: string, repoName: string) {
    setDetailLoading(true);
    setSelectedRepo(null);
    setReadme("");
    setCommits([]);
    try {
      const [detail, readmeData, commitsData] = await Promise.all([
        api<RepoDetail>(`/api/v1/mcp/github/repos/${owner}/${repoName}`),
        api<{ content: string }>(`/api/v1/mcp/github/repos/${owner}/${repoName}/readme`),
        api<{ commits: CommitItem[] }>(`/api/v1/mcp/github/repos/${owner}/${repoName}/commits?per_page=10`),
      ]);
      setSelectedRepo(detail);
      setReadme(readmeData.content);
      setCommits(commitsData.commits);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载仓库详情失败");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    setSelectedRepo(null);
    setRepos([]);
    setConnected(false);
  }, [workspace.id]);

  return (
    <div className="view">
      <header className="view-header">
        <button className="ghost" onClick={onBack}>← 返回</button>
        <div>
          <h1>GitHub</h1>
          <p className="muted">连接 GitHub 查看仓库与项目信息</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {connected ? (
            <button className="ghost" onClick={disconnect}>断开</button>
          ) : (
            <button className="ghost" onClick={connect} disabled={loading}>
              {loading ? "连接中…" : "连接"}
            </button>
          )}
        </div>
      </header>

      {error && <div className="toast" role="alert">{error}</div>}

      {!connected && !loading ? (
        <div className="empty-card">
          <p className="eyebrow">GITHUB MCP</p>
          <h2>未连接 GitHub</h2>
          <p className="muted">
            在 .env 中配置 GITHUB_TOKEN 后点击"连接"按钮。
          </p>
        </div>
      ) : selectedRepo ? (
        <div>
          <button className="ghost" onClick={() => setSelectedRepo(null)} style={{ marginBottom: 12 }}>
            ← 返回仓库列表
          </button>
          <div className="trace-card completed">
            <div style={{ padding: 16 }}>
              <h2 style={{ margin: "0 0 4px" }}>{selectedRepo.full_name}</h2>
              <p className="muted" style={{ margin: "0 0 8px" }}>{selectedRepo.description}</p>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
                <span className="trace-badge completed">{selectedRepo.language || "N/A"}</span>
                <span className="trace-badge">★ {selectedRepo.stargazers_count}</span>
                <span className="trace-badge">{selectedRepo.default_branch}</span>
              </div>
              {selectedRepo.topics.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  {selectedRepo.topics.map((t) => (
                    <span key={t} className="skill-tag">{t}</span>
                  ))}
                </div>
              )}
            </div>

            {readme && (
              <div className="trace-detail" style={{ maxHeight: 400, overflow: "auto" }}>
                <pre style={{ fontSize: 12, margin: 0, whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
                  {readme.slice(0, 8000)}
                  {readme.length > 8000 ? "\n\n... (内容过长，已截断)" : ""}
                </pre>
              </div>
            )}

            {commits.length > 0 && (
              <div className="trace-detail">
                <h4 style={{ margin: "0 0 8px" }}>最近提交</h4>
                {commits.map((c) => (
                  <div key={c.sha} style={{ marginBottom: 6, fontSize: 13 }}>
                    <span style={{ fontFamily: "monospace", color: "var(--text-muted)", marginRight: 8 }}>
                      {c.sha.slice(0, 7)}
                    </span>
                    <span>{c.message}</span>
                    <span style={{ color: "var(--text-muted)", marginLeft: 8 }}>
                      — {c.author} · {new Date(c.date).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="trace-list">
          <p className="muted" style={{ marginBottom: 12 }}>
            {repos.length > 0 ? `共 ${repos.length} 个仓库` : "暂无仓库"}
          </p>
          {repos.map((r) => (
            <div
              key={r.full_name}
              className="trace-card completed"
              style={{ cursor: "pointer" }}
              onClick={() => {
                const [owner, name] = r.full_name.split("/");
                void openRepo(owner, name);
              }}
            >
              <div className="trace-summary">
                <div className="trace-left">
                  <span className="trace-badge completed">{r.language || "N/A"}</span>
                  <span className="trace-type">{r.full_name}</span>
                </div>
                <div className="trace-right">
                  <span className="trace-time">★ {r.stargazers_count}</span>
                </div>
              </div>
              <div style={{ padding: "0 16px 8px" }}>
                <p className="muted" style={{ fontSize: 13 }}>
                  {r.description || "无描述"}
                </p>
              </div>
            </div>
          ))}
          {detailLoading && <div className="empty-card">加载中…</div>}
        </div>
      )}
    </div>
  );
}