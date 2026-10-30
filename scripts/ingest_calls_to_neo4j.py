#!/usr/bin/env python3
"""
Script to ingest call details from calls_details.json into Neo4j as Call nodes.
"""

import json
import logging
import os
import sys
import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()


def resolve_neo4j_credentials() -> Tuple[str, str, Optional[str]]:
    """
    Resolve Neo4j URI, user and password (same contract as ingest_data.py).

    Supports:
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    - NEO4J_AUTH=username/password (Docker; password is after first '/')
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


def open_neo4j_driver():
    """Return a Neo4j driver using resolved env auth, or raise ValueError if password is missing."""
    neo4j_uri, neo4j_user, neo4j_password = resolve_neo4j_credentials()
    if not neo4j_password:
        raise ValueError(
            "Neo4j password not set. Set NEO4J_PASSWORD or NEO4J_AUTH=user/password"
        )
    return GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password),
        database="neo4j",
    )

def sanitize_property_value(value):
    """Sanitize property values for Neo4j."""
    if value is None:
        return None
    
    # Convert to string if it's not already
    if not isinstance(value, str):
        value = str(value)
    
    # Remove or replace problematic characters
    # Neo4j doesn't like certain characters in property values
    value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    
    # Limit length to avoid Neo4j property size limits
    if len(value) > 10000:
        value = value[:10000] + "..."
    
    return value

def extract_call_id_from_url(url):
    """Extract a unique call ID from the URL."""
    try:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        
        # Look for call ID in the path
        for part in path_parts:
            if part and ('-' in part or '_' in part):
                return part
        
        # If no clear ID found, use the last part
        if path_parts:
            return path_parts[-1]
        
        # Fallback to a hash of the URL
        return str(hash(url))[-10:]
    except:
        return str(hash(url))[-10:]

def generate_unique_id(call_data):
    """Generate a unique ID for the call node."""
    # Try to extract from URL first
    call_id = extract_call_id_from_url(call_data.get('url', ''))
    
    # If we have a title, combine it with the call_id for uniqueness
    title = call_data.get('title', '')
    if title:
        # Create a hash from title and call_id to ensure uniqueness
        combined = f"{call_id}_{title}"
        # Use hash and take last 12 characters for a reasonable length
        unique_id = str(hash(combined))[-12:]
        return f"CALL_{call_id}_{unique_id}"
    else:
        # Fallback if no title
        return f"CALL_{call_id}_{str(hash(call_data.get('url', '')))[-8:]}"

def prepare_call_properties(call_data):
    """Prepare call data for Neo4j ingestion."""
    properties = {}
    
    # Basic properties
    basic_fields = [
        'url', 'title', 'programme', 'call', 'type_of_action', 'type_of_mga',
        'deadline_model', 'planned_opening_date', 'deadline_date', 'budget'
    ]
    
    for field in basic_fields:
        if field in call_data and call_data[field]:
            properties[field] = sanitize_property_value(call_data[field])
    
    # Handle text fields that might be long
    text_fields = ['topic_description', 'topic_destination']
    for field in text_fields:
        if field in call_data and call_data[field]:
            # Truncate very long text fields
            text = call_data[field]
            if len(text) > 5000:
                text = text[:5000] + "..."
            properties[field] = sanitize_property_value(text)
    
    # Handle arrays/lists
    if 'conditions' in call_data and call_data['conditions']:
        # Join conditions into a single string
        conditions_text = "; ".join(call_data['conditions'])
        properties['conditions'] = sanitize_property_value(conditions_text)
    
    # Handle documents (count and first few)
    if 'documents' in call_data and call_data['documents']:
        properties['document_count'] = len(call_data['documents'])
        # Store first few document titles
        doc_titles = [doc.get('text', '') for doc in call_data['documents'][:3]]
        properties['documents'] = sanitize_property_value("; ".join(doc_titles))
    
    # Handle partner search announcements
    if 'partner_search_announcements' in call_data and call_data['partner_search_announcements']:
        properties['partner_search_count'] = len(call_data['partner_search_announcements'])
    
    # Handle QA links
    if 'qa_links' in call_data and call_data['qa_links']:
        properties['qa_links_count'] = len(call_data['qa_links'])
    
    # Add metadata
    properties['ingested_at'] = datetime.now().isoformat()
    properties['call_id'] = extract_call_id_from_url(call_data.get('url', ''))
    properties['id'] = generate_unique_id(call_data)
    
    return properties

def create_call_node(session, call_data):
    """Create a Call node in Neo4j."""
    try:
        properties = prepare_call_properties(call_data)
        
        # Create the Call node using the unique ID
        query = """
        MERGE (c:Call {id: $id})
        SET c += $properties
        RETURN c
        """
        
        result = session.run(query, id=properties['id'], properties=properties)
        record = result.single()
        
        if record:
            return {
                'success': True,
                'node_id': record['c'].element_id,
                'properties': properties
            }
        else:
            return {
                'success': False,
                'error': 'No node created'
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def ingest_single_call(call_data):
    """Ingest a single call into Neo4j."""
    try:
        driver = open_neo4j_driver()
        with driver.session() as session:
            return create_call_node(session, call_data)
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        if 'driver' in locals():
            driver.close()

def check_existing_calls(session):
    """Check how many Call nodes already exist."""
    try:
        result = session.run("MATCH (c:Call) RETURN count(c) as count")
        record = result.single()
        return record['count'] if record else 0
    except Exception as e:
        logger.error(f"Error checking existing calls: {e}")
        return 0

def ingest_calls_from_file(calls_file, max_calls=None, skip_existing=True):
    """Ingest calls from JSON file into Neo4j."""
    print(f"Starting call ingestion from {calls_file}")
    
    # Load calls data
    try:
        with open(calls_file, 'r', encoding='utf-8') as f:
            calls_data = json.load(f)
    except Exception as e:
        print(f"Error loading calls file: {e}")
        return
    
    if not calls_data:
        print("No calls found in the file")
        return
    
    print(f"Found {len(calls_data)} calls in file")
    
    # Limit number of calls if specified
    if max_calls:
        calls_data = calls_data[:max_calls]
        print(f"Limited to {max_calls} calls")
    
    # Setup Neo4j connection
    try:
        driver = open_neo4j_driver()
    except ValueError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        return
    
    try:
        with driver.session() as session:
            # Check existing calls
            existing_count = check_existing_calls(session)
            print(f"Found {existing_count} existing Call nodes in database")
            
            # Filter out existing calls if requested
            if skip_existing and existing_count > 0:
                # Get existing IDs
                result = session.run("MATCH (c:Call) RETURN c.id as id")
                existing_ids = {record['id'] for record in result}
                
                original_count = len(calls_data)
                # Generate IDs for all calls to check for duplicates
                calls_with_ids = []
                for call in calls_data:
                    call_id = generate_unique_id(call)
                    if call_id not in existing_ids:
                        calls_with_ids.append(call)
                    else:
                        print(f"Skipping existing call: {call.get('title', 'Unknown')} (ID: {call_id})")
                
                calls_data = calls_with_ids
                skipped_count = original_count - len(calls_data)
                
                if skipped_count > 0:
                    print(f"Skipped {skipped_count} existing calls")
            
            if not calls_data:
                print("No new calls to ingest")
                return
            
            print(f"Processing {len(calls_data)} calls...")
            
            # Process calls with progress bar
            successful = 0
            failed = 0
            results = []
            
            pbar = tqdm(calls_data, desc="Ingesting calls", unit="call")
            
            for call_data in pbar:
                # Update progress bar description
                title = call_data.get('title', 'Unknown')
                short_title = title[:30] + "..." if len(title) > 30 else title
                pbar.set_description(f"Ingesting: {short_title}")
                
                # Ingest the call
                result = create_call_node(session, call_data)
                results.append({
                    'title': title,
                    'url': call_data.get('url'),
                    'success': result['success'],
                    'error': result.get('error')
                })
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
                    logger.warning(f"Failed to ingest {title}: {result.get('error')}")
            
            # Print summary
            print(f"\nIngestion completed!")
            print(f"  Successful: {successful}")
            print(f"  Failed: {failed}")
            print(f"  Total processed: {len(results)}")
            
            # Save results to file
            results_file = f"ingestion_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Results saved to: {results_file}")
            
    except Exception as e:
        print(f"Error during ingestion: {e}")
    finally:
        driver.close()

def create_indexes():
    """Create indexes for better query performance."""
    try:
        driver = open_neo4j_driver()
        with driver.session() as session:
            # Create indexes
            indexes = [
                "CREATE INDEX call_id_index IF NOT EXISTS FOR (c:Call) ON (c.id)",
                "CREATE INDEX call_url_index IF NOT EXISTS FOR (c:Call) ON (c.url)",
                "CREATE INDEX call_title_index IF NOT EXISTS FOR (c:Call) ON (c.title)",
                "CREATE INDEX call_programme_index IF NOT EXISTS FOR (c:Call) ON (c.programme)",
                "CREATE INDEX call_call_id_index IF NOT EXISTS FOR (c:Call) ON (c.call_id)"
            ]
            
            for index_query in indexes:
                try:
                    session.run(index_query)
                    print(f"✓ Created index: {index_query}")
                except Exception as e:
                    print(f"⚠️  Index creation warning: {e}")
                    
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error creating indexes: {e}")
    finally:
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_calls_to_neo4j.py <calls_details_file> [max_calls] [--no-skip-existing]")
        print("Example: python ingest_calls_to_neo4j.py calls_details.json 10")
        sys.exit(1)
    
    calls_file = sys.argv[1]
    max_calls = int(sys.argv[2]) if len(sys.argv) > 2 else None
    skip_existing = '--no-skip-existing' not in sys.argv
    
    # Create indexes first
    print("Creating database indexes...")
    create_indexes()
    
    # Ingest calls
    ingest_calls_from_file(calls_file, max_calls, skip_existing) 
