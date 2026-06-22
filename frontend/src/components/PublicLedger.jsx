import { useState, useEffect } from "react";

const STATUS_COLORS = {
  ACKNOWLEDGED: "#10B981", PENDING: "#F59E0B",
  TAMPERED: "#EF4444", COMPROMISED: "#EF4444",
  DISAGREEING: "#F59E0B", ACTIONED: "#3B82F6",
  default: "#6B6B8A",
};

export default function PublicLedger({ mainUrl }) {
  const [complaints, setComplaints] = useState([]);
  const [chainStatus, setChainStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  
  // Search & Filters state
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("ALL");
  const [filterStatus, setFilterStatus] = useState("ALL");
  const [copiedField, setCopiedField] = useState(null);

  useEffect(() => {
    fetchLedger();
    const interval = setInterval(fetchLedger, 8000);
    return () => clearInterval(interval);
  }, []);

  async function fetchLedger() {
    try {
      const [ledgerRes, verifyRes] = await Promise.all([
        fetch(`${mainUrl}/ledger`),
        fetch(`${mainUrl}/ledger/verify`),
      ]);
      if (ledgerRes.ok) {
        const d = await ledgerRes.json();
        setComplaints(d.complaints || []);
      }
      if (verifyRes.ok) {
        setChainStatus(await verifyRes.json());
      }
    } catch (_) {}
    setLoading(false);
  }

  const handleCopy = (text, fieldName) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Extract unique complaint types
  const types = ["ALL", ...new Set(complaints.map((c) => c.complaint_type))];
  // Extract unique statuses
  const statuses = ["ALL", ...new Set(complaints.map((c) => c.status))];

  // Filter complaints
  const filteredComplaints = complaints.filter((c) => {
    const matchesSearch =
      c.location?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.complaint_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.id?.toString() === searchQuery;
    const matchesType = filterType === "ALL" || c.complaint_type === filterType;
    const matchesStatus = filterStatus === "ALL" || c.status === filterStatus;
    return matchesSearch && matchesType && matchesStatus;
  });

  return (
    <div className="animate-fade-in">
      {/* ── Chain integrity status ── */}
      {chainStatus && (
        <div style={{
          background: chainStatus.valid ? "var(--green-dim)" : "var(--red-dim)",
          border: `1px solid ${chainStatus.valid ? "rgba(16,185,129,0.22)" : "rgba(239,68,68,0.28)"}`,
          borderRadius: "10px", padding: "14px 18px", marginBottom: "20px",
          display: "flex", alignItems: "center", gap: "12px",
        }}>
          <div style={{
            color: chainStatus.valid ? "var(--green)" : "var(--red)",
            fontWeight: 700, fontSize: "13px"
          }}>
            {chainStatus.valid ? "✓ CRYPTOGRAPHIC MAIN CHAIN VALID" : "✗ CRYPTOGRAPHIC MAIN CHAIN TAMPERED"}
          </div>
          <div style={{ color: "var(--text-2)", fontSize: "12px" }}>{chainStatus.message}</div>
          <div style={{ marginLeft: "auto", color: "var(--muted)", fontSize: "11px", fontWeight: 600 }}>
            {chainStatus.total_records} RECORDS SECURED
          </div>
        </div>
      )}

      {/* ── Filter Bar ── */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: "14px", padding: "16px 20px", marginBottom: "20px",
        display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center"
      }}>
        <div style={{ flex: 1, minWidth: "200px" }}>
          <input
            type="text"
            placeholder="Search by ID, type, or location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ padding: "8px 12px" }}
          />
        </div>
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", fontWeight: 600 }}>TYPE</span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              style={{ width: "auto", minWidth: "120px", padding: "7px 12px" }}
            >
              {types.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", fontWeight: 600 }}>STATUS</span>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              style={{ width: "auto", minWidth: "140px", padding: "7px 12px" }}
            >
              {statuses.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div style={{ color: "var(--muted)", textAlign: "center", padding: "40px" }}>
          Loading public ledger ledger...
        </div>
      )}

      {/* ── Complaints list ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {filteredComplaints.map((c) => {
          const isSelected = selected?.id === c.id;
          const urgencyColor = c.urgency_score > 70 ? "var(--red)" : c.urgency_score > 30 ? "var(--amber)" : "var(--green)";
          return (
            <div
              key={c.id}
              onClick={() => setSelected(isSelected ? null : c)}
              style={{
                background: "var(--surface)",
                border: `1px solid ${isSelected ? "var(--accent)" : "var(--border)"}`,
                borderRadius: "12px", padding: "14px 18px", cursor: "pointer",
                transition: "all 0.2s ease"
              }}
            >
              <div style={{
                display: "flex", alignItems: "center",
                justifyContent: "space-between",
                marginBottom: isSelected ? "14px" : "0",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <span className="mono" style={{ color: "var(--muted)", fontSize: "12px", fontWeight: 700 }}>#{c.id}</span>
                  <span style={{ fontWeight: 600, fontSize: "13px" }}>{c.complaint_type}</span>
                  <span style={{ color: "var(--text-2)", fontSize: "12px" }}>{c.location}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                  <span style={{
                    color: STATUS_COLORS[c.status] || STATUS_COLORS.default,
                    fontSize: "10px", fontWeight: 700, letterSpacing: "0.05em",
                    background: `${STATUS_COLORS[c.status] || STATUS_COLORS.default}15`,
                    padding: "3px 8px", borderRadius: "4px"
                  }}>
                    {c.status}
                  </span>
                  <span style={{ color: "var(--muted)", fontSize: "11px" }}>
                    {new Date(c.timestamp * 1000).toLocaleString()}
                  </span>
                </div>
              </div>

              {isSelected && (
                <div className="animate-slide-in" style={{
                  borderTop: "1px solid var(--border)", paddingTop: "14px",
                  display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px",
                  cursor: "default"
                }} onClick={(e) => e.stopPropagation()}>
                  <HashField
                    label="EVIDENCE HASH"
                    value={c.evidence_hash}
                    onCopy={() => handleCopy(c.evidence_hash, `ev-${c.id}`)}
                    copied={copiedField === `ev-${c.id}`}
                  />
                  <HashField
                    label="RECORD BLOCK HASH"
                    value={c.record_hash}
                    onCopy={() => handleCopy(c.record_hash, `rec-${c.id}`)}
                    copied={copiedField === `rec-${c.id}`}
                  />
                  <HashField
                    label="PREVIOUS BLOCK HASH"
                    value={c.prev_hash}
                    onCopy={() => handleCopy(c.prev_hash, `prev-${c.id}`)}
                    copied={copiedField === `prev-${c.id}`}
                  />
                  
                  <div>
                    <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em", fontWeight: 700, marginBottom: "4px" }}>
                      NODE REPLICATIONS
                    </div>
                    <div style={{ display: "flex", gap: "6px" }}>
                      {c.node_acks?.map(node => (
                        <span key={node} className="badge badge-accent" style={{ background: "var(--surface-2)", color: "var(--text)" }}>{node}</span>
                      )) || <span style={{ color: "var(--muted)", fontSize: "12px" }}>None</span>}
                    </div>
                  </div>

                  <div style={{ gridColumn: "span 2", marginTop: "4px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                      <span style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em", fontWeight: 700 }}>
                        ESCALATION URGENCY
                      </span>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: urgencyColor }}>
                        {c.urgency_score?.toFixed(1)}% Urgency
                      </span>
                    </div>
                    <div className="progress-bar" style={{ height: "6px" }}>
                      <div className="progress-fill" style={{ width: `${c.urgency_score}%`, background: urgencyColor }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {!loading && filteredComplaints.length === 0 && (
          <div style={{
            color: "var(--muted)", textAlign: "center", padding: "40px",
            background: "var(--surface)", borderRadius: "12px",
            border: "1px solid var(--border)",
          }}>
            No complaints match the filter criteria.
          </div>
        )}
      </div>
    </div>
  );
}

function HashField({ label, value, onCopy, copied }) {
  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
        <span style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em", fontWeight: 700 }}>{label}</span>
        <button
          onClick={onCopy}
          style={{
            background: "none", color: "var(--accent)", fontSize: "10px", fontWeight: 600,
            padding: "2px 6px"
          }}
        >
          {copied ? "Copied! ✓" : "Copy Hash"}
        </button>
      </div>
      <div className="hash-display">{value}</div>
    </div>
  );
}
