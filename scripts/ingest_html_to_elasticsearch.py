#!/usr/bin/env python3
"""
Script to ingest HTML files from calls_htmls directory into Elasticsearch.
Creates two indices: 'callshtml' (raw HTML) and 'callstext' (clean text).
Uses BM25 scoring for text search and dense vector embeddings for semantic search.
"""

import os
import json
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import logging

from dotenv import load_dotenv

# HTML processing
from bs4 import BeautifulSoup
import html2text

# Vector embeddings
from sentence_transformers import SentenceTransformer
import numpy as np

# Elasticsearch client
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


def resolve_elasticsearch_credentials() -> Tuple[str, Optional[str], Optional[str]]:
    """
    Elasticsearch URL and optional basic-auth (same as ingest_data.py).

    ELASTICSEARCH_USERNAME / ELASTICSEARCH_PASSWORD (legacy)
    plus ELASTIC_PASSWORD (official ES Docker variable; default username 'elastic').
    """
    hosts = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    user = os.getenv("ELASTICSEARCH_USERNAME") or os.getenv("ELASTIC_USER")
    password = os.getenv("ELASTICSEARCH_PASSWORD") or os.getenv("ELASTIC_PASSWORD")

    user = user.strip() if user else None
    password = password.strip() if password else None

    if password and not user:
        user = os.getenv("ELASTIC_USERNAME_DEFAULT") or "elastic"

    return hosts, user, password


def make_elasticsearch_client(elasticsearch_url: Optional[str] = None) -> Elasticsearch:
    """Elasticsearch client with optional basic_auth from environment."""
    resolved_url, es_user, es_password = resolve_elasticsearch_credentials()
    url = elasticsearch_url if elasticsearch_url is not None else resolved_url
    es_config: Dict[str, Any] = {
        "hosts": [url],
        "request_timeout": 120,
    }
    if es_user and es_password:
        es_config["basic_auth"] = (es_user, es_password)
    elif es_password and not es_user:
        es_config["basic_auth"] = ("elastic", es_password)

    client = Elasticsearch(**es_config)
    if es_password:
        logger.info("Elasticsearch: using basic auth from environment")
    else:
        logger.info("Elasticsearch: no password in env (anonymous; fails if security is enabled)")
    return client


class HTMLIngestionManager:
    def __init__(self, elasticsearch_url: Optional[str] = None):
        """Initialize the HTML ingestion manager (auth from .env / environment)."""
        self.es_client = make_elasticsearch_client(elasticsearch_url)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_size = 384
        
        # Index names
        self.html_index = "callshtml"
        self.text_index = "callstext"
        
        # Chunking parameters (optimized based on HTML content analysis)
        self.html_chunk_size = 16384  # ~16KB for HTML chunks
        self.html_overlap = 1024      # 1KB overlap
        self.text_chunk_size = 2000   # 2KB for text chunks  
        self.text_overlap = 200       # 200 char overlap
        
        logger.info(f"Initialized with vector size: {self.vector_size}")
        logger.info(f"HTML chunk size: {self.html_chunk_size}, overlap: {self.html_overlap}")
        logger.info(f"Text chunk size: {self.text_chunk_size}, overlap: {self.text_overlap}")

    def create_indices(self) -> None:
        """Delete existing indices and create new ones with proper mappings."""
        indices = [self.html_index, self.text_index]
        
        for index_name in indices:
            # Delete existing index if it exists
            try:
                if self.es_client.indices.exists(index=index_name):
                    self.es_client.indices.delete(index=index_name)
                    logger.info(f"Deleted existing index '{index_name}'")
            except Exception as e:
                logger.info(f"Index '{index_name}' does not exist or could not be deleted: {e}")
            
            # Create new index with mapping
            try:
                mapping = {
                    "mappings": {
                        "properties": {
                            "content": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "filename": {
                                "type": "keyword"
                            },
                            "chunk_index": {
                                "type": "integer"
                            },
                            "total_chunks": {
                                "type": "integer"
                            },
                            "content_type": {
                                "type": "keyword"
                            },
                            "chunk_size": {
                                "type": "integer"
                            },
                            "processed_at": {
                                "type": "date"
                            },
                            "content_vector": {
                                "type": "dense_vector",
                                "dims": self.vector_size,
                                "index": True,
                                "similarity": "cosine"
                            }
                        }
                    },
                    "settings": {
                        "index": {
                            "number_of_shards": 1,
                            "number_of_replicas": 0
                        }
                    }
                }
                
                self.es_client.indices.create(
                    index=index_name,
                    body=mapping
                )
                logger.info(f"Created index '{index_name}' with vector mapping")
            except Exception as e:
                logger.error(f"Failed to create index '{index_name}': {e}")
                raise

    def extract_text_from_html(self, html_content: str) -> str:
        """Extract clean text from HTML content."""
        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # Find the main content area
            main_content = soup.find('eui-page-content', class_='eui-page-content')
            if main_content:
                content = str(main_content)
            else:
                # Fallback to body content
                content = str(soup.find('body')) if soup.find('body') else html_content
            
            # Convert HTML to text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # No line wrapping
            
            text = h.handle(content)
            
            # Clean up the text
            text = re.sub(r'\n\s*\n', '\n\n', text)  # Remove excessive newlines
            text = re.sub(r'[ \t]+', ' ', text)      # Normalize whitespace
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from HTML: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # If this isn't the last chunk, try to break at a sentence boundary
            if end < len(text):
                # Look for sentence endings within the last 200 characters
                search_start = max(start + chunk_size - 200, start)
                search_text = text[search_start:end]
                
                # Find the last sentence ending
                sentence_endings = ['. ', '! ', '? ', '\n\n']
                last_break = -1
                
                for ending in sentence_endings:
                    pos = search_text.rfind(ending)
                    if pos != -1:
                        last_break = max(last_break, pos + len(ending))
                
                if last_break != -1:
                    end = search_start + last_break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position, accounting for overlap
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        try:
            embeddings = self.embedding_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    def process_html_file(self, file_path: Path) -> Tuple[List[Dict], List[Dict]]:
        """Process a single HTML file and return HTML and text chunks with metadata."""
        try:
            # Read HTML file
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Extract filename without extension
            filename = file_path.stem
            
            # Extract text from HTML
            text_content = self.extract_text_from_html(html_content)
            
            # Chunk the content
            html_chunks = self.chunk_text(html_content, self.html_chunk_size, self.html_overlap)
            text_chunks = self.chunk_text(text_content, self.text_chunk_size, self.text_overlap)
            
            # Prepare HTML chunks
            html_points = []
            for i, chunk in enumerate(html_chunks):
                chunk_id = f"{filename}_html_{i}"
                html_points.append({
                    'id': chunk_id,
                    'content': chunk,
                    'filename': filename,
                    'chunk_index': i,
                    'total_chunks': len(html_chunks),
                    'content_type': 'html',
                    'chunk_size': len(chunk),
                    'processed_at': datetime.now().isoformat()
                })
            
            # Prepare text chunks
            text_points = []
            for i, chunk in enumerate(text_chunks):
                chunk_id = f"{filename}_text_{i}"
                text_points.append({
                    'id': chunk_id,
                    'content': chunk,
                    'filename': filename,
                    'chunk_index': i,
                    'total_chunks': len(text_chunks),
                    'content_type': 'text',
                    'chunk_size': len(chunk),
                    'processed_at': datetime.now().isoformat()
                })
            
            logger.info(f"Processed {file_path.name}: {len(html_chunks)} HTML chunks, {len(text_chunks)} text chunks")
            return html_points, text_points
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return [], []

    def ingest_to_elasticsearch(self, html_points: List[Dict], text_points: List[Dict]) -> Dict[str, int]:
        """Ingest points into Elasticsearch indices."""
        results = {'html_ingested': 0, 'text_ingested': 0, 'html_errors': 0, 'text_errors': 0}
        
        # Ingest HTML chunks
        if html_points:
            try:
                # Generate embeddings for HTML chunks
                html_contents = [point['content'] for point in html_points]
                html_embeddings = self.generate_embeddings(html_contents)
                
                if html_embeddings:
                    # Prepare documents for bulk indexing
                    html_docs = []
                    for i, point in enumerate(html_points):
                        doc = {
                            '_index': self.html_index,
                            '_id': point['id'],
                            '_source': {
                                'content': point['content'],
                                'filename': point['filename'],
                                'chunk_index': point['chunk_index'],
                                'total_chunks': point['total_chunks'],
                                'content_type': point['content_type'],
                                'chunk_size': point['chunk_size'],
                                'processed_at': point['processed_at'],
                                'content_vector': html_embeddings[i]
                            }
                        }
                        html_docs.append(doc)
                    
                    # Bulk index HTML documents
                    success, failed = bulk(self.es_client, html_docs, refresh=True)
                    results['html_ingested'] = success
                    results['html_errors'] = failed
                    logger.info(f"Ingested {success} HTML chunks, {failed} failed")
                else:
                    results['html_errors'] = len(html_points)
                    
            except Exception as e:
                logger.error(f"Error ingesting HTML chunks: {e}")
                results['html_errors'] = len(html_points)
        
        # Ingest text chunks
        if text_points:
            try:
                # Generate embeddings for text chunks
                text_contents = [point['content'] for point in text_points]
                text_embeddings = self.generate_embeddings(text_contents)
                
                if text_embeddings:
                    # Prepare documents for bulk indexing
                    text_docs = []
                    for i, point in enumerate(text_points):
                        doc = {
                            '_index': self.text_index,
                            '_id': point['id'],
                            '_source': {
                                'content': point['content'],
                                'filename': point['filename'],
                                'chunk_index': point['chunk_index'],
                                'total_chunks': point['total_chunks'],
                                'content_type': point['content_type'],
                                'chunk_size': point['chunk_size'],
                                'processed_at': point['processed_at'],
                                'content_vector': text_embeddings[i]
                            }
                        }
                        text_docs.append(doc)
                    
                    # Bulk index text documents
                    success, failed = bulk(self.es_client, text_docs, refresh=True)
                    results['text_ingested'] = success
                    results['text_errors'] = failed
                    logger.info(f"Ingested {success} text chunks, {failed} failed")
                else:
                    results['text_errors'] = len(text_points)
                    
            except Exception as e:
                logger.error(f"Error ingesting text chunks: {e}")
                results['text_errors'] = len(text_points)
        
        return results

    def run_ingestion(self, html_dir: str = "calls_htmls", max_files: int = None) -> Dict[str, Any]:
        """Run the complete ingestion process."""
        logger.info("Starting HTML ingestion process to Elasticsearch...")
        
        # Check Elasticsearch connection
        try:
            if not self.es_client.ping():
                raise ConnectionError("Cannot connect to Elasticsearch")
            logger.info("Connected to Elasticsearch successfully")
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            raise
        
        # Create indices
        self.create_indices()
        
        # Find HTML files
        html_path = Path(html_dir)
        if not html_path.exists():
            raise FileNotFoundError(f"Directory {html_dir} not found")
        
        html_files = list(html_path.glob("*.html"))
        if max_files:
            html_files = html_files[:max_files]
        
        logger.info(f"Found {len(html_files)} HTML files to process")
        
        # Process files
        total_results = {
            'files_processed': 0,
            'html_ingested': 0,
            'text_ingested': 0,
            'html_errors': 0,
            'text_errors': 0,
            'processing_errors': 0
        }
        
        for i, html_file in enumerate(html_files, 1):
            logger.info(f"Processing file {i}/{len(html_files)}: {html_file.name}")
            
            try:
                # Process the file
                html_points, text_points = self.process_html_file(html_file)
                
                # Ingest to Elasticsearch
                results = self.ingest_to_elasticsearch(html_points, text_points)
                
                # Update totals
                total_results['files_processed'] += 1
                total_results['html_ingested'] += results['html_ingested']
                total_results['text_ingested'] += results['text_ingested']
                total_results['html_errors'] += results['html_errors']
                total_results['text_errors'] += results['text_errors']
                
            except Exception as e:
                logger.error(f"Error processing {html_file.name}: {e}")
                total_results['processing_errors'] += 1
        
        # Log final results
        logger.info("Ingestion completed!")
        logger.info(f"Files processed: {total_results['files_processed']}")
        logger.info(f"HTML chunks ingested: {total_results['html_ingested']}")
        logger.info(f"Text chunks ingested: {total_results['text_ingested']}")
        logger.info(f"HTML errors: {total_results['html_errors']}")
        logger.info(f"Text errors: {total_results['text_errors']}")
        logger.info(f"Processing errors: {total_results['processing_errors']}")
        
        return total_results

def main():
    """Main function to run the ingestion."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest HTML files into Elasticsearch")
    parser.add_argument("--html-dir", default="calls_htmls", help="Directory containing HTML files")
    parser.add_argument("--max-files", type=int, help="Maximum number of files to process")
    parser.add_argument(
        "--elasticsearch-url",
        default=None,
        help="Elasticsearch URL (overrides ELASTICSEARCH_URL from environment; credentials still from env)",
    )

    args = parser.parse_args()
    
    try:
        # Initialize manager
        manager = HTMLIngestionManager(elasticsearch_url=args.elasticsearch_url)
        
        # Run ingestion
        results = manager.run_ingestion(
            html_dir=args.html_dir,
            max_files=args.max_files
        )
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"elasticsearch_ingestion_results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 