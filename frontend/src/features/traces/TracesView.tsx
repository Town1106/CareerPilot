import { useEffect, useState } from "react";

import { api } from "../../api";
import type { Run, RunDetail, RunList, RunStep, Workspace } from "../../types";

const RUN_TYPE_LABELS: Record<string, string> = {
  rag_qa: "RAG 问答",
  jd_analysis: "JD 分析",
  interview_generate_question: "生成题目",
  interview_assess: "回答评估",
  interview_report: "面试报告",
  interview_search: "面经搜索",
  plan_generate: "计划生成",
};

const STATUS_LABELS: Record<string, string> = {
  completed: "成功",
  failed: "失败",
  running: "进行中",
};

const STEP_LABELS: Record<string, string> = {
  retrieve: "检索",
  generate: "生成",
  extract_requirements: "抽取要求",
  retrieve_evidence: "检索证据",
  judge_evidence: "核验证据",
  assess: "评估",
  generate_report: "生成报告",
  search: "搜索",
};

export function TracesView({ workspace, onBack }: { workspace: Workspace; onBack: () => void }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function loadRuns() {
    setLoading(true);
    try {
      const data = await api<RunList>(`/api/v1/workspaces/${workspace.id}/runs?limit=50`);
      setRuns(data.runs);
      setTotal(data.total);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, [workspace.id]);

  async function toggleDetail(runId: string) {
    if (expanded === runId) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(runId);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await api<RunDetail>(`/api/v1/runs/${runId}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载详情失败");
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="view">
      <header className="view-header">
        <button className="ghost" onClick={onBack}>← 返回</button>
        <div>
          <h1>运行轨迹</h1>
          <p className="muted">AI 操作记录、Token 用量和检索结果</p>
        </div>
        <button className="ghost" onClick={loadRuns}>刷新</button>
      </header>

      {loading ? (
        <div className="empty-card">正在加载…</div>
      ) : runs.length === 0 ? (
        <div className="empty-card">
          <p className="eyebrow">NO TRACES</p>
          <h2>暂无运行记录</h2>
          <p className="muted">进行 RAG 问答、JD 分析、模拟面试或生成学习计划后，记录会出现在这里。</p>
        </div>
      ) : (
        <div className="trace-list">
          <p className="muted" style={{ marginBottom: 12 }}>共 {total} 条记录，显示最近 {runs.length} 条</p>
          {runs.map((run) => (
            <div key={run.id} className={`trace-card ${run.status}`}>
              <div className="trace-summary" onClick={() => toggleDetail(run.id)}>
                <div className="trace-left">
                  <span className={`trace-badge ${run.status}`}>
                    {STATUS_LABELS[run.status] || run.status}
                  </span>
                  <span className="trace-type">
                    {RUN_TYPE_LABELS[run.run_type] || run.run_type}
                  </span>
                </div>
                <div className="trace-right">
                  <span className="trace-tokens">{run.total_tokens} tokens</span>
                  <span className="trace-time">
                    {new Date(run.started_at).toLocaleTimeString("zh-CN")}
                  </span>
                  <span className="trace-expand">{expanded === run.id ? "▲" : "▼"}</span>
                </div>
              </div>
              {run.error_code && (
                <div className="trace-error">{run.error_code}</div>
              )}
              {expanded === run.id && (
                <div className="trace-detail">
                  {detailLoading ? (
                    <div className="muted">加载中…</div>
                  ) : detail ? (
                    <div>
                      <div className="trace-meta">
                        <span>模型：{detail.model_id || "—"}</span>
                        <span>Prompt：{detail.prompt_tokens} tokens</span>
                        <span>Completion：{detail.completion_tokens} tokens</span>
                      </div>
                      {detail.steps.map((step) => (
                        <div key={step.id} className="trace-step">
                          <div className="trace-step-header">
                            <span className={`trace-badge small ${step.status}`}>
                              {STATUS_LABELS[step.status] || step.status}
                            </span>
                            <span className="trace-step-name">
                              {STEP_LABELS[step.step_name] || step.step_name}
                            </span>
                            <span className="trace-step-time">
                              {step.latency_ms}ms
                            </span>
                          </div>
                          {step.input_summary && (
                            <div className="trace-step-body">
                              <span className="trace-label">输入：</span>
                              {step.input_summary}
                            </div>
                          )}
                          {step.output_summary && (
                            <div className="trace-step-body">
                              <span className="trace-label">输出：</span>
                              {step.output_summary}
                            </div>
                          )}
                          {step.retrieved_chunks && (() => {
                            try {
                              const chunks = JSON.parse(step.retrieved_chunks);
                              if (!Array.isArray(chunks) || chunks.length === 0) return null;
                              return (
                                <div className="trace-step-body">
                                  <span className="trace-label">检索到 {chunks.length} 条文档：</span>
                                  <ul className="trace-chunks">
                                    {chunks.map((c: any, i: number) => (
                                      <li key={i}>
                                        [{c.score}] {c.document} — {c.content}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              );
                            } catch {
                              return null;
                            }
                          })()}
                          {step.error_code && (
                            <div className="trace-step-error">{step.error_code}</div>
                          )}
                        </div>
                      ))}
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