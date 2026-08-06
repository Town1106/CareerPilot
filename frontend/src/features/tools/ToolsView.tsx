import { useEffect, useState } from "react";

import { api } from "../../api";
import type { ApprovalItem, ToolDetail, ToolItem, Workspace } from "../../types";

const RISK_LABELS: Record<string, string> = {
  R0: "只读",
  R1: "低风险写入",
  R2: "外部写入",
  R3: "高风险",
};

export function ToolsView({ workspace, onBack, onGitHub }: { workspace: Workspace; onBack: () => void; onGitHub?: () => void }) {
  const [tools, setTools] = useState<ToolItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<ToolDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);

  async function loadTools() {
    setLoading(true);
    try {
      const data = await api<{ tools: ToolItem[] }>("/api/v1/tools");
      setTools(data.tools);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadApprovals() {
    setApprovalsLoading(true);
    try {
      const data = await api<{ approvals: ApprovalItem[] }>("/api/v1/tools/approvals/pending");
      setApprovals(data.approvals);
    } catch {
      // 忽略审批加载错误
    } finally {
      setApprovalsLoading(false);
    }
  }

  useEffect(() => {
    void loadTools();
    void loadApprovals();
  }, []);

  async function toggleDetail(name: string) {
    if (expanded === name) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(name);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await api<ToolDetail>(`/api/v1/tools/${name}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载详情失败");
    } finally {
      setDetailLoading(false);
    }
  }

  async function decideApproval(id: string, approve: boolean) {
    try {
      await api(`/api/v1/tools/approvals/${id}/decide`, {
        method: "POST",
        body: JSON.stringify({ approve }),
      });
      setApprovals((prev) => prev.filter((a) => a.id !== id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "审批失败");
    }
  }

  return (
    <div className="view">
      <header className="view-header">
        <button className="ghost" onClick={onBack}>← 返回</button>
        <div>
          <h1>工具中心</h1>
          <p className="muted">Agent 可调用的工具目录与审批策略</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ghost" onClick={loadApprovals}>刷新审批</button>
          <button className="ghost" onClick={loadTools}>刷新</button>
          {onGitHub && <button className="ghost" onClick={onGitHub}>GitHub →</button>}
        </div>
      </header>

      {approvals.length > 0 && (
        <div className="trace-list" style={{ marginBottom: 24 }}>
          <h3 style={{ margin: "0 0 8px 0", color: "var(--text-muted)" }}>
            待审批 ({approvals.length})
          </h3>
          {approvals.map((a) => (
            <div key={a.id} className="trace-card" style={{ borderLeft: "3px solid var(--accent)" }}>
              <div className="trace-summary">
                <div className="trace-left">
                  <span className="trace-badge" style={{ background: "#fcf2db", color: "#9e7700" }}>
                    {a.tool_name}
                  </span>
                  {a.requested_by_skill && (
                    <span className="trace-type" style={{ fontSize: 13 }}>
                      由 {a.requested_by_skill} 触发
                    </span>
                  )}
                </div>
                <div className="trace-right">
                  <span className="trace-time">
                    {new Date(a.created_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>
              <div style={{ padding: "0 16px 8px" }}>
                <p className="muted" style={{ fontSize: 13 }}>{a.payload_summary}</p>
              </div>
              <div style={{ padding: "0 16px 12px", display: "flex", gap: 8 }}>
                <button className="ghost" onClick={() => decideApproval(a.id, true)}>
                  ✓ 批准
                </button>
                <button className="ghost" onClick={() => decideApproval(a.id, false)}>
                  ✗ 拒绝
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="empty-card">正在加载…</div>
      ) : tools.length === 0 ? (
        <div className="empty-card">
          <p className="eyebrow">NO TOOLS</p>
          <h2>暂无已注册工具</h2>
          <p className="muted">工具注册后会自动出现在这里。</p>
        </div>
      ) : (
        <div className="trace-list">
          <p className="muted" style={{ marginBottom: 12 }}>共 {tools.length} 个工具</p>
          {tools.map((t) => (
            <div key={t.id} className="trace-card completed">
              <div className="trace-summary" onClick={() => toggleDetail(t.name)}>
                <div className="trace-left">
                  <span className="trace-badge completed">
                    {RISK_LABELS[t.risk_level] || t.risk_level}
                  </span>
                  <span className="trace-type">{t.name}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: 13, marginLeft: 8 }}>
                    v{t.version}
                  </span>
                </div>
                <div className="trace-right">
                  <span className="trace-time">{t.status}</span>
                  <span className="trace-expand">{expanded === t.name ? "▲" : "▼"}</span>
                </div>
              </div>
              <div style={{ padding: "0 16px 8px" }}>
                <p className="muted" style={{ fontSize: 13 }}>{t.description}</p>
              </div>
              {expanded === t.name && (
                <div className="trace-detail">
                  {detailLoading ? (
                    <div className="muted">加载中…</div>
                  ) : detail ? (
                    <div>
                      <div className="trace-meta">
                        <span>路径：{detail.manifest_path}</span>
                        <span style={{ marginLeft: 16 }}>
                          审批：{detail.require_approval ? "需要" : "自动批准"}
                        </span>
                      </div>
                      {detail.approval_prompt && (
                        <div className="trace-meta">
                          <span>审批提示：{detail.approval_prompt}</span>
                        </div>
                      )}
                      {detail.input_schema && (
                        <div className="trace-step">
                          <div className="trace-step-header">
                            <span className="trace-step-name">输入 Schema</span>
                          </div>
                          <div className="trace-step-body">
                            <pre style={{ fontSize: 12, margin: 0, whiteSpace: "pre-wrap" }}>
                              {detail.input_schema}
                            </pre>
                          </div>
                        </div>
                      )}
                      {detail.output_schema && (
                        <div className="trace-step">
                          <div className="trace-step-header">
                            <span className="trace-step-name">输出 Schema</span>
                          </div>
                          <div className="trace-step-body">
                            <pre style={{ fontSize: 12, margin: 0, whiteSpace: "pre-wrap" }}>
                              {detail.output_schema}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="muted">暂无详情</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {error && <div className="toast" role="alert">{error}</div>}
    </div>
  );
}