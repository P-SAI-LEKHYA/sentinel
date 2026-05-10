# backend/nodes/node_server.py

import sys
import os
import time
import asyncio
import hashlib
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add backend directory to path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)

# ─── Node Identity ────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("Usage: python node_server.py <NODE_ID> <PORT>")
    print("Example: python node_server.py NGO 8001")
    sys.exit(1)

NODE_ID = sys.argv[1].upper()
PORT = int(sys.argv[2])

VALID_NODES = ["NGO", "MEDIA", "OMBUDSMAN", "PUBLIC"]
if NODE_ID not in VALID_NODES:
    print(f"Invalid node ID. Must be one of: {VALID_NODES}")
    sys.exit(1)

# Set database path BEFORE importing database module
DB_FILE = os.path.join(BACKEND_DIR, f"sentinel_{NODE_ID.lower()}.db")

# Import database and set path
import database
database.set_db_path(DB_FILE)

from database import (
    init_db, insert_complaint, get_all_complaints,
    update_complaint_status, add_node_ack,
    insert_tamper_alert, update_node_trust, get_all_node_trust
)
from chain import HashChain
from models import ComplaintStatus

NODE_URLS = {
    "NGO":       "http://localhost:8001",
    "MEDIA":     "http://localhost:8002",
    "OMBUDSMAN": "http://localhost:8003",
    "PUBLIC":    "http://localhost:8004",
}

# ─── App Setup ────────────────────────────────────────────────────
app = FastAPI(title=f"SENTINEL Node — {NODE_ID}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

chain = HashChain()
active_connections: List[WebSocket] = []

# ─── WebSocket ────────────────────────────────────────────────────
async def broadcast_to_dashboards(message: dict):
    disconnected = []
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_connections.remove(ws)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        await websocket.send_json({
            "type": "INIT",
            "node_id": NODE_ID,
            "total_complaints": len(chain.chain),
            "chain_head": chain.get_chain_head(),
            "trust_scores": get_all_node_trust()
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ─── Routes ───────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "node": NODE_ID,
        "port": PORT,
        "status": "ONLINE",
        "total_complaints": len(chain.chain),
        "chain_head": chain.get_chain_head()
    }

@app.post("/complaint/receive")
async def receive_complaint(complaint: dict):
    try:
        # Store exactly what main server sent — don't rebuild
        record = complaint.copy()
        
        # Add to in-memory chain
        chain.chain.append(record)
        chain.index[record["id"]] = len(chain.chain) - 1
        
        # Persist to this node's database
        insert_complaint(record)
        
        # Mark acknowledgement
        add_node_ack(record["id"], NODE_ID)
        
        await broadcast_to_dashboards({
            "type": "NEW_COMPLAINT",
            "node_id": NODE_ID,
            "complaint_id": record["id"],
            "complaint_type": record["complaint_type"],
            "location": record["location"],
            "timestamp": record["timestamp"],
            "record_hash": record["record_hash"],
            "chain_head": chain.get_chain_head(),
            "total_complaints": len(chain.chain)
        })
        
        return {
            "success": True,
            "node_id": NODE_ID,
            "complaint_id": record["id"],
            "record_hash": record["record_hash"],
            "acknowledged_at": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chain/verify")
async def verify_chain():
    result = chain.verify_chain()
    if not result["valid"]:
        await broadcast_to_dashboards({
            "type": "TAMPER_DETECTED",
            "node_id": NODE_ID,
            "tampered_record": result["tampered_record"],
            "message": result["message"],
            "timestamp": time.time()
        })
    return result

@app.get("/chain/head")
def get_chain_head():
    return {
        "node_id": NODE_ID,
        "chain_head": chain.get_chain_head(),
        "total_records": len(chain.chain),
        "timestamp": time.time()
    }

@app.get("/chain/all")
def get_all_chain():
    return {
        "node_id": NODE_ID,
        "complaints": chain.export_for_public_ledger(),
        "chain_head": chain.get_chain_head(),
        "total": len(chain.chain)
    }

@app.get("/complaint/{complaint_id}")
def get_complaint(complaint_id: int):
    record = chain.get_complaint(complaint_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    public = {k: v for k, v in record.items() if k != "token_hash"}
    return public

@app.post("/complaint/{complaint_id}/action")
async def mark_actioned(complaint_id: int, body: dict):
    status = body.get("status", "ACTIONED")
    update_complaint_status(complaint_id, status)
    chain.update_complaint_status(complaint_id, status, NODE_ID)
    await broadcast_to_dashboards({
        "type": "STATUS_UPDATE",
        "node_id": NODE_ID,
        "complaint_id": complaint_id,
        "new_status": status,
        "timestamp": time.time()
    })
    return {"success": True, "complaint_id": complaint_id, "status": status}

@app.post("/sync/hash")
async def receive_hash_sync(payload: dict):
    their_node_id = payload.get("node_id")
    their_chain_head = payload.get("chain_head")
    their_total = payload.get("total_records", 0)
    our_chain_head = chain.get_chain_head()
    our_total = len(chain.chain)
    
    if their_total == our_total and their_chain_head != our_chain_head:
        alert = {
            "detected_by_node": NODE_ID,
            "tampered_node": their_node_id,
            "complaint_id": our_total,
            "expected_hash": our_chain_head,
            "found_hash": their_chain_head,
            "timestamp": time.time()
        }
        insert_tamper_alert(alert)
        await broadcast_to_dashboards({
            "type": "TAMPER_ALERT",
            "detected_by": NODE_ID,
            "suspect_node": their_node_id,
            "our_head": our_chain_head,
            "their_head": their_chain_head,
            "timestamp": time.time()
        })
        return {
            "match": False,
            "alert": "HASH_MISMATCH",
            "suspect_node": their_node_id
        }
    
    return {
        "match": their_chain_head == our_chain_head,
        "our_head": our_chain_head,
        "their_head": their_chain_head
    }

@app.get("/trust/scores")
def get_trust_scores():
    return get_all_node_trust()

@app.post("/simulate/tamper/{complaint_id}")
async def simulate_tamper(complaint_id: int):
    record = chain.get_complaint(complaint_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    # Modify both evidence_hash and record_hash so verify/1 catches it
    chain.chain[complaint_id - 1]["evidence_hash"] = "TAMPERED_" + "0" * 55
    chain.chain[complaint_id - 1]["record_hash"] = "TAMPERED_" + "0" * 55
    
    await broadcast_to_dashboards({
        "type": "TAMPER_SIMULATED",
        "node_id": NODE_ID,
        "complaint_id": complaint_id,
        "message": f"Evidence hash modified on {NODE_ID} node",
        "timestamp": time.time()
    })
    
    return {
        "tampered": True,
        "node": NODE_ID,
        "complaint_id": complaint_id,
        "message": "Record modified — run /chain/verify on any node to detect"
    }

# ─── Background Hash Sync ─────────────────────────────────────────
async def periodic_hash_sync():
    import httpx
    await asyncio.sleep(30)
    while True:
        await asyncio.sleep(60)
        other_nodes = {k: v for k, v in NODE_URLS.items() if k != NODE_ID}
        payload = {
            "node_id": NODE_ID,
            "chain_head": chain.get_chain_head(),
            "total_records": len(chain.chain),
            "timestamp": time.time()
        }
        for node_id, url in other_nodes.items():
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(f"{url}/sync/hash", json=payload)
                    elapsed_ms = (time.time() - start) * 1000
                    result = response.json()
                    success = result.get("match", False)
                    update_node_trust(node_id, success, elapsed_ms)
                    if not result.get("match", True):
                        print(f"[{NODE_ID}] HASH MISMATCH with {node_id}")
                        await broadcast_to_dashboards({
                            "type": "SYNC_MISMATCH",
                            "our_node": NODE_ID,
                            "their_node": node_id,
                            "timestamp": time.time()
                        })
            except Exception as e:
                elapsed_ms = (time.time() - start) * 1000
                update_node_trust(node_id, False, elapsed_ms)
                print(f"[{NODE_ID}] Sync failed with {node_id}: {e}")

@app.on_event("startup")
async def startup():
    init_db()
    
    # Rebuild chain from this node's database on startup
    existing = get_all_complaints()
    for complaint in existing:
        chain.chain.append(complaint)
        chain.index[complaint["id"]] = len(chain.chain) - 1
    
    print(f"\n{'='*40}")
    print(f"SENTINEL Node {NODE_ID} starting on port {PORT}")
    print(f"Database: {DB_FILE}")
    print(f"Loaded {len(chain.chain)} existing complaints")
    print(f"{'='*40}\n")
    asyncio.create_task(periodic_hash_sync())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)