"""Shared config for the db/ layer — model, vector, batch-size, and timeout constants
used by both the Chanakya and Crisis pipelines. Centralized here per CLAUDE.md's
"config over hardcoding" principle (previously duplicated across db/embedding.py,
db/qdrant_client.py, and db/crisis_qdrant_client.py — see forensics_report.md).
"""
from __future__ import annotations

from qdrant_client.models import Distance

# --- Embedding model ---------------------------------------------------------------
# Deliberately lightweight for a weak laptop (no GPU, 16GB RAM): ~137M params, CPU-only.
MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
VECTOR_SIZE = 768

# nomic-embed-text-v1.5 is instruction-prefixed: document text and search queries need
# different prefixes for retrieval to work well.
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

# --- Sparse embedding (Piece 3: hybrid dense+sparse retrieval) ----------------------
# Pure BM25 term-statistics via fastembed — no neural model, no GPU, deterministic
# hashed-vocabulary indices (not corpus-specific), so it's cheap on a CPU-only laptop.
SPARSE_MODEL_NAME = "Qdrant/bm25"

# Named-vector keys used on hybrid ("_v2"+) collections. Dense-only "_v1" collections
# use an unnamed vector; hybrid collections name both explicitly rather than relying on
# Qdrant's implicit empty-string name for "the" dense vector once sparse is added —
# that convention is easy to get wrong at a Prefetch call site.
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# --- Qdrant ---------------------------------------------------------------------
DISTANCE_METRIC = Distance.COSINE
QDRANT_TIMEOUT = 60  # seconds — raised above the client default for batch writes over a home connection.

UPLOAD_BATCH_SIZE = 100
PAYLOAD_BATCH_SIZE = 25  # smaller than UPLOAD_BATCH_SIZE — payload-only batches carry
# per-point distinct operations, so keep requests smaller to avoid write timeouts.
EMBED_BATCH_SIZE = 32  # CPU-only, 16GB RAM: keep modest, don't blow up memory.

# --- Collection base names (Piece 2: versioned collections + alias) -----------------
# The live alias name each KB is served under. The actual data lives in
# "{base}_v{n}" collections; the alias points at whichever version is currently live.
CHANAKYA_COLLECTION_BASE = "chanakya_kb"
CRISIS_COLLECTION_BASE = "crisis_kb"

# Fields the retrieval layer needs to filter *before* semantic search on crisis_kb.
# Qdrant Cloud requires an explicit index per field before it will accept a filter on it.
CRISIS_FILTERABLE_FIELDS = ("region", "crisis_type", "industry")

# parent_id: filtered on by db/parent_expansion.py (Piece 5) to gather sibling chunks —
# same "index required" constraint applies.
CHANAKYA_FILTERABLE_FIELDS = ("parent_id",)
