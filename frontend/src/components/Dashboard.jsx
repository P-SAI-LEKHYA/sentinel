import { useState, useEffect } from "react";
import NodePanel from "./NodePanel";

const NODE_IDS = ["NGO", "MEDIA", "OMBUDSMAN", "PUBLIC"];

export default function Dashboard({ wsMessages, mainUrl }) {
  const [verifyId,     setVerifyId]     = useState("1");
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifying,    setVerifying]    = useState(false);
  const [mainStatus,   setMainStatus]   = useState(null);
  const [stats,        setStats]        = useState(null);

  useEffect(() => {
    fetchStatus();
    const iv = setInterval(fetchStatus, 6000);
    return () => clearInterval(iv);
  }, []);

  async function fetchStatus() {
    try {
      const [rootRes, statsRes] = await Promise.all([
        fetch(`${mainUrl}/`),
        fetch(`${mainUrl}/stats`),
      ]);
      if (rootRes.ok)  setMainStatus(await rootRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (_) {}
  }

  async function handleVerify() {
    if (!verifyId) return;
    setVerifying(true);
    setVerifyResult(null);
    try {
      const res = await fetch(`${mainUrl}/verify/${verifyId}`);
      setVerifyResult(await res.json());
    } catch (_) {
      setVerifyResult({ error: "Could not reach main server" });
    }
    setVerifying(false);
  }

  const integrity = verifyResult?.integrity;

  function integrityStyle() {
    if (!integrity) return { color: "var(--muted)", bg: "var(--surface-2)", border: "var(--border)" };
    const s = integrity.integrity_status;
    if (s === "INTACT")           return { color: "var(--green)", bg: "var(--green-dim)", border: "rgba(16,185,129,0.28)" };
    if (s === "NODES_OUT_OF_SYNC") return { color: "var(--amber)", bg: "var(--amber-dim)", border: "rgba(245,158,11,0.28)" };
    return { color: "var(--red)", bg: "var(--red-dim)", border: "rgba(239,68,68,0.28)" };
  }

  function eventColor(type) {
    if (type?.includes("TAMPER") || type?.includes("QUORUM")) return "var(--red)";
    if (type === "NEW_COMPLAINT" || type === "NEW_SUBMISSION")  return "var(--green)";
    if (type === "STATUS_UPDATE")  return "var(--blue)";
    if (type === "ESCALATION")     return "var(--amber)";
    if (type === "SYNC_MISMATCH")  return "var(--red)";
    return "var(--muted)";
  }

  const iStyle = integrityStyle();

  return (
    <div>
      {/* ── Stats bar ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "12px",
        marginBottom: "24px",
      }}>
        {[
          {
            label: "TOTAL COMPLAINTS",
            value: mainStatus?.total_complaints ?? "—",
            color: "var(--text)",
            sub: "on main chain",
          },
          {
            label: "QUORUM THRESHOLD",
            value: "3 / 4",
            color: "var(--accent)",
            sub: "nodes required",
          },
          {
            label: "ALERTS TODAY",
            value: stats?.alerts_today ?? "—",
            color: stats?.alerts_today > 0 ? "var(--amber)" : "var(--green)",
            sub: "urgency score > 70",
          },
          {
            label: "MAIN SERVER",
            value: "ONLINE",
            color: mainStatus ? "var(--green)" : "var(--red)",
            sub: "port 8000",
          },
        ].map(({ label, value, color, sub }) => (
          <div key={label} className="stat-card">
            <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.09em", marginBottom: "8px" }}>
              {label}
            </div>
            <div style={{ color, fontWeight: 700, fontSize: "22px", lineHeight: 1, marginBottom: "4px" }}>
              {value}
            </div>
            <div style={{ color: "var(--muted)", fontSize: "10px" }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* ── Node panels ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "14px",
        marginBottom: "22px",
      }}>
        {NODE_IDS.map((nodeId) => (
          <NodePanel key={nodeId} nodeId={nodeId} wsMessages={wsMessages} />
        ))}
      </div>

      {/* ── Bottom row: Verify + Event log ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>

        {/* Verify panel */}
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: "16px", padding: "24px",
        }}>
          <div style={{ fontWeight: 700, fontSize: "12px", letterSpacing: "0.08em", marginBottom: "4px" }}>
            VERIFY COMPLAINT INTEGRITY
          </div>
          <div style={{ color: "var(--muted)", fontSize: "12px", marginBottom: "20px" }}>
            Cross-check a complaint's hash across all 4 nodes
          </div>

          <div style={{ display: "flex", gap: "10px", marginBottom: "16px" }}>
            <input
              id="verify-complaint-id"
              type="number"
              value={verifyId}
              onChange={(e) => setVerifyId(e.target.value)}
              placeholder="ID"
              onKeyDown={(e) => e.key === "Enter" && handleVerify()}
              style={{ flex: "0 0 100px" }}
              min="1"
            />
            <button
              id="verify-btn"
              onClick={handleVerify}
              disabled={verifying}
              className="btn-primary"
              style={{ flex: 1 }}
            >
              {verifying
                ? <span className="animate-spin">⟳</span>
                : "Verify"}
            </button>
          </div>

          {/* Verify result */}
          {integrity && (
            <div className="animate-slide-in">
              <div style={{
                background: iStyle.bg,
                border: `1px solid ${iStyle.border}`,
                borderRadius: "10px",
                padding: "14px 16px",
                marginBottom: "12px",
              }}>
                <div style={{ color: iStyle.color, fontWeight: 700, fontSize: "13px", marginBottom: "10px" }}>
                  {integrity.integrity_status === "INTACT" ? "✓ " : "✗ "}
                  {integrity.integrity_status?.replace(/_/g, " ")}
                </div>
                <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
                  {[
                    { label: "Verified",     val: integrity.verified,            good: true  },
                    { label: "Tampered",     val: integrity.tamper_detected,     good: false },
                    { label: "Quorum",       val: integrity.quorum_met,          good: true  },
                    { label: "Compromised",  val: integrity.actually_compromised, good: false },
                  ].map(({ label, val, good }) => (
                    <div key={label}>
                      <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em" }}>{label}</div>
                      <div style={{
                        fontWeight: 700, fontSize: "12px",
                        color: (good ? val : !val) ? "var(--green)" : "var(--red)",
                      }}>
                        {val ? "YES" : "NO"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", marginBottom: "12px" }}>
                {[
                  { label: "AGREEING",    nodes: integrity.nodes_agreeing,    color: "var(--green)" },
                  { label: "TAMPERED",    nodes: integrity.nodes_tampered,    color: "var(--red)"   },
                  { label: "OUT OF SYNC", nodes: integrity.nodes_out_of_sync, color: "var(--amber)" },
                ].map(({ label, nodes, color }) => (
                  <div key={label} style={{ background: "var(--bg-2)", borderRadius: "8px", padding: "10px" }}>
                    <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em", marginBottom: "5px" }}>
                      {label} ({nodes?.length ?? 0})
                    </div>
                    {!nodes?.length
                      ? <div style={{ color: "var(--muted)", fontSize: "11px" }}>None</div>
                      : nodes.map((n) => (
                          <div key={n} style={{ color, fontWeight: 700, fontSize: "11px" }}>{n}</div>
                        ))
                    }
                  </div>
                ))}
              </div>

              <div>
                <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginBottom: "5px" }}>
                  RECORD HASH
                </div>
                <div className="hash-display">{integrity.hash}</div>
              </div>
            </div>
          )}

          {verifyResult?.error && (
            <div style={{
              color: "var(--red)", fontSize: "12px",
              background: "var(--red-dim)", border: "1px solid rgba(239,68,68,0.2)",
              borderRadius: "8px", padding: "10px 14px",
            }}>
              {verifyResult.error}
            </div>
          )}
        </div>

        {/* Live event log */}
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: "16px", padding: "24px",
          display: "flex", flexDirection: "column",
        }}>
          <div style={{ fontWeight: 700, fontSize: "12px", letterSpacing: "0.08em", marginBottom: "4px" }}>
            LIVE EVENT LOG
          </div>
          <div style={{ color: "var(--muted)", fontSize: "12px", marginBottom: "16px" }}>
            Real-time WebSocket stream from all nodes
          </div>
          <div style={{
            flex: 1,
            height: "340px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}>
            {wsMessages.length === 0 && (
              <div style={{
                color: "var(--muted)", fontSize: "12px",
                textAlign: "center", padding: "32px 16px",
              }}>
                Waiting for events...
              </div>
            )}
            {wsMessages.map((msg, i) => {
              const col = eventColor(msg.type);
              return (
                <div key={i} style={{
                  background: "var(--bg-2)",
                  borderRadius: "6px",
                  padding: "7px 10px",
                  borderLeft: `2px solid ${col}`,
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  fontSize: "11px",
                  flexShrink: 0,
                }}>
                  <span style={{ color: col, fontWeight: 700, fontSize: "9px", letterSpacing: "0.06em", whiteSpace: "nowrap" }}>
                    {msg.type}
                  </span>
                  {msg.node_id      && <span style={{ color: "var(--muted)" }}>{msg.node_id}</span>}
                  {msg.complaint_id && <span style={{ color: "var(--text-2)" }}>#{msg.complaint_id}</span>}
                  {msg.quorum_reached !== undefined && (
                    <span style={{
                      marginLeft: "auto",
                      color: msg.quorum_reached ? "var(--green)" : "var(--red)",
                      fontSize: "9px", fontWeight: 700,
                    }}>
                      {msg.quorum_reached ? "QUORUM✓" : "NO QUORUM"}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
