# backend/chain.py

import hashlib
import json
import time
from typing import Optional
from utils.hasher import hash_bytes
class HashChain:
    """
    The core data structure of SENTINEL.
    
    An append-only linked list where each node contains
    the hash of the previous node. This means:
    
    - You cannot delete a record without breaking the chain
    - You cannot modify a record without breaking the chain
    - You cannot reorder records without breaking the chain
    - Any tampering is immediately detectable by recomputing hashes
    
    This is the same principle as blockchain but without
    distributed consensus overhead — we handle consistency
    through our quorum replication model instead.
    """
    
    def __init__(self):
        # The chain is stored as a simple Python list in memory.
        # In production this syncs with PostgreSQL — database.py handles that.
        # chain.py only handles the logic, not the persistence.
        self.chain = []
        
        # Index for fast lookup by complaint ID.
        # Without this, finding complaint #500 requires scanning 500 records.
        # With this, it's instant O(1) dictionary lookup.
        self.index = {}
        
        # The genesis hash — what the first complaint's prev_hash points to.
        # All zeros by convention, same as Bitcoin's genesis block.
        # This is a well-known constant so any verifier knows what to expect.
        self.GENESIS_HASH = "0" * 64
    
    def _compute_record_hash(self, record: dict) -> str:
        """
        Takes a complaint record dict and computes its SHA-256 hash.
        
        Critical design decision: we serialize the record to JSON
        with sorted keys before hashing. This guarantees that
        {"id": 1, "timestamp": 123} and {"timestamp": 123, "id": 1}
        produce IDENTICAL hashes — key order doesn't matter.
        
        Without sort_keys=True, Python dicts with same content
        but different insertion order would produce different hashes.
        That would be a serious bug — false tamper alerts everywhere.
        """
        
        # We hash everything EXCEPT record_hash itself
        # because record_hash is what we're computing right now.
        # Including it would be circular.
        record_without_self_hash = {
            k: v for k, v in record.items() 
            if k not in ("record_hash", "status", "node_acks", "urgency_score")
        }
        
        # Serialize to JSON string with sorted keys
        # separators=(',', ':') removes whitespace — consistent byte output
        record_string = json.dumps(
            record_without_self_hash, 
            sort_keys=True,
            separators=(',', ':')
        )
        
        # Hash the JSON string
        return hashlib.sha256(record_string.encode('utf-8')).hexdigest()
    
    def add_complaint(
        self,
        evidence_hash: str,
        complaint_type: str,
        location: str,
        token_hash: str,
        timestamp: Optional[float] = None
    ) -> dict:
        """
        Adds a new complaint to the chain.
        
        Parameters:
            evidence_hash:   SHA-256 hash of the evidence file
                             computed by hasher.py AFTER metadata stripping
            complaint_type:  category string eg "Bribery"
            location:        district/city — never GPS coordinates
            token_hash:      SHA-256 of the whistleblower's 256-bit token
                             the token itself never reaches this function
            timestamp:       Unix time — defaults to now
                             only override in tests
        
        Returns the complete complaint record that was added.
        """
        
        # Determine previous hash
        # If chain is empty this is the first complaint — use genesis hash
        # Otherwise use the hash of the most recent complaint
        if len(self.chain) == 0:
            prev_hash = self.GENESIS_HASH
        else:
            prev_hash = self.chain[-1]["record_hash"]
        
        # Build the record — everything except record_hash
        # because we need to compute that from the record itself
        record = {
            "id":             len(self.chain) + 1,
            "timestamp":      timestamp if timestamp else time.time(),
            "evidence_hash":  evidence_hash,
            "complaint_type": complaint_type,
            "location":       location,
            "token_hash":     token_hash,
            "prev_hash":      prev_hash,
            "status":         "PENDING",
            "node_acks":      [],    # which nodes acknowledged receipt
            "record_hash":    ""     # placeholder, computed next line
        }
        
        # Now compute the record hash from all the above fields
        record["record_hash"] = self._compute_record_hash(record)
        
        # Append to chain
        self.chain.append(record)
        
        # Add to index for fast lookup
        self.index[record["id"]] = len(self.chain) - 1
        
        return record
    
    def verify_chain(self) -> dict:
        """
        Walks the entire chain and verifies every hash.
        
        This is what your tamper detection calls every 60 seconds.
        It checks three things for every record:
        
        1. Does prev_hash match the actual previous record's hash?
           If no — a record was deleted or reordered
        
        2. Does record_hash match what we get when we recompute it?
           If no — this record was modified after insertion
        
        3. Is the chain contiguous? No gaps in IDs?
           If no — a record was deleted
        
        Time complexity: O(n) where n is number of complaints.
        For 10,000 complaints this takes milliseconds.
        """
        
        if len(self.chain) == 0:
            return {
                "valid": True,
                "message": "Chain is empty",
                "total_records": 0,
                "tampered_record": None
            }
        
        for i, record in enumerate(self.chain):
            
            # Check 1 — prev_hash linkage
            expected_prev = self.GENESIS_HASH if i == 0 else self.chain[i-1]["record_hash"]
            
            if record["prev_hash"] != expected_prev:
                return {
                    "valid": False,
                    "message": f"Chain break detected at record {record['id']}",
                    "total_records": len(self.chain),
                    "tampered_record": record["id"],
                    "tamper_type": "DELETION_OR_REORDER",
                    "detail": f"prev_hash mismatch at position {i}"
                }
            
            # Check 2 — record_hash integrity
            recomputed_hash = self._compute_record_hash(record)
            
            if recomputed_hash != record["record_hash"]:
                return {
                    "valid": False,
                    "message": f"Tampered record detected: complaint #{record['id']}",
                    "total_records": len(self.chain),
                    "tampered_record": record["id"],
                    "tamper_type": "MODIFICATION",
                    "detail": f"Expected {recomputed_hash[:16]}... got {record['record_hash'][:16]}..."
                }
            
            # Check 3 — ID contiguity
            if record["id"] != i + 1:
                return {
                    "valid": False,
                    "message": f"Gap in chain — missing record at position {i+1}",
                    "total_records": len(self.chain),
                    "tampered_record": i + 1,
                    "tamper_type": "DELETION",
                    "detail": f"Expected ID {i+1}, found {record['id']}"
                }
        
        return {
            "valid": True,
            "message": f"Chain intact — all {len(self.chain)} records verified",
            "total_records": len(self.chain),
            "tampered_record": None
        }
    
    def locate_tamper(self) -> dict:
        """
        When verify_chain() returns valid=False, this function
        uses binary search to find EXACTLY which record was tampered.
        
        Why binary search:
        verify_chain() scans from the start — it finds the FIRST
        broken link which may be far from the actual tampered record.
        Binary search finds the tampered record faster.
        
        Algorithm:
        1. Split chain in half
        2. Verify first half — if invalid, tamper is in first half
        3. Verify second half — if invalid, tamper is in second half
        4. Recurse into the invalid half
        5. Repeat until single record isolated
        
        Time complexity: O(log n) comparisons of O(n) verification
        In practice with checkpoints: O(log n/100) * O(100) = very fast
        """
        
        if len(self.chain) == 0:
            return {"found": False, "message": "Chain is empty"}
        
        result = self._binary_search_tamper(0, len(self.chain) - 1)
        return result
    
    def _binary_search_tamper(self, left: int, right: int) -> dict:
        """
        Recursive binary search for tampered record.
        left and right are indices into self.chain.
        """
        
        # Base case — single record
        if left == right:
            record = self.chain[left]
            recomputed = self._compute_record_hash(record)
            
            if recomputed != record["record_hash"]:
                return {
                    "found": True,
                    "tampered_id": record["id"],
                    "position": left,
                    "tamper_type": "MODIFICATION",
                    "original_hash": record["record_hash"],
                    "recomputed_hash": recomputed
                }
            else:
                return {
                    "found": False,
                    "message": "No tamper found in this segment"
                }
        
        mid = (left + right) // 2
        
        # Check if first half has a tamper
        first_half_valid = self._verify_segment(left, mid)
        
        if not first_half_valid:
            return self._binary_search_tamper(left, mid)
        else:
            return self._binary_search_tamper(mid + 1, right)
    
    def _verify_segment(self, start: int, end: int) -> bool:
        """
        Verify a segment of the chain from index start to end.
        Returns True if segment is valid, False if tampered.
        Helper for binary search.
        """
        
        for i in range(start, end + 1):
            record = self.chain[i]
            
            # Check prev_hash
            expected_prev = self.GENESIS_HASH if i == 0 else self.chain[i-1]["record_hash"]
            if record["prev_hash"] != expected_prev:
                return False
            
            # Check record_hash
            if self._compute_record_hash(record) != record["record_hash"]:
                return False
        
        return True
    
    def get_complaint(self, complaint_id: int) -> Optional[dict]:
        """
        Fast O(1) lookup by complaint ID using the index dict.
        Returns None if not found.
        """
        
        if complaint_id not in self.index:
            return None
        
        position = self.index[complaint_id]
        return self.chain[position]
    
    def get_chain_head(self) -> Optional[str]:
        """
        Returns the hash of the most recent record.
        This is what nodes broadcast to each other every 60 seconds
        for synchronization. If two nodes have different chain heads
        their chains have diverged — tamper detected.
        """
        
        if len(self.chain) == 0:
            return self.GENESIS_HASH
        
        return self.chain[-1]["record_hash"]
    
    def update_complaint_status(self, complaint_id: int, status: str, node_id: str) -> bool:
        """
        Updates complaint status and records which node acknowledged.
        
        IMPORTANT: This does NOT recompute record_hash after updating.
        Status and node_acks are mutable fields — they're expected to change.
        Only the core evidence fields (evidence_hash, prev_hash etc)
        are covered by record_hash integrity protection.
        
        This is a deliberate design choice: nodes marking a complaint
        as actioned should not invalidate the chain.
        """
        
        complaint = self.get_complaint(complaint_id)
        if complaint is None:
            return False
        
        complaint["status"] = status
        
        if node_id not in complaint["node_acks"]:
            complaint["node_acks"].append(node_id)
        
        return True
    
    def export_for_public_ledger(self) -> list:
        """
        Returns a sanitized version of the chain for public display.
        Removes token_hash — even though it's a hash not the actual token,
        we don't expose it publicly to prevent correlation attacks.
        Keeps everything else — integrity hashes, status, timestamps.
        """
        
        public_chain = []
        for record in self.chain:
            public_record = {k: v for k, v in record.items() if k != "token_hash"}
            public_chain.append(public_record)
        
        return public_chain
    # Test harness
if __name__ == "__main__":
    print("=== SENTINEL Hash Chain Test ===\n")
    
    chain = HashChain()
    
    # Add 3 complaints
    print("Adding complaints...")
    c1 = chain.add_complaint(
        evidence_hash="abc123" * 10,
        complaint_type="Bribery",
        location="Bengaluru",
        token_hash="tok111" * 10
    )
    print(f"Complaint #1 added — hash: {c1['record_hash'][:16]}...")
    
    c2 = chain.add_complaint(
        evidence_hash="def456" * 10,
        complaint_type="Fraud",
        location="Mumbai",
        token_hash="tok222" * 10
    )
    print(f"Complaint #2 added — hash: {c2['record_hash'][:16]}...")
    
    c3 = chain.add_complaint(
        evidence_hash="ghi789" * 10,
        complaint_type="Extortion",
        location="Delhi",
        token_hash="tok333" * 10
    )
    print(f"Complaint #3 added — hash: {c3['record_hash'][:16]}...")
    
    # Verify intact chain
    print("\n--- Verifying intact chain ---")
    result = chain.verify_chain()
    print(f"Valid: {result['valid']}")
    print(f"Message: {result['message']}")
    
    # Simulate tampering — modify complaint #2
    print("\n--- Simulating tamper on complaint #2 ---")
    chain.chain[1]["complaint_type"] = "DELETED"
    
    # Verify tampered chain
    print("--- Verifying after tamper ---")
    result = chain.verify_chain()
    print(f"Valid: {result['valid']}")
    print(f"Message: {result['message']}")
    print(f"Tampered record: #{result['tampered_record']}")
    
    # Locate exact tamper
    print("\n--- Locating tamper with binary search ---")
    location = chain.locate_tamper()
    print(f"Tamper found: {location['found']}")
    print(f"Tampered ID: #{location['tampered_id']}")
    print(f"Type: {location['tamper_type']}")
    
    # Chain head
    print(f"\nChain head: {chain.get_chain_head()[:16]}...")