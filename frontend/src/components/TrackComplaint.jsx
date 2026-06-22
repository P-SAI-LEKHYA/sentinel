import { useState } from "react";

const STATUS_COLORS = {
  ACKNOWLEDGED: "#10B981", PENDING: "#F59E0B",
  TAMPERED: "#EF4444", COMPROMISED: "#EF4444",
  DISAGREEING: "#F59E0B", ACTIONED: "#3B82F6",
  UNDER_INVESTIGATION: "#3B82F6",
  default: "#6B6B8A",
};

export default function TrackComplaint({ mainUrl }) {
  const [token, setToken] = useState("");
  const [tracking, setTracking] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copiedHash, setCopiedHash] = useState(null);

  async function handleTrack() {
    if (!token) {
      setError("Please enter your secret access token.");
      return;
    }
    setTracking(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${mainUrl}/track`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const data = await res.json();
      if (res.ok) {
        setResult(data);
      } else {
        setError(data.detail || "No complaints found for this token");
      }
    } catch (_) {
      setError("Could not reach main server");
    } finally {
      setTracking(false);
    }
  }

  const handleCopy = (text, fieldId) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(fieldId);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Helper to determine active step in timeline
  function getActiveStep(status) {
    if (status === "COMPROMISED" || status === "TAMPERED") return -1; // alert state
    if (status === "ACTIONED") return 3;
    if (status === "UNDER_INVESTIGATION") return 2;
    return 1; // ACKNOWLEDGED, PENDING, etc.
  }

  return (
    <div className="animate-fade-in" style={{ maxWidth: "720px", margin: "0 auto" }}>
      {/* Search Token Panel */}
      <div className="card" style={{ marginBottom: "20px" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "4px" }}>Secure Incident Tracking</h2>
        <p style={{ color: "var(--text-2)", fontSize: "13px", marginBottom: "20px" }}>
          Provide the secret token received during filing. Sentinel uses client-side hashing to secure queries.
        </p>

        <div style={{ display: "flex", gap: "10px" }}>
          <input
            id="track-token-input"
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter secret token (e.g. key_abcdef123...)"
            onKeyDown={(e) => e.key === "Enter" && handleTrack()}
            style={{ flex: 1 }}
          />
          <button
            id="track-btn"
            onClick={handleTrack}
            disabled={tracking}
            className="btn-primary"
            style={{ padding: "10px 24px" }}
          >
            {tracking ? <span className="animate-spin">⟳</span> : "Query Network"}
          </button>
        </div>

        {error && (
          <div className="animate-slide-in" style={{
            color: "var(--red)", fontSize: "12px", marginTop: "12px",
            background: "var(--red-dim)", border: "1px solid rgba(239, 68, 68, 0.2)",
            borderRadius: "8px", padding: "10px 14px",
          }}>
            {error}
          </div>
        )}
      </div>

      {/* Query Results */}
      {result && (
        <div className="animate-slide-in">
          <div style={{ color: "var(--green)", fontWeight: 700, fontSize: "13px", marginBottom: "12px", letterSpacing: "0.04em" }}>
            FOUND {result.found} REPORT{result.found > 1 ? "S" : ""} MATCHING TARGET KEY
          </div>

          {result.complaints.map((c) => {
            const activeStep = getActiveStep(c.status);
            const statusColor = STATUS_COLORS[c.status] || STATUS_COLORS.default;
            const urgencyColor = c.urgency_score > 70 ? "var(--red)" : c.urgency_score > 30 ? "var(--amber)" : "var(--green)";
            
            return (
              <div key={c.id} className="card" style={{ marginBottom: "16px", background: "var(--surface)", border: "1px solid var(--border)" }}>
                
                {/* Card Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                  <div>
                    <h3 style={{ fontSize: "16px", fontWeight: 700 }}>Report Reference #{c.id}</h3>
                    <span style={{ color: "var(--muted)", fontSize: "11px" }}>Type: {c.complaint_type} | Location: {c.location}</span>
                  </div>
                  <span style={{
                    color: statusColor,
                    fontWeight: 700, fontSize: "11px", letterSpacing: "0.06em",
                    background: `${statusColor}15`,
                    border: `1px solid ${statusColor}28`,
                    padding: "4px 10px", borderRadius: "5px"
                  }}>
                    {c.status}
                  </span>
                </div>

                {/* Timeline Progress */}
                <div style={{ background: "var(--bg-2)", padding: "18px 24px", borderRadius: "10px", marginBottom: "20px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", position: "relative", marginBottom: "10px" }}>
                    
                    {/* Horizontal Connector Line */}
                    <div style={{
                      position: "absolute", top: "8px", left: "10%", right: "10%", height: "2px",
                      background: "var(--border)", zIndex: 1
                    }} />
                    {activeStep > 1 && (
                      <div style={{
                        position: "absolute", top: "8px", left: "10%",
                        width: activeStep === 2 ? "40%" : "80%", height: "2px",
                        background: "var(--accent)", zIndex: 2, transition: "width 0.5s ease"
                      }} />
                    )}

                    {/* Step 1 */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 3, width: "20%" }}>
                      <div style={{
                        width: "18px", height: "18px", borderRadius: "50%",
                        background: activeStep >= 1 ? "var(--accent)" : "var(--border)",
                        border: "3px solid var(--surface-2)",
                        boxShadow: activeStep >= 1 ? "0 0 8px var(--accent)" : "none"
                      }} />
                      <span style={{ fontSize: "10px", fontWeight: 600, marginTop: "6px", color: activeStep >= 1 ? "var(--text)" : "var(--muted)" }}>
                        Replicated
                      </span>
                    </div>

                    {/* Step 2 */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 3, width: "20%" }}>
                      <div style={{
                        width: "18px", height: "18px", borderRadius: "50%",
                        background: activeStep >= 2 ? "var(--accent)" : "var(--border)",
                        border: "3px solid var(--surface-2)",
                        boxShadow: activeStep >= 2 ? "0 0 8px var(--accent)" : "none"
                      }} />
                      <span style={{ fontSize: "10px", fontWeight: 600, marginTop: "6px", color: activeStep >= 2 ? "var(--text)" : "var(--muted)" }}>
                        Investigating
                      </span>
                    </div>

                    {/* Step 3 */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", zIndex: 3, width: "20%" }}>
                      <div style={{
                        width: "18px", height: "18px", borderRadius: "50%",
                        background: activeStep >= 3 ? "var(--green)" : "var(--border)",
                        border: "3px solid var(--surface-2)",
                        boxShadow: activeStep >= 3 ? "0 0 8px var(--green)" : "none"
                      }} />
                      <span style={{ fontSize: "10px", fontWeight: 600, marginTop: "6px", color: activeStep >= 3 ? "var(--green)" : "var(--muted)" }}>
                        Resolved
                      </span>
                    </div>

                  </div>

                  {activeStep === -1 && (
                    <div style={{
                      color: "var(--red)", fontSize: "11px", fontWeight: 600, textAlign: "center",
                      border: "1px dashed rgba(239,68,68,0.25)", background: "rgba(239,68,68,0.04)",
                      padding: "8px", borderRadius: "6px", marginTop: "12px"
                    }}>
                      🚨 CRITICAL WARNING: Cryptographic integrity verification failed on this complaint. Tampering alert triggered.
                    </div>
                  )}
                </div>

                {/* Details Details Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "20px" }}>
                  <div style={{ background: "var(--bg-2)", padding: "10px 12px", borderRadius: "8px" }}>
                    <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "3px" }}>
                      SUBMITTED ON
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text)", fontWeight: 600 }}>
                      {new Date(c.timestamp * 1000).toLocaleString()}
                    </div>
                  </div>

                  <div style={{ background: "var(--bg-2)", padding: "10px 12px", borderRadius: "8px" }}>
                    <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "3px" }}>
                      ESCALATION PRIORITY
                    </div>
                    <div style={{ fontSize: "12px", color: urgencyColor, fontWeight: 700 }}>
                      {c.urgency_score?.toFixed(1)}% (Urgency Level)
                    </div>
                  </div>
                </div>

                {/* Hash Details */}
                <div style={{ marginBottom: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <span style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em", fontWeight: 700 }}>
                      VERIFIED EVIDENCE HASH
                    </span>
                    <button
                      onClick={() => handleCopy(c.evidence_hash, `hash-${c.id}`)}
                      style={{ background: "none", color: "var(--accent)", fontSize: "10px", fontWeight: 600 }}
                    >
                      {copiedHash === `hash-${c.id}` ? "Copied! ✓" : "Copy Hash"}
                    </button>
                  </div>
                  <div className="hash-display">{c.evidence_hash}</div>
                </div>

                <div style={{ background: "var(--bg-2)", borderRadius: "8px", padding: "12px" }}>
                  <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "4px" }}>
                    NODE ACKNOWLEDGEMENTS
                  </div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                    {c.node_acks?.map(node => (
                      <span key={node} className="badge badge-accent" style={{ background: "var(--surface)", color: "var(--text)" }}>{node}</span>
                    )) || <span style={{ color: "var(--muted)", fontSize: "12px" }}>Replicating on nodes...</span>}
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
