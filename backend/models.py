# backend/models.py

from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class ComplaintStatus(str, Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    ACTIONED = "ACTIONED"
    PARTIALLY_REPLICATED = "PARTIALLY_REPLICATED"
    FAILED_REPLICATION = "FAILED_REPLICATION"
    UNACTIONED_DAY2 = "UNACTIONED_DAY_2"

class ComplaintType(str, Enum):
    BRIBERY = "Bribery"
    FRAUD = "Fraud"
    EXTORTION = "Extortion"
    CORRUPTION = "Corruption"
    MISCONDUCT = "Misconduct"
    OTHER = "Other"

class NodeID(str, Enum):
    NGO = "NGO"
    MEDIA = "MEDIA"
    OMBUDSMAN = "OMBUDSMAN"
    PUBLIC = "PUBLIC"

# Request model — what whistleblower sends
class ComplaintSubmission(BaseModel):
    evidence_hash: str
    complaint_type: ComplaintType
    location: str
    token_hash: str
    file_name: str
    file_size_bytes: int

# Full complaint record stored in chain and DB
class ComplaintRecord(BaseModel):
    id: int
    timestamp: float
    evidence_hash: str
    complaint_type: str
    location: str
    token_hash: str
    prev_hash: str
    record_hash: str
    status: ComplaintStatus = ComplaintStatus.PENDING
    node_acks: List[str] = []
    urgency_score: float = 0.0

# What nodes send to each other during hash sync
class HashSyncPayload(BaseModel):
    node_id: NodeID
    chain_head: str
    total_records: int
    timestamp: float

# Node acknowledgement of complaint receipt
class NodeAck(BaseModel):
    node_id: NodeID
    complaint_id: int
    received_hash: str
    timestamp: float
    success: bool

# Anonymous tracking request
class TrackRequest(BaseModel):
    token_hash: str

# Public ledger complaint — no token_hash
class PublicComplaintRecord(BaseModel):
    id: int
    timestamp: float
    evidence_hash: str
    complaint_type: str
    location: str
    prev_hash: str
    record_hash: str
    status: str
    node_acks: List[str]
    urgency_score: float

# Tamper alert
class TamperAlert(BaseModel):
    detected_by_node: str
    tampered_node: str
    complaint_id: int
    expected_hash: str
    found_hash: str
    timestamp: float

# Broadcast result
class BroadcastResult(BaseModel):
    complaint_id: int
    successful_nodes: List[str]
    failed_nodes: List[str]
    quorum_reached: bool
    status: ComplaintStatus