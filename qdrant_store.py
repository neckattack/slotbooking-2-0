import os
from typing import List, Optional, Sequence, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from openai import OpenAI

# Konfiguration über Env
QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY")
# Priorität: spezielle E-Mail-Collection, sonst generische QDRANT_COLLECTION, Default "knowledge"
QDRANT_COLLECTION = (
    os.environ.get("QDRANT_COLLECTION_EMAILS")
    or os.environ.get("QDRANT_COLLECTION")
    or "knowledge"
)
EMBED_MODEL = os.environ.get("AGENT_EMBED_MODEL", "text-embedding-3-small")

_openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def get_client() -> QdrantClient:
    if not QDRANT_URL:
        raise RuntimeError("QDRANT_URL fehlt (Env)")
    headers = {"api-key": QDRANT_API_KEY} if QDRANT_API_KEY else None
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=10.0, prefer_grpc=False)


def _embed(texts: Sequence[str]) -> List[List[float]]:
    # OpenAI Embeddings
    res = _openai.embeddings.create(model=EMBED_MODEL, input=list(texts))
    return [d.embedding for d in res.data]


def ensure_collection(vector_size: int, distance: str = "Cosine") -> None:
    """Erstellt die Collection falls nicht vorhanden."""
    client = get_client()
    try:
        exists = client.collection_exists(QDRANT_COLLECTION)
    except Exception:
        exists = False
    if not exists:
        # Distance-String robust auf Enum-Werte mappen (COSINE, DOT, EUCLID)
        dist_key = (distance or "cosine").strip().upper()
        if dist_key not in {"COSINE", "DOT", "EUCLID"}:
            dist_key = "COSINE"
        dist = getattr(qmodels.Distance, dist_key)
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=dist),
        )


def upsert_texts(texts: Sequence[str], ids: Optional[Sequence[str]] = None, metadata: Optional[Sequence[Dict[str, Any]]] = None) -> int:
    if not texts:
        return 0
    vecs = _embed(texts)
    ensure_collection(vector_size=len(vecs[0]))
    points: List[qmodels.PointStruct] = []
    for i, v in enumerate(vecs):
        # Wenn keine externe ID angegeben ist, nutze eine einfache Integer-ID
        raw_pid = ids[i] if ids and i < len(ids) else None
        try:
            pid = int(raw_pid) if raw_pid is not None else i
        except Exception:
            pid = i
        payload = (metadata[i] if metadata and i < len(metadata) else {}) or {}
        payload.setdefault("text", texts[i])
        points.append(qmodels.PointStruct(id=pid, vector=v, payload=payload))
    client = get_client()
    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    return len(points)


def similarity_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    vec = _embed([query])[0]
    client = get_client()
    ensure_collection(vector_size=len(vec))
    res = client.search(collection_name=QDRANT_COLLECTION, query_vector=vec, limit=limit)
    out: List[Dict[str, Any]] = []
    for pt in res:
        out.append({
            "id": str(pt.id),
            "score": float(pt.score),
            "text": (pt.payload or {}).get("text", ""),
            "payload": pt.payload or {},
        })
    return out


def index_knowledge_md(path: str = "docs/knowledge.md", chunk_size: int = 800, overlap: int = 120) -> int:
    """Teilt knowledge.md in überlappende Chunks und speichert sie in Qdrant."""
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    chunks: List[str] = []
    i = 0
    while i < len(content):
        chunk = content[i:i+chunk_size]
        chunks.append(chunk)
        i += max(1, chunk_size - overlap)
    meta = [{"source": path, "idx": idx} for idx in range(len(chunks))]
    return upsert_texts(chunks, metadata=meta)
