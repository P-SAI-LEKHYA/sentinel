import { useState } from "react";

export default function SubmitComplaint({ mainUrl }) {
  const [file,          setFile]          = useState(null);
  const [complaintType, setComplaintType] = useState("Bribery");
  const [location,      setLocation]      = useState("");
  const [token,         setToken]         = useState("");
  const [submitting,    setSubmitting]    = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [result,        setResult]        = useState(null);
  const [error,         setError]         = useState(null);
  const [isDragActive, setIsDragActive]   = useState(false);
  const [copiedToken,   setCopiedToken]   = useState(false);
  const [copiedHash,    setCopiedHash]    = useState(false);

  // Generate a random token on load
  function generateToken() {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let autoToken = "";
    for (let i = 0; i < 16; i++) {
      autoToken += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setToken(autoToken);
  }

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  async function handleSubmit() {
    if (!file || !location || !token) {
      setError("Please fill all fields and upload a file.");
      return;
    }
    setSubmitting(true);
    setUploadProgress(0);
    setResult(null);
    setError(null);

    // Simulate progress bar increase for UI premium feel
    const interval = setInterval(() => {
      setUploadProgress((old) => {
        if (old >= 90) {
          clearInterval(interval);
          return 90;
        }
        return old + 15;
      });
    }, 150);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("complaint_type", complaintType);
      formData.append("location", location);
      formData.append("token", token);

      const res = await fetch(`${mainUrl}/submit`, { method: "POST", body: formData });
      const data = await res.json();
      
      clearInterval(interval);
      setUploadProgress(100);

      if (res.ok) {
        setResult(data);
        setFile(null);
        setLocation("");
      } else {
        setError(data.detail || "Submission failed");
      }
    } catch (_) {
      clearInterval(interval);
      setError("Could not reach main broadcast server.");
    } finally {
      setSubmitting(false);
    }
  }

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    if (type === "token") {
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    } else {
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: "680px", margin: "0 auto" }}>
      <div className="card">
        <h2 style={{ fontSize: "18px", fontWeight: 700, marginBottom: "4px" }}>File Anonymous Incident Report</h2>
        <p style={{ color: "var(--text-2)", fontSize: "13px", marginBottom: "24px" }}>
          Metadata is stripped automatically. Access tokens are hashed using SHA-256 before storage.
        </p>

        {/* File Drag and Drop */}
        <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "6px" }}>
          EVIDENCE ARCHIVE (IMAGE/VIDEO/PDF/AUDIO)
        </div>
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => document.getElementById("file-input").click()}
          style={{
            border: `2px dashed ${isDragActive ? "var(--accent)" : file ? "rgba(124, 58, 237, 0.4)" : "var(--border)"}`,
            borderRadius: "10px",
            padding: "30px 20px",
            textAlign: "center",
            cursor: "pointer",
            background: isDragActive ? "rgba(124, 58, 237, 0.05)" : "var(--bg-2)",
            transition: "all 0.2s ease-in-out",
            marginBottom: "18px",
          }}
        >
          <input
            id="file-input"
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
            style={{ display: "none" }}
            accept="image/*,video/*,audio/*,.pdf"
          />
          {file ? (
            <div>
              <div style={{ fontSize: "32px", marginBottom: "8px" }}>📄</div>
              <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--text)" }}>{file.name}</div>
              <div style={{ color: "var(--muted)", fontSize: "11px", marginTop: "4px" }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: "32px", marginBottom: "8px", opacity: 0.8 }}>📥</div>
              <div style={{ color: "var(--text)", fontWeight: 500, fontSize: "13px" }}>
                Drag and drop your evidence here or <span style={{ color: "var(--accent)" }}>Browse files</span>
              </div>
              <div style={{ color: "var(--muted)", fontSize: "11px", marginTop: "4px" }}>
                Supported formats: PDF, MP4, MP3, JPG, PNG
              </div>
            </div>
          )}
        </div>

        {/* Grid for Form Details */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "18px" }}>
          <div>
            <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "6px" }}>
              COMPLAINT CLASSIFICATION
            </div>
            <select value={complaintType} onChange={(e) => setComplaintType(e.target.value)}>
              {["Bribery", "Fraud", "Extortion", "Corruption", "Misconduct", "Other"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div>
            <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "6px" }}>
              INCIDENT LOCATION
            </div>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Headquarters, Region B"
            />
          </div>
        </div>

        {/* Access Token */}
        <div style={{ marginBottom: "22px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
            <span style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700 }}>
              PRIVATE ACCESS TOKEN
            </span>
            <button
              onClick={generateToken}
              style={{ background: "none", color: "var(--accent)", fontSize: "11px", fontWeight: 600 }}
            >
              🔑 Auto-generate
            </button>
          </div>
          <input
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter a secret password or token to track your submission status"
          />
          <div style={{ color: "var(--muted)", fontSize: "10px", marginTop: "4px" }}>
            Do not lose this token. It is needed to track progress and cannot be recovered.
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="animate-slide-in" style={{
            color: "var(--red)", fontSize: "12px", marginBottom: "16px",
            background: "var(--red-dim)", border: "1px solid rgba(239, 68, 68, 0.2)",
            borderRadius: "8px", padding: "10px 14px",
          }}>
            {error}
          </div>
        )}

        {/* Submit Button */}
        {submitting ? (
          <div style={{ marginBottom: "10px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
              <span style={{ color: "var(--muted)" }}>Processing & Hashing Evidence...</span>
              <span style={{ color: "var(--accent)", fontWeight: 700 }}>{uploadProgress}%</span>
            </div>
            <div className="progress-bar" style={{ height: "6px" }}>
              <div className="progress-fill" style={{ width: `${uploadProgress}%`, background: "var(--gradient)" }} />
            </div>
          </div>
        ) : (
          <button onClick={handleSubmit} className="btn-primary" style={{ width: "100%", padding: "12px" }}>
            Cryptographically Sign & Submit Complaint
          </button>
        )}
      </div>

      {/* Success Result Panel */}
      {result && (
        <div className="animate-slide-in" style={{
          background: "var(--green-dim)",
          border: "1px solid rgba(16, 185, 129, 0.3)",
          borderRadius: "14px", padding: "20px", marginTop: "20px",
        }}>
          <h3 style={{ color: "var(--green)", fontWeight: 700, fontSize: "15px", marginBottom: "12px" }}>
            ✓ Report Filed Successfully
          </h3>
          
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "14px" }}>
            <Row label="Complaint ID" value={`#${result.complaint_id}`} />
            <Row label="Initial Status" value={result.status} color="var(--green)" />
            <Row label="Consensus Quorum Met" value={result.quorum_reached ? "YES (3/4 Nodes)" : "NO"} />
            <Row label="Replicated Nodes" value={result.successful_nodes?.join(", ") || "None"} />
          </div>

          <div style={{ marginBottom: "14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
              <span style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.06em", fontWeight: 700 }}>
                STRIPPED EVIDENCE HASH
              </span>
              <button
                onClick={() => copyToClipboard(result.evidence_hash, "hash")}
                style={{ background: "none", color: "var(--accent)", fontSize: "10px", fontWeight: 600 }}
              >
                {copiedHash ? "Copied! ✓" : "Copy Hash"}
              </button>
            </div>
            <div className="hash-display">{result.evidence_hash}</div>
          </div>

          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "8px", padding: "12px 14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "3px" }}>
              <span style={{ color: "var(--amber)", fontSize: "12px", fontWeight: 700 }}>
                SAVE SECURE ACCESS TOKEN
              </span>
              <button
                onClick={() => copyToClipboard(result.tracking_token, "token")}
                style={{ background: "none", color: "var(--accent)", fontSize: "11px", fontWeight: 600 }}
              >
                {copiedToken ? "Copied! ✓" : "Copy Token"}
              </button>
            </div>
            <p style={{ color: "var(--text-2)", fontSize: "12px" }}>
              Use token <strong style={{ color: "var(--text)" }}>{result.tracking_token}</strong> under the "Track" tab to follow the investigation anonymously.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, color }) {
  return (
    <div style={{ background: "var(--bg)", padding: "10px", borderRadius: "8px" }}>
      <div style={{ color: "var(--muted)", fontSize: "9px", letterSpacing: "0.08em", fontWeight: 700, marginBottom: "2px" }}>
        {label}
      </div>
      <div style={{ color: color || "var(--text)", fontWeight: 600, fontSize: "12px" }}>{value}</div>
    </div>
  );
}
