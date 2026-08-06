import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import type { StudyPlan, StudyTask, Workspace } from "../../types";

const STATUS_LABELS: Record<string, string> = {
  pending: "待完成",
  completed: "已完成",
  postponed: "已延期",
  skipped: "已跳过",
  draft: "草稿",
  active: "进行中",
  archived: "已归档",
};

const STATUS_STYLE: Record<string, string> = {
  pending: "var(--color-muted)",
  completed: "var(--color-positive)",
  postponed: "var(--color-warning, #f0a020)",
  skipped: "var(--color-muted)",
};

function groupByDate(tasks: StudyTask[]): Map<string, StudyTask[]> {
  const map = new Map<string, StudyTask[]>();
  for (const task of tasks) {
    const key = task.scheduled_date;
    const list = map.get(key) || [];
    list.push(task);
    map.set(key, list);
  }
  return map;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric", weekday: "short" });
}

export function PlansView({ workspace, onBack, onTraces }: { workspace: Workspace; onBack: () => void; onTraces?: () => void }) {
  const [plans, setPlans] = useState<StudyPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedPlan, setExpandedPlan] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [startDate, setStartDate] = useState(todayStr());
  const [endDate, setEndDate] = useState(
    new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10)
  );
  const [dailyMinutes, setDailyMinutes] = useState(120);

  const loadPlans = useCallback(async () => {
    try {
      setPlans(await api<StudyPlan[]>(`/api/v1/workspaces/${workspace.id}/plans`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [workspace.id]);

  useEffect(() => {
    void loadPlans();
  }, [loadPlans]);

  async function createPlan(event: FormEvent) {
    event.preventDefault();
    setGenerating(true);
    setError("");
    try {
      const plan = await api<StudyPlan>(`/api/v1/workspaces/${workspace.id}/plans`, {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, daily_minutes: dailyMinutes }),
      });
      setPlans((items) => [plan, ...items]);
      setShowCreate(false);
      setExpandedPlan(plan.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成失败");
    } finally {
      setGenerating(false);
    }
  }

  async function patchTask(planId: string, taskId: string, updates: Record<string, unknown>) {
    try {
      await api<StudyTask>(
        `/api/v1/workspaces/${workspace.id}/plans/${planId}/tasks/${taskId}`,
        { method: "PATCH", body: JSON.stringify(updates) }
      );
      await loadPlans();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "更新失败");
    }
  }

  async function archivePlan(planId: string) {
    if (!window.confirm("归档后不能再修改任务，确认吗？")) return;
    try {
      await api(`/api/v1/workspaces/${workspace.id}/plans/${planId}/archive`, { method: "POST" });
      await loadPlans();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "归档失败");
    }
  }

  return (
    <section className="plan-view">
      <header className="view-header">
        <div>
          <button className="ghost" onClick={onBack}>← 返回</button>
          <h1>学习计划</h1>
          <p className="muted">{workspace.name}</p>
        </div>
        {onTraces && <button className="ghost" onClick={onTraces}>运行轨迹 →</button>}
        <button
          className="primary"
          onClick={() => setShowCreate(true)}
          disabled={plans.some((p) => p.status === "active")}
        >
          {plans.some((p) => p.status === "active") ? "已有进行中计划" : "＋ 生成新计划"}
        </button>
      </header>

      {showCreate && (
        <form className="plan-create-form" onSubmit={createPlan}>
          <h3>生成学习计划</h3>
          <div className="form-row">
            <label>
              开始日期
              <input type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>
            <label>
              结束日期
              <input type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </label>
            <label>
              每日可用时长（分钟）
              <input
                type="number"
                min={30}
                max={480}
                value={dailyMinutes}
                onChange={(e) => setDailyMinutes(Number(e.target.value))}
              />
            </label>
          </div>
          <div className="form-actions">
            <button className="primary" disabled={generating}>
              {generating ? "生成中…" : "生成计划"}
            </button>
            <button className="ghost" type="button" onClick={() => setShowCreate(false)}>
              取消
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="muted">正在加载学习计划…</p>
      ) : plans.length === 0 ? (
        <div className="empty-card">
          <h2>还没有学习计划</h2>
          <p className="muted">点击上方按钮，根据你的能力差距和面试表现自动生成每日学习任务。</p>
        </div>
      ) : (
        <div className="plan-list">
          {plans.map((plan) => {
            const isExpanded = expandedPlan === plan.id;
            const grouped = groupByDate(plan.tasks);
            return (
              <article key={plan.id} className={`plan-card ${isExpanded ? "expanded" : ""}`}>
                <header
                  className="plan-card-header"
                  onClick={() => setExpandedPlan(isExpanded ? null : plan.id)}
                >
                  <div>
                    <h3>{plan.goal}</h3>
                    <p className="muted">
                      {plan.start_date} ~ {plan.end_date} · 版本 {plan.version} ·{" "}
                      {STATUS_LABELS[plan.status] || plan.status}
                    </p>
                  </div>
                  <div className="plan-meta">
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${plan.coverage}%` }}
                      />
                    </div>
                    <span className="progress-text">
                      {plan.completed_tasks}/{plan.total_tasks} ({plan.coverage}%)
                    </span>
                    {plan.status === "active" && (
                      <button
                        className="ghost small"
                        onClick={(e) => { e.stopPropagation(); archivePlan(plan.id); }}
                      >
                        归档
                      </button>
                    )}
                  </div>
                </header>
                {isExpanded && (
                  <div className="plan-tasks">
                    {Array.from(grouped.entries()).map(([dateStr, tasks]) => (
                      <div key={dateStr} className="day-group">
                        <h4 className="day-label">{formatDate(dateStr)}</h4>
                        {tasks.map((task) => (
                          <div
                            key={task.id}
                            className={`task-item ${task.status}`}
                          >
                            <div className="task-info">
                              <span className="task-title">
                                {task.competency_name && (
                                  <span className="task-tag">{task.competency_name}</span>
                                )}
                                {task.title}
                              </span>
                              <p className="task-desc">{task.description}</p>
                              <span className="task-duration">
                                {task.duration_minutes} 分钟 · 优先级 {task.priority}
                              </span>
                            </div>
                            <div className="task-status">
                              <span style={{ color: STATUS_STYLE[task.status] }}>
                                {STATUS_LABELS[task.status] || task.status}
                              </span>
                              {plan.status === "active" && task.status === "pending" && (
                                <div className="task-actions">
                                  <button
                                    className="primary small"
                                    onClick={() => patchTask(plan.id, task.id, { status: "completed" })}
                                  >
                                    完成
                                  </button>
                                  <button
                                    className="ghost small"
                                    onClick={() => patchTask(plan.id, task.id, { status: "postponed" })}
                                  >
                                    延期
                                  </button>
                                  <button
                                    className="ghost small"
                                    onClick={() => patchTask(plan.id, task.id, { status: "skipped" })}
                                  >
                                    跳过
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
      {error && <div className="toast" role="alert">{error}</div>}
    </section>
  );
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}