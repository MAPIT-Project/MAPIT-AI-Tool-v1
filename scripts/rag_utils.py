#!/usr/bin/env python3
"""
Utility functions for RAG (Retrieval-Augmented Generation) operations
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import os

@dataclass
class DocumentSource:
    """Represents a document source with metadata for RAG systems"""
    document_id: str
    filename: str
    document_link: str
    source_type: str
    chunk_index: int = 0
    total_chunks: int = 1
    page_count: int = 0
    file_size: int = 0
    ingested_at: str = ""

def extract_document_sources_from_chunks(chunks_with_scores: List[tuple]) -> List[DocumentSource]:
    """
    Extract document source information from retrieved chunks
    
    Args:
        chunks_with_scores: List of tuples (chunk_text, metadata, score)
    
    Returns:
        List of DocumentSource objects with document information
    """
    document_sources = []
    
    for chunk_text, metadata, score in chunks_with_scores:
        source = DocumentSource(
            document_id=metadata.get('document_id', 'unknown'),
            filename=metadata.get('filename', 'unknown'),
            document_link=metadata.get('document_link', ''),
            source_type=metadata.get('type', 'unknown'),
            chunk_index=metadata.get('chunk_index', 0),
            total_chunks=metadata.get('total_chunks', 1),
            page_count=metadata.get('page_count', 0),
            file_size=metadata.get('file_size', 0),
            ingested_at=metadata.get('ingested_at', '')
        )
        document_sources.append(source)
    
    return document_sources

def format_document_citations(chunks_with_scores: List[tuple]) -> str:
    """
    Format document citations for LLM responses
    
    Args:
        chunks_with_scores: List of tuples (chunk_text, metadata, score)
    
    Returns:
        Formatted string with document citations
    """
    if not chunks_with_scores:
        return ""
    
    citations = []
    seen_documents = set()
    
    for chunk_text, metadata, score in chunks_with_scores:
        doc_id = metadata.get('document_id', 'unknown')
        
        if doc_id not in seen_documents:
            filename = metadata.get('filename', 'Unknown Document')
            source_type = metadata.get('type', 'unknown')
            chunk_info = ""
            
            if metadata.get('total_chunks', 1) > 1:
                chunk_info = f" (chunk {metadata.get('chunk_index', 0) + 1}/{metadata.get('total_chunks', 1)})"
            
            citation = f"- {filename} ({source_type}){chunk_info}"
            citations.append(citation)
            seen_documents.add(doc_id)
    
    if citations:
        return "\n\n**Sources:**\n" + "\n".join(citations)
    
    return ""

def create_llm_prompt_with_sources(query: str, chunks_with_scores: List[tuple], 
                                  include_sources: bool = True) -> str:
    """
    Create a prompt for the LLM that includes source information
    
    Args:
        query: User's question
        chunks_with_scores: Retrieved chunks with metadata and scores
        include_sources: Whether to include source citations
    
    Returns:
        Formatted prompt for the LLM
    """
    # Extract context from chunks
    context_parts = []
    for chunk_text, metadata, score in chunks_with_scores:
        source_info = f"[Source: {metadata.get('filename', 'Unknown')}]"
        context_parts.append(f"{source_info}\n{chunk_text}")
    
    context = "\n\n".join(context_parts)
    
    # Create the prompt
    prompt = f"""Based on the following information, please answer the user's question. 
If you cannot answer the question based on the provided information, please say so.

Context:
{context}

Question: {query}

Answer:"""
    
    if include_sources:
        sources = format_document_citations(chunks_with_scores)
        prompt += sources
    
    return prompt

def get_document_links(chunks_with_scores: List[tuple]) -> List[str]:
    """
    Extract document links from retrieved chunks
    
    Args:
        chunks_with_scores: List of tuples (chunk_text, metadata, score)
    
    Returns:
        List of document links
    """
    links = []
    seen_links = set()
    
    for chunk_text, metadata, score in chunks_with_scores:
        link = metadata.get('document_link', '')
        if link and link not in seen_links:
            links.append(link)
            seen_links.add(link)
    
    return links

def validate_document_access(metadata: Dict[str, Any]) -> bool:
    """
    Check if a document is accessible based on its metadata
    
    Args:
        metadata: Document metadata
    
    Returns:
        True if document is accessible, False otherwise
    """
    file_path = metadata.get('file_path', '')
    if file_path and os.path.exists(file_path):
        return True
    
    # For CORDIS projects, they're always accessible
    if metadata.get('type') == 'project':
        return True
    
    return False

def format_source_summary(chunks_with_scores: List[tuple]) -> str:
    """
    Create a summary of sources used in the response
    
    Args:
        chunks_with_scores: List of tuples (chunk_text, metadata, score)
    
    Returns:
        Formatted summary of sources
    """
    if not chunks_with_scores:
        return "No sources were used to generate this response."
    
    # Group by document type
    by_type = {}
    for chunk_text, metadata, score in chunks_with_scores:
        doc_type = metadata.get('type', 'unknown')
        if doc_type not in by_type:
            by_type[doc_type] = []
        by_type[doc_type].append(metadata.get('filename', 'Unknown'))
    
    summary_parts = []
    for doc_type, filenames in by_type.items():
        unique_files = list(set(filenames))
        summary_parts.append(f"{doc_type.capitalize()} documents: {', '.join(unique_files[:3])}")
        if len(unique_files) > 3:
            summary_parts[-1] += f" and {len(unique_files) - 3} more"
    
    return "Sources used: " + "; ".join(summary_parts) 