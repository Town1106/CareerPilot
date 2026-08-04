import { FormEvent, useCallback, useEffect, useState } from "react";

type User = {
  id: string;
  email: string;
};

type Workspace = {
  id: string;
  name: string;
  target_role: string | null;
  created_at: string;
};

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || "请求失败，请稍后重试");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}

function AuthForm({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const user = await api<User>("/api/v1/auth/" + mode, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      onAuthenticated(user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "请求失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="intro">
        <div className="brand-mark">CP</div>
        <p className="eyebrow">CAREER INTELLIGENCE</p>
        <h1>让每一次准备，都有证据可循。</h1>
        <p className="intro-copy">
          CareerPilot 将岗位要求、个人经历与训练结果连成一条可追溯的成长路径。
        </p>
        <div className="feature-row">
          <span>岗位差距</span>
          <span>项目证据</span>
          <span>模拟面试</span>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <p className="eyebrow">{mode === "login" ? "WELCOME BACK" : "GET STARTED"}</p>
          <h2>{mode === "login" ? "继续你的求职计划" : "创建 CareerPilot 账户"}</h2>
          <p className="muted">
            {mode === "login" ? "登录后查看工作空间。" : "从一个目标岗位开始。"}
          </p>

          <form onSubmit={submit}>
            <label>
              邮箱
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label>
              密码
              <input
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength={8}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="至少 8 位"
              />
            </label>
            {error && <p className="error" role="alert">{error}</p>}
            <button className="primary" disabled={submitting}>
              {submitting ? "请稍候…" : mode === "login" ? "登录" : "注册"}
            </button>
          </form>

          <button
            className="text-button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "没有账户？立即注册" : "已有账户？返回登录"}
          </button>
        </div>
      </section>
    </main>
  );
}

function WorkspaceApp({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

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

      <section className="workspace-hero">
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
                <button className="ghost" onClick={() => renameWorkspace(workspace)}>重命名</button>
                <button className="danger" onClick={() => removeWorkspace(workspace)}>删除</button>
              </div>
            </article>
          ))
        )}
      </section>
      {error && <div className="toast" role="alert">{error}</div>}
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api<User>("/api/v1/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  async function logout() {
    await api<void>("/api/v1/auth/logout", { method: "POST" });
    setUser(null);
  }

  if (checking) {
    return <div className="loading-screen"><div className="brand-mark">CP</div></div>;
  }
  if (!user) {
    return <AuthForm onAuthenticated={setUser} />;
  }
  return <WorkspaceApp user={user} onLogout={logout} />;
}

