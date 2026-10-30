import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase
from tqdm import tqdm

# Prefer repo scripts/.env when running from any cwd, then local .env
_repo_root = Path(__file__).resolve().parent.parent
load_dotenv(_repo_root / "scripts" / ".env")
load_dotenv()

headers = {
    "User-Agent": "MAPIT-Script (mailto:tolgaayav@iyte.edu.tr)"
}


def resolve_neo4j_credentials() -> Tuple[str, str, Optional[str]]:
    """
    Neo4j URI, user, password — same contract as ingest_data.py / ingest_calls_to_neo4j.py.

    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD; NEO4J_AUTH=user/password (Docker).
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


def open_neo4j_driver() -> Driver:
    uri, username, password = resolve_neo4j_credentials()
    if not password:
        raise ValueError(
            "Neo4j password not set. Set NEO4J_PASSWORD or NEO4J_AUTH=user/password"
        )
    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        database="neo4j",
    )


def fetch_authors_from_crossref(doi):
    url = f"https://api.crossref.org/works/{doi}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            authors = data.get("message", {}).get("author", [])
            return [{
                "name": f"{a.get('given', '')} {a.get('family', '')}".strip(),
                "orcid": a.get("ORCID", "").replace("https://orcid.org/", "") if a.get("ORCID") else "N/A",
                "affiliation": a.get("affiliation")[0]["name"] if a.get("affiliation") else "N/A"
            } for a in authors]
        elif response.status_code == 429:
            print("Rate limit hit, sleeping for 5 seconds...")
            time.sleep(5)
            return fetch_authors_from_crossref(doi)
    except Exception as e:
        print(f"Error fetching {doi}: {e}")
    return []

def store_authors_in_neo4j(driver: Driver, publication_id, authors):
    with driver.session() as session:
        for author in authors:
            session.run("""
                MERGE (a:PubAuthor {name: $name})
                SET a.orcid = $orcid,
                    a.affiliation = $affiliation
                WITH a
                MATCH (p:Publication {id: $pub_id})
                MERGE (a)-[:AUTHORED]->(p)
            """, {
                "name": author["name"],
                "orcid": author["orcid"],
                "affiliation": author["affiliation"],
                "pub_id": publication_id
            })

def get_all_authors_and_store(driver: Driver):
    with driver.session() as session:
        result = session.run("""
            MATCH (p:Publication)
            WHERE p.doi IS NOT NULL
            RETURN DISTINCT p.doi AS doi, p.id AS id
        """)
        dois = [(record["doi"], record["id"]) for record in result if record["doi"]]

    print("Total publications to process:", len(dois))

    for (doi, pub_id) in tqdm(dois, desc="Processing publications"):
        authors = fetch_authors_from_crossref(doi)
        if authors:
            store_authors_in_neo4j(driver, pub_id, authors)

if __name__ == "__main__":
    try:
        _driver = open_neo4j_driver()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    try:
        get_all_authors_and_store(_driver)
    finally:
        _driver.close()
