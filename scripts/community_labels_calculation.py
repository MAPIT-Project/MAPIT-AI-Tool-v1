#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate Organization Community Labels with a Local LLM (Ollama)

- Reads distinct communityGlobal IDs from Neo4j
- For each community, aggregates member orgs' projects' titleObjectiveText
- Preprocesses text, extracts top keywords
- Calls local Ollama (e.g., model "llama3.1") to synthesize a concise label
- Writes the resulting label to all orgs in that community (communityLabelGlobal)
- Shows progress with tqdm

Requirements:
  pip install neo4j requests tqdm

Ollama:
  - Default endpoint: http://localhost:11434
  - Start Ollama and pull a model, e.g.: ollama pull llama3.1
"""

import os
from dotenv import load_dotenv
load_dotenv()
import re
import math
import json
import time
import html
import string
import logging
from collections import Counter
from typing import List, Dict, Tuple, Optional

import requests
from neo4j import GraphDatabase, basic_auth
from tqdm import tqdm

# ---------------------------
# Configuration (env-first)
# ---------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")  # no trailing slash needed
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Limits & knobs
MAX_PROJECTS_PER_COMMUNITY = int(os.getenv("MAX_PROJECTS_PER_COMMUNITY", "500"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "120000"))  # cap prompt size
TOPK_TERMS = int(os.getenv("TOPK_TERMS", "30"))
MIN_TOKEN_LEN = int(os.getenv("MIN_TOKEN_LEN", "3"))
LABEL_MAX_WORDS = int(os.getenv("LABEL_MAX_WORDS", "6"))  # desired label length (soft)
APOC_CHUNK_WRITE = int(os.getenv("APOC_CHUNK_WRITE", "1000"))  # not used here, but kept for reference

# Logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("community-labels")

# Basic stopwords (extend as needed)
STOPWORDS = set(map(str.lower, [
    "the","and","for","with","from","into","onto","about","between","within","without",
    "across","under","over","of","in","on","to","a","an","by","as","at","is","are","be",
    "this","that","these","those","we","our","their","its","it","you","your","i","they",
    "he","she","them","his","her","was","were","been","being","or","not","can","could",
    "may","might","should","would","will","shall","than","then","there","here","such",
    "also","however","thus","therefore","via","per","each","other","more","most","many",
    "much","some","any","one","two","three","four","five","new","novel","based","using",
    "project","research","study","system","data","analysis","approach","method","result",
    "results","application","applications","technology","technologies","development",
    "evaluation","design","model","models","framework","platform","solution","solutions"
]))

# ---------------------------
# Neo4j access helpers
# ---------------------------
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD))

def fetch_communities(tx) -> List[int]:
    q = """
    MATCH (o:Organization)
    WHERE o.communityGlobal IS NOT NULL
    RETURN DISTINCT o.communityGlobal AS cid
    ORDER BY cid
    """
    return [rec["cid"] for rec in tx.run(q)]

def fetch_title_objective_texts_for_community(tx, cid: int, limit: int) -> List[str]:
    # Aggregate titleObjectiveText (fallback to title + objective) for projects of orgs in the community
    q = """
    MATCH (o:Organization)
    WHERE o.communityGlobal = $cid
    MATCH (o)-[:PARTICIPATES_IN]->(p:Project)
    WITH DISTINCT p, coalesce(p.titleObjectiveText, coalesce(p.title,'') + ' ' + coalesce(p.objective,'')) AS txt
    WHERE txt IS NOT NULL AND txt <> ''
    RETURN txt
    LIMIT $limit
    """
    return [rec["txt"] for rec in tx.run(q, cid=cid, limit=limit)]

def write_label_to_community(tx, cid: int, label: str) -> int:
    q = """
    MATCH (o:Organization)
    WHERE o.communityGlobal = $cid
    SET o.communityLabelGlobal = $label
    RETURN count(o) AS updated
    """
    rec = tx.run(q, cid=cid, label=label).single()
    return int(rec["updated"] if rec else 0)

# ---------------------------
# Text preprocessing
# ---------------------------
PUNCTUATION = set(string.punctuation)

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def strip_non_letters(s: str) -> str:
    # Keep letters, numbers, and spaces
    return re.sub(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿİıĞğŞşÜüÇçÑñĀ-ž\s\-]", " ", s)

def tokenize(text: str) -> List[str]:
    text = normalize_whitespace(strip_non_letters(text.lower()))
    toks = text.split()
    toks = [t.strip("-_") for t in toks]
    # remove stopwords & short tokens & pure digits
    toks = [t for t in toks if len(t) >= MIN_TOKEN_LEN and not t.isdigit() and t not in STOPWORDS]
    return toks

def top_keywords(texts: List[str], k: int) -> List[Tuple[str, int]]:
    counter = Counter()
    for t in texts:
        for tok in tokenize(t):
            counter[tok] += 1
    return counter.most_common(k)

def make_prompt(cid: int, keywords: List[Tuple[str, int]], sample_snippets: List[str]) -> str:
    kw_str = ", ".join([w for w, _ in keywords])
    # use up to 5 short snippets for extra context
    sample_snips = []
    for s in sample_snippets[:5]:
        s = normalize_whitespace(s)
        if len(s) > 240:
            s = s[:240] + "…"
        sample_snips.append(f"- {s}")

    snippets_block = "\n".join(sample_snips) if sample_snips else "- (no snippets available)"

    system_instructions = (
        "You are an expert research analyst. "
        "Given topic keywords and brief project snippets, produce a short, human-friendly label "
        "for this community of organizations. The label should be 2–6 words, title-cased when suitable, "
        "avoid generic words (project, research, study), and reflect the *dominant* theme. "
        "Return only the label text, no quotes, no punctuation at the end."
    )

    user_block = f"""
Community ID: {cid}

Top Keywords:
{kw_str if kw_str else "(none)"}

Sample Project Snippets:
{snippets_block}

Output format: A single short label, 2–6 words, no quotes.
"""

    prompt = f"{system_instructions}\n\n{user_block}"
    return prompt.strip()

# ---------------------------
# LLM (Ollama) call
# ---------------------------
def call_ollama_label(prompt: str,
                      model: str = OLLAMA_MODEL,
                      url: str = OLLAMA_URL,
                      timeout: int = 120) -> str:
    """
    Calls Ollama /api/generate with streaming disabled to get full response at once.
    """
    endpoint = f"{url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Optional controls you may tweak:
        "options": {
            "temperature": 0.3,
            "repeat_penalty": 1.1,
            "num_predict": 64  # short output
        }
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "").strip()
        # Post-process: keep a short, single-line label
        text = normalize_whitespace(text)
        text = text.strip().strip('"').strip("'")
        # Limit words (soft)
        words = text.split()
        if len(words) > LABEL_MAX_WORDS:
            text = " ".join(words[:LABEL_MAX_WORDS])
        # Remove trailing punctuation
        return text.rstrip(".;,:-–—")
    except Exception as e:
        log.error(f"Ollama call failed: {e}")
        return ""  # caller will fallback

# ---------------------------
# Main processing
# ---------------------------
def main():
    log.info("Connecting to Neo4j...")
    drv = get_driver()

    with drv.session() as session:
        log.info("Fetching communities...")
        cids = session.read_transaction(fetch_communities)
        if not cids:
            log.warning("No communities found (communityGlobal is NULL everywhere). Exiting.")
            return

        log.info(f"Found {len(cids)} communities.")

        for cid in tqdm(cids, desc="Communities", unit="comm"):
            try:
                # 1) Fetch raw texts
                texts = session.read_transaction(
                    fetch_title_objective_texts_for_community,
                    cid, MAX_PROJECTS_PER_COMMUNITY
                )
                if not texts:
                    # no data; write fallback label
                    fallback_label = "General"
                    updated = session.write_transaction(write_label_to_community, cid, fallback_label)
                    log.info(f"[cid={cid}] No texts; set label='{fallback_label}' for {updated} org(s).")
                    continue

                # 2) Preprocess & cap size
                # Cap total characters to keep prompt short
                total = 0
                capped_texts = []
                for t in texts:
                    t = normalize_whitespace(t)
                    if total + len(t) <= MAX_TEXT_CHARS:
                        capped_texts.append(t)
                        total += len(t)
                    else:
                        remain = MAX_TEXT_CHARS - total
                        if remain > 200:  # keep a minimum useful slice
                            capped_texts.append(t[:remain])
                            total += remain
                        break

                # 3) Extract top keywords
                kws = top_keywords(capped_texts, TOPK_TERMS)

                # 4) Prepare prompt for Ollama
                prompt = make_prompt(cid, kws, capped_texts)

                # 5) Call LLM
                label = call_ollama_label(prompt)
                if not label:
                    # fallback: synthesize from keywords
                    if kws:
                        label = " / ".join([w for w, _ in kws[:3]])
                    else:
                        label = "General"

                # 6) Write label to all orgs in this community
                updated = session.write_transaction(write_label_to_community, cid, label)
                log.info(f"[cid={cid}] label='{label}' → updated {updated} org(s)")

                # Friendly pacing to avoid overloading local LLM
                time.sleep(0.2)

            except KeyboardInterrupt:
                log.warning("Interrupted by user.")
                break
            except Exception as e:
                log.error(f"[cid={cid}] Error: {e}")
                # Continue with next community

    drv.close()
    log.info("Done.")

if __name__ == "__main__":
    main()
