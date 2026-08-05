import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import type { CompetencyGap, Job, JobAnalysis, JobComparison, Workspace } from "../../types";

const STATUS_NAMES: Record<string, string> = {
  draft: "待分析",
  analyzing: "分析中",
  analyzed: "已分析",
  failed: "分析失败",
};
const COVERAGE_NAMES: Record<string, string> = {
  covered: "已覆盖",
  partial: "部分覆盖",
  uncovered: "未覆盖",
  conflict: "证据冲突",
};
export function JobsView({ workspace, onBack, onInterviews }: { workspace: Workspace; onBack: () => void; onInterviews: () => void }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [creating, setCreating] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<JobAnalysis | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparison, setComparison] = useState<JobComparison | null>(null);
  const [gaps, setGaps] = useState<CompetencyGap[]>([]);
  const [error, setError] = useState("");
  const url = `/api/v1/workspaces/${workspace.id}/jobs`;

  const load = useCallback(async () => {
    try {
      const [jobItems, gapItems] = await Promise.all([
        api<Job[]>(url),
        api<CompetencyGap[]>(`/api/v1/workspaces/${workspace.id}/competency-gap`),
      ]);
      setJobs(jobItems);
      setGaps(gapItems);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载 JD 失败");
    }
  }, [url, workspace.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      const job = await api<Job>(url, {
        method: "POST",
        body: JSON.stringify({ company, title, raw_text: rawText }),
      });
      setJobs((items) => [job, ...items]);
      setCompany("");
      setTitle("");
      setRawText("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存 JD 失败");
    } finally {
      setCreating(false);
    }
  }

  async function analyze(job: Job) {
    setAnalyzingId(job.id);
    setError("");
    try {
      const result = await api<JobAnalysis>(`${url}/${job.id}/analyze`, { method: "POST" });
      setAnalysis(result);
      setJobs((items) => items.map((item) => item.id === job.id ? result.job : item));
      setGaps(await api<CompetencyGap[]>(`/api/v1/workspaces/${workspace.id}/competency-gap`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "分析 JD 失败");
      await load();
    } finally {
      setAnalyzingId(null);
    }
  }

  async function showAnalysis(job: Job) {
    try {
      setAnalysis(await api<JobAnalysis>(`${url}/${job.id}/requirements`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载分析结果失败");
    }
  }

  async function remove(job: Job) {
    if (!window.confirm(`确定删除“${job.company} · ${job.title}”吗？`)) return;
    try {
      await api<void>(`${url}/${job.id}`, { method: "DELETE" });
      setJobs((items) => items.filter((item) => item.id !== job.id));
      setSelectedIds((items) => items.filter((id) => id !== job.id));
      if (analysis?.job.id === job.id) setAnalysis(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除 JD 失败");
    }
  }

  async function compare() {
    try {
      setComparison(await api<JobComparison>(`${url}/compare`, {
        method: "POST",
        body: JSON.stringify({ job_ids: selectedIds }),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "比较岗位失败");
    }
  }

  function toggleSelection(jobId: string) {
    setSelectedIds((items) => items.includes(jobId)
      ? items.filter((id) => id !== jobId)
      : [...items, jobId]);
  }

  return (
    <section className="knowledge-shell jobs-shell">
      <button className="text-button back-button" onClick={onBack}>← 返回知识库</button>
      <div className="knowledge-header">
        <div>
          <p className="eyebrow">JOB GAP ANALYSIS · {workspace.target_role || "未设置岗位"}</p>
          <h1>岗位能力差距</h1>
          <p className="muted">将 JD 要求与当前版本的简历、项目资料逐项核验。</p>
        </div>
        <div className="header-actions">
          <button className="primary" onClick={onInterviews}>模拟面试</button>
          <button className="ghost" disabled={selectedIds.length < 2} onClick={() => void compare()}>
            比较已选岗位（{selectedIds.length}）
          </button>
        </div>
      </div>

      <div className="jobs-grid">
        <form className="job-form" onSubmit={create}>
          <p className="eyebrow">ADD JOB DESCRIPTION</p>
          <h2>录入目标岗位</h2>
          <label>公司<input required maxLength={120} value={company} onChange={(event) => setCompany(event.target.value)} /></label>
          <label>岗位<input required maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label>JD 原文<textarea required minLength={50} maxLength={30000} value={rawText} onChange={(event) => setRawText(event.target.value)} /></label>
          <button className="primary" disabled={creating}>{creating ? "保存中…" : "保存 JD"}</button>
        </form>

        <div className="job-list-card">
          <div className="documents-title"><div><p className="eyebrow">TARGETS</p><h2>目标岗位</h2></div><strong>{jobs.length}</strong></div>
          {jobs.length === 0 ? <div className="documents-empty">录入第一份 JD 后开始证据分析。</div> : jobs.map((job) => (
            <article className="job-row" key={job.id}>
              <input type="checkbox" aria-label="选择比较" disabled={job.status !== "analyzed"} checked={selectedIds.includes(job.id)} onChange={() => toggleSelection(job.id)} />
              <div><h3>{job.title}</h3><p>{job.company} · {STATUS_NAMES[job.status] || job.status}</p></div>
              <strong>{job.coverage_score === null ? "—" : `${job.coverage_score}%`}</strong>
              <div className="document-actions">
                <button className="ghost" disabled={analyzingId === job.id} onClick={() => void analyze(job)}>{analyzingId === job.id ? "分析中…" : job.status === "analyzed" ? "重新分析" : "开始分析"}</button>
                {job.status === "analyzed" && <button className="ghost" onClick={() => void showAnalysis(job)}>查看</button>}
                <button className="danger" onClick={() => void remove(job)}>删除</button>
              </div>
              {job.analysis_error && <p className="index-error">{job.analysis_error}</p>}
            </article>
          ))}
        </div>
      </div>

      {gaps.length > 0 && <section className="gap-card"><p className="eyebrow">PRIORITY GAPS</p><h2>跨岗位优先缺口</h2><div className="gap-list">{gaps.slice(0, 8).map((gap) => <div key={gap.competency}><strong>{gap.competency}</strong><span>{COVERAGE_NAMES[gap.worst_coverage]}</span><span>{gap.job_count} 个岗位</span></div>)}</div></section>}

      {analysis && <section className="analysis-card">
        <div className="analysis-heading"><div><p className="eyebrow">EVIDENCE MATRIX</p><h2>{analysis.job.company} · {analysis.job.title}</h2></div><strong>{analysis.job.coverage_score}%</strong></div>
        <div className="requirement-list">{analysis.requirements.map((item) => <article className={`requirement-row ${item.coverage}`} key={item.id}>
          <div><span className="coverage-badge">{COVERAGE_NAMES[item.coverage]}</span><h3>{item.competency}</h3><p>{item.raw_evidence}</p><p className="muted">{item.explanation}</p></div>
          {item.evidence.map((evidence) => <details key={evidence.chunk_id || evidence.original_name}><summary>{evidence.original_name || "来源已删除"}{evidence.page_number ? ` · 第 ${evidence.page_number} 页` : ""}</summary><p>{evidence.content || "原文已不可用"}</p></details>)}
        </article>)}</div>
      </section>}

      {comparison && <section className="analysis-card"><p className="eyebrow">JOB COMPARISON</p><h2>多岗位共同要求与差异</h2><h3>共同要求</h3><div className="comparison-tags">{comparison.common.map((item) => <span key={item.competency}>{item.competency}</span>)}</div><h3>差异要求</h3><div className="comparison-tags">{comparison.differences.map((item) => <span key={item.competency}>{item.competency}</span>)}</div></section>}
      {error && <div className="toast" role="alert">{error}</div>}
    </section>
  );
}
