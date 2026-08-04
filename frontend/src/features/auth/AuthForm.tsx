import { type FormEvent, useState } from "react";

import { api } from "../../api";
import type { User } from "../../types";

export function AuthForm({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
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
