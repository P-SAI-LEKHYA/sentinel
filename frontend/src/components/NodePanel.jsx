import { useState, useEffect } from "react";

const NODE_PORTS = { NGO: 8001, MEDIA: 8002, OMBUDSMAN: 8003, PUBLIC: 8004 };

const NODE_COLORS = {
  NGO:       "#10B981",
  MEDIA:     "#3B82F6",
  OMBUDSMAN: "#F59E0B",
  PUBLIC:    "#8B5CF6",
};

const STATUS_COLORS = {
  ACKNOWLEDGED:        "var(--green)",
  PENDING:             "var(--amber)",
  TAMPERED:            "var(--red)",
  DISAGREEING:         "var(--amber)",
  COMPROMISED:         "var(--red)",
  ACTIONED:            "var(--blue)",
  UNDER_INVESTIGATION: "var(--blue)",
  PARTIALLY_REPLICATED:"var(--amber)",
  FAILED_REPLICATION:  "var(--red)",
};

function trunc(hash, n = 14) {
  if (!hash || hash.length < 20) return hash || "—";
  return hash.slice(0, n) + "…" + hash.slice(-4);
}

export default function NodePanel({ nodeId, wsMessages }) {
  const port  = NODE_PORTS[nodeId];
  const color = NODE_COLORS[nodeId];

  const [nodeData,    setNodeData]    = useState(null);
  const [complaints,  setComplaints]  = useState([]);
  const [chainStatus, setChainStatus] = useState(null);
  const [myTrust,     setMyTrust]     = useState(null);
  const [online,      setOnline]      = useState(false);
  const [alerting,    setAlerting]    = useState(false);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 6000);
    return () => clearInterval(iv);
  }, []); // eslint-disable-line

  useEffect(() => {
    if (!wsMessages.length) return;
    const m = wsMessages[0];
    if (m.node_id === nodeId) {
      if (["TAMPER_DETECTED","TAMPER_SIMULATED","TAMPER_ALERT"].includes(m.type)) {
        setAlerting(true);
        setTimeout(() => setAlerting(false), 10000);
      }
      if (["NEW_COMPLAINT","STATUS_UPDATE"].includes(m.type)) fetchAll();
    }
  }, [wsMessages]); // eslint-disable-line

  async function fetchAll() {
    try {
      const [rootRes, chainRes, allRes, trustRes] = await Promise.all([
        fetch(`http://localhost:${port}/`),
        fetch(`http://localhost:${port}/chain/verify`),
        fetch(`http://localhost:${port}/chain/all`),
        fetch(`http://localhost:${port}/trust/scores`),
      ]);
      if (rootRes.ok)  { setNodeData(await rootRes.json()); setOnline(true); }
      if (chainRes.ok) { const c = await chainRes.json(); setChainStatus(c); if (!c.valid) setAlerting(true); }
      if (allRes.ok)   { const a = await allRes.json(); setComplaints(a.complaints || []); }
      if (trustRes.ok) {
        const scores = await trustRes.json();
        setMyTrust(scores.find((t) => t.node_id === nodeId) || null);
      }
    } catch (_) { setOnline(false); }
  }

  const trustColor = !myTrust ? "var(--muted)"
    : myTrust.trust_score > 70 ? "var(--green)"
    : myTrust.trust_score > 40 ? "var(--amber)"
    : "var(--red)";

  return (
    <div style={{
      background: "var(--surface)",
      border: `1px solid ${alerting ? "rgba(239,68,68,0.6)" : "var(--border)"}`,
      borderRadius: "16px",
      padding: "18px",
      transition: "border-color 0.35s, box-shadow 0.35s",
      boxShadow: alerting ? "0 0 28px rgba(239,68,68,0.18)" : "none",
      position: "relative",
      overflow: "hidden",
    }}>

      {/* Colour top bar */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: "2px",
        background: alerting ? "var(--red)" : color,
        boxShadow: `0 0 10px ${alerting ? "rgba(239,68,68,0.8)" : color + "80"}`,
      }} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div className={`node-dot ${alerting ? "alert" : online ? "online" : "offline"}`} />
          <span style={{ fontWeight: 700, fontSize: "12px", letterSpacing: "0.04em" }}>{nodeId}</span>
          <span style={{ color: "var(--muted)", fontSize: "10px" }}>:{port}</span>
        </div>
        {alerting && (
          <span className="badge badge-red animate-pulse">ALERT</span>
        )}
      </div>

      {/* Chain status */}
      {chainStatus && (
        <div style={{
          background: chainStatus.valid ? "var(--green-dim)" : "var(--red-dim)",
          border: `1px solid ${chainStatus.valid ? "rgba(16,185,129,0.22)" : "rgba(239,68,68,0.28)"}`,
          borderRadius: "8px", padding: "8px 10px", marginBottom: "12px",
        }}>
          <div style={{
            color: chainStatus.valid ? "var(--green)" : "var(--red)",
            fontWeight: 700, fontSize: "10px", letterSpacing: "0.04em", marginBottom: "2px",
          }}>
            {chainStatus.valid ? "✓ CHAIN INTACT" : "✗ CHAIN BROKEN"}
          </div>
          <div style={{ color: "var(--muted)", fontSize: "10px", lineHeight: 1.4 }}>{chainStatus.message}</div>
          {!chainStatus.valid && chainStatus.tampered_record && (
            <div style={{ color: "var(--red)", fontSize: "10px", marginTop: "3px", fontWeight: 600 }}>
              Tampered record: #{chainStatus.tampered_record}
            </div>
          )}
        </div>
      )}

      {/* Stats grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "12px" }}>
        <div style={{ background: "var(--bg-2)", borderRadius: "8px", padding: "10px 12px" }}>
          <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginBottom: "3px" }}>RECORDS</div>
          <div style={{ fontWeight: 700, fontSize: "20px", color }}>{nodeData?.total_complaints ?? "—"}</div>
        </div>
        <div style={{ background: "var(--bg-2)", borderRadius: "8px", padding: "10px 12px" }}>
          <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginBottom: "3px" }}>TRUST</div>
          <div style={{ fontWeight: 700, fontSize: "20px", color: trustColor }}>
            {myTrust ? `${myTrust.trust_score.toFixed(0)}%` : "N/A"}
          </div>
        </div>
      </div>

      {/* Trust bar */}
      {myTrust && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginBottom: "5px" }}>TRUST SCORE</div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${myTrust.trust_score}%`, background: trustColor }} />
          </div>
        </div>
      )}

      {/* Chain head */}
      {nodeData?.chain_head && (
        <div style={{ marginBottom: "12px" }}>
          <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginBottom: "4px" }}>CHAIN HEAD</div>
          <div className="mono" style={{ color, fontSize: "10px" }}>
            {trunc(nodeData.chain_head, 18)}
          </div>
        </div>
      )}

      {/* Recent complaints */}
      {complaints.length > 0 && (
        <div>
          <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginBottom: "6px" }}>RECENT</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
            {complaints.slice(-3).reverse().map((c) => (
              <div key={c.id} style={{
                background: "var(--bg-2)",
                borderRadius: "6px",
                padding: "5px 8px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}>
                <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                  #{c.id} {c.complaint_type}
                </span>
                <span style={{
                  color: STATUS_COLORS[c.status] || "var(--muted)",
                  fontWeight: 700, fontSize: "9px", letterSpacing: "0.04em",
                }}>
                  {c.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!online && (
        <div style={{
          color: "var(--muted)", fontSize: "11px", textAlign: "center",
          padding: "14px", background: "var(--bg-2)", borderRadius: "8px",
        }}>
          Node offline
        </div>
      )}
    </div>
  );
}
