import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import type { CompetencyMemory, Interview, Job, Workspace } from "../../types";

const TYPE_NAMES: Record<string, string> = {
  mixed: "综合面试",
  technical: "技术基础",
  project: "项目深挖",
  system_design: "系统设计",
  behavioral: "行为面试",
};

const STATUS_NAMES: Record<string, string> = {
  draft: "待开始",
  in_progress: "进行中",
  completed: "已完成",
};

export function InterviewsView({ workspace, onBack, onPlans }: { workspace: Workspace; onBack: () => void; onPlans: () => void }) {
  const base = `/api/v1/workspaces/${workspace.id}`;
  const [jobs, setJobs] = useState<Job[]>([]);
  const [sessions, setSessions] = useState<Interview[]>([]);
  const [memories, setMemories] = useState<CompetencyMemory[]>([]);
  const [current, setCurrent] = useState<Interview | null>(null);
  const [jobId, setJobId] = useState("");
  const [interviewType, setInterviewType] = useState("mixed");
  const [questionLimit, setQuestionLimit] = useState(10);
  const [questionSourceMode, setQuestionSourceMode] = useState<"all_real" | "mixed" | "no_search">("mixed");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [jobItems, interviewItems, memoryItems] = await Promise.all([
        api<Job[]>(`${base}/jobs`),
        api<Interview[]>(`${base}/interviews`),
        api<CompetencyMemory[]>(`${base}/memories`),
      ]);
      const analyzed = jobItems.filter((job) => job.status === "analyzed");
      setJobs(analyzed);
      setSessions(interviewItems);
      setMemories(memoryItems);
      setJobId((value) => value || analyzed[0]?.id || "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载模拟面试失败");
    }
  }, [base]);

  useEffect(() => {
    void load();
  }, [load]);

  function replaceSession(session: Interview) {
    setCurrent(session);
    setSessions((items) => [session, ...items.filter((item) => item.id !== session.id)]);
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api<Interview>(`${base}/interviews`, {
        method: "POST",
        body: JSON.stringify({
          job_description_id: jobId,
          interview_type: interviewType,
          question_limit: questionLimit,
          question_source_mode: questionSourceMode,
        }),
      });
      replaceSession(await api<Interview>(`${base}/interviews/${created.id}/start`, {
        method: "POST",
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建面试失败");
    } finally {
      setBusy(false);
    }
  }

  async function open(session: Interview) {
    setBusy(true);
    setError("");
    try {
      let detail = await api<Interview>(`${base}/interviews/${session.id}`);
      if (detail.status === "draft") {
        detail = await api<Interview>(`${base}/interviews/${session.id}/start`, { method: "POST" });
      }
      replaceSession(detail);
      setAnswer("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "打开面试失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(event: FormEvent) {
    event.preventDefault();
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Interview>(`${base}/interviews/${current.id}/answers`, {
        method: "POST",
        body: JSON.stringify({ answer }),
      });
      replaceSession(updated);
      setAnswer("");
      if (updated.status === "completed") {
        setMemories(await api<CompetencyMemory[]>(`${base}/memories`));
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交回答失败");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    if (!current || !window.confirm("确定提前结束并生成评分报告吗？")) return;
    setBusy(true);
    setError("");
    try {
      replaceSession(await api<Interview>(`${base}/interviews/${current.id}/finish`, {
        method: "POST",
      }));
      setMemories(await api<CompetencyMemory[]>(`${base}/memories`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成报告失败");
    } finally {
      setBusy(false);
    }
  }

  async function confirmMemory(memory: CompetencyMemory) {
    try {
      const updated = await api<CompetencyMemory>(`${base}/memories/${memory.id}`, {
        method: "PATCH",
        body: JSON.stringify({ confirmed: true }),
      });
      setMemories((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认记忆失败");
    }
  }

  async function editMemory(memory: CompetencyMemory) {
    const value = window.prompt("掌握度（0-100）", String(memory.mastery_score));
    if (value === null) return;
    const score = Number(value);
    if (!Number.isFinite(score) || score < 0 || score > 100) {
      setError("掌握度必须是 0 到 100 之间的数字");
      return;
    }
    const summary = window.prompt("证据与备注", memory.evidence_summary);
    if (!summary?.trim()) return;
    try {
      const updated = await api<CompetencyMemory>(`${base}/memories/${memory.id}`, {
        method: "PATCH",
        body: JSON.stringify({ mastery_score: score, evidence_summary: summary, confirmed: true }),
      });
      setMemories((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "修改记忆失败");
    }
  }

  async function removeMemory(memory: CompetencyMemory) {
    if (!window.confirm(`确定删除“${memory.competency_name}”能力记忆吗？`)) return;
    try {
      await api<void>(`${base}/memories/${memory.id}`, { method: "DELETE" });
      setMemories((items) => items.filter((item) => item.id !== memory.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除记忆失败");
    }
  }

  const pendingTurn = current?.status === "in_progress"
    ? current.turns.find((turn) => turn.answer === null)
    : null;

  return <section className="knowledge-shell interview-shell">
    <button className="text-button back-button" onClick={onBack}>← 返回岗位分析</button>
    <div className="knowledge-header">
      <div><p className="eyebrow">ADAPTIVE INTERVIEW · {workspace.target_role || "目标岗位"}</p><h1>模拟面试与能力记忆</h1><p className="muted">根据岗位缺口动态追问，结束后统一评分。</p></div>
      <button className="primary" onClick={onPlans}>查看学习计划 →</button>
    </div>

    <div className="interview-grid">
      <form className="job-form" onSubmit={create}>
        <p className="eyebrow">NEW SESSION</p><h2>开始一场面试</h2>
        <label>目标岗位<select required value={jobId} onChange={(event) => setJobId(event.target.value)}><option value="">请选择已分析岗位</option>{jobs.map((job) => <option key={job.id} value={job.id}>{job.company} · {job.title}</option>)}</select></label>
        <label>面试方向<select value={interviewType} onChange={(event) => setInterviewType(event.target.value)}>{Object.entries(TYPE_NAMES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>题目数量<input type="number" min={3} max={15} value={questionLimit} onChange={(event) => setQuestionLimit(Number(event.target.value))} /></label>
        <fieldset className="source-mode">
          <legend>题目来源</legend>
          <label><input type="radio" name="question-source" value="all_real" checked={questionSourceMode === "all_real"} onChange={() => setQuestionSourceMode("all_real")} />搜索真实面经并全部使用</label>
          <label><input type="radio" name="question-source" value="mixed" checked={questionSourceMode === "mixed"} onChange={() => setQuestionSourceMode("mixed")} />搜索真实面经但混合使用</label>
          <label><input type="radio" name="question-source" value="no_search" checked={questionSourceMode === "no_search"} onChange={() => setQuestionSourceMode("no_search")} />不搜索面经</label>
        </fieldset>
        {questionSourceMode !== "no_search" && <p className="muted">开始面试时会联网搜索新题；没有新题时会复用该公司和岗位已保存的题目。</p>}
        <button className="primary" disabled={busy || !jobId}>{busy ? "正在准备…" : "开始模拟面试"}</button>
        {jobs.length === 0 && <p className="muted">请先在岗位分析页完成至少一个 JD 分析。</p>}
      </form>

      <section className="job-list-card"><div className="documents-title"><div><p className="eyebrow">HISTORY</p><h2>面试记录</h2></div><strong>{sessions.length}</strong></div>
        {sessions.length === 0 ? <div className="documents-empty">还没有面试记录。</div> : sessions.map((session) => <article className="session-row" key={session.id}>
          <div><h3>{session.job_name || "岗位已删除"}</h3><p>{TYPE_NAMES[session.interview_type]} · {STATUS_NAMES[session.status] || session.status} · {session.turns.filter((turn) => turn.answer).length}/{session.question_limit} 题</p></div>
          <strong>{session.overall_score === null ? "—" : `${session.overall_score} 分`}</strong>
          <button className="ghost" disabled={busy} onClick={() => void open(session)}>{session.status === "completed" ? "查看报告" : "继续"}</button>
        </article>)}
      </section>
    </div>

    {current?.status === "in_progress" && pendingTurn && <section className="interview-room">
      <div className="question-meta"><span>第 {pendingTurn.sequence} / {current.question_limit} 题</span><span>{pendingTurn.source_type === "company_research" ? "公司面经" : "岗位能力缺口"} · {pendingTurn.competency_name}{pendingTurn.is_follow_up ? " · 追问" : ""}</span></div>
      <h2>{pendingTurn.question}</h2>
      {pendingTurn.source_url && <a className="question-source" href={pendingTurn.source_url} target="_blank" rel="noreferrer">查看面经来源 ↗</a>}
      <form onSubmit={submitAnswer}><textarea required minLength={1} maxLength={5000} value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="像真实面试一样作答，建议说明原理、场景和取舍。" /><div className="room-actions"><button className="primary" disabled={busy}>{busy ? "面试官思考中…" : "提交回答"}</button><button type="button" className="ghost" disabled={busy || !current.turns.some((turn) => turn.answer)} onClick={() => void finish()}>提前结束</button></div></form>
      <details className="answer-history"><summary>查看已回答内容</summary>{current.turns.filter((turn) => turn.answer).map((turn) => <div key={turn.id}><strong>Q{turn.sequence} · {turn.source_type === "company_research" ? "公司面经" : "岗位缺口"} · {turn.competency_name}</strong><p>{turn.question}</p><p className="muted">{turn.answer}</p></div>)}</details>
    </section>}

    {current?.status === "completed" && <section className="interview-report"><div className="analysis-heading"><div><p className="eyebrow">INTERVIEW REPORT</p><h2>{current.job_name}</h2></div><strong>{current.overall_score} 分</strong></div><p>{current.report_summary}</p>
      <div className="report-columns"><div><h3>优点</h3>{current.report_strengths.map((item) => <p key={item}>＋ {item}</p>)}</div><div><h3>待改进</h3>{current.report_issues.map((item) => <p key={item}>－ {item}</p>)}</div></div>
      <div className="score-list">{current.scores.map((score) => <article key={score.id}><div><h3>{score.competency_name}</h3><strong>{score.score}</strong></div><p><b>评分标准：</b>{score.rubric}</p><p><b>回答证据：</b>{score.evidence.join("；")}</p><p><b>改进建议：</b>{score.suggestion}</p></article>)}</div>
    </section>}

    <section className="memory-card"><p className="eyebrow">COMPETENCY MEMORY</p><h2>能力记忆</h2><p className="muted">面试推断默认待确认；你可以修改或删除。</p>
      {memories.length === 0 ? <div className="documents-empty">完成面试后会在这里沉淀能力记录。</div> : <div className="memory-list">{memories.map((memory) => <article key={memory.id}><div className="memory-score"><strong>{memory.mastery_score}</strong><span>掌握度</span></div><div><h3>{memory.competency_name}</h3><p>{memory.evidence_summary}</p><small>{memory.confirmed ? "已确认" : "待确认"} · 历史薄弱 {memory.error_count} 次</small></div><div className="document-actions">{!memory.confirmed && <button className="ghost" onClick={() => void confirmMemory(memory)}>确认</button>}<button className="ghost" onClick={() => void editMemory(memory)}>修改</button><button className="danger" onClick={() => void removeMemory(memory)}>删除</button></div></article>)}</div>}
    </section>
    {error && <div className="toast" role="alert">{error}</div>}
  </section>;
}
