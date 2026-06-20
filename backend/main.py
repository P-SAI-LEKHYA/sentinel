import os
import sys
import time
import asyncio
import hashlib
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import httpx
import uvicorn

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chain import HashChain
from database import (
    init_db, insert_complaint, get_all_complaints,
    get_complaint_by_id, update_complaint_status,
    add_node_ack, get_complaints_by_token_hash, update_urgency_score
)
from models import ComplaintStatus, BroadcastResult
from utils.hasher import hash_bytes
from utils.metadata_strip import strip_metadata

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

app = FastAPI(title="SENTINEL — Main Broadcast Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

main_chain = HashChain()
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
            "total_complaints": len(main_chain.chain),
            "chain_head": main_chain.get_chain_head(),
            "node_urls": NODE_URLS
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ─── Broadcast ────────────────────────────────────────────────────

async def broadcast_to_nodes(complaint: dict, attempt: int = 1) -> BroadcastResult:
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

    tasks = [send_to_node(node_id, url) for node_id, url in NODE_URLS.items()]
    results = await asyncio.gather(*tasks)

    for node_id, success in results:
        if success:
            successful_nodes.append(node_id)
            add_node_ack(complaint["id"], node_id)
        else:
            failed_nodes.append(node_id)

    quorum_reached = len(successful_nodes) >= QUORUM_REQUIRED

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

    # Update all successful nodes to ACKNOWLEDGED
    if quorum_reached:
        async def update_node_status(url):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{url}/complaint/{complaint['id']}/status",
                        json={"status": "ACKNOWLEDGED"}
                    )
            except Exception:
                pass

        await asyncio.gather(*[
            update_node_status(url)
            for url in NODE_URLS.values()
        ])

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

# ─── Submit ───────────────────────────────────────────────────────

@app.post("/submit")
async def submit_complaint(
    file: UploadFile = File(...),
    complaint_type: str = Form(...),
    location: str = Form(...),
    token: str = Form(...)
):
    file_bytes = await file.read()
    file_name = file.filename

    temp_input = f"temp_input_{int(time.time())}_{file_name}"
    temp_output = f"temp_stripped_{int(time.time())}_{file_name}"

    with open(temp_input, "wb") as f:
        f.write(file_bytes)

    try:
        strip_result = strip_metadata(temp_input, temp_output)
        with open(temp_output, "rb") as f:
            stripped_bytes = f.read()
        evidence_hash = hash_bytes(stripped_bytes)
    except Exception as e:
        evidence_hash = hash_bytes(file_bytes)
        strip_result = {"status": "failed", "warning": str(e)}
    finally:
        for f in [temp_input, temp_output]:
            if os.path.exists(f):
                os.remove(f)

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    record = main_chain.add_complaint(
        evidence_hash=evidence_hash,
        complaint_type=complaint_type,
        location=location,
        token_hash=token_hash
    )

    insert_complaint(record)
    broadcast_result = await broadcast_to_nodes(record)

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

# ─── Verify ───────────────────────────────────────────────────────

@app.get("/verify/{complaint_id}")
async def verify_complaint(complaint_id: int):
    record = main_chain.get_complaint(complaint_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Step 1 — get record hash from all nodes
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

    our_hash = record["record_hash"]
    agreeing = [n for n, h in node_hashes.items() if h == our_hash]
    disagreeing = [n for n, h in node_hashes.items() if h != our_hash and h is not None]

    tamper_detected = len(actually_tampered) > 0

    quorum_met = len(agreeing) >= QUORUM_REQUIRED

    # Step 2 — for disagreeing nodes check if actually tampered
    # or just out of sync
    async def check_node_chain(node_id, url):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check node status first
                status_r = await client.get(f"{url}/status")
                if status_r.status_code == 200:
                    status_data = status_r.json()
                    # If simulating disagreement chain is intact
                    if status_data.get("simulating_disagreement"):
                        # Check if this specific complaint is in disagreeing set
                        disagreeing_list = status_data.get(
                            "disagreeing_complaints", []
                        )
                        if complaint_id in disagreeing_list:
                            return node_id, False  # not tampered just disagreeing
                    # Check actual chain validity
                    chain_invalid = not status_data.get("chain_valid", True)
                    return node_id, chain_invalid
        except Exception:
            return node_id, False
        return node_id, False

    chain_check_tasks = [
        check_node_chain(nid, NODE_URLS[nid])
        for nid in disagreeing
        if nid in NODE_URLS
    ]
    chain_results = await asyncio.gather(*chain_check_tasks)

    actually_tampered = [nid for nid, is_tampered in chain_results if is_tampered]
    out_of_sync = [nid for nid, is_tampered in chain_results if not is_tampered]

    # Step 3 — verified is based on actual tampering not just disagreement
    actually_compromised = len(actually_tampered) > 0
    verified = (not actually_compromised) and quorum_met

    # Step 4 — determine integrity status
    if len(disagreeing) == 0 and quorum_met:
        integrity_status = "INTACT"
    elif len(disagreeing) > 0 and len(actually_tampered) == 0 and quorum_met:
        integrity_status = "NODES_OUT_OF_SYNC"
    elif len(actually_tampered) > 0 and quorum_met:
        integrity_status = "TAMPERED_NODE_ISOLATED"
    elif len(actually_tampered) > 0 and not quorum_met:
        integrity_status = "QUORUM_FAILED_EVIDENCE_COMPROMISED"
    else:
        integrity_status = "UNKNOWN"

    # Step 5 — update node statuses
    for nid in actually_tampered:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{NODE_URLS[nid]}/complaint/{complaint_id}/status",
                    json={"status": "TAMPERED"}
                )
        except Exception:
            pass

    for nid in out_of_sync:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{NODE_URLS[nid]}/complaint/{complaint_id}/status",
                    json={"status": "DISAGREEING"}
                )
        except Exception:
            pass

    # Step 6 — handle compromised case
    if integrity_status == "QUORUM_FAILED_EVIDENCE_COMPROMISED":
        update_complaint_status(complaint_id, "COMPROMISED")
        async def update_all_nodes(url):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{url}/complaint/{complaint_id}/status",
                        json={"status": "COMPROMISED"}
                    )
            except Exception:
                pass
        await asyncio.gather(*[
            update_all_nodes(url)
            for url in NODE_URLS.values()
        ])
        await broadcast_to_dashboards({
            "type": "QUORUM_FAILED",
            "complaint_id": complaint_id,
            "agreeing_nodes": agreeing,
            "disagreeing_nodes": disagreeing,
            "timestamp": time.time()
        })

    public_record = {k: v for k, v in record.items() if k != "token_hash"}

    return {
        "complaint_id": complaint_id,
        "record": public_record,
        "integrity": {
            "hash": our_hash,
            "nodes_agreeing": agreeing,
            "nodes_disagreeing": disagreeing,
            "nodes_tampered": actually_tampered,
            "nodes_out_of_sync": out_of_sync,
            "tamper_detected": tamper_detected,
            "actually_compromised": actually_compromised,
            "quorum_met": quorum_met,
            "verified": verified,
            "integrity_status": integrity_status
        }
    }

# ─── Track ────────────────────────────────────────────────────────

@app.post("/track")
async def track_complaint(body: dict):
    token = body.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token required")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    complaints = get_complaints_by_token_hash(token_hash)
    if not complaints:
        raise HTTPException(status_code=404, detail="No complaints found for this token")
    public_complaints = []
    for c in complaints:
        public = {k: v for k, v in c.items() if k != "token_hash"}
        public_complaints.append(public)
    return {
        "found": len(public_complaints),
        "complaints": public_complaints
    }

# ─── Ledger ───────────────────────────────────────────────────────

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

# ─── Escalation ───────────────────────────────────────────────────

async def escalation_engine():
    while True:
        await asyncio.sleep(ESCALATION_INTERVAL)
        complaints = get_all_complaints()
        now = time.time()
        for complaint in complaints:
            if complaint["status"] in [
                "ACTIONED", "UNDER_INVESTIGATION", "COMPROMISED"
            ]:
                continue
            hours_pending = (now - complaint["timestamp"]) / 3600
            urgency = min(100.0, (hours_pending ** 1.5) * 2)
            update_urgency_score(complaint["id"], urgency)
            if hours_pending >= 48 and complaint["status"] == "ACKNOWLEDGED":
                update_complaint_status(
                    complaint["id"],
                    ComplaintStatus.UNACTIONED_DAY2.value
                )
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
    existing = get_all_complaints()
    for complaint in existing:
        main_chain.chain.append(complaint)
        main_chain.index[complaint["id"]] = len(main_chain.chain) - 1
    print(f"\n{'='*40}")
    print(f"SENTINEL Main Server starting on port {MAIN_PORT}")
    print(f"Loaded {len(main_chain.chain)} existing complaints")
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=MAIN_PORT, reload=False)