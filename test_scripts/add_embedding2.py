import os
from pathlib import Path
from typing import Any, List, Optional, Tuple

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import torch
import numpy as np
from dotenv import load_dotenv

# Prefer test_scripts/.env, then scripts/.env, then default discovery
_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / "scripts" / ".env")
load_dotenv()


def resolve_neo4j_credentials() -> Tuple[str, str, Optional[str]]:
    """Resolve Neo4j credentials (supports NEO4J_AUTH=user/password)."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    env_user_explicit = os.getenv("NEO4J_USER") is not None
    user = os.getenv("NEO4J_USER") or "neo4j"
    password: Optional[str] = os.getenv("NEO4J_PASSWORD")

    neo4j_auth = os.getenv("NEO4J_AUTH")
    if neo4j_auth and str(neo4j_auth).strip():
        raw = str(neo4j_auth).strip()
        auth_user, sep, auth_pass_rest = raw.partition("/")
        if sep:
            if not env_user_explicit and auth_user:
                user = auth_user.strip()
            if not password:
                password = auth_pass_rest if auth_pass_rest else None
        elif not password:
            password = raw or None

    if password == "":
        password = None
    return uri, user, password


def open_neo4j_driver():
    uri, user, password = resolve_neo4j_credentials()
    if not password:
        raise ValueError("Neo4j password not set. Set NEO4J_PASSWORD or NEO4J_AUTH=user/password")
    return GraphDatabase.driver(uri, auth=(user, password), database="neo4j")


driver = open_neo4j_driver()

# MPS device configuration for MacBook M3
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {device}")

# Load the model and move it to the selected device
model = SentenceTransformer("all-MiniLM-L6-v2")
model.to(device)


def _needs_embedding_cypher() -> str:
    """Nodes with no usable ST embedding yet (missing, null, or empty list)."""
    return """
            MATCH (p:SemanticNode)
            WHERE p.EmbeddingText IS NOT NULL AND NOT p.EmbeddingText = ''
              AND (
                p.SentenceTransformerEmbedding IS NULL
                OR size(p.SentenceTransformerEmbedding) = 0
              )
            RETURN elementId(p) AS eid, p.id AS graph_id, p.EmbeddingText AS text
        """


def _build_processed_records(records: List[Any]) -> List[dict]:
    """
    Build rows for embedding. Uses elementId(eid) for writes — many SemanticNodes have no `id`
    property; previously RETURN p.id AS id was null for all rows → 0 processed_records.
    """
    processed: List[dict] = []
    skipped_empty_text = 0
    null_graph_id_sample = 0
    for i, record in enumerate(records):
        eid = record.get("eid")
        if eid is None:
            continue
        eid = str(eid).strip()
        if not eid:
            continue
        text = record.get("text")
        if text is None:
            skipped_empty_text += 1
            continue
        if not isinstance(text, str):
            text = str(text)
        t = text.strip()
        if not t:
            skipped_empty_text += 1
            continue
        gid = record.get("graph_id")
        if gid is None and i < 5:
            null_graph_id_sample += 1
        processed.append({"eid": eid, "text": t, "graph_id": gid})
    if null_graph_id_sample:
        print(
            f"[info] `p.id` (graph_id) is null in the first records; "
            f"updates will use `elementId(p)` (expected behavior)."
        )
    if skipped_empty_text:
        print(f"[info] Rows skipped because EmbeddingText is empty: {skipped_empty_text}")
    return processed


def _write_embeddings_batch(
    session, element_ids: List[str], embedding_lists: List[List[float]], *, log_first: bool
) -> None:
    """Batch SET by stable Neo4j elementId (works when p.id is missing)."""
    if not element_ids:
        return
    if log_first:
        chk = session.run(
            "MATCH (p:SemanticNode) WHERE elementId(p) IN $eids RETURN count(p) AS c",
            eids=element_ids,
        ).single()
        matched = int(chk["c"]) if chk else 0
        print(
            f"[check first batch] eids in batch={len(element_ids)}, "
            f"nodes matched by elementId IN $eids={matched}"
        )
    res = session.run(
        """
        UNWIND range(0, size($eids) - 1) AS idx
        WITH $eids[idx] AS eid, $embeddings[idx] AS embedding
        MATCH (p:SemanticNode)
        WHERE elementId(p) = eid
        SET p.SentenceTransformerEmbedding = embedding
        """,
        eids=element_ids,
        embeddings=embedding_lists,
    )
    summary = res.consume()
    c = summary.counters
    if log_first:
        print(
            f"[check first batch] properties_set={c.properties_set}, "
            f"labels_added={c.labels_added}, nodes_created={c.nodes_created}"
        )


def generate_and_write_embeddings(batch_size=32):
    with driver.session() as session:
        # 1. Fetch the dataset
        result = session.run(_needs_embedding_cypher())
        records = list(result)

        processed_records = _build_processed_records(records)

        print(f"Found {len(records)} total records, {len(processed_records)} processed records")

        # 2. Batch processing for better MPS utilization
        for i in tqdm(range(0, len(processed_records), batch_size), desc="Processing batches"):
            batch = processed_records[i:i + batch_size]
            
            # Extract texts and IDs
            texts = [record["text"] for record in batch]
            eids = [record["eid"] for record in batch]
            
            # Generate embeddings in batch (much faster with MPS)
            embeddings = model.encode(texts, convert_to_tensor=True, device=device)
            
            # Convert to list format for Neo4j storage
            embedding_lists = embeddings.cpu().numpy().tolist()
            
            # 3. Write embeddings to Neo4j in batch
            _write_embeddings_batch(
                session,
                eids,
                embedding_lists,
                log_first=(i == 0),
            )

    print("✅ All embeddings were written successfully.")

def generate_and_write_embeddings_optimized(batch_size=64):
    """
    Optimized version with better memory management and larger batches
    """
    with driver.session() as session:
        # 1. Fetch the dataset
        result = session.run(_needs_embedding_cypher())
        records = list(result)

        processed_records = _build_processed_records(records)

        print(f"Found {len(records)} total records, {len(processed_records)} processed records")

        # 2. Process in larger batches for maximum MPS efficiency
        for i in tqdm(range(0, len(processed_records), batch_size), desc="Processing batches"):
            batch = processed_records[i:i + batch_size]
            
            # Extract texts and IDs
            texts = [record["text"] for record in batch]
            eids = [record["eid"] for record in batch]
            
            # Generate embeddings with optimized settings
            with torch.no_grad():  # Disable gradient computation for inference
                embeddings = model.encode(
                    texts, 
                    convert_to_tensor=True, 
                    device=device,
                    show_progress_bar=False,  # Disable internal progress bar
                    normalize_embeddings=True  # Normalize embeddings for better performance
                )
            
            # Convert to list format and clear GPU memory
            embedding_lists = embeddings.cpu().numpy().tolist()
            del embeddings  # Free GPU memory
            
            # 3. Write embeddings to Neo4j
            _write_embeddings_batch(
                session,
                eids,
                embedding_lists,
                log_first=(i == 0),
            )

    print("✅ All embeddings were written successfully.")

if __name__ == "__main__":
    # Use the optimized version for better MPS performance
    try:
        generate_and_write_embeddings_optimized(batch_size=32)
    finally:
        driver.close()
