import { useEffect, useState } from "react";

import { api } from "./api";
import { AuthForm } from "./features/auth/AuthForm";
import { WorkspaceApp } from "./features/workspaces/WorkspaceApp";
import type { User } from "./types";

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

  if (checking) return <div className="loading-screen"><div className="brand-mark">CP</div></div>;
  if (!user) return <AuthForm onAuthenticated={setUser} />;
  return <WorkspaceApp user={user} onLogout={logout} />;
}
