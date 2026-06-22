import { useState, useEffect, useRef } from "react";
import Dashboard from "./components/Dashboard";
import SubmitComplaint from "./components/SubmitComplaint";
import PublicLedger from "./components/PublicLedger";
import TrackComplaint from "./components/TrackComplaint";
import NodeControl from "./components/NodeControl";
import TamperAlert from "./components/TamperAlert";
import "./index.css";

const MAIN_URL = "http://localhost:8000";

const TABS = [
  { id: "dashboard", label: "Dashboard",    icon: "▦" },
  { id: "submit",    label: "Submit",       icon: "⊕" },
  { id: "ledger",    label: "Ledger",       icon: "≡" },
  { id: "track",     label: "Track",        icon: "◎" },
  { id: "control",   label: "Node Control", icon: "⚙" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [wsMessages, setWsMessages] = useState([]);
  const [alerts, setAlerts]         = useState([]);
  const [connected, setConnected]   = useState(false);
  const wsRefs = useRef({});

  useEffect(() => {
    const ports = [8000, 8001, 8002, 8003, 8004];
    ports.forEach(connectWebSocket);
    return () => { 
      Object.values(wsRefs.current).forEach(ws => ws.close()); 
    };
  }, []); // eslint-disable-line

  function connectWebSocket(port) {
    try {
      const ws = new WebSocket(`ws://localhost:${port}/ws`);
      wsRefs.current[port] = ws;
      ws.onopen  = () => { if (port === 8000) setConnected(true); };
      ws.onclose = () => { 
        if (port === 8000) setConnected(false); 
        setTimeout(() => connectWebSocket(port), 3000); 
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        setWsMessages((prev) => [msg, ...prev].slice(0, 100));
        if (["TAMPER_ALERT","TAMPER_SIMULATED","QUORUM_FAILED","TAMPER_DETECTED"].includes(msg.type)) {
          setAlerts((prev) => [
            { id: Date.now() + Math.random(), type: msg.type, message: getTamperMessage(msg), timestamp: new Date().toLocaleTimeString() },
            ...prev,
          ].slice(0, 5));
        }
      };
    } catch (e) { console.error("WebSocket error:", e); }
  }

  function getTamperMessage(msg) {
    if (msg.type === "TAMPER_SIMULATED") return `Evidence modified on ${msg.node_id} — complaint #${msg.complaint_id}`;
    if (msg.type === "QUORUM_FAILED")    return `Quorum failed on complaint #${msg.complaint_id} — evidence compromised`;
    if (msg.type === "TAMPER_DETECTED")  return `Chain broken on ${msg.node_id} — record #${msg.tampered_record}`;
    return "Tamper detected on network";
  }

  function dismissAlert(id) {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", position: "relative", zIndex: 1 }}>

      {/* ── Header ── */}
      <header style={{
        borderBottom: "1px solid var(--border)",
        padding: "0 28px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: "60px",
        position: "sticky",
        top: 0,
        background: "rgba(5,5,8,0.92)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        zIndex: 100,
      }}>
        {/* Logo + brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{
            width: "34px", height: "34px",
            background: "var(--gradient)",
            borderRadius: "9px",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "16px", fontWeight: 800, color: "#fff",
            boxShadow: "0 0 20px rgba(124,58,237,0.5)",
            letterSpacing: "-0.05em",
            flexShrink: 0,
          }}>S</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: "14px", letterSpacing: "0.1em", color: "var(--text)" }}>
              SENTINEL
            </div>
            <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", marginTop: "-1px" }}>
              TAMPER-EVIDENT WHISTLEBLOWER NETWORK
            </div>
          </div>
        </div>

        {/* Right controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          {alerts.length > 0 && (
            <div className="animate-pulse" style={{
              background: "var(--red-dim)",
              border: "1px solid rgba(239,68,68,0.35)",
              borderRadius: "6px",
              padding: "4px 12px",
              fontSize: "11px",
              color: "var(--red)",
              fontWeight: 700,
              letterSpacing: "0.05em",
            }}>
              {alerts.length} ALERT{alerts.length > 1 ? "S" : ""}
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
            <div className={`node-dot ${connected ? "online" : "offline"}`} />
            <span style={{ color: "var(--muted)", fontSize: "11px", fontWeight: 500, letterSpacing: "0.04em" }}>
              {connected ? "LIVE" : "RECONNECTING"}
            </span>
          </div>
        </div>
      </header>

      {/* ── Alert banners ── */}
      {alerts.length > 0 && (
        <div style={{ padding: "12px 28px 0", position: "relative", zIndex: 50 }}>
          {alerts.map((alert) => (
            <TamperAlert key={alert.id} alert={alert} onDismiss={() => dismissAlert(alert.id)} />
          ))}
        </div>
      )}

      {/* ── Tab navigation ── */}
      <nav style={{
        padding: "0 28px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        gap: "2px",
        background: "rgba(5,5,8,0.7)",
        backdropFilter: "blur(12px)",
        position: "sticky",
        top: "60px",
        zIndex: 90,
      }}>
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "13px 18px",
                background: "none",
                color: active ? "var(--text)" : "var(--muted)",
                fontSize: "12px",
                fontWeight: active ? 600 : 400,
                borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
                transition: "all 0.2s",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                letterSpacing: "0.02em",
                whiteSpace: "nowrap",
              }}
            >
              <span style={{ fontSize: "13px", opacity: active ? 1 : 0.6 }}>{tab.icon}</span>
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* ── Main content ── */}
      <main style={{ padding: "28px", maxWidth: "1440px", margin: "0 auto" }}>
        {activeTab === "dashboard" && <Dashboard wsMessages={wsMessages} mainUrl={MAIN_URL} />}
        {activeTab === "submit"    && <SubmitComplaint mainUrl={MAIN_URL} />}
        {activeTab === "ledger"    && <PublicLedger mainUrl={MAIN_URL} />}
        {activeTab === "track"     && <TrackComplaint mainUrl={MAIN_URL} />}
        {activeTab === "control"   && <NodeControl mainUrl={MAIN_URL} />}
      </main>
    </div>
  );
}
