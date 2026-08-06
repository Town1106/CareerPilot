import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../../api";
import type { User, Workspace } from "../../types";
import { DocumentsView } from "../documents/DocumentsView";
import { GitHubView } from "../github/GitHubView";
import { InterviewsView } from "../interviews/InterviewsView";
import { JobsView } from "../jobs/JobsView";
import { PlansView } from "../plans/PlansView";
import { SkillsView } from "../skills/SkillsView";
import { ToolsView } from "../tools/ToolsView";
import { TracesView } from "../traces/TracesView";

export function WorkspaceApp({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [workspaceView, setWorkspaceView] = useState<"documents" | "jobs" | "interviews" | "plans" | "traces" | "skills" | "tools" | "github">("documents");

  const loadWorkspaces = useCallback(async () => {
    try {
      setWorkspaces(await api<Workspace[]>("/api/v1/workspaces"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  async function createWorkspace(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const workspace = await api<Workspace>("/api/v1/workspaces", {
        method: "POST",
        body: JSON.stringify({ name, target_role: targetRole || null }),
      });
      setWorkspaces((items) => [...items, workspace]);
      setName("");
      setTargetRole("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建失败");
    }
  }

  async function renameWorkspace(workspace: Workspace) {
    const nextName = window.prompt("新的工作空间名称", workspace.name)?.trim();
    if (!nextName || nextName === workspace.name) return;
    try {
      const updated = await api<Workspace>("/api/v1/workspaces/" + workspace.id, {
        method: "PATCH",
        body: JSON.stringify({ name: nextName }),
      });
      setWorkspaces((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重命名失败");
    }
  }

  async function removeWorkspace(workspace: Workspace) {
    if (!window.confirm("确定删除“" + workspace.name + "”吗？")) return;
    try {
      await api<void>("/api/v1/workspaces/" + workspace.id, { method: "DELETE" });
      setWorkspaces((items) => items.filter((item) => item.id !== workspace.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除失败");
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark small">CP</div>
          <span>CareerPilot</span>
        </div>
        <div className="account">
          <span>{user.email}</span>
          <button className="ghost" onClick={onLogout}>退出</button>
        </div>
      </header>

      {selectedWorkspace ? (
        workspaceView === "documents" ? (
          <DocumentsView
            workspace={selectedWorkspace}
            onBack={() => setSelectedWorkspace(null)}
            onJobs={() => setWorkspaceView("jobs")}
          />
        ) : workspaceView === "jobs" ? (
          <JobsView
            workspace={selectedWorkspace}
            onBack={() => setWorkspaceView("documents")}
            onInterviews={() => setWorkspaceView("interviews")}
          />
        ) : workspaceView === "interviews" ? (
          <InterviewsView
            workspace={selectedWorkspace}
            onBack={() => setWorkspaceView("jobs")}
            onPlans={() => setWorkspaceView("plans")}
          />
        ) : workspaceView === "plans" ? (
          <PlansView workspace={selectedWorkspace} onBack={() => setWorkspaceView("interviews")} onTraces={() => setWorkspaceView("traces")} onSkills={() => setWorkspaceView("skills")} />
        ) : workspaceView === "traces" ? (
          <TracesView workspace={selectedWorkspace} onBack={() => setWorkspaceView("plans")} />
        ) : workspaceView === "skills" ? (
          <SkillsView workspace={selectedWorkspace} onBack={() => setWorkspaceView("traces")} onTools={() => setWorkspaceView("tools")} />
        ) : workspaceView === "tools" ? (
          <ToolsView workspace={selectedWorkspace} onBack={() => setWorkspaceView("skills")} onGitHub={() => setWorkspaceView("github")} />
        ) : (
          <GitHubView workspace={selectedWorkspace} onBack={() => setWorkspaceView("tools")} />
        )
      ) : <><section className="workspace-hero">
        <div>
          <p className="eyebrow">YOUR WORKSPACES</p>
          <h1>选择你的下一段旅程</h1>
          <p className="muted">每个工作空间独立保存岗位、资料、面试和学习计划。</p>
        </div>
        <div className="status-pill"><span /> API 已连接</div>
      </section>

      <section className="workspace-grid">
        <form className="new-workspace" onSubmit={createWorkspace}>
          <div className="plus">＋</div>
          <h2>创建工作空间</h2>
          <label>
            名称
            <input
              required
              maxLength={100}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：秋招 Java 后端"
            />
          </label>
          <label>
            目标岗位
            <input
              maxLength={100}
              value={targetRole}
              onChange={(event) => setTargetRole(event.target.value)}
              placeholder="例如：后端开发工程师"
            />
          </label>
          <button className="primary">创建</button>
        </form>

        {loading ? (
          <div className="empty-card">正在加载工作空间…</div>
        ) : workspaces.length === 0 ? (
          <div className="empty-card">
            <p className="eyebrow">EMPTY, FOR NOW</p>
            <h2>从左侧创建第一个目标</h2>
            <p className="muted">下一步将可以上传简历与岗位 JD。</p>
          </div>
        ) : (
          workspaces.map((workspace, index) => (
            <article className="workspace-card" key={workspace.id}>
              <span className="index">{String(index + 1).padStart(2, "0")}</span>
              <p className="eyebrow">{workspace.target_role || "目标待设置"}</p>
              <h2>{workspace.name}</h2>
              <p className="muted">
                创建于 {new Date(workspace.created_at).toLocaleDateString("zh-CN")}
              </p>
              <div className="card-actions">
                <button className="primary" onClick={() => { setSelectedWorkspace(workspace); setWorkspaceView("documents"); }}>打开知识库</button>
                <button className="ghost" onClick={() => renameWorkspace(workspace)}>重命名</button>
                <button className="danger" onClick={() => removeWorkspace(workspace)}>删除</button>
              </div>
            </article>
          ))
        )}
      </section>
      </>}
      {error && <div className="toast" role="alert">{error}</div>}
    </main>
  );
}
