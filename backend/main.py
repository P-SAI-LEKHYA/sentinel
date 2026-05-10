# backend/main.py

import os
import sys
import time
import asyncio
import hashlib
import secrets
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chain import HashChain
from database import init_db, insert_complaint, get_all_complaints, get_complaint_by_id, update_complaint_status, add_node_ack, get_complaints_by_token_hash, update_urgency_score
from models import ComplaintStatus, BroadcastResult
from utils.hasher import hash_bytes
from utils.metadata_strip import strip_metadata

# ─── Configuration ───────────────────────────────────────────────

NODE_URLS = {
    "NGO":       "http://localhost:8001",
    "MEDIA":     "http://localhost:8002",
    "OMBUDSMAN": "http://localhost:8003",
    "PUBLIC":    "http://localhost:8004",
}

QUORUM_REQUIRED = 3
BROADCAST_TIMEOUT = 10.0
REBROADCAST_ATTEMPTS = 3
ESCALATION_INTERVAL = 60
MAIN_PORT = 8000

# ─── App Setup ───────────────────────────────────────────────────

app = FastAPI(title="SENTINEL — Main Broadcast Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

main_chain = HashChain()
active_connections: List[WebSocket] = []

# ─── WebSocket ───────────────────────────────────────────────────

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
            "total_complaints": len(main_chain.chain),
            "chain_head": main_chain.get_chain_head(),
            "node_urls": NODE_URLS
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ─── Broadcast Logic ─────────────────────────────────────────────

async def broadcast_to_nodes(complaint: dict, attempt: int = 1) -> BroadcastResult:
    """
    Broadcast complaint to all four nodes in parallel.
    Uses asyncio.gather() — all requests fire simultaneously.
    Checks quorum — minimum 3 of 4 must acknowledge.
    Retries up to 3 times if quorum not met.
    """
    
    successful_nodes = []
    failed_nodes = []
    
    async def send_to_node(node_id: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=BROADCAST_TIMEOUT) as client:
                response = await client.post(
                    f"{url}/complaint/receive",
                    json=complaint
                )
                if response.status_code == 200:
                    return node_id, True
                return node_id, False
        except Exception as e:
            print(f"Broadcast failed to {node_id}: {e}")
            return node_id, False
    
    # Fire all four requests simultaneously
    tasks = [send_to_node(node_id, url) for node_id, url in NODE_URLS.items()]
    results = await asyncio.gather(*tasks)
    
    for node_id, success in results:
        if success:
            successful_nodes.append(node_id)
            add_node_ack(complaint["id"], node_id)
        else:
            failed_nodes.append(node_id)
    
    quorum_reached = len(successful_nodes) >= QUORUM_REQUIRED
    
    # If quorum not met retry up to 3 times
    if not quorum_reached and attempt < REBROADCAST_ATTEMPTS:
        print(f"Quorum not met ({len(successful_nodes)}/4). Retrying attempt {attempt + 1}...")
        await asyncio.sleep(2)
        return await broadcast_to_nodes(complaint, attempt + 1)
    
    if quorum_reached:
        status = ComplaintStatus.ACKNOWLEDGED
    elif len(successful_nodes) > 0:
        status = ComplaintStatus.PARTIALLY_REPLICATED
    else:
        status = ComplaintStatus.FAILED_REPLICATION
    
    update_complaint_status(complaint["id"], status.value)
    
    await broadcast_to_dashboards({
        "type": "BROADCAST_RESULT",
        "complaint_id": complaint["id"],
        "successful_nodes": successful_nodes,
        "failed_nodes": failed_nodes,
        "quorum_reached": quorum_reached,
        "status": status.value,
        "timestamp": time.time()
    })
    
    return BroadcastResult(
        complaint_id=complaint["id"],
        successful_nodes=successful_nodes,
        failed_nodes=failed_nodes,
        quorum_reached=quorum_reached,
        status=status
    )

# ─── Main Submission Endpoint ─────────────────────────────────────

@app.post("/submit")
async def submit_complaint(
    file: UploadFile = File(...),
    complaint_type: str = Form(...),
    location: str = Form(...),
    token: str = Form(...)
):
    """
    Main submission endpoint called by frontend.
    
    Full flow:
    1. Receive file upload
    2. Strip metadata
    3. Hash the cleaned file
    4. Hash the token (token itself never stored)
    5. Add to main chain
    6. Broadcast to all four nodes in parallel
    7. Check quorum
    8. Return tracking token to whistleblower
    """
    
    # Step 1 — Read file bytes
    file_bytes = await file.read()
    file_name = file.filename
    
    # Step 2 — Save temporarily for metadata stripping
    temp_input = f"temp_input_{int(time.time())}_{file_name}"
    temp_output = f"temp_stripped_{int(time.time())}_{file_name}"
    
    with open(temp_input, "wb") as f:
        f.write(file_bytes)
    
    try:
        strip_result = strip_metadata(temp_input, temp_output)
        
        # Step 3 — Hash the stripped file
        with open(temp_output, "rb") as f:
            stripped_bytes = f.read()
        
        evidence_hash = hash_bytes(stripped_bytes)
        
    except Exception as e:
        evidence_hash = hash_bytes(file_bytes)
        strip_result = {"status": "failed", "warning": str(e)}
    
    finally:
        # Clean up temp files
        for f in [temp_input, temp_output]:
            if os.path.exists(f):
                os.remove(f)
    
    # Step 4 — Hash the token
    # Token itself NEVER stored — only its hash
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    # Step 5 — Add to main chain
    record = main_chain.add_complaint(
        evidence_hash=evidence_hash,
        complaint_type=complaint_type,
        location=location,
        token_hash=token_hash
    )
    
    # Persist to main database
    insert_complaint(record)
    
    # Step 6 — Broadcast to all nodes in parallel
    broadcast_result = await broadcast_to_nodes(record)
    
    # Step 7 — Notify dashboards
    await broadcast_to_dashboards({
        "type": "NEW_SUBMISSION",
        "complaint_id": record["id"],
        "complaint_type": complaint_type,
        "location": location,
        "evidence_hash": evidence_hash,
        "record_hash": record["record_hash"],
        "quorum_reached": broadcast_result.quorum_reached,
        "successful_nodes": broadcast_result.successful_nodes,
        "strip_result": strip_result,
        "timestamp": record["timestamp"]
    })
    
    return {
        "success": True,
        "complaint_id": record["id"],
        "evidence_hash": evidence_hash,
        "record_hash": record["record_hash"],
        "quorum_reached": broadcast_result.quorum_reached,
        "successful_nodes": broadcast_result.successful_nodes,
        "failed_nodes": broadcast_result.failed_nodes,
        "status": broadcast_result.status.value,
        "tracking_token": token,
        "message": "Complaint submitted and replicated across nodes"
    }

# ─── Public Verification Endpoint ────────────────────────────────

@app.get("/verify/{complaint_id}")
async def verify_complaint(complaint_id: int):
    """
    Open public endpoint — no auth required.
    Anyone can verify a complaint exists and is untampered.
    """
    record = main_chain.get_complaint(complaint_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    # Check integrity across all nodes
    node_hashes = {}
    async def check_node(node_id, url):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{url}/complaint/{complaint_id}")
                if r.status_code == 200:
                    data = r.json()
                    return node_id, data.get("record_hash")
        except Exception:
            return node_id, None
        return node_id, None
    
    tasks = [check_node(nid, url) for nid, url in NODE_URLS.items()]
    results = await asyncio.gather(*tasks)
    
    for node_id, node_hash in results:
        node_hashes[node_id] = node_hash
    
    # Check how many nodes agree on the hash
    our_hash = record["record_hash"]
    agreeing = [n for n, h in node_hashes.items() if h == our_hash]
    disagreeing = [n for n, h in node_hashes.items() if h != our_hash and h is not None]

    tamper_detected = len(disagreeing) > 0

# verified means:
# 1. No tamper detected AND
# 2. Quorum of honest nodes agree
    verified = (not tamper_detected) and (len(agreeing) >= QUORUM_REQUIRED)

    public_record = {k: v for k, v in record.items() if k != "token_hash"}

    return {
        "complaint_id": complaint_id,
        "record": public_record,
        "integrity": {
            "hash": our_hash,
            "nodes_agreeing": agreeing,
            "nodes_disagreeing": disagreeing,
            "tamper_detected": tamper_detected,
            "verified": verified
        }
    }
    
    

# ─── Anonymous Tracking ───────────────────────────────────────────

@app.post("/track")
async def track_complaint(body: dict):
    """
    Whistleblower enters their token to track complaint.
    We hash the token and look up by token_hash.
    Original token never stored — cannot be recovered.
    """
    token = body.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    complaints = get_complaints_by_token_hash(token_hash)
    
    if not complaints:
        raise HTTPException(status_code=404, detail="No complaints found for this token")
    
    # Strip sensitive fields before returning
    public_complaints = []
    for c in complaints:
        public = {k: v for k, v in c.items() if k != "token_hash"}
        public_complaints.append(public)
    
    return {
        "found": len(public_complaints),
        "complaints": public_complaints
    }

# ─── Public Ledger ────────────────────────────────────────────────

@app.get("/ledger")
def get_public_ledger():
    return {
        "total": len(main_chain.chain),
        "chain_head": main_chain.get_chain_head(),
        "complaints": main_chain.export_for_public_ledger()
    }

@app.get("/ledger/verify")
def verify_full_chain():
    return main_chain.verify_chain()

# ─── Escalation Engine ────────────────────────────────────────────

async def escalation_engine():
    """
    Runs every 60 seconds.
    Increases urgency score for unactioned complaints.
    Non-linear growth — longer ignored = much higher urgency.
    Marks complaints UNACTIONED_DAY_2 after 48 hours.
    """
    while True:
        await asyncio.sleep(ESCALATION_INTERVAL)
        
        complaints = get_all_complaints()
        now = time.time()
        
        for complaint in complaints:
            if complaint["status"] in ["ACTIONED", "UNDER_INVESTIGATION"]:
                continue
            
            hours_pending = (now - complaint["timestamp"]) / 3600
            
            # Non-linear urgency — squares with time
            urgency = min(100.0, (hours_pending ** 1.5) * 2)
            update_urgency_score(complaint["id"], urgency)
            
            # Mark as UNACTIONED after 48 hours
            if hours_pending >= 48 and complaint["status"] == "ACKNOWLEDGED":
                update_complaint_status(complaint["id"], ComplaintStatus.UNACTIONED_DAY2.value)
                
                await broadcast_to_dashboards({
                    "type": "ESCALATION",
                    "complaint_id": complaint["id"],
                    "hours_pending": hours_pending,
                    "urgency_score": urgency,
                    "new_status": ComplaintStatus.UNACTIONED_DAY2.value,
                    "timestamp": now
                })

# ─── Startup ──────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    
    # Rebuild in-memory chain from database on every startup
    # This keeps main_chain in sync with what's actually stored
    existing = get_all_complaints()
    for complaint in existing:
        main_chain.chain.append(complaint)
        main_chain.index[complaint["id"]] = len(main_chain.chain) - 1
    
    print(f"\n{'='*40}")
    print(f"SENTINEL Main Server starting on port {MAIN_PORT}")
    print(f"Loaded {len(main_chain.chain)} existing complaints from database")
    print(f"Chain head: {main_chain.get_chain_head()[:16]}...")
    print(f"{'='*40}\n")
    asyncio.create_task(escalation_engine())
@app.get("/")
def root():
    return {
        "service": "SENTINEL Main Broadcast Server",
        "port": MAIN_PORT,
        "nodes": NODE_URLS,
        "total_complaints": len(main_chain.chain),
        "quorum_required": QUORUM_REQUIRED
    }

# ─── Run ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=MAIN_PORT, reload=False)