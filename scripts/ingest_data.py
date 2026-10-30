import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
import random
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from datetime import datetime
import ast
from sentence_transformers import SentenceTransformer
import torch
from tqdm import tqdm
import os
from PyPDF2 import PdfReader
import re
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
from pathlib import Path
import sys
import argparse
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
import warnings

# Suppress PyPDF2 warnings globally (can be overridden with --show-warnings)
warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2")
warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2.generic")
warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2.pdf")
warnings.filterwarnings("ignore", category=UserWarning, module="PyPDF2.utils")
warnings.filterwarnings("ignore", message="Multiple definitions in dictionary")
warnings.filterwarnings("ignore", message=".*Multiple definitions.*")

load_dotenv()


def resolve_neo4j_credentials() -> Tuple[str, str, Optional[str]]:
    """
    Resolve Neo4j URI, user and password.

    Supports:
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (.env style)
    - NEO4J_AUTH=username/password (Docker official image, password is after first '/')
    """
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
        else:
            if not password:
                password = raw or None

    if password == "":
        password = None
    return uri, user, password


def resolve_qdrant_credentials() -> Tuple[str, Optional[str]]:
    """
    Qdrant URL + optional API key.

    Recognises Docker env QDRANT__SERVICE__API_KEY alongside QDRANT_API_KEY.
    """
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    raw = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT__SERVICE__API_KEY") or ""
    api_key = raw.strip() or None
    return url, api_key


def resolve_elasticsearch_credentials() -> Tuple[str, Optional[str], Optional[str]]:
    """
    Elasticsearch hosts URL and optional basic-auth.

    ELASTICSEARCH_USERNAME / ELASTICSEARCH_PASSWORD (legacy)
    plus ELASTIC_PASSWORD (official ES Docker variable; default username 'elastic').
    """
    hosts = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    user = (
        os.getenv("ELASTICSEARCH_USERNAME")
        or os.getenv("ELASTIC_USER")
    )
    password = (
        os.getenv("ELASTICSEARCH_PASSWORD")
        or os.getenv("ELASTIC_PASSWORD")
    )

    user = user.strip() if user else None
    password = password.strip() if password else None

    if password and not user:
        user = os.getenv("ELASTIC_USERNAME_DEFAULT") or "elastic"

    return hosts, user, password


def make_qdrant_client(qdrant_url: str, qdrant_api_key: Optional[str]) -> Any:
    """Instantiate QdrantClient; omit api_key when absent (instance without API key auth)."""
    if qdrant_api_key:
        return QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    return QdrantClient(url=qdrant_url)


def check_database_connections(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: Optional[str],
    qdrant_url: str,
    qdrant_api_key: Optional[str],
    es_url: str,
    es_username: Optional[str],
    es_password: Optional[str],
    targets: List[str],
    *,
    verbose: bool = True,
) -> bool:
    """
    Ping Neo4j, Qdrant, and Elasticsearch for the given targets.
    Returns True only if every selected target succeeds.
    """
    all_ok = True

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    log("")
    log("=== Database connection check ===")
    log(f"Targets: {', '.join(targets)}")
    log("")

    if "neo4j" in targets:
        log("[Neo4j]")
        log(f"  URI: {neo4j_uri}  user: {neo4j_user}")
        try:
            if not neo4j_password:
                log("  FAIL: Missing password (set NEO4J_PASSWORD or NEO4J_AUTH=user/password)")
                all_ok = False
            else:
                driver = GraphDatabase.driver(
                    neo4j_uri,
                    auth=(neo4j_user, neo4j_password),
                    database="neo4j",
                )
                driver.verify_connectivity()
                with driver.session() as session:
                    session.run("RETURN 1 AS ok").single()
                driver.close()
                log("  OK — verify_connectivity + RETURN 1")
        except Exception as e:
            log(f"  FAIL: {e}")
            all_ok = False
        log("")

    if "qdrant" in targets:
        log("[Qdrant]")
        log(f"  URL: {qdrant_url}")
        log(
            "  API key: "
            + ("set (" + str(len(qdrant_api_key)) + " chars)" if qdrant_api_key else "not set")
        )
        try:
            client = make_qdrant_client(qdrant_url, qdrant_api_key)
            cols = client.get_collections().collections
            log(f"  OK — reachable, {len(cols)} collection(s)")
        except Exception as e:
            log(f"  FAIL: {e}")
            all_ok = False
        log("")

    if "elasticsearch" in targets:
        log("[Elasticsearch]")
        log(f"  URL: {es_url}")
        if es_password:
            log(
                "  Auth: "
                + f"user={es_username or '(default elastic)'} "
                + f"(password {len(es_password)} chars)"
            )
        else:
            log("  Auth: none (anonymous)")
        try:
            es_config: Dict[str, Any] = {"hosts": [es_url], "request_timeout": 30}
            if es_username and es_password:
                es_config["basic_auth"] = (es_username, es_password)
            elif es_password and not es_username:
                es_config["basic_auth"] = ("elastic", es_password)
            es_client = Elasticsearch(**es_config)
            if not es_client.ping():
                raise RuntimeError("ping() returned False")
            info = es_client.info()
            if isinstance(info, dict):
                ver = (info.get("version") or {}).get("number", "?")
            else:
                body = getattr(info, "body", info)
                if isinstance(body, dict):
                    ver = (body.get("version") or {}).get("number", "?")
                else:
                    ver = "?"
            log(f"  OK — ping + cluster info (version={ver})")
        except Exception as e:
            log(f"  FAIL: {e}")
            all_ok = False
        log("")

    if all_ok:
        log("All selected connections OK.")
    else:
        log("One or more connection checks FAILED — fix credentials or networking.")
    return all_ok


def convert_european_number(value):
    """Convert European number format (comma as decimal separator) to float"""
    if pd.isna(value):
        return 0.0
    try:
        # Remove any thousand separators and replace comma with dot
        cleaned = str(value).replace('.', '').replace(',', '.')
        return float(cleaned)
    except (ValueError, TypeError):
        print(f"Warning: Could not convert value '{value}' to float. Using 0.0")
        return 0.0

def load_csv_safely(file_path: str, expected_fields: int = None) -> pd.DataFrame:
    """Load CSV file safely handling inconsistent field counts"""
    try:
        # First try to read with error_bad_lines=False to skip problematic lines
        df = pd.read_csv(file_path, sep=';', low_memory=False, on_bad_lines='skip')
        
        # Convert numeric columns if they exist
        numeric_columns = {
            'totalCost': 'totalCost',
            'ecMaxContribution': 'ecMaxContribution',
            'ecContribution': 'ecContribution',
            'netEcContribution': 'netEcContribution'
        }
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].apply(convert_european_number)
        
        print(f"Successfully loaded {file_path}")
        return df
    except Exception as e:
        print(f"Error loading {file_path}: {str(e)}")
        raise

def extract_text_from_pdf(pdf_path: str, source_type: str = 'manual', suppress_stderr: bool = True) -> Tuple[str, Dict]:
    """Extract text and metadata from a PDF file."""
    try:
        # Suppress PyPDF2 warnings about malformed PDFs
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            
            # Redirect stderr to suppress PyPDF2 warnings
            import io
            import sys
            from contextlib import redirect_stderr
            
            # Create a null device for stderr
            null_stderr = io.StringIO()
            
            # Conditionally suppress stderr
            if suppress_stderr:
                stderr_context = redirect_stderr(null_stderr)
            else:
                stderr_context = null_stderr  # No-op context manager
            
            with stderr_context:
                reader = PdfReader(pdf_path)
                
                # Check if PDF is encrypted
                if reader.is_encrypted:
                    return "", {}
                
                # Extract text from all pages
                text = ""
                for page in reader.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    except Exception as e:
                        # Skip problematic pages but continue with others
                        continue
                
                # Clean the text
                text = re.sub(r'\s+', ' ', text).strip()
                
                # Remove problematic characters that might cause embedding issues
                text = text.replace('\x00', '')  # Remove null bytes
                text = text.replace('\ufffd', '')  # Remove Unicode replacement characters
                
                # Only return if we have meaningful text
                if len(text) < 10:  # Skip files with very little text
                    return "", {}
                
                # Ensure text is valid UTF-8
                try:
                    text.encode('utf-8')
                except UnicodeEncodeError:
                    # Try to fix encoding issues
                    text = text.encode('utf-8', errors='ignore').decode('utf-8')
                
                # Extract metadata
                metadata = {
                    'filename': os.path.basename(pdf_path),
                    'file_path': pdf_path,  # Full path for potential file access
                    'page_count': len(reader.pages),
                    'file_size': os.path.getsize(pdf_path),
                    'type': source_type,
                    'source': source_type.capitalize(),
                    'document_id': f"{source_type}_{os.path.basename(pdf_path)}",
                    'document_link': f"file://{pdf_path}",  # File protocol link
                    'ingested_at': datetime.now().isoformat()
                }
                
                return text, metadata
    except Exception as e:
        # Silently skip problematic PDFs
        return "", {}

def process_pdf_worker(args):
    """Worker function for parallel PDF processing."""
    pdf_path, source_type, suppress_stderr = args
    try:
        # Suppress all warnings in worker processes
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            text, metadata = extract_text_from_pdf(pdf_path, source_type, suppress_stderr)
            return text, metadata
    except Exception as e:
        # Return empty result for any worker errors
        return "", {}
    except KeyboardInterrupt:
        # Handle interruption gracefully
        return "", {}

def process_batch_with_immediate_embedding(batch_data: List[Tuple[str, Dict]], source_type: str, 
                                         qdrant_client=None, es_client=None, collection_name: str = None, 
                                         enable_chunking: bool = False, chunk_size: int = 1000, chunk_overlap: int = 200,
                                         targets: List[str] = ['qdrant']) -> None:
    # Global counter for unique IDs
    global _point_id_counter
    if not hasattr(process_batch_with_immediate_embedding, '_point_id_counter'):
        process_batch_with_immediate_embedding._point_id_counter = 0
    """
    Process a batch of PDF data with immediate embedding and ingestion
    
    Args:
        batch_data: List of (text, metadata) tuples
        source_type: Type of source (manual, pdf)
        qdrant_client: Qdrant client for ingestion (optional)
        es_client: Elasticsearch client for ingestion (optional)
        collection_name: Collection name for ingestion
        enable_chunking: Whether to enable chunking
        chunk_size: Size of chunks
        chunk_overlap: Overlap between chunks
        targets: List of target databases ['qdrant', 'elasticsearch']
    """
    if not batch_data:
        return
    
    print(f"Processing batch of {len(batch_data)} {source_type} documents...")
    
    # Apply chunking if enabled
    if enable_chunking:
        print(f"Creating chunks with size {chunk_size} and overlap {chunk_overlap}")
        all_chunks = []
        for text, meta in batch_data:
            chunks = create_document_chunks(text, meta, chunk_size, chunk_overlap)
            all_chunks.extend(chunks)
        texts = [text for text, _ in all_chunks]
        metadata = [meta for _, meta in all_chunks]
        print(f"Created {len(all_chunks)} chunks from {len(batch_data)} documents")
    else:
        texts = [text for text, _ in batch_data]
        metadata = [meta for _, meta in batch_data]
    
    # Generate embeddings
    try:
        print("Generating embeddings...")
        embeddings = generate_embeddings(texts, batch_size=32)
        
        # Upload to target databases
        batch_size_upload = 50
        
        if 'qdrant' in targets and qdrant_client:
            print("Uploading to Qdrant...")
            for i in range(0, len(texts), batch_size_upload):
                batch_end = min(i + batch_size_upload, len(texts))
                points = []
                for j, (vec, meta) in enumerate(zip(embeddings[i:batch_end], metadata[i:batch_end])):
                    point_id = process_batch_with_immediate_embedding._point_id_counter
                    process_batch_with_immediate_embedding._point_id_counter += 1
                    points.append(PointStruct(
                        id=point_id,
                        vector=vec,
                        payload=meta
                    ))
                qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
            print(f"Successfully uploaded {len(texts)} {source_type} documents to Qdrant")
        
        if 'elasticsearch' in targets and es_client:
            print("Uploading to Elasticsearch...")
            from elasticsearch.helpers import bulk
            from datetime import datetime
            
            # Prepare Elasticsearch documents
            es_documents = []
            for i, (text, meta) in enumerate(zip(texts, metadata)):
                es_doc = {
                    '_index': collection_name,
                    '_id': f"{source_type}_{i}_{process_batch_with_immediate_embedding._point_id_counter}",
                    '_source': {
                        'content': text,
                        'type': source_type,
                        'ingested_at': datetime.now().isoformat(),
                        **meta
                    }
                }
                es_documents.append(es_doc)
                process_batch_with_immediate_embedding._point_id_counter += 1
            
            # Bulk upload to Elasticsearch
            success, failed = bulk(es_client, es_documents, chunk_size=batch_size_upload, request_timeout=30)
            print(f"Successfully uploaded {success} {source_type} documents to Elasticsearch")
            if failed:
                print(f"Failed to upload {len(failed)} documents to Elasticsearch")
        
    except Exception as e:
        print(f"Error processing batch embeddings: {str(e)}")

def load_pdf_data(pdf_dir: str, source_type: str = 'manual', max_files: int = None, num_workers: int = None, timeout: int = 60, suppress_stderr: bool = True, total_timeout: int = None, batch_size: int = None) -> List[Tuple[str, Dict]]:
    """Load and process PDF files from a directory using parallel processing."""
    print(f"Loading PDF files from {pdf_dir} directory...")
    pdf_data = []
    
    # Get all PDF files in the directory
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    # Apply limit if specified
    if max_files is not None:
        pdf_files = pdf_files[:max_files]
        print(f"Processing first {max_files} PDF files (use --max-pdfs to change)")
    
    # Determine number of workers
    if num_workers is None:
        num_workers = min(mp.cpu_count(), 8)  # Use up to 8 cores
    
    print(f"Using {num_workers} worker processes for parallel processing")
    
    # Calculate dynamic timeout based on number of files and workers
    # Each worker should have enough time to process its share of files
    files_per_worker = len(pdf_files) / num_workers
    per_file_timeout = max(30, timeout)  # Minimum 30 seconds per file
    
    # Use total_timeout if provided, otherwise calculate dynamically
    if total_timeout is not None:
        dynamic_timeout = total_timeout
        print(f"Using user-specified total timeout: {dynamic_timeout} seconds")
    else:
        # For large numbers of files, use a more conservative timeout
        if len(pdf_files) > 500:
            dynamic_timeout = min(1800, int(files_per_worker * per_file_timeout))  # Max 30 minutes
            print(f"Large file set detected ({len(pdf_files)} files), using conservative timeout: {dynamic_timeout} seconds")
        else:
            dynamic_timeout = int(files_per_worker * per_file_timeout)
            print(f"Using dynamic timeout: {dynamic_timeout} seconds (based on {files_per_worker:.1f} files per worker)")
    
    # Prepare arguments for workers
    pdf_paths = [os.path.join(pdf_dir, pdf_file) for pdf_file in pdf_files]
    worker_args = [(pdf_path, source_type, suppress_stderr) for pdf_path in pdf_paths]
    
    successful_extractions = 0
    failed_extractions = 0
    
    # Process PDFs in parallel with better timeout handling
    if batch_size and len(pdf_files) > batch_size:
        print(f"Processing {len(pdf_files)} files in batches of {batch_size}")
        all_pdf_data = []
        
        for i in range(0, len(worker_args), batch_size):
            batch_worker_args = worker_args[i:i + batch_size]
            batch_timeout = min(dynamic_timeout, batch_size * per_file_timeout)
            print(f"\nProcessing batch {i//batch_size + 1}/{(len(worker_args) + batch_size - 1)//batch_size} ({len(batch_worker_args)} files)")
            
            batch_pdf_data = []
            
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                future_to_pdf = {executor.submit(process_pdf_worker, args): args for args in batch_worker_args}
                
                try:
                    for future in tqdm(as_completed(future_to_pdf, timeout=batch_timeout), total=len(batch_worker_args), desc=f"Batch {i//batch_size + 1}"):
                        try:
                            text, metadata = future.result(timeout=per_file_timeout)
                            if text:
                                batch_pdf_data.append((text, metadata))
                                successful_extractions += 1
                            else:
                                failed_extractions += 1
                        except Exception as e:
                            failed_extractions += 1
                            continue
                except TimeoutError as e:
                    print(f"\nWarning: Batch {i//batch_size + 1} timed out after {batch_timeout} seconds")
                    
                    # Try to get any remaining completed results
                    for future in list(future_to_pdf.keys()):
                        if future.done():
                            try:
                                text, metadata = future.result(timeout=5)
                                if text:
                                    batch_pdf_data.append((text, metadata))
                                    successful_extractions += 1
                            except:
                                failed_extractions += 1
                        else:
                            future.cancel()
            
            all_pdf_data.extend(batch_pdf_data)
        
        pdf_data = all_pdf_data
    else:
        # Process all files at once (original logic)
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            future_to_pdf = {executor.submit(process_pdf_worker, args): args for args in worker_args}
            
            # Process completed tasks with progress bar and improved timeout handling
            try:
                for future in tqdm(as_completed(future_to_pdf, timeout=dynamic_timeout), total=len(worker_args), desc=f"Processing {source_type} PDFs"):
                    try:
                        # Use a reasonable per-file timeout
                        text, metadata = future.result(timeout=per_file_timeout)
                        if text:  # Only add if text was successfully extracted
                            pdf_data.append((text, metadata))
                            successful_extractions += 1
                        else:
                            failed_extractions += 1
                    except Exception as e:
                        # Skip failed extractions (timeout or other errors)
                        failed_extractions += 1
                        continue
            except TimeoutError as e:
                print(f"\nWarning: Processing timed out after {dynamic_timeout} seconds")
                print(f"Completed: {successful_extractions}, Failed: {failed_extractions}, Remaining: {len(future_to_pdf) - successful_extractions - failed_extractions}")
                
                # Try to get any remaining completed results
                for future in list(future_to_pdf.keys()):
                    if future.done():
                        try:
                            text, metadata = future.result(timeout=5)  # Quick timeout for remaining
                            if text:
                                pdf_data.append((text, metadata))
                                successful_extractions += 1
                        except:
                            failed_extractions += 1
                    else:
                        future.cancel()  # Cancel unfinished futures
    
    print(f"Successfully extracted text from {successful_extractions}/{len(pdf_files)} {source_type} PDFs")
    if failed_extractions > 0:
        print(f"Failed to extract text from {failed_extractions} PDFs (timeout or errors)")
    return pdf_data

def load_pdf_data_with_immediate_embedding(pdf_dir: str, source_type: str, qdrant_client=None, es_client=None, 
                                          collection_name: str = None, max_files: int = None, num_workers: int = None, 
                                          timeout: int = 60, suppress_stderr: bool = True, total_timeout: int = None, 
                                          batch_size: int = None, enable_chunking: bool = False, chunk_size: int = 1000, 
                                          chunk_overlap: int = 200, targets: List[str] = ['qdrant']) -> None:
    """
    Load and process PDF files with immediate embedding and ingestion after each batch
    """
    print(f"Loading PDF files from {pdf_dir} directory with immediate embedding...")
    
    # Get all PDF files in the directory
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
    print(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
    
    # Apply limit if specified
    if max_files is not None:
        pdf_files = pdf_files[:max_files]
        print(f"Processing first {max_files} PDF files (use --max-pdfs to change)")
    
    # Determine number of workers
    if num_workers is None:
        num_workers = min(mp.cpu_count(), 8)  # Use up to 8 cores
    
    print(f"Using {num_workers} worker processes for parallel processing")
    
    # Calculate dynamic timeout
    files_per_worker = len(pdf_files) / num_workers
    per_file_timeout = max(30, timeout)
    
    if total_timeout is not None:
        dynamic_timeout = total_timeout
        print(f"Using user-specified total timeout: {dynamic_timeout} seconds")
    else:
        if len(pdf_files) > 500:
            dynamic_timeout = min(1800, int(files_per_worker * per_file_timeout))
            print(f"Large file set detected ({len(pdf_files)} files), using conservative timeout: {dynamic_timeout} seconds")
        else:
            dynamic_timeout = int(files_per_worker * per_file_timeout)
            print(f"Using dynamic timeout: {dynamic_timeout} seconds (based on {files_per_worker:.1f} files per worker)")
    
    # Prepare arguments for workers
    pdf_paths = [os.path.join(pdf_dir, pdf_file) for pdf_file in pdf_files]
    worker_args = [(pdf_path, source_type, suppress_stderr) for pdf_path in pdf_paths]
    
    successful_extractions = 0
    failed_extractions = 0
    
    # Process in batches with immediate embedding
    if batch_size and len(pdf_files) > batch_size:
        print(f"Processing {len(pdf_files)} files in batches of {batch_size} with immediate embedding")
        
        for i in range(0, len(worker_args), batch_size):
            batch_worker_args = worker_args[i:i + batch_size]
            batch_timeout = min(dynamic_timeout, batch_size * per_file_timeout)
            print(f"\nProcessing batch {i//batch_size + 1}/{(len(worker_args) + batch_size - 1)//batch_size} ({len(batch_worker_args)} files)")
            
            batch_pdf_data = []
            
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                future_to_pdf = {executor.submit(process_pdf_worker, args): args for args in batch_worker_args}
                
                try:
                    for future in tqdm(as_completed(future_to_pdf, timeout=batch_timeout), total=len(batch_worker_args), desc=f"Batch {i//batch_size + 1}"):
                        try:
                            text, metadata = future.result(timeout=per_file_timeout)
                            if text:
                                batch_pdf_data.append((text, metadata))
                                successful_extractions += 1
                            else:
                                failed_extractions += 1
                        except Exception as e:
                            failed_extractions += 1
                            continue
                except TimeoutError as e:
                    print(f"\nWarning: Batch {i//batch_size + 1} timed out after {batch_timeout} seconds")
                    
                    # Try to get any remaining completed results
                    for future in list(future_to_pdf.keys()):
                        if future.done():
                            try:
                                text, metadata = future.result(timeout=5)
                                if text:
                                    batch_pdf_data.append((text, metadata))
                                    successful_extractions += 1
                            except:
                                failed_extractions += 1
                        else:
                            future.cancel()
            
            # Process batch with immediate embedding
            if batch_pdf_data:
                process_batch_with_immediate_embedding(
                    batch_pdf_data, source_type, qdrant_client, es_client, collection_name,
                    enable_chunking, chunk_size, chunk_overlap, targets
                )
    else:
        # Process all files at once with immediate embedding
        print("Processing all files at once with immediate embedding")
        all_pdf_data = []
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_pdf = {executor.submit(process_pdf_worker, args): args for args in worker_args}
            
            try:
                for future in tqdm(as_completed(future_to_pdf, timeout=dynamic_timeout), total=len(worker_args), desc=f"Processing {source_type} PDFs"):
                    try:
                        text, metadata = future.result(timeout=per_file_timeout)
                        if text:
                            all_pdf_data.append((text, metadata))
                            successful_extractions += 1
                        else:
                            failed_extractions += 1
                    except Exception as e:
                        failed_extractions += 1
                        continue
            except TimeoutError as e:
                print(f"\nWarning: Processing timed out after {dynamic_timeout} seconds")
                
                for future in list(future_to_pdf.keys()):
                    if future.done():
                        try:
                            text, metadata = future.result(timeout=5)
                            if text:
                                all_pdf_data.append((text, metadata))
                                successful_extractions += 1
                        except:
                            failed_extractions += 1
                    else:
                        future.cancel()
        
        # Process all data with immediate embedding
        if all_pdf_data:
            process_batch_with_immediate_embedding(
                all_pdf_data, source_type, qdrant_client, es_client, collection_name,
                enable_chunking, chunk_size, chunk_overlap, targets
            )
    
    print(f"Successfully extracted text from {successful_extractions}/{len(pdf_files)} {source_type} PDFs")
    if failed_extractions > 0:
        print(f"Failed to extract text from {failed_extractions} PDFs (timeout or errors)")

def parse_project_xml(xml_path: str) -> Dict:
    """Parse a project XML file and extract relevant information."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Extract basic project info
    project_info = {
        'id': root.find('id').text if root.find('id') is not None else None,
        'rcn': root.find('rcn').text if root.find('rcn') is not None else None,
        'acronym': root.find('acronym').text if root.find('acronym') is not None else None,
        'title': root.find('title').text if root.find('title') is not None else None,
        'objective': root.find('objective').text if root.find('objective') is not None else None,
        'teaser': root.find('teaser').text if root.find('teaser') is not None else None,
        'keywords': root.find('keywords').text if root.find('keywords') is not None else None,
        'totalCost': float(root.find('totalCost').text) if root.find('totalCost') is not None else 0.0,
        'ecMaxContribution': float(root.find('ecMaxContribution').text) if root.find('ecMaxContribution') is not None else 0.0,
        'startDate': root.find('startDate').text if root.find('startDate') is not None else None,
        'endDate': root.find('endDate').text if root.find('endDate') is not None else None,
        'status': root.find('status').text if root.find('status') is not None else None,
        'duration': int(root.find('duration').text) if root.find('duration') is not None else None,
        'ecSignatureDate': root.find('ecSignatureDate').text if root.find('ecSignatureDate') is not None else None,
        'sourceUpdateDate': root.find('sourceUpdateDate').text if root.find('sourceUpdateDate') is not None else None,
        'contentCreationDate': root.find('contentCreationDate').text if root.find('contentCreationDate') is not None else None,
        'contentUpdateDate': root.find('contentUpdateDate').text if root.find('contentUpdateDate') is not None else None,
        'lastUpdateDate': root.find('lastUpdateDate').text if root.find('lastUpdateDate') is not None else None,
        'partners': [],
        'publications': [],
        'deliverables': []
    }
    
    # Extract partner information
    for org in root.findall('.//organization'):
        partner = {
            'id': org.find('id').text if org.find('id') is not None else None,
            'name': org.find('legalName').text if org.find('legalName') is not None else None,
            'shortName': org.find('shortName').text if org.find('shortName') is not None else None,
            'type': org.get('type'),
            'role': org.get('type'),  # coordinator, participant, or associatedPartner
            'ecContribution': float(org.get('ecContribution', 0)),
            'totalCost': float(org.get('totalCost', 0)),
            'country': org.find('.//country').text if org.find('.//country') is not None else None,
            'city': org.find('.//city').text if org.find('.//city') is not None else None,
            'address': org.find('.//street').text if org.find('.//street') is not None else None,
            'url': org.find('.//url').text if org.find('.//url') is not None else None,
            'vatNumber': org.find('vatNumber').text if org.find('vatNumber') is not None else None,
            'departmentName': org.find('departmentName').text if org.find('departmentName') is not None else None,
            'geolocation': org.find('.//geolocation').text if org.find('.//geolocation') is not None else None,
            'postBox': org.find('.//postBox').text if org.find('.//postBox') is not None else None,
            'postalCode': org.find('.//postalCode').text if org.find('.//postalCode') is not None else None
        }
        project_info['partners'].append(partner)
    
    # Extract publications
    for pub in root.findall('.//result[@type="relatedResult"]'):
        if pub.find('.//category[@code="/publication"]') is not None:
            publication = {
                'id': pub.find('id').text if pub.find('id') is not None else None,
                'title': pub.find('title').text if pub.find('title') is not None else None,
                'type': pub.find('.//category[@code="/PEER_REVIEWED_ARTICLE"]') is not None and 'PEER_REVIEWED' or 'OTHER',
                'journal': pub.find('.//journalTitle').text if pub.find('.//journalTitle') is not None else None,
                'year': pub.find('.//publishedYear').text if pub.find('.//publishedYear') is not None else None,
                'doi': pub.find('.//doi').text if pub.find('.//doi') is not None else None,
                'publisher': pub.find('.//publisher').text if pub.find('.//publisher') is not None else None,
                'journalNumber': pub.find('.//journalNumber').text if pub.find('.//journalNumber') is not None else None,
                'publishedPages': pub.find('.//publishedPages').text if pub.find('.//publishedPages') is not None else None,
                'issn': pub.find('.//issn').text if pub.find('.//issn') is not None else None,
                'isbn': pub.find('.//isbn').text if pub.find('.//isbn') is not None else None,
                'authors': pub.find('.//authors').text if pub.find('.//authors') is not None else None
            }
            project_info['publications'].append(publication)
    
    # Extract deliverables
    for deliv in root.findall('.//result[@type="relatedResult"]'):
        if deliv.find('.//category[@code="/deliverable"]') is not None:
            deliverable = {
                'id': deliv.find('id').text if deliv.find('id') is not None else None,
                'title': deliv.find('title').text if deliv.find('title') is not None else None,
                'description': deliv.find('description').text if deliv.find('description') is not None else None,
                'type': deliv.find('.//category[@code="/O"]') is not None and 'OTHER' or 
                        deliv.find('.//category[@code="/DEC"]') is not None and 'WEBSITE' or 'REPORT',
                'webLink': deliv.find('.//webLink/physUrl').text if deliv.find('.//webLink/physUrl') is not None else None
            }
            project_info['deliverables'].append(deliverable)
    
    return project_info

def load_xml_data(xml_dir: str) -> Dict[str, Dict]:
    """Load and parse all project XML files from a directory."""
    print("Loading project XML files...")
    xml_data = {}
    
    xml_files = list(Path(xml_dir).glob('*.xml'))
    for xml_file in tqdm(xml_files, desc="Processing XML files"):
        try:
            project_info = parse_project_xml(str(xml_file))
            if project_info['rcn']:
                xml_data[project_info['rcn']] = project_info
        except Exception as e:
            print(f"Error processing {xml_file}: {str(e)}")
    
    return xml_data

def create_neo4j_constraints(session):
    """Create necessary constraints in Neo4j."""
    constraints = [
        "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT org_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
        "CREATE CONSTRAINT funding_instrument_type IF NOT EXISTS FOR (f:FundingInstrument) REQUIRE f.type IS UNIQUE",
        "CREATE CONSTRAINT thematic_area_name IF NOT EXISTS FOR (t:ThematicArea) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT publication_id IF NOT EXISTS FOR (p:Publication) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT deliverable_id IF NOT EXISTS FOR (d:Deliverable) REQUIRE d.id IS UNIQUE"
    ]
    
    for constraint in constraints:
        try:
            session.run(constraint)
        except Exception as e:
            print(f"Warning: Constraint creation failed: {str(e)}")

def insert_into_neo4j(uri, user, password, projects_df, organizations_df, xml_data,
                     publications_df, deliverables_df, topics_df, legal_basis_df,
                     euro_sci_voc_df, policy_priorities_df, report_summaries_df,
                     web_items_df, web_links_df):
    """Insert data into Neo4j"""
    print("Connected to Neo4j successfully!")
    
    # Create driver with database name
    driver = GraphDatabase.driver(uri, auth=(user, password), database="neo4j")
    
    # Create constraints
    with driver.session() as session:
        print("Creating constraints...")
        # Create constraints for all node types
        session.run("""
            CREATE CONSTRAINT project_id IF NOT EXISTS
            FOR (p:Project) REQUIRE p.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT organization_id IF NOT EXISTS
            FOR (o:Organization) REQUIRE o.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT publication_id IF NOT EXISTS
            FOR (p:Publication) REQUIRE p.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT deliverable_id IF NOT EXISTS
            FOR (d:Deliverable) REQUIRE d.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT topic_id IF NOT EXISTS
            FOR (t:Topic) REQUIRE t.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT legal_basis_id IF NOT EXISTS
            FOR (l:LegalBasis) REQUIRE l.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT euro_sci_voc_id IF NOT EXISTS
            FOR (e:EuroSciVoc) REQUIRE e.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT policy_priority_id IF NOT EXISTS
            FOR (p:PolicyPriority) REQUIRE p.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT report_summary_id IF NOT EXISTS
            FOR (r:ReportSummary) REQUIRE r.id IS UNIQUE
        """)
        
        session.run("""
            CREATE CONSTRAINT web_item_id IF NOT EXISTS
            FOR (w:WebItem) REQUIRE w.id IS UNIQUE
        """)
        
        print("\nCreating Project nodes...")
        # Create Project nodes with progress bar
        for _, row in tqdm(projects_df.iterrows(), total=len(projects_df), desc="Projects"):
            # Get additional data from XML if available
            project_id = str(row['id'])
            xml_info = xml_data.get(project_id, {})
            
            # Combine CSV and XML data
            project_data = {
                'id': project_id,
                'acronym': row['acronym'],
                'title': row['title'],
                'startDate': row['startDate'],
                'endDate': row['endDate'],
                'status': row['status'],
                'topics': row['topics'],
                'frameworkProgramme': row['frameworkProgramme'],
                'objective': row['objective'],
                'legalBasis': row['legalBasis'],
                'rcn': row['rcn'],
                'grantDoi': row['grantDoi'],
                'teaser': xml_info.get('teaser', ''),
                'keywords': xml_info.get('keywords', []),
                'totalCost': row['totalCost'],  # Already converted in load_csv_safely
                'ecMaxContribution': row['ecMaxContribution']  # Already converted in load_csv_safely
            }
            
            # Create Project node with all properties
            session.run("""
                MERGE (p:Project {id: $id})
                SET p += $properties
            """, id=project_id, properties=project_data)
            
            # Create relationships with organizations
            if 'partners' in xml_info:
                for partner in xml_info['partners']:
                    session.run("""
                        MATCH (p:Project {id: $project_id})
                        MERGE (o:Organization {id: $org_id})
                        SET o += $org_properties
                        MERGE (o)-[r:PARTICIPATES_IN]->(p)
                        SET r.role = $role,
                            r.ecContribution = $ecContribution
                    """, 
                    project_id=project_id,
                    org_id=partner['id'],
                    org_properties={
                        'name': partner['legalName'],
                        'shortName': partner.get('shortName', ''),
                        'type': partner['type'],
                        'country': partner.get('country', '')
                    },
                    role=partner['role'],
                    ecContribution=partner['ecContribution'])
        
        print("\nCreating Organization nodes and relationships...")
        # Create Organization nodes with progress bar
        for _, row in tqdm(organizations_df.iterrows(), total=len(organizations_df), desc="Organizations"):
            session.run("""
                MERGE (o:Organization {id: $id})
                SET o.name = $name,
                    o.shortName = $shortName,
                    o.type = $type,
                    o.country = $country
            """, 
            id=str(row['organisationID']),
            name=row['name'],
            shortName=row['shortName'],
            type=row['activityType'],
            country=row['country'])
            
            # Create relationship with project if projectID exists
            if pd.notnull(row['projectID']):
                session.run("""
                    MATCH (o:Organization {id: $org_id})
                    MATCH (p:Project {id: $project_id})
                    MERGE (o)-[r:PARTICIPATES_IN]->(p)
                    SET r.role = $role,
                        r.ecContribution = $ecContribution,
                        r.totalCost = $totalCost
                """,
                org_id=str(row['organisationID']),
                project_id=str(row['projectID']),
                role=row['role'],
                ecContribution=float(row['ecContribution']) if pd.notnull(row['ecContribution']) else 0.0,
                totalCost=float(row['totalCost']) if pd.notnull(row['totalCost']) else 0.0)
        
        print("\nCreating Publication nodes and relationships...")
        # Create Publication nodes and relationships
        for _, row in tqdm(publications_df.iterrows(), total=len(publications_df), desc="Publications"):
            session.run("""
                MATCH (p:Project {id: $project_id})
                MERGE (pub:Publication {id: $pub_id})
                SET pub += $properties
                MERGE (p)-[r:HAS_PUBLICATION]->(pub)
            """,
            project_id=str(row['projectID']),
            pub_id=str(row['id']),
            properties={
                'title': row['title'],
                'authors': row['authors'],
                'year': row['publishedYear'],
                'journalTitle': row['journalTitle'],
                'journalNumber': row['journalNumber'],
                'pages': row['publishedPages'],
                'issn': row['issn'],
                'isbn': row['isbn'],
                'doi': row['doi'],
                'isPublishedAs': row['isPublishedAs']
            })
        
        print("\nCreating Deliverable nodes and relationships...")
        # Create Deliverable nodes and relationships
        for _, row in tqdm(deliverables_df.iterrows(), total=len(deliverables_df), desc="Deliverables"):
            session.run("""
                MATCH (p:Project {id: $project_id})
                MERGE (d:Deliverable {id: $deliv_id})
                SET d += $properties
                MERGE (p)-[r:HAS_DELIVERABLE]->(d)
            """,
            project_id=str(row['projectID']),
            deliv_id=str(row['id']),
            properties={
                'title': row['title'],
                'type': row['deliverableType'],
                'description': row['description'],
                'url': row['url']
            })
        
        print("\nCreating Topic nodes and relationships...")
        # Create Topic nodes and relationships
        for _, row in tqdm(topics_df.iterrows(), total=len(topics_df), desc="Topics"):
            session.run("""
                MERGE (t:Topic {
                    id: $topic,
                    title: $title
                })
                WITH t
                MATCH (p:Project {id: $project_id})
                MERGE (p)-[:HAS_TOPIC]->(t)
            """, {
                'topic': str(row['topic']),
                'title': str(row['title']),
                'project_id': str(row['projectID'])
            })
        
        print("\nCreating Legal Basis nodes and relationships...")
        # Create Legal Basis nodes and relationships
        for _, row in tqdm(legal_basis_df.iterrows(), total=len(legal_basis_df), desc="Legal Basis"):
            session.run("""
                MERGE (l:LegalBasis {
                    id: $legal_basis,
                    title: $title
                })
                WITH l
                MATCH (p:Project {id: $project_id})
                MERGE (p)-[:HAS_LEGAL_BASIS]->(l)
            """, {
                'legal_basis': str(row['legalBasis']),
                'title': str(row['title']),
                'project_id': str(row['projectID'])
            })
        
        print("\nCreating EuroSciVoc nodes and relationships...")
        # Create EuroSciVoc nodes and relationships
        for _, row in tqdm(euro_sci_voc_df.iterrows(), total=len(euro_sci_voc_df), desc="EuroSciVoc"):
            session.run("""
                MERGE (e:EuroSciVoc {
                    id: $euro_sci_voc_code,
                    title: $euro_sci_voc_title,
                    description: $euro_sci_voc_description
                })
                WITH e
                MATCH (p:Project {id: $project_id})
                MERGE (p)-[:HAS_EUROSCIVOC]->(e)
            """, {
                'euro_sci_voc_code': str(row['euroSciVocCode']),
                'euro_sci_voc_title': str(row['euroSciVocTitle']),
                'euro_sci_voc_description': str(row['euroSciVocDescription']),
                'project_id': str(row['projectID'])
            })
        
        print("\nCreating Policy Priority nodes and relationships...")
        # Create Policy Priority nodes and relationships
        policy_columns = ['ai', 'biodiversity', 'cleanAir', 'climate', 'digitalAgenda']
        for _, row in tqdm(policy_priorities_df.iterrows(), total=len(policy_priorities_df), desc="Policy Priorities"):
            for policy in policy_columns:
                value = row[policy]
                if str(value) != '0':
                    session.run("""
                        MERGE (pp:PolicyPriority {name: $policy})
                        WITH pp
                        MATCH (p:Project {id: $project_id})
                        MERGE (p)-[:HAS_POLICY_PRIORITY {value: $value}]->(pp)
                    """, {
                        'policy': policy,
                        'project_id': str(row['projectID']),
                        'value': value
                    })
        
        print("\nCreating Report Summary nodes and relationships...")
        # Create Report Summary nodes and relationships
        for _, row in tqdm(report_summaries_df.iterrows(), total=len(report_summaries_df), desc="Report Summaries"):
            session.run("""
                MERGE (rs:ReportSummary {
                    id: $id,
                    title: $title,
                    projectAcronym: $projectAcronym,
                    attachment: $attachment,
                    contentUpdateDate: $contentUpdateDate,
                    rcn: $rcn
                })
                WITH rs
                MATCH (p:Project {id: $project_id})
                MERGE (p)-[:HAS_REPORT_SUMMARY]->(rs)
            """, {
                'id': str(row['id']),
                'title': str(row['title']),
                'projectAcronym': str(row['projectAcronym']),
                'attachment': str(row['attachment']),
                'contentUpdateDate': str(row['contentUpdateDate']),
                'rcn': str(row['rcn']),
                'project_id': str(row['projectID'])
            })
        
        print("\nCreating Web Item nodes and relationships...")
        # Create Web Item nodes and relationships
        for _, row in tqdm(web_items_df.iterrows(), total=len(web_items_df), desc="Web Items"):
            session.run("""
                MERGE (wi:WebItem {
                    uri: $uri,
                    language: $language,
                    availableLanguages: $availableLanguages,
                    title: $title,
                    type: $type,
                    source: $source,
                    represents: $represents
                })
            """, {
                'uri': str(row['uri']),
                'language': str(row['language']),
                'availableLanguages': str(row['availableLanguages']),
                'title': str(row['title']),
                'type': str(row['type']),
                'source': str(row['source']),
                'represents': str(row['represents'])
            })
        
        print("\nCreating Web Link nodes and relationships...")
        # Create Web Link nodes and relationships
        for _, row in tqdm(web_links_df.iterrows(), total=len(web_links_df), desc="Web Links"):
            session.run("""
                MERGE (wl:WebLink {
                    id: $id,
                    physUrl: $physUrl,
                    availableLanguages: $availableLanguages,
                    status: $status,
                    archivedDate: $archivedDate,
                    type: $type,
                    source: $source,
                    represents: $represents
                })
                WITH wl
                MATCH (p:Project {id: $project_id})
                MERGE (p)-[:HAS_WEB_LINK]->(wl)
            """, {
                'id': str(row['id']),
                'physUrl': str(row['physUrl']),
                'availableLanguages': str(row['availableLanguages']),
                'status': str(row['status']),
                'archivedDate': str(row['archivedDate']),
                'type': str(row['type']),
                'source': str(row['source']),
                'represents': str(row['represents']),
                'project_id': str(row['projectID'])
            })
        
        # Print summary of created nodes and relationships
        print("\nVerifying data ingestion...")
        result = session.run("""
            MATCH (n)
            RETURN labels(n) as type, count(*) as count
            ORDER BY type
        """)
        print("\nNode counts:")
        for record in result:
            print(f"{record['type']}: {record['count']}")
        
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY type
        """)
        print("\nRelationship counts:")
        for record in result:
            print(f"{record['type']}: {record['count']}")
    
    driver.close()
    print("\nData ingestion completed successfully!")

def create_elasticsearch_indices(es_client: Elasticsearch, recreate_existing: bool = True):
    """Create Elasticsearch indices with mappings for BM25 search."""
    print("Creating Elasticsearch indices...")
    
    # Index for CORDIS projects
    project_mapping = {
        "mappings": {
            "properties": {
                "project_id": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "standard"},
                "acronym": {"type": "keyword"},
                "objective": {"type": "text", "analyzer": "standard"},
                "teaser": {"type": "text", "analyzer": "standard"},
                "keywords": {"type": "text", "analyzer": "standard"},
                "status": {"type": "keyword"},
                "framework": {"type": "keyword"},
                "start_date": {"type": "date"},
                "end_date": {"type": "date"},
                "total_cost": {"type": "float"},
                "ec_max_contribution": {"type": "float"},
                "partners": {"type": "text", "analyzer": "standard"},
                "publications": {"type": "text", "analyzer": "standard"},
                "deliverables": {"type": "text", "analyzer": "standard"},
                "content": {"type": "text", "analyzer": "standard"},
                "type": {"type": "keyword"},
                "ingested_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
    
    # Index for manuals
    manual_mapping = {
        "mappings": {
            "properties": {
                "filename": {"type": "keyword"},
                "content": {"type": "text", "analyzer": "standard"},
                "page_count": {"type": "integer"},
                "file_size": {"type": "long"},
                "type": {"type": "keyword"},
                "source": {"type": "keyword"},
                "ingested_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
    
    # Index for PDFs
    pdf_mapping = {
        "mappings": {
            "properties": {
                "filename": {"type": "keyword"},
                "content": {"type": "text", "analyzer": "standard"},
                "page_count": {"type": "integer"},
                "file_size": {"type": "long"},
                "type": {"type": "keyword"},
                "source": {"type": "keyword"},
                "ingested_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        }
    }
    
    indices = {
        "cordis_projects": project_mapping,
        "manuals": manual_mapping,
        "pdfs": pdf_mapping
    }
    
    for index_name, mapping in indices.items():
        try:
            if es_client.indices.exists(index=index_name):
                if recreate_existing:
                    print(f"Index {index_name} already exists, deleting...")
                    es_client.indices.delete(index=index_name)
                else:
                    print(f"Index {index_name} already exists, keeping it (no reset).")
                    continue
            
            es_client.indices.create(index=index_name, body=mapping)
            print(f"Created index: {index_name}")
        except Exception as e:
            print(f"Error creating index {index_name}: {str(e)}")

def generate_embeddings(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Generate embeddings using sentence-transformers with MPS acceleration."""
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Determine the best available device
    if torch.backends.mps.is_available():
        device = torch.device('mps')
        print("✓ Using MPS (Apple Silicon GPU) for acceleration")
    elif torch.cuda.is_available():
        device = torch.device('cuda')
        print("✓ Using CUDA GPU for acceleration")
    else:
        device = torch.device('cpu')
        print("⚠ Using CPU (no GPU acceleration available)")
    
    model = model.to(device)
    
    # Preprocess texts to ensure they are valid for the embedding model
    def preprocess_text(text):
        """Clean and validate text for embedding"""
        if not isinstance(text, str):
            return ""
        
        # Remove null bytes and other problematic characters
        text = text.replace('\x00', '')
        text = text.replace('\ufffd', '')  # Unicode replacement character
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Ensure text is not empty and has reasonable length
        if len(text.strip()) < 10:
            return ""
        
        # Truncate very long texts to prevent memory issues
        if len(text) > 10000:
            text = text[:10000]
        
        return text.strip()
    
    # Preprocess all texts
    processed_texts = []
    valid_indices = []
    
    for i, text in enumerate(texts):
        processed_text = preprocess_text(text)
        if processed_text:
            processed_texts.append(processed_text)
            valid_indices.append(i)
        else:
            print(f"Warning: Skipping invalid text at index {i}")
    
    if not processed_texts:
        print("Error: No valid texts found for embedding")
        return []
    
    print(f"Processing {len(processed_texts)} valid texts out of {len(texts)} total")
    
    all_embeddings = []
    total_batches = (len(processed_texts) + batch_size - 1) // batch_size
    print(f"Generating embeddings on {device} for {len(processed_texts)} texts in {total_batches} batches...")
    
    # Process in batches with error handling
    for i in tqdm(range(0, len(processed_texts), batch_size), desc="Generating embeddings"):
        batch_texts = processed_texts[i:i + batch_size]
        
        try:
            # Generate embeddings for the batch
            with torch.no_grad():
                embeddings = model.encode(batch_texts, convert_to_tensor=True, show_progress_bar=False)
                # Move to CPU for numpy conversion
                embeddings = embeddings.cpu().numpy().tolist()
                all_embeddings.extend(embeddings)
        except Exception as e:
            print(f"Error processing batch {i//batch_size + 1}: {str(e)}")
            # Add zero embeddings for failed batch to maintain index alignment
            batch_size_actual = len(batch_texts)
            zero_embedding = [0.0] * 384  # all-MiniLM-L6-v2 produces 384-dimensional embeddings
            all_embeddings.extend([zero_embedding] * batch_size_actual)
    
    # Create final embeddings list with proper indexing
    final_embeddings = []
    embedding_index = 0
    
    for i in range(len(texts)):
        if i in valid_indices:
            if embedding_index < len(all_embeddings):
                final_embeddings.append(all_embeddings[embedding_index])
                embedding_index += 1
            else:
                # Fallback zero embedding
                final_embeddings.append([0.0] * 384)
        else:
            # Zero embedding for invalid texts
            final_embeddings.append([0.0] * 384)
    
    return final_embeddings

def create_document_chunks(text: str, metadata: Dict, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Tuple[str, Dict]]:
    """Create document chunks with enhanced metadata for RAG systems."""
    chunks = []
    
    # Simple text chunking (you can implement more sophisticated chunking if needed)
    words = text.split()
    if len(words) <= chunk_size:
        # Single chunk for short documents
        chunk_metadata = metadata.copy()
        chunk_metadata.update({
            'chunk_id': f"{metadata.get('document_id', 'doc')}_chunk_0",
            'chunk_index': 0,
            'total_chunks': 1,
            'chunk_size': len(words),
            'chunk_start': 0,
            'chunk_end': len(words)
        })
        chunks.append((text, chunk_metadata))
    else:
        # Multiple chunks for long documents
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                'chunk_id': f"{metadata.get('document_id', 'doc')}_chunk_{i//(chunk_size - chunk_overlap)}",
                'chunk_index': i//(chunk_size - chunk_overlap),
                'total_chunks': (len(words) + chunk_size - chunk_overlap - 1) // (chunk_size - chunk_overlap),
                'chunk_size': len(chunk_words),
                'chunk_start': i,
                'chunk_end': min(i + chunk_size, len(words))
            })
            chunks.append((chunk_text, chunk_metadata))
    
    return chunks

def embed_and_load_to_databases(
    qdrant_url: str,
    qdrant_api_key: Optional[str],
    es_url: str,
    es_username: str = None,
    es_password: str = None,
    projects_df: pd.DataFrame = None,
    xml_data: Dict[str, Dict] = None,
    manuals_data: List[Tuple[str, Dict]] = None,
    pdfs_data: List[Tuple[str, Dict]] = None,
    targets: List[str] = ['qdrant', 'elasticsearch'],
    enable_chunking: bool = False,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    recreate_es_indices: bool = True,
) -> None:
    """Embed project descriptions, XML data, and PDF content, then load them into Qdrant and Elasticsearch."""
    try:
        # Initialize clients based on targets
        qdrant_client = None
        es_client = None
        
        if 'qdrant' in targets:
            # Connect to Qdrant
            qdrant_client = make_qdrant_client(qdrant_url, qdrant_api_key)
            print("Connected to Qdrant successfully!")
            
            # Create Qdrant collections if they don't exist
            collections = {
                "cordis_projects": "Project data from CORDIS",
                "manuals": "PDF manuals and documentation",
                "pdfs": "Additional PDF documents"
            }
            
            for collection_name, description in collections.items():
                if not any(c.name == collection_name for c in qdrant_client.get_collections().collections):
                    qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                    )
                    print(f"Created Qdrant collection: {collection_name}")
        
        if 'elasticsearch' in targets:
            # Connect to Elasticsearch
            es_config = {"hosts": [es_url]}
            if es_username and es_password:
                es_config["basic_auth"] = (es_username, es_password)
            
            es_client = Elasticsearch(**es_config)
            
            # Test Elasticsearch connection
            if es_client.ping():
                print("Connected to Elasticsearch successfully!")
            else:
                raise Exception("Could not connect to Elasticsearch")
            
            # Create Elasticsearch indices (or keep existing when immediate embedding already populated them)
            create_elasticsearch_indices(es_client, recreate_existing=recreate_es_indices)

        # Process project data
        if not projects_df.empty:
            print("Processing project data...")
            project_texts = []
            project_metadata = []
            es_documents = []
            
            for _, project in projects_df.iterrows():
                project_id = str(project['id'])
                text_content = f"Title: {project['title']}\n"
                if pd.notnull(project['objective']):
                    text_content += f"Objective: {project['objective']}\n"
                
                # Add XML data if available
                if xml_data and project_id in xml_data:
                    xml_info = xml_data[project_id]
                    if xml_info.get('teaser'):
                        text_content += f"Teaser: {xml_info['teaser']}\n"
                    if xml_info.get('keywords'):
                        text_content += f"Keywords: {xml_info['keywords']}\n"
                    
                    # Add partner information
                    if xml_info.get('partners'):
                        text_content += "Partners:\n"
                        for partner in xml_info['partners']:
                            text_content += f"- {partner.get('name', '')} ({partner.get('country', '')})\n"
                    
                    # Add publication information
                    if xml_info.get('publications'):
                        text_content += "Publications:\n"
                        for pub in xml_info['publications']:
                            text_content += f"- {pub.get('title', '')} ({pub.get('year', '')})\n"
                    
                    # Add deliverable information
                    if xml_info.get('deliverables'):
                        text_content += "Deliverables:\n"
                        for deliv in xml_info['deliverables']:
                            text_content += f"- {deliv.get('title', '')} ({deliv.get('type', '')})\n"
                
                project_texts.append(text_content)
                
                # Enhanced metadata with XML data
                meta = {
                    'project_id': project_id,
                    'title': project['title'],
                    'acronym': project['acronym'],
                    'status': project['status'],
                    'framework': project['frameworkProgramme'],
                    'start_date': pd.to_datetime(project['startDate']).isoformat() if pd.notnull(project['startDate']) else None,
                    'end_date': pd.to_datetime(project['endDate']).isoformat() if pd.notnull(project['endDate']) else None,
                    'type': 'project',
                    'document_id': f"project_{project_id}",
                    'document_link': f"cordis://project/{project_id}",  # Custom protocol for CORDIS projects
                    'source': 'CORDIS Database',
                    'ingested_at': datetime.now().isoformat()
                }
                
                # Add XML metadata if available
                if xml_data and project_id in xml_data:
                    xml_info = xml_data[project_id]
                    meta.update({
                        'teaser': xml_info.get('teaser', ''),
                        'keywords': xml_info.get('keywords', []),
                        'duration': xml_info.get('duration'),
                        'ec_signature_date': xml_info.get('ecSignatureDate'),
                        'source_update_date': xml_info.get('sourceUpdateDate'),
                        'content_creation_date': xml_info.get('contentCreationDate'),
                        'content_update_date': xml_info.get('contentUpdateDate'),
                        'last_update_date': xml_info.get('lastUpdateDate'),
                        'partners_count': len(xml_info.get('partners', [])),
                        'publications_count': len(xml_info.get('publications', [])),
                        'deliverables_count': len(xml_info.get('deliverables', []))
                    })
                
                project_metadata.append(meta)
                
                # Prepare Elasticsearch document
                es_doc = {
                    '_index': 'cordis_projects',
                    '_id': project_id,
                    '_source': {
                        'project_id': project_id,
                        'title': project['title'],
                        'acronym': project['acronym'],
                        'objective': project['objective'] if pd.notnull(project['objective']) else '',
                        'teaser': xml_info.get('teaser', '') if xml_data and project_id in xml_data else '',
                        'keywords': xml_info.get('keywords', '') if xml_data and project_id in xml_data else '',
                        'status': project['status'],
                        'framework': project['frameworkProgramme'],
                        'start_date': project['startDate'] if pd.notnull(project['startDate']) else None,
                        'end_date': project['endDate'] if pd.notnull(project['endDate']) else None,
                        'total_cost': float(project['totalCost']) if pd.notnull(project['totalCost']) else 0.0,
                        'ec_max_contribution': float(project['ecMaxContribution']) if pd.notnull(project['ecMaxContribution']) else 0.0,
                        'partners': '; '.join([f"{p.get('name', '')} ({p.get('country', '')})" for p in xml_info.get('partners', [])]) if xml_data and project_id in xml_data else '',
                        'publications': '; '.join([f"{p.get('title', '')} ({p.get('year', '')})" for p in xml_info.get('publications', [])]) if xml_data and project_id in xml_data else '',
                        'deliverables': '; '.join([f"{d.get('title', '')} ({d.get('type', '')})" for d in xml_info.get('deliverables', [])]) if xml_data and project_id in xml_data else '',
                        'content': text_content,
                        'type': 'project',
                        'ingested_at': datetime.now().isoformat()
                    }
                }
                es_documents.append(es_doc)

            # Apply chunking to project data if enabled
            if enable_chunking:
                print(f"Creating project chunks with size {chunk_size} and overlap {chunk_overlap}")
                project_chunks = []
                for text, meta in zip(project_texts, project_metadata):
                    chunks = create_document_chunks(text, meta, chunk_size, chunk_overlap)
                    project_chunks.extend(chunks)
                texts = [text for text, _ in project_chunks]
                metadata = [meta for _, meta in project_chunks]
                print(f"Created {len(project_chunks)} chunks from {len(project_texts)} projects")
            else:
                texts = project_texts
                metadata = project_metadata

            # Generate embeddings for projects (only if needed for vector databases)
            if 'qdrant' in targets or 'elasticsearch' in targets:
                # Use optimal batch size for MPS acceleration
                try:
                    project_embeddings = generate_embeddings(texts, batch_size=32)
                except Exception as e:
                    print(f"Error generating project embeddings: {str(e)}")
                    print("Skipping project embeddings for Qdrant/Elasticsearch")
                    project_embeddings = None

            # Upload project points to Qdrant in batches
            if 'qdrant' in targets and project_embeddings is not None:
                batch_size = 100
                print("Uploading project data to Qdrant...")
                for i in tqdm(range(0, len(texts), batch_size)):
                    batch_end = min(i + batch_size, len(texts))
                    points = [
                        PointStruct(
                            id=idx,
                            vector=vec,
                            payload=meta
                        )
                        for idx, (vec, meta) in enumerate(
                            zip(project_embeddings[i:batch_end], metadata[i:batch_end]),
                            start=i
                        )
                    ]
                    qdrant_client.upsert(
                        collection_name="cordis_projects",
                        points=points
                    )
            
            # Upload project documents to Elasticsearch
            if 'elasticsearch' in targets:
                print("Uploading project data to Elasticsearch...")
                success, failed = bulk(es_client, es_documents, chunk_size=100, request_timeout=30)
                print(f"Elasticsearch bulk upload: {success} succeeded, {len(failed)} failed")

        # Process PDF data
        if manuals_data:
            print("Processing manuals data...")
            
            # Apply chunking if enabled
            if enable_chunking:
                print(f"Creating chunks with size {chunk_size} and overlap {chunk_overlap}")
                manuals_chunks = []
                for text, meta in manuals_data:
                    chunks = create_document_chunks(text, meta, chunk_size, chunk_overlap)
                    manuals_chunks.extend(chunks)
                manuals_texts = [text for text, _ in manuals_chunks]
                manuals_metadata = [meta for _, meta in manuals_chunks]
                print(f"Created {len(manuals_chunks)} chunks from {len(manuals_data)} documents")
            else:
                manuals_texts = [text for text, _ in manuals_data]
                manuals_metadata = [meta for _, meta in manuals_data]
            
            # Prepare Elasticsearch documents for manuals
            manuals_es_documents = []
            if 'elasticsearch' in targets:
                for i, (text, meta) in enumerate(manuals_data):
                    es_doc = {
                        '_index': 'manuals',
                        '_id': f"manual_{i}",
                        '_source': {
                            'filename': meta.get('filename', ''),
                            'content': text,
                            'page_count': meta.get('page_count', 0),
                            'file_size': meta.get('file_size', 0),
                            'type': meta.get('type', 'manual'),
                            'source': meta.get('source', 'Manual'),
                            'ingested_at': datetime.now().isoformat()
                        }
                    }
                    manuals_es_documents.append(es_doc)

            # Generate embeddings for manuals content (only if needed for vector databases)
            if 'qdrant' in targets:
                # Use optimal batch size for MPS acceleration
                try:
                    manuals_embeddings = generate_embeddings(manuals_texts, batch_size=32)
                except Exception as e:
                    print(f"Error generating manuals embeddings: {str(e)}")
                    print("Skipping manuals embeddings for Qdrant")
                    manuals_embeddings = None

                # Upload manuals points to Qdrant in batches
                if manuals_embeddings is not None:
                    print("Uploading manuals data to Qdrant...")
                    batch_size = 50  # Smaller batch size for potentially larger texts
                    for i in tqdm(range(0, len(manuals_texts), batch_size)):
                        batch_end = min(i + batch_size, len(manuals_texts))
                        points = [
                            PointStruct(
                                id=idx,
                                vector=vec,
                                payload=meta
                            )
                            for idx, (vec, meta) in enumerate(
                                zip(manuals_embeddings[i:batch_end], manuals_metadata[i:batch_end]),
                                start=i
                            )
                        ]
                        qdrant_client.upsert(
                            collection_name="manuals",
                            points=points
                        )
            
            # Upload manuals documents to Elasticsearch
            if 'elasticsearch' in targets:
                print("Uploading manuals data to Elasticsearch...")
                success, failed = bulk(es_client, manuals_es_documents, chunk_size=50, request_timeout=30)
                print(f"Elasticsearch bulk upload: {success} succeeded, {len(failed)} failed")

        if pdfs_data:
            print("Processing PDFs data...")
            
            # Apply chunking if enabled
            if enable_chunking:
                print(f"Creating chunks with size {chunk_size} and overlap {chunk_overlap}")
                pdfs_chunks = []
                for text, meta in pdfs_data:
                    chunks = create_document_chunks(text, meta, chunk_size, chunk_overlap)
                    pdfs_chunks.extend(chunks)
                pdfs_texts = [text for text, _ in pdfs_chunks]
                pdfs_metadata = [meta for _, meta in pdfs_chunks]
                print(f"Created {len(pdfs_chunks)} chunks from {len(pdfs_data)} documents")
            else:
                pdfs_texts = [text for text, _ in pdfs_data]
                pdfs_metadata = [meta for _, meta in pdfs_data]
            
            # Prepare Elasticsearch documents for PDFs
            pdfs_es_documents = []
            if 'elasticsearch' in targets:
                for i, (text, meta) in enumerate(pdfs_data):
                    es_doc = {
                        '_index': 'pdfs',
                        '_id': f"pdf_{i}",
                        '_source': {
                            'filename': meta.get('filename', ''),
                            'content': text,
                            'page_count': meta.get('page_count', 0),
                            'file_size': meta.get('file_size', 0),
                            'type': meta.get('type', 'pdf'),
                            'source': meta.get('source', 'PDF'),
                            'ingested_at': datetime.now().isoformat()
                        }
                    }
                    pdfs_es_documents.append(es_doc)

            # Generate embeddings for PDFs content (only if needed for vector databases)
            if 'qdrant' in targets:
                # Use optimal batch size for MPS acceleration (32 was fastest in tests)
                try:
                    pdfs_embeddings = generate_embeddings(pdfs_texts, batch_size=32)
                except Exception as e:
                    print(f"Error generating PDFs embeddings: {str(e)}")
                    print("Skipping PDFs embeddings for Qdrant")
                    pdfs_embeddings = None

                # Upload PDFs points to Qdrant in batches
                if pdfs_embeddings is not None:
                    print("Uploading PDFs data to Qdrant...")
                    batch_size = 50  # Smaller batch size for potentially larger texts
                    for i in tqdm(range(0, len(pdfs_texts), batch_size)):
                        batch_end = min(i + batch_size, len(pdfs_texts))
                        points = [
                            PointStruct(
                                id=idx,
                                vector=vec,
                                payload=meta
                            )
                            for idx, (vec, meta) in enumerate(
                                zip(pdfs_embeddings[i:batch_end], pdfs_metadata[i:batch_end]),
                                start=i
                            )
                        ]
                        qdrant_client.upsert(
                            collection_name="pdfs",
                            points=points
                        )
            
            # Upload PDFs documents to Elasticsearch
            if 'elasticsearch' in targets:
                print("Uploading PDFs data to Elasticsearch...")
                success, failed = bulk(es_client, pdfs_es_documents, chunk_size=50, request_timeout=30)
                print(f"Elasticsearch bulk upload: {success} succeeded, {len(failed)} failed")

        print(f"All data inserted into selected targets ({', '.join(targets)}) successfully!")
    except Exception as e:
        print(f"Error with Qdrant operations: {str(e)}")

def clear_databases(neo4j_uri: str, neo4j_user: str, neo4j_password: str, qdrant_url: str, qdrant_api_key: Optional[str],
                   es_url: str, es_username: str = None, es_password: str = None, database: str = "all"):
    """Clear specified database(s)"""
    print(f"Clearing database(s): {database}")
    
    if database in ["all", "neo4j"]:
        # Clear Neo4j database
        print("Clearing Neo4j database...")
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password), database="neo4j")
        with driver.session() as session:
            # Drop all constraints
            print("Dropping constraints...")
            result = session.run("SHOW CONSTRAINTS")
            constraints = [record["name"] for record in result]
            for constraint in constraints:
                session.run(f"DROP CONSTRAINT {constraint} IF EXISTS")
            
            # Delete all nodes and relationships
            print("Deleting all nodes and relationships...")
            session.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("Neo4j database cleared successfully!")
    
    if database in ["all", "qdrant"]:
        # Clear Qdrant database
        print("Clearing Qdrant database...")
        qdrant_client = make_qdrant_client(qdrant_url, qdrant_api_key)
        collections_to_clear = ["cordis_projects", "manuals", "pdfs"]
        for collection_name in collections_to_clear:
            try:
                qdrant_client.delete_collection(collection_name=collection_name)
                print(f"Cleared collection: {collection_name}")
            except Exception as e:
                print(f"Warning: Could not clear collection {collection_name}: {str(e)}")
        
        print("Qdrant database cleared successfully!")
    
    if database in ["all", "elasticsearch"]:
        # Clear Elasticsearch database
        print("Clearing Elasticsearch database...")
        es_config = {"hosts": [es_url]}
        if es_username and es_password:
            es_config["basic_auth"] = (es_username, es_password)
        
        es_client = Elasticsearch(**es_config)
        indices_to_clear = ["cordis_projects", "manuals", "pdfs"]
        for index_name in indices_to_clear:
            try:
                if es_client.indices.exists(index=index_name):
                    es_client.indices.delete(index=index_name)
                    print(f"Cleared index: {index_name}")
            except Exception as e:
                print(f"Warning: Could not clear index {index_name}: {str(e)}")
        
        print("Elasticsearch database cleared successfully!")
    
    print("Database clearing completed!")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='CORDIS Data Ingestion Script')
    parser.add_argument('--delete', nargs='?', const='all', choices=['all', 'neo4j', 'qdrant', 'elasticsearch'], 
                       help='Clear specified database(s) and exit. Options: all, neo4j, qdrant, elasticsearch. Default: all')
    parser.add_argument('--targets', nargs='+', choices=['neo4j', 'qdrant', 'elasticsearch'], default=['neo4j', 'qdrant', 'elasticsearch'],
                       help='Specify which targets to ingest data into. Options: neo4j, qdrant, elasticsearch. Default: all')
    parser.add_argument(
        '--check-connections',
        action='store_true',
        help='Only verify connectivity to the selected --targets (no data load / ingest), then exit. Exit code 0 if all checks pass.',
    )
    parser.add_argument('--skip-data-loading', action='store_true',
                       help='Skip loading CSV/XML/PDF data (useful for testing with existing data)')
    parser.add_argument('--max-pdfs', type=int, default=None,
                       help='Maximum number of PDF files to process (default: all files)')
    parser.add_argument('--num-workers', type=int, default=None,
                       help='Number of worker processes for PDF processing (default: min(cpu_count, 8))')
    parser.add_argument('--pdf-timeout', type=int, default=60,
                       help='Timeout in seconds per PDF file (default: 60)')
    parser.add_argument('--total-timeout', type=int, default=None,
                       help='Total timeout in seconds for all PDF processing (default: calculated based on files and workers)')
    parser.add_argument('--batch-size', type=int, default=None,
                       help='Process PDFs in batches of this size (useful for very large datasets)')
    parser.add_argument('--chunk-size', type=int, default=1000,
                       help='Number of words per chunk for document splitting (default: 1000)')
    parser.add_argument('--chunk-overlap', type=int, default=200,
                       help='Number of overlapping words between chunks (default: 200)')
    parser.add_argument('--enable-chunking', action='store_true',
                       help='Enable document chunking for better RAG retrieval')
    parser.add_argument('--immediate-embedding', action='store_true',
                       help='Process embeddings and ingest immediately after each batch (requires --batch-size)')
    parser.add_argument('--show-warnings', action='store_true',
                       help='Show PDF processing warnings (default: suppressed)')
    parser.add_argument('--show-stderr', action='store_true',
                       help='Show PDF processing stderr output (default: suppressed)')
    args = parser.parse_args()

    if not args.check_connections:
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if not conda_prefix or "mapit" not in conda_prefix:
            print("Please activate the conda environment 'mapit' before running this script")
            print("You can do this by running: conda activate mapit")
            sys.exit(1)

    load_dotenv()

    # Handle warning suppression
    if args.show_warnings:
        # Re-enable warnings if requested
        warnings.filterwarnings("default", category=UserWarning, module="PyPDF2")
        warnings.filterwarnings("default", category=UserWarning, module="PyPDF2.generic")
        warnings.filterwarnings("default", category=UserWarning, module="PyPDF2.pdf")
        warnings.filterwarnings("default", category=UserWarning, module="PyPDF2.utils")
        warnings.filterwarnings("default", message="Multiple definitions in dictionary")
        warnings.filterwarnings("default", message=".*Multiple definitions.*")
        print("PDF processing warnings are enabled")
    else:
        print("PDF processing warnings are suppressed (use --show-warnings to enable)")
    
    neo4j_uri, neo4j_user, neo4j_password = resolve_neo4j_credentials()
    qdrant_url, qdrant_api_key = resolve_qdrant_credentials()
    es_url, es_username, es_password = resolve_elasticsearch_credentials()

    if args.check_connections and args.delete:
        raise ValueError("Use either --check-connections or --delete, not both.")

    if "neo4j" in args.targets and not neo4j_password:
        if not args.check_connections:
            raise ValueError(
                "Neo4j password not set. Set NEO4J_PASSWORD or NEO4J_AUTH=user/password"
            )
    if "qdrant" in args.targets and not qdrant_api_key:
        print(
            "Warning: QDRANT_API_KEY / QDRANT__SERVICE__API_KEY not set; "
            "connecting without an API key (will fail if your Qdrant requires one)."
        )
    if "elasticsearch" in args.targets and not es_password:
        print(
            "Warning: ELASTICSEARCH_PASSWORD / ELASTIC_PASSWORD not set; "
            "using unauthenticated ES (will fail if security is enabled)."
        )

    if args.delete in ("all", "neo4j") and not neo4j_password:
        raise ValueError(
            "Neo4j password required for this --delete scope. "
            "Set NEO4J_PASSWORD or NEO4J_AUTH=user/password"
        )

    if args.check_connections:
        ok = check_database_connections(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            qdrant_url,
            qdrant_api_key,
            es_url,
            es_username,
            es_password,
            targets=args.targets,
        )
        sys.exit(0 if ok else 1)

    # Validate immediate embedding requires batch size
    if args.immediate_embedding and not args.batch_size:
        raise ValueError("--immediate-embedding requires --batch-size to be specified")
    
    # If --delete flag is set, clear databases and exit
    if args.delete:
        clear_databases(neo4j_uri, neo4j_user, neo4j_password, qdrant_url, qdrant_api_key, 
                       es_url, es_username, es_password, args.delete)
        return
    
    # Check if we're in the correct conda environment
    if os.getenv('CONDA_DEFAULT_ENV') != 'mapit':
        print("Warning: Not running in 'mapit' conda environment")
        print("Please activate the correct environment with: conda activate mapit")
        return

    try:
        # Initialize data variables
        projects_df = None
        organizations_df = None
        publications_df = None
        deliverables_df = None
        topics_df = None
        legal_basis_df = None
        euro_sci_voc_df = None
        policy_priorities_df = None
        report_summaries_df = None
        web_items_df = None
        web_links_df = None
        xml_data = None
        manuals_data = None
        pdfs_data = None
        
        if not args.skip_data_loading:
            print("Loading CORDIS data from CSV files...")
            
            # Load all CSV files
            csv_dir = 'scripts/csv'
            projects_df = load_csv_safely(f'{csv_dir}/project.csv')
            organizations_df = load_csv_safely(f'{csv_dir}/organization.csv')
            publications_df = load_csv_safely(f'{csv_dir}/projectPublications.csv')
            deliverables_df = load_csv_safely(f'{csv_dir}/projectDeliverables.csv')
            topics_df = load_csv_safely(f'{csv_dir}/topics.csv')
            legal_basis_df = load_csv_safely(f'{csv_dir}/legalBasis.csv')
            euro_sci_voc_df = load_csv_safely(f'{csv_dir}/euroSciVoc.csv')
            policy_priorities_df = load_csv_safely(f'{csv_dir}/policyPriorities.csv')
            report_summaries_df = load_csv_safely(f'{csv_dir}/reportSummaries.csv')
            web_items_df = load_csv_safely(f'{csv_dir}/webItem.csv')
            web_links_df = load_csv_safely(f'{csv_dir}/webLink.csv')
            
            print("Loading XML data...")
            # Load XML data
            xml_dir = 'scripts/csv/projects-xml'  # Updated path
            xml_data = load_xml_data(xml_dir)
            
            print("Loading PDF data...")
            
            # Initialize clients if immediate embedding is enabled
            qdrant_client = None
            es_client = None
            if args.immediate_embedding and ('qdrant' in args.targets or 'elasticsearch' in args.targets):
                if 'qdrant' in args.targets:
                    from qdrant_client import QdrantClient
                    qdrant_client = make_qdrant_client(qdrant_url, qdrant_api_key)
                    print("Initialized Qdrant client for immediate embedding")
                
                if 'elasticsearch' in args.targets:
                    from elasticsearch import Elasticsearch
                    es_config = {"hosts": [es_url]}
                    if es_username and es_password:
                        es_config["basic_auth"] = (es_username, es_password)
                    es_client = Elasticsearch(**es_config)
                    print("Initialized Elasticsearch client for immediate embedding")
            
            # Load PDF data from Manuals directory
            manuals_dir = 'scripts/Manuals'  # Path relative to project root
            print(f"Looking for Manuals directory at: {os.path.abspath(manuals_dir)}")
            if os.path.exists(manuals_dir):
                print(f"Found Manuals directory with {len(os.listdir(manuals_dir))} files")
                
                if args.immediate_embedding and (qdrant_client or es_client):
                    # Use immediate embedding
                    load_pdf_data_with_immediate_embedding(
                        manuals_dir, 'manual', qdrant_client, es_client, 'manuals',
                        args.max_pdfs, args.num_workers, args.pdf_timeout, not args.show_stderr, 
                        args.total_timeout, args.batch_size, args.enable_chunking, 
                        args.chunk_size, args.chunk_overlap, args.targets
                    )
                    manuals_data = []  # Data already ingested
                else:
                    # Use regular loading
                    manuals_data = load_pdf_data(manuals_dir, 'manual', args.max_pdfs, args.num_workers, args.pdf_timeout, not args.show_stderr, args.total_timeout, args.batch_size)
                    print(f"Successfully loaded {len(manuals_data)} manual documents")
            else:
                print(f"Warning: Manuals directory not found at {manuals_dir}")
                manuals_data = None
            
            # Load PDF data from pdfs directory
            pdfs_dir = 'scripts/pdfs'  # Path relative to project root
            print(f"Looking for PDFs directory at: {os.path.abspath(pdfs_dir)}")
            if os.path.exists(pdfs_dir):
                print(f"Found PDFs directory with {len(os.listdir(pdfs_dir))} files")
                
                if args.immediate_embedding and (qdrant_client or es_client):
                    # Use immediate embedding
                    load_pdf_data_with_immediate_embedding(
                        pdfs_dir, 'pdf', qdrant_client, es_client, 'pdfs',
                        args.max_pdfs, args.num_workers, args.pdf_timeout, not args.show_stderr, 
                        args.total_timeout, args.batch_size, args.enable_chunking, 
                        args.chunk_size, args.chunk_overlap, args.targets
                    )
                    pdfs_data = []  # Data already ingested
                else:
                    # Use regular loading
                    pdfs_data = load_pdf_data(pdfs_dir, 'pdf', args.max_pdfs, args.num_workers, args.pdf_timeout, not args.show_stderr, args.total_timeout, args.batch_size)
                    print(f"Successfully loaded {len(pdfs_data)} PDF documents")
            else:
                print(f"Warning: PDFs directory not found at {pdfs_dir}")
                pdfs_data = None
        
        print(f"Selected targets for ingestion: {args.targets}")
        
        # Perform ingestion based on selected targets
        if 'neo4j' in args.targets:
            print("\n" + "="*50)
            print("INGESTING INTO NEO4J")
            print("="*50)
            if projects_df is not None:
                insert_into_neo4j(neo4j_uri, neo4j_user, neo4j_password, 
                                 projects_df, organizations_df, xml_data,
                                 publications_df, deliverables_df, topics_df,
                                 legal_basis_df, euro_sci_voc_df, policy_priorities_df,
                                 report_summaries_df, web_items_df, web_links_df)
            else:
                print("Error: No data loaded for Neo4j ingestion")
        
        if 'qdrant' in args.targets or 'elasticsearch' in args.targets:
            print("\n" + "="*50)
            print("INGESTING INTO VECTOR DATABASES")
            print("="*50)
            if projects_df is not None:
                embed_and_load_to_databases(qdrant_url, qdrant_api_key, es_url, es_username, es_password, 
                                           projects_df, xml_data, manuals_data, pdfs_data,
                                           targets=args.targets,
                                           enable_chunking=args.enable_chunking,
                                           chunk_size=args.chunk_size,
                                           chunk_overlap=args.chunk_overlap,
                                           recreate_es_indices=not args.immediate_embedding)
            else:
                print("Error: No data loaded for vector database ingestion")

    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main() 