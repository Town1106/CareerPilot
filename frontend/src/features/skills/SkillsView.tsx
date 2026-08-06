import { useEffect, useState } from "react";

import { api } from "../../api";
import type { SkillItem, SkillDetail, Workspace } from "../../types";

const RISK_LABELS: Record<string, string> = {
  R0: "只读",
  R1: "低风险写入",
  R2: "外部写入",
  R3: "高风险",
};

export function SkillsView({ workspace, onBack, onTools }: { workspace: Workspace; onBack: () => void; onTools?: () => void }) {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function loadSkills() {
    setLoading(true);
    try {
      const data = await api<{ skills: SkillItem[] }>("/api/v1/skills");
      setSkills(data.skills);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSkills();
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
      setDetail(await api<SkillDetail>(`/api/v1/skills/${name}`));
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
          <h1>技能中心</h1>
          <p className="muted">Agent 可用的领域技能与工具白名单</p>
        </div>
        <button className="ghost" onClick={loadSkills}>刷新</button>
        {onTools && <button className="ghost" onClick={onTools}>工具中心 →</button>}
      </header>

      {loading ? (
        <div className="empty-card">正在加载…</div>
      ) : skills.length === 0 ? (
        <div className="empty-card">
          <p className="eyebrow">NO SKILLS</p>
          <h2>暂无已注册技能</h2>
          <p className="muted">技能注册后会自动出现在这里。</p>
        </div>
      ) : (
        <div className="trace-list">
          <p className="muted" style={{ marginBottom: 12 }}>共 {skills.length} 个技能</p>
          {skills.map((skill) => (
            <div key={skill.id} className="trace-card completed">
              <div className="trace-summary" onClick={() => toggleDetail(skill.name)}>
                <div className="trace-left">
                  <span className="trace-badge completed">
                    {RISK_LABELS[skill.risk_level] || skill.risk_level}
                  </span>
                  <span className="trace-type">{skill.name}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: 13, marginLeft: 8 }}>
                    v{skill.version}
                  </span>
                </div>
                <div className="trace-right">
                  <span className="trace-time">{skill.status}</span>
                  <span className="trace-expand">{expanded === skill.name ? "▲" : "▼"}</span>
                </div>
              </div>
              <div style={{ padding: "0 16px 8px" }}>
                <p className="muted" style={{ fontSize: 13 }}>{skill.description}</p>
              </div>
              {expanded === skill.name && (
                <div className="trace-detail">
                  {detailLoading ? (
                    <div className="muted">加载中…</div>
                  ) : detail ? (
                    <div>
                      <div className="trace-meta">
                        <span>路径：{detail.manifest_path}</span>
                      </div>
                      {detail.triggers.length > 0 && (
                        <div className="trace-step">
                          <div className="trace-step-header">
                            <span className="trace-step-name">触发条件</span>
                          </div>
                          <div className="trace-step-body">
                            {detail.triggers.map((t, i) => (
                              <span key={i} className="skill-tag">{t}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {detail.required_inputs.length > 0 && (
                        <div className="trace-step">
                          <div className="trace-step-header">
                            <span className="trace-step-name">必需输入</span>
                          </div>
                          <div className="trace-step-body">
                            {detail.required_inputs.map((t, i) => (
                              <span key={i} className="skill-tag">{t}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {detail.allowed_tools.length > 0 && (
                        <div className="trace-step">
                          <div className="trace-step-header">
                            <span className="trace-step-name">允许工具</span>
                          </div>
                          <div className="trace-step-body">
                            {detail.allowed_tools.map((t, i) => (
                              <span key={i} className="skill-tag">{t}</span>
                            ))}
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