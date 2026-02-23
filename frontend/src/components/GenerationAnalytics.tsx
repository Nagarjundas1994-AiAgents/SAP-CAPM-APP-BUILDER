/**
 * GenerationAnalytics Component
 *
 * Displays post-generation analytics:
 * - Quality score with radial gauge
 * - Score breakdown by category (data model, service, etc.)
 * - Agent execution timeline
 * - Self-healing corrections applied
 * - File count and sizes
 */

import React from "react";

interface QualityBreakdown {
  data_model: number;
  service_layer: number;
  business_logic: number;
  fiori_ui: number;
  security: number;
  deployment: number;
}

interface QualityScore {
  total: number;
  breakdown: QualityBreakdown;
  details: string[];
}

interface AgentHistory {
  agent_name: string;
  status: string;
  started_at: string;
  completed_at: string;
  duration_ms: number | null;
  retry_count?: number;
  error: string | null;
}

interface CorrectionEntry {
  agent: string;
  summary: string;
  timestamp: string;
}

interface GenerationAnalyticsProps {
  qualityScore: QualityScore | null;
  agentHistory: AgentHistory[];
  autoFixedErrors: CorrectionEntry[];
  validationErrors: Array<{ severity: string; message: string; agent: string }>;
  fileCount: number;
}

const CATEGORY_LABELS: Record<string, string> = {
  data_model: "Data Model",
  service_layer: "Service Layer",
  business_logic: "Business Logic",
  fiori_ui: "Fiori UI",
  security: "Security",
  deployment: "Deployment",
};

const CATEGORY_ICONS: Record<string, string> = {
  data_model: "📊",
  service_layer: "🔗",
  business_logic: "⚙️",
  fiori_ui: "🎨",
  security: "🔒",
  deployment: "🚀",
};

function getScoreColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#eab308";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}

function getAgentLabel(name: string): string {
  return name
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function GenerationAnalytics({
  qualityScore,
  agentHistory,
  autoFixedErrors,
  validationErrors,
  fileCount,
}: GenerationAnalyticsProps) {
  const totalScore = qualityScore?.total ?? 0;
  const scoreColor = getScoreColor(totalScore);
  const errorCount = validationErrors.filter((e) => e.severity === "error").length;
  const warningCount = validationErrors.filter((e) => e.severity === "warning").length;

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>📈 Generation Analytics</h2>

      {/* Top summary cards */}
      <div style={styles.cardRow}>
        {/* Quality Score */}
        <div style={{ ...styles.card, ...styles.scoreCard }}>
          <div style={styles.scoreCircle}>
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle
                cx="50" cy="50" r="42"
                fill="none" stroke="#334155" strokeWidth="8"
              />
              <circle
                cx="50" cy="50" r="42"
                fill="none" stroke={scoreColor} strokeWidth="8"
                strokeDasharray={`${(totalScore / 100) * 264} 264`}
                strokeLinecap="round"
                transform="rotate(-90 50 50)"
                style={{ transition: "stroke-dasharray 1s ease" }}
              />
              <text x="50" y="50" textAnchor="middle" dominantBaseline="central"
                fill={scoreColor} fontSize="22" fontWeight="700">
                {totalScore}
              </text>
            </svg>
          </div>
          <div style={styles.scoreLabel}>Quality Score</div>
        </div>

        {/* Files */}
        <div style={styles.card}>
          <div style={styles.statNumber}>{fileCount}</div>
          <div style={styles.statLabel}>Files Generated</div>
        </div>

        {/* Errors */}
        <div style={styles.card}>
          <div style={{ ...styles.statNumber, color: errorCount > 0 ? "#ef4444" : "#22c55e" }}>
            {errorCount}
          </div>
          <div style={styles.statLabel}>Errors</div>
        </div>

        {/* Warnings */}
        <div style={styles.card}>
          <div style={{ ...styles.statNumber, color: warningCount > 0 ? "#eab308" : "#22c55e" }}>
            {warningCount}
          </div>
          <div style={styles.statLabel}>Warnings</div>
        </div>
      </div>

      {/* Score breakdown */}
      {qualityScore?.breakdown && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Score Breakdown</h3>
          <div style={styles.breakdownGrid}>
            {Object.entries(qualityScore.breakdown).map(([key, score]) => (
              <div key={key} style={styles.breakdownItem}>
                <div style={styles.breakdownHeader}>
                  <span>{CATEGORY_ICONS[key] || "📦"} {CATEGORY_LABELS[key] || key}</span>
                  <span style={{ color: getScoreColor(score), fontWeight: 700 }}>{score}</span>
                </div>
                <div style={styles.progressBarBg}>
                  <div
                    style={{
                      ...styles.progressBarFill,
                      width: `${score}%`,
                      backgroundColor: getScoreColor(score),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agent timeline */}
      {agentHistory.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Agent Execution Timeline</h3>
          <div style={styles.timeline}>
            {agentHistory.map((agent, idx) => (
              <div key={idx} style={styles.timelineItem}>
                <div style={{
                  ...styles.timelineDot,
                  backgroundColor: agent.status === "completed" ? "#22c55e" : "#ef4444",
                }} />
                <div style={styles.timelineContent}>
                  <span style={styles.timelineAgent}>{getAgentLabel(agent.agent_name)}</span>
                  <span style={{
                    ...styles.timelineBadge,
                    backgroundColor: agent.status === "completed" ? "#166534" : "#991b1b",
                  }}>
                    {agent.status}
                    {agent.retry_count ? ` (${agent.retry_count} retries)` : ""}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Self-healing corrections */}
      {autoFixedErrors.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>🔧 Auto-Fixed Issues</h3>
          {autoFixedErrors.map((fix, idx) => (
            <div key={idx} style={styles.fixItem}>
              <span style={styles.fixAgent}>{getAgentLabel(fix.agent)}</span>
              <span style={styles.fixSummary}>{fix.summary}</span>
            </div>
          ))}
        </div>
      )}

      {/* Quality details */}
      {qualityScore?.details && qualityScore.details.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Quality Details</h3>
          <div style={styles.detailsList}>
            {qualityScore.details.map((d, i) => (
              <div key={i} style={styles.detailItem}>{d}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: "24px",
    color: "#e2e8f0",
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
  },
  title: {
    fontSize: "20px",
    fontWeight: 700,
    marginBottom: "20px",
    color: "#f1f5f9",
  },
  cardRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "16px",
    marginBottom: "24px",
  },
  card: {
    background: "linear-gradient(135deg, #1e293b, #0f172a)",
    borderRadius: "12px",
    padding: "20px",
    textAlign: "center" as const,
    border: "1px solid #334155",
  },
  scoreCard: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
  },
  scoreCircle: { marginBottom: "8px" },
  scoreLabel: { fontSize: "13px", color: "#94a3b8", fontWeight: 600 },
  statNumber: { fontSize: "32px", fontWeight: 700, color: "#60a5fa" },
  statLabel: { fontSize: "13px", color: "#94a3b8", marginTop: "4px" },
  section: {
    marginBottom: "24px",
    background: "#1e293b",
    borderRadius: "12px",
    padding: "20px",
    border: "1px solid #334155",
  },
  sectionTitle: {
    fontSize: "15px",
    fontWeight: 700,
    marginBottom: "14px",
    color: "#cbd5e1",
  },
  breakdownGrid: { display: "grid", gap: "12px" },
  breakdownItem: {},
  breakdownHeader: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "13px",
    marginBottom: "4px",
    color: "#cbd5e1",
  },
  progressBarBg: {
    width: "100%",
    height: "6px",
    backgroundColor: "#334155",
    borderRadius: "3px",
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    borderRadius: "3px",
    transition: "width 1s ease",
  },
  timeline: { display: "flex", flexDirection: "column" as const, gap: "12px" },
  timelineItem: { display: "flex", alignItems: "center", gap: "12px" },
  timelineDot: { width: "10px", height: "10px", borderRadius: "50%", flexShrink: 0 },
  timelineContent: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" as const },
  timelineAgent: { fontSize: "13px", fontWeight: 600, color: "#e2e8f0" },
  timelineBadge: {
    fontSize: "11px",
    padding: "2px 8px",
    borderRadius: "8px",
    color: "#fff",
    fontWeight: 600,
  },
  fixItem: {
    display: "flex",
    gap: "8px",
    padding: "8px 12px",
    background: "#0f172a",
    borderRadius: "8px",
    marginBottom: "6px",
    alignItems: "center",
  },
  fixAgent: { fontSize: "12px", fontWeight: 700, color: "#60a5fa", whiteSpace: "nowrap" as const },
  fixSummary: { fontSize: "12px", color: "#94a3b8" },
  detailsList: { display: "flex", flexDirection: "column" as const, gap: "4px" },
  detailItem: { fontSize: "12px", color: "#94a3b8", paddingLeft: "8px" },
};
