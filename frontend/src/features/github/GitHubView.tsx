import { useEffect, useState } from "react";

import { api } from "../../api";
import type { CommitItem, ConsistencyReport, FactItem, RepoDetail, RepoSummary, Workspace } from "../../types";

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

  const [fact, setFact] = useState<FactItem | null>(null);
  const [report, setReport] = useState<ConsistencyReport | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [checking, setChecking] = useState(false);

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
    setFact(null);
    setReport(null);
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

  async function doExtract() {
    if (!selectedRepo) return;
    setAnalyzing(true);
    setError("");
    try {
      const data = await api<FactItem>("/api/v1/analysis/extract-facts", {
        method: "POST",
        body: JSON.stringify({ repo_full_name: selectedRepo.full_name }),
      });
      setFact(data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "分析失败");
    } finally {
      setAnalyzing(false);
    }
  }

  async function doCheck() {
    if (!selectedRepo) return;
    setChecking(true);
    setError("");
    try {
      const data = await api<ConsistencyReport>("/api/v1/analysis/check-consistency", {
        method: "POST",
        body: JSON.stringify({ repo_full_name: selectedRepo.full_name }),
      });
      setReport(data);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "校验失败");
    } finally {
      setChecking(false);
    }
  }

  useEffect(() => {
    setSelectedRepo(null);
    setRepos([]);
    setConnected(false);
    setFact(null);
    setReport(null);
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
          <button className="ghost" onClick={() => { setSelectedRepo(null); setFact(null); setReport(null); }} style={{ marginBottom: 12 }}>
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
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <button className="ghost" onClick={doExtract} disabled={analyzing}>
                  {analyzing ? "分析中…" : "🔍 提取项目事实"}
                </button>
                {fact && (
                  <button className="ghost" onClick={doCheck} disabled={checking}>
                    {checking ? "校验中…" : "✓ 简历一致性校验"}
                  </button>
                )}
              </div>
            </div>

            {fact && (
              <div className="trace-detail" style={{ background: "#f5f8f4" }}>
                <h4 style={{ margin: "0 0 8px" }}>项目事实提取</h4>
                <div className="trace-meta">
                  <span>角色：{fact.extracted_role || "N/A"}</span>
                </div>
                <p style={{ fontSize: 13, margin: "4px 0 8px" }}>{fact.extracted_summary}</p>
                {fact.extracted_tech_stack && fact.extracted_tech_stack.length > 0 && (
                  <div style={{ marginBottom: 4 }}>
                    {fact.extracted_tech_stack.map((t: string) => (
                      <span key={t} className="skill-tag">{t}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {report && (
              <div className="trace-detail">
                <h4 style={{ margin: "0 0 8px" }}>
                  简历一致性报告 — 评分：{report.overall_score}/100
                </h4>
                <div style={{ marginBottom: 8, background: "#e8ede7", borderRadius: 8, height: 8, overflow: "hidden" }}>
                  <div style={{
                    width: `${report.overall_score}%`,
                    height: "100%",
                    background: report.overall_score >= 70 ? "var(--accent)" : report.overall_score >= 40 ? "#f0c040" : "#d14b4b",
                    borderRadius: 8,
                  }} />
                </div>

                {report.matched_items && report.matched_items.length > 0 && (
                  <div className="trace-step" style={{ borderLeft: "3px solid #2a7d4f" }}>
                    <div className="trace-step-header">
                      <span className="trace-step-name">✓ 匹配项 ({report.matched_items.length})</span>
                    </div>
                    <div className="trace-step-body">
                      {report.matched_items.map((m, i) => (
                        <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                          <span style={{ color: "#2a7d4f" }}>{m.item}</span>
                          <span className="muted" style={{ marginLeft: 8 }}>— {m.source}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {report.missing_in_resume && report.missing_in_resume.length > 0 && (
                  <div className="trace-step" style={{ borderLeft: "3px solid #f0c040" }}>
                    <div className="trace-step-header">
                      <span className="trace-step-name">⚠ 缺失项 ({report.missing_in_resume.length})</span>
                    </div>
                    <div className="trace-step-body">
                      {report.missing_in_resume.map((m, i) => (
                        <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                          <span style={{ color: "#9e7700" }}>{m.item}</span>
                          <span className="muted" style={{ marginLeft: 8 }}>— {m.evidence}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {report.conflicts && report.conflicts.length > 0 && (
                  <div className="trace-step" style={{ borderLeft: "3px solid #d14b4b" }}>
                    <div className="trace-step-header">
                      <span className="trace-step-name">✗ 矛盾项 ({report.conflicts.length})</span>
                    </div>
                    <div className="trace-step-body">
                      {report.conflicts.map((c, i) => (
                        <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                          <span style={{ color: "#9c3e36" }}>简历声称：{c.claim}</span>
                          <br />
                          <span className="muted">GitHub 实际：{c.reality}</span>
                          <span className="trace-badge" style={{ marginLeft: 8, fontSize: 11 }}>
                            {c.severity}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

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