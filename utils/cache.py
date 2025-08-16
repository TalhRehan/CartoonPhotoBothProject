import os
import hashlib
import time
import tempfile
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

# ---- Configurable locations/limits ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_ROOT = os.getenv("CACHE_DIR") or os.path.normpath(os.path.join(BASE_DIR, "..", "cache"))
os.makedirs(CACHE_ROOT, exist_ok=True)

# TTL: seconds (0 = never expire)
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "0"))
# Max files and bytes (0 = unbounded). Oldest items are pruned first.
MAX_FILES = int(os.getenv("CACHE_MAX_FILES", "0"))
MAX_BYTES = int(os.getenv("CACHE_MAX_BYTES", "0"))

def _key(bytes_data: bytes, *parts: str) -> str:
    m = hashlib.sha256()
    m.update(bytes_data)
    for p in parts:
        if p:
            m.update(str(p).encode("utf-8"))
    return m.hexdigest()

def path_for(prefix: str, bytes_data: bytes, *parts: str) -> str:
    """Stable, namespaced path like <cache>/<prefix>/<hash>.bin"""
    h = _key(bytes_data, *parts)
    subdir = os.path.join(CACHE_ROOT, prefix)
    os.makedirs(subdir, exist_ok=True)
    return os.path.join(subdir, f"{h}.bin")

def get(prefix: str, bytes_data: bytes, *parts: str) -> Optional[bytes]:
    p = path_for(prefix, bytes_data, *parts)
    if not os.path.exists(p):
        return None

    # TTL expiry
    if CACHE_TTL_SECONDS > 0:
        age = time.time() - os.path.getmtime(p)
        if age > CACHE_TTL_SECONDS:
            try:
                os.remove(p)
            except Exception:
                pass
            return None

    try:
        with open(p, "rb") as f:
            return f.read()
    except Exception:
        return None

def set(prefix: str, bytes_data: bytes, out_bytes: bytes, *parts: str) -> None:
    p = path_for(prefix, bytes_data, *parts)
    d = os.path.dirname(p)
    try:
        # Atomic write: write to temp then replace
        fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=d)
        with os.fdopen(fd, "wb") as f:
            f.write(out_bytes)
        os.replace(tmp, p)
    except Exception:
        # Best-effort fallback
        try:
            with open(p, "wb") as f:
                f.write(out_bytes)
        except Exception:
            pass
    _maybe_sweep()

def clear(prefix: str = None) -> None:
    """Delete all cached files (optionally under a single prefix)."""
    root = os.path.join(CACHE_ROOT, prefix) if prefix else CACHE_ROOT
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            try:
                os.remove(os.path.join(dirpath, fn))
            except Exception:
                pass

def _maybe_sweep():
    """Enforce MAX_FILES / MAX_BYTES (oldest-first pruning)."""
    if MAX_FILES <= 0 and MAX_BYTES <= 0:
        return

    files = []
    total = 0
    for dirpath, _, filenames in os.walk(CACHE_ROOT):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(p)
                total += sz
                files.append((os.path.getmtime(p), sz, p))
            except Exception:
                pass

    files.sort()  # oldest first

    # Prune by file count
    if MAX_FILES > 0 and len(files) > MAX_FILES:
        to_delete = len(files) - MAX_FILES
        for i in range(to_delete):
            try:
                os.remove(files[i][2])
            except Exception:
                pass
        files = files[to_delete:]

    # Prune by total bytes
    if MAX_BYTES > 0:
        total = sum(sz for _, sz, _ in files)
        i = 0
        while total > MAX_BYTES and i < len(files):
            _, sz, p = files[i]
            try:
                os.remove(p)
                total -= sz
            except Exception:
                pass
            i += 1
