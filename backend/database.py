import os
import json
import time
import sqlite3
from typing import List, Optional

# All db files will be created in backend/ folder
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(BACKEND_DIR, "sentinel.db")

def set_db_path(path: str):
    global _DB_PATH
    _DB_PATH = path
    print(f"Database path: {_DB_PATH}")

def get_connection():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY,
            timestamp REAL NOT NULL,
            evidence_hash TEXT NOT NULL,
            complaint_type TEXT NOT NULL,
            location TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            node_acks TEXT DEFAULT '[]',
            urgency_score REAL DEFAULT 0.0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tamper_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_by_node TEXT NOT NULL,
            tampered_node TEXT NOT NULL,
            complaint_id INTEGER NOT NULL,
            expected_hash TEXT NOT NULL,
            found_hash TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS node_trust (
            node_id TEXT PRIMARY KEY,
            total_checks INTEGER DEFAULT 0,
            failed_checks INTEGER DEFAULT 0,
            avg_response_ms REAL DEFAULT 0.0,
            last_seen REAL DEFAULT 0.0,
            trust_score REAL DEFAULT 100.0
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {_DB_PATH}")

def insert_complaint(record: dict) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO complaints 
            (id, timestamp, evidence_hash, complaint_type, location,
             token_hash, prev_hash, record_hash, status, node_acks, urgency_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            record["id"],
            record["timestamp"],
            record["evidence_hash"],
            record["complaint_type"],
            record["location"],
            record.get("token_hash", ""),
            record["prev_hash"],
            record["record_hash"],
            record.get("status", "PENDING"),
            json.dumps(record.get("node_acks", [])),
            record.get("urgency_score", 0.0)
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB insert error: {e}")
        return False

def get_complaint_by_id(complaint_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    result["node_acks"] = json.loads(result["node_acks"])
    return result

def get_all_complaints() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        r = dict(row)
        r["node_acks"] = json.loads(r["node_acks"])
        result.append(r)
    return result

def update_complaint_status(complaint_id: int, status: str) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE complaints SET status = ? WHERE id = ?",
            (status, complaint_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB update error: {e}")
        return False

def add_node_ack(complaint_id: int, node_id: str) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT node_acks FROM complaints WHERE id = ?",
            (complaint_id,)
        )
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return False
        acks = json.loads(row["node_acks"])
        if node_id not in acks:
            acks.append(node_id)
        cursor.execute(
            "UPDATE complaints SET node_acks = ? WHERE id = ?",
            (json.dumps(acks), complaint_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB ack error: {e}")
        return False

def insert_tamper_alert(alert: dict) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tamper_alerts
            (detected_by_node, tampered_node, complaint_id,
             expected_hash, found_hash, timestamp)
            VALUES (?,?,?,?,?,?)
        """, (
            alert["detected_by_node"],
            alert["tampered_node"],
            alert["complaint_id"],
            alert["expected_hash"],
            alert["found_hash"],
            alert["timestamp"]
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB tamper alert error: {e}")
        return False

def get_complaints_by_token_hash(token_hash: str) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM complaints WHERE token_hash = ? ORDER BY id ASC",
        (token_hash,)
    )
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        r = dict(row)
        r["node_acks"] = json.loads(r["node_acks"])
        result.append(r)
    return result

def update_urgency_score(complaint_id: int, score: float) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE complaints SET urgency_score = ? WHERE id = ?",
            (score, complaint_id)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB urgency error: {e}")
        return False

def update_node_trust(node_id: str, success: bool, response_ms: float) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM node_trust WHERE node_id = ?", (node_id,)
        )
        row = cursor.fetchone()
        
        if row is None:
            cursor.execute("""
                INSERT INTO node_trust 
                (node_id, total_checks, failed_checks, avg_response_ms, last_seen, trust_score)
                VALUES (?, 1, ?, ?, ?, ?)
            """, (node_id, 0 if success else 1, response_ms, time.time(), 100.0 if success else 80.0))
        else:
            total = row["total_checks"] + 1
            failed = row["failed_checks"] + (0 if success else 1)
            avg_ms = (row["avg_response_ms"] * row["total_checks"] + response_ms) / total
            consistency = ((total - failed) / total) * 45
            uptime = 25.0
            latency_score = max(0, 20 - (avg_ms / 100)) if avg_ms < 2000 else 0
            false_alert_penalty = 10.0
            trust = consistency + uptime + latency_score + false_alert_penalty
            trust = max(0.0, min(100.0, trust))
            cursor.execute("""
                UPDATE node_trust
                SET total_checks=?, failed_checks=?, avg_response_ms=?,
                    last_seen=?, trust_score=?
                WHERE node_id=?
            """, (total, failed, avg_ms, time.time(), trust, node_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB trust error: {e}")
        return False

def get_all_node_trust() -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM node_trust")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")
    complaints = get_all_complaints()
    print(f"Current complaints in DB: {len(complaints)}")