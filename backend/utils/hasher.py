import hashlib
import os
CHUNK_SIZE = 65536
def hash_file(file_path: str) -> dict:
    """
    Takes a path to any file and returns its SHA-256 hash.
    Works on PDFs, images (JPG, PNG, HEIC), videos (MP4, MOV),
    audio (MP3, WAV), and any other binary or text file.
    
    Returns a dict, not just a string, because callers need
    metadata alongside the hash — file size, algorithm used, etc.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No file found at: {file_path}")
    sha256 = hashlib.sha256()
    total_bytes_read = 0
    with open(file_path, "rb") as f:
        
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
            total_bytes_read += len(chunk)
    file_hash = sha256.hexdigest()
    
    return {
        "hash": file_hash,
        "algorithm": "sha256",
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "file_size_bytes": total_bytes_read,
        # Human readable size — easier to display on dashboard
        "file_size_human": _format_size(total_bytes_read),
    }
def hash_bytes(data: bytes) -> str:
    """
    Hash raw bytes directly instead of a file path.
    Used when evidence comes in as bytes over HTTP (file upload)
    rather than a local file path.
    
    Returns just the hex string, not a dict,
    because there's no file metadata to return.
    """
    sha256 = hashlib.sha256()
    
    # For bytes objects, we still chunk manually.
    # A large video upload arrives as a single bytes object in memory,
    # but we slice it into chunks so this function behaves identically
    # to hash_file regardless of input size.
    offset = 0
    while offset < len(data):
        chunk = data[offset : offset + CHUNK_SIZE]
        sha256.update(chunk)
        offset += CHUNK_SIZE
    
    return sha256.hexdigest()
def verify_file_integrity(file_path: str, expected_hash: str) -> dict:
    """
    Given a file and a hash we recorded earlier,
    check if the file still matches that hash.
    
    This is what your tamper detection calls every 60 seconds
    on each node's stored evidence files.
    """
    
    result = hash_file(file_path)
    current_hash = result["hash"]
    
    # String comparison. Either they match exactly or they don't.
    # SHA-256 has no "close" — one pixel different = completely different hash.
    is_intact = (current_hash == expected_hash)
    
    return {
        "intact": is_intact,
        "expected_hash": expected_hash,
        "current_hash": current_hash,
        # If tampered, this field tells you what changed.
        # If intact, this is None.
        "mismatch_detail": None if is_intact else {
            "expected": expected_hash,
            "found": current_hash,
            "file": file_path
        }
    }
def _format_size(size_bytes: int) -> str:
    """
    Private helper. Converts raw bytes to human readable string.
    Underscore prefix means: don't import this from outside this file.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
# This block only runs when you execute hasher.py directly:
# python hasher.py
# It does NOT run when chain.py does "from utils.hasher import hash_file"
# This is standard Python — if __name__ == "__main__" is your test harness.

if __name__ == "__main__":
    import sys
    
    # Allow: python hasher.py path/to/evidence.mp4
    if len(sys.argv) < 2:
        print("Usage: python hasher.py <file_path>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    print(f"\nHashing: {target}")
    print("-" * 50)
    
    result = hash_file(target)
    
    print(f"File:      {result['file_name']}")
    print(f"Size:      {result['file_size_human']}")
    print(f"Algorithm: {result['algorithm'].upper()}")
    print(f"Hash:      {result['hash']}")
    print("-" * 50)
    print("Any modification to this file will produce a completely different hash.")