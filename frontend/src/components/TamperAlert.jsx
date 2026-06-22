export default function TamperAlert({ alert, onDismiss }) {
  const isQuorum   = alert.type === "QUORUM_FAILED";
  const isDetected = alert.type === "TAMPER_DETECTED";
  const isCritical = isQuorum || isDetected;

  const color   = isCritical ? "var(--red)"   : "var(--amber)";
  const bgColor = isCritical ? "rgba(239,68,68,0.10)" : "rgba(245,158,11,0.08)";
  const bdColor = isCritical ? "rgba(239,68,68,0.35)" : "rgba(245,158,11,0.28)";
  const label   = isQuorum   ? "QUORUM FAILED" : isDetected ? "CHAIN BROKEN" : "TAMPER DETECTED";
  const icon    = isQuorum   ? "🚨" : "⚠️";

  return (
    <div
      className="animate-slide-in"
      style={{
        background: bgColor,
        border: `1px solid ${bdColor}`,
        borderRadius: "10px",
        padding: "12px 16px",
        marginBottom: "8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "12px",
        boxShadow: isCritical
          ? "0 4px 20px rgba(239,68,68,0.18)"
          : "0 4px 16px rgba(245,158,11,0.12)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <span style={{ fontSize: "20px", flexShrink: 0 }}>{icon}</span>
        <div>
          <div style={{ color, fontWeight: 700, fontSize: "11px", letterSpacing: "0.07em", marginBottom: "2px" }}>
            {label}
          </div>
          <div style={{ color: "var(--text-2)", fontSize: "12px" }}>
            {alert.message}
            <span style={{ color: "var(--muted)", fontSize: "11px", marginLeft: "8px" }}>
              {alert.timestamp}
            </span>
          </div>
        </div>
      </div>
      <button
        id={`dismiss-alert-${alert.id}`}
        onClick={onDismiss}
        style={{
          background: "none",
          color: "var(--muted)",
          fontSize: "22px",
          lineHeight: 1,
          padding: "0 4px",
          flexShrink: 0,
          transition: "color 0.2s",
        }}
        onMouseEnter={(e) => (e.target.style.color = "var(--text)")}
        onMouseLeave={(e) => (e.target.style.color = "var(--muted)")}
      >
        ×
      </button>
    </div>
  );
}
