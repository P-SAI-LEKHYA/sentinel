import { useState, useEffect } from "react";

const NODE_PORTS = { NGO: 8001, MEDIA: 8002, OMBUDSMAN: 8003, PUBLIC: 8004 };
const NODE_COLORS = {
  NGO:       "#10B981",
  MEDIA:     "#3B82F6",
  OMBUDSMAN: "#F59E0B",
  PUBLIC:    "#8B5CF6",
};

export default function NodeControl({ mainUrl }) {
  const [nodesStatus, setNodesStatus] = useState({});
  const [actionIds, setActionIds] = useState({ NGO: "1", MEDIA: "1", OMBUDSMAN: "1", PUBLIC: "1" });
  const [results, setResults] = useState({});
  const [verifying, setVerifying] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchNodeStatuses();
    const iv = setInterval(fetchNodeStatuses, 5000);
    return () => clearInterval(iv);
  }, []);

  async function fetchNodeStatuses() {
    const statuses = {};
    await Promise.all(
      Object.entries(NODE_PORTS).map(async ([nodeId, port]) => {
        try {
          const res = await fetch(`http://localhost:${port}/status`);
          if (res.ok) {
            statuses[nodeId] = await res.json();
            statuses[nodeId].online = true;
          } else {
            statuses[nodeId] = { online: false };
          }
        } catch (_) {
          statuses[nodeId] = { online: false };
        }
      })
    );
    setNodesStatus(statuses);
    setLoading(false);
  }

  async function handleAction(nodeId, actionType) {
    const port = NODE_PORTS[nodeId];
    const complaintId = parseInt(actionIds[nodeId]);
    if (!complaintId || isNaN(complaintId)) {
      setResults(prev => ({ ...prev, [nodeId]: { error: "Invalid complaint ID" } }));
      return;
    }

    try {
      let endpoint = "";
      if (actionType === "tamper") endpoint = `/simulate/tamper/${complaintId}`;
      else if (actionType === "disagree") endpoint = `/simulate/disagree/${complaintId}`;
      else if (actionType === "stop_disagree") endpoint = `/simulate/stop_disagree/${complaintId}`;

      const res = await fetch(`http://localhost:${port}${endpoint}`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setResults(prev => ({
          ...prev,
          [nodeId]: { success: true, message: data.message || `Action ${actionType} completed.` }
        }));
        fetchNodeStatuses();
      } else {
        setResults(prev => ({
          ...prev,
          [nodeId]: { error: data.detail || "Action failed on node" }
        }));
      }
    } catch (_) {
      setResults(prev => ({ ...prev, [nodeId]: { error: "Failed to connect to node" } }));
    }
  }

  async function handleVerify(nodeId) {
    const port = NODE_PORTS[nodeId];
    setVerifying(prev => ({ ...prev, [nodeId]: true }));
    setResults(prev => ({ ...prev, [nodeId]: null }));
    try {
      const res = await fetch(`http://localhost:${port}/chain/verify`);
      const data = await res.json();
      if (res.ok) {
        setResults(prev => ({
          ...prev,
          [nodeId]: {
            success: true,
            verifyResult: data,
            message: data.valid ? "✓ Chain integrity verified successfully" : `✗ Tamper detected! Block #${data.tampered_record} is broken`
          }
        }));
      } else {
        setResults(prev => ({ ...prev, [nodeId]: { error: "Failed to verify chain" } }));
      }
    } catch (_) {
      setResults(prev => ({ ...prev, [nodeId]: { error: "Could not connect to node" } }));
    } finally {
      setVerifying(prev => ({ ...prev, [nodeId]: false }));
    }
  }

  function handleIdChange(nodeId, val) {
    setActionIds(prev => ({ ...prev, [nodeId]: val }));
  }

  return (
    <div className="animate-fade-in">
      <div style={{ marginBottom: "24px" }}>
        <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "6px" }}>Network Node Simulation Controls</h2>
        <p style={{ color: "var(--text-2)", fontSize: "13px" }}>
          Simulate malicious database tampering or consensus disagreement to test Sentinel's cryptographic verification engine and automated isolation protocols.
        </p>
      </div>

      {loading && (
        <div style={{ color: "var(--muted)", textAlign: "center", padding: "40px" }}>
          Loading node controls...
        </div>
      )}

      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          {Object.entries(NODE_PORTS).map(([nodeId, port]) => {
            const status = nodesStatus[nodeId] || { online: false };
            const result = results[nodeId];
            const isVerifying = verifying[nodeId];
            const color = NODE_COLORS[nodeId];

            return (
              <div key={nodeId} className="card animate-slide-in" style={{ position: "relative" }}>
                <div style={{
                  position: "absolute", top: 0, left: 0, right: 0, height: "3px",
                  background: color, boxShadow: `0 0 10px ${color}80`
                }} />

                {/* Node Info Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div>
                    <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text)" }}>{nodeId} Node Control</h3>
                    <span style={{ color: "var(--muted)", fontSize: "11px" }}>Running on port {port}</span>
                  </div>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <div className={`node-dot ${status.online ? (status.chain_valid ? "online" : "alert") : "offline"}`} />
                    <span style={{ fontSize: "11px", fontWeight: 600, color: status.online ? "var(--text)" : "var(--muted)" }}>
                      {status.online ? (status.chain_valid ? "ONLINE" : "TAMPERED") : "OFFLINE"}
                    </span>
                  </div>
                </div>

                {status.online ? (
                  <div>
                    {/* Status Overview */}
                    <div style={{ display: "flex", gap: "10px", marginBottom: "20px", flexWrap: "wrap" }}>
                      <span className={`badge ${status.chain_valid ? "badge-green" : "badge-red"}`}>
                        {status.chain_valid ? "Chain Intact" : "Chain Corrupted"}
                      </span>
                      {status.simulating_disagreement && (
                        <span className="badge badge-amber">
                          Simulating Disagreement ({status.disagreeing_complaints?.length || 0})
                        </span>
                      )}
                    </div>

                    {/* Simulation Panel */}
                    <div style={{ background: "var(--bg-2)", padding: "16px", borderRadius: "10px", marginBottom: "16px" }}>
                      <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "8px" }}>
                        SIMULATE BEHAVIOR
                      </div>
                      
                      <div style={{ display: "flex", gap: "10px", marginBottom: "12px", alignItems: "center" }}>
                        <span style={{ fontSize: "12px", color: "var(--text-2)", whiteSpace: "nowrap" }}>Complaint ID:</span>
                        <input
                          type="number"
                          value={actionIds[nodeId]}
                          onChange={(e) => handleIdChange(nodeId, e.target.value)}
                          placeholder="ID"
                          min="1"
                          style={{ width: "80px", padding: "6px 10px" }}
                        />
                      </div>

                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          onClick={() => handleAction(nodeId, "tamper")}
                          className="btn-danger"
                          style={{ flex: 1, padding: "8px" }}
                        >
                          Tamper Evidence
                        </button>
                        <button
                          onClick={() => handleAction(nodeId, "disagree")}
                          className="btn-amber"
                          style={{ flex: 1, padding: "8px" }}
                        >
                          Disagree
                        </button>
                        {status.simulating_disagreement && (
                          <button
                            onClick={() => handleAction(nodeId, "stop_disagree")}
                            className="btn-ghost"
                            style={{ flex: 1, padding: "8px", borderColor: "var(--green)", color: "var(--green)" }}
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Verification Action */}
                    <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                      <button
                        onClick={() => handleVerify(nodeId)}
                        disabled={isVerifying}
                        className="btn-ghost"
                        style={{ flex: 1 }}
                      >
                        {isVerifying ? <span className="animate-spin">⟳</span> : "Verify Node Chain"}
                      </button>
                    </div>

                    {/* Feedback result */}
                    {result && (
                      <div className="animate-slide-in" style={{ marginTop: "14px" }}>
                        <div style={{
                          background: result.error ? "var(--red-dim)" : "var(--bg-2)",
                          border: `1px solid ${result.error ? "rgba(239,68,68,0.2)" : "var(--border)"}`,
                          borderRadius: "8px", padding: "10px 12px", fontSize: "12px"
                        }}>
                          <div style={{
                            color: result.error ? "var(--red)" : result.verifyResult?.valid === false ? "var(--red)" : "var(--green)",
                            fontWeight: 700, marginBottom: "2px"
                          }}>
                            {result.error ? "Execution Error" : "Result"}
                          </div>
                          <div style={{ color: "var(--text)" }}>{result.message || result.error}</div>
                          {result.verifyResult && !result.verifyResult.valid && result.verifyResult.tampered_record && (
                            <div className="mono" style={{ color: "var(--red)", marginTop: "4px", fontSize: "11px" }}>
                              Broken block hash: {result.verifyResult.tampered_record}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                  </div>
                ) : (
                  <div style={{ color: "var(--muted)", textAlign: "center", padding: "30px 10px" }}>
                    Node is currently offline. Ensure port {port} is running.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
