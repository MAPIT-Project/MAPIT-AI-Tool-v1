import os
from typing import Any, Dict, Optional, Tuple

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from elasticsearch import Elasticsearch


def resolve_neo4j_credentials() -> Tuple[str, str, Optional[str]]:
    """
    Resolve Neo4j URI, user and password.

    Supports:
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (.env style)
    - NEO4J_AUTH=username/password (Docker official image; password is after first '/')
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


def make_neo4j_driver(*, require_password: bool = True) -> Any:
    uri, user, password = resolve_neo4j_credentials()
    if require_password and not password:
        raise ValueError("Neo4j password not set. Set NEO4J_PASSWORD or NEO4J_AUTH=user/password")
    return GraphDatabase.driver(
        uri,
        auth=(user, password) if password else None,
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )


def resolve_qdrant_credentials() -> Tuple[str, Optional[str]]:
    """
    Qdrant URL + optional API key.

    Recognises Docker env QDRANT__SERVICE__API_KEY alongside QDRANT_API_KEY.
    """
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    raw = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT__SERVICE__API_KEY") or ""
    api_key = raw.strip() or None
    return url, api_key


def make_qdrant_client() -> QdrantClient:
    url, api_key = resolve_qdrant_credentials()
    if api_key:
        return QdrantClient(url=url, api_key=api_key)
    return QdrantClient(url=url)


def resolve_elasticsearch_credentials() -> Tuple[str, Optional[str], Optional[str]]:
    """
    Elasticsearch URL and optional basic-auth.

    Supports:
    - ELASTICSEARCH_URL
    - ELASTICSEARCH_USERNAME / ELASTICSEARCH_PASSWORD (legacy)
    - ELASTIC_USER / ELASTIC_PASSWORD (official Docker-style)
    """
    hosts = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    user = os.getenv("ELASTICSEARCH_USERNAME") or os.getenv("ELASTIC_USER")
    password = os.getenv("ELASTICSEARCH_PASSWORD") or os.getenv("ELASTIC_PASSWORD")

    user = user.strip() if user else None
    password = password.strip() if password else None

    if password and not user:
        user = os.getenv("ELASTIC_USERNAME_DEFAULT") or "elastic"

    return hosts, user, password


def make_elasticsearch_client() -> Elasticsearch:
    hosts, user, password = resolve_elasticsearch_credentials()
    es_config: Dict[str, Any] = {"hosts": [hosts], "request_timeout": 60}
    if user and password:
        es_config["basic_auth"] = (user, password)
    elif password and not user:
        es_config["basic_auth"] = ("elastic", password)
    return Elasticsearch(**es_config)

