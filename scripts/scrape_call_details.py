#!/usr/bin/env python3
"""
Extract topic/call details for the Funding & Tenders portal.

Primary path: EC SEDIA Search API (same backend as the portal) — full structured
fields without relying on Shadow DOM.

Fallback: Selenium page scrape (legacy) when the API returns no hit.

Usage:
  python scrape_call_details.py calls_links.json calls_details.json
  python scrape_call_details.py calls_links.json calls_details.json --selenium-only
"""

import html
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from selenium import webdriver
from tqdm import tqdm
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SEDIA_SEARCH_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"

_FRAMEWORK_NAMES = {
    "43108390": "Horizon Europe (HORIZON)",
    "43108391": "Digital Europe Programme (DIGITAL)",
    "664087": "Connecting Europe Facility (CEF)",
}

_MONTH_EN = (
    "January February March April May June July August September October November December"
).split()


def _strip_html(html: Optional[str]) -> str:
    if not html or not isinstance(html, str):
        return ""
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _meta_first(md: dict, key: str, default: Optional[str] = None) -> Optional[str]:
    if not md or key not in md:
        return default
    v = md[key]
    if isinstance(v, list) and v:
        x = v[0]
        return str(x) if x is not None else default
    if v is None:
        return default
    return str(v)


def _format_date_iso(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    try:
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return f"{dt.day} {_MONTH_EN[dt.month - 1]} {dt.year}"
    except Exception:
        return iso


def _extract_document_links_from_html(*chunks: Optional[str]) -> list:
    out: list = []
    seen = set()
    pat = re.compile(
        r'href="(https?://[^"]+\.(?:pdf|docx?|xlsx?|zip)(?:\?[^"]*)?)"',
        re.IGNORECASE,
    )
    for html in chunks:
        if not html:
            continue
        for m in pat.finditer(html):
            u = m.group(1)
            if u not in seen:
                seen.add(u)
                short = u.split("/")[-1][:120]
                out.append({"text": short, "url": u})
    return out


def _topic_identifier_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    m = re.search(
        r"/(?:topic-details|call-details)/([^/?#]+)/?", url, re.IGNORECASE
    )
    return m.group(1) if m else None


def query_sedia_topic_record(url: str) -> Optional[tuple[dict[str, Any], dict[str, Any]]]:
    """
    Fetch first SEDIA hit for topic/call URL. Returns (result_row, metadata_dict) or None.
    Shared by structured JSON export and HTML export.
    """
    topic_id = _topic_identifier_from_url(url)
    if not topic_id:
        return None

    query = {
        "bool": {
            "must": [
                {"terms": {"status": ["31094501", "31094502"]}},
                {"term": {"programmePeriod": "2021 - 2027"}},
            ]
        }
    }
    languages = ["en"]
    sort = {"field": "startDate", "order": "DESC"}

    try:
        r = requests.post(
            SEDIA_SEARCH_URL,
            params={
                "apiKey": "SEDIA",
                "text": f'"{topic_id}"',
                "pageSize": "5",
                "pageNumber": "1",
            },
            files={
                "query": ("blob", json.dumps(query), "application/json"),
                "languages": ("blob", json.dumps(languages), "application/json"),
                "sort": ("blob", json.dumps(sort), "application/json"),
            },
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("SEDIA request failed for %s: %s", topic_id, e)
        return None

    results = data.get("results") or []
    if data.get("totalResults", 0) < 1 or not results:
        logger.warning("SEDIA: no hit for quoted topic id %s", topic_id)
        return None

    res = results[0]
    md = res.get("metadata") or {}
    ident = _meta_first(md, "identifier") or ""
    if ident and ident != topic_id:
        for cand in results:
            cimd = cand.get("metadata") or {}
            if _meta_first(cimd, "identifier") == topic_id:
                res = cand
                md = cimd
                break

    return (res, md)


def build_topic_html_from_sedia(
    url: str, fallback_title: Optional[str] = None
) -> Optional[str]:
    """
    Build a self-contained HTML document from SEDIA metadata (rich text where available).
    Used when saving call/topic pages without relying on Shadow DOM rendering.
    """
    rec = query_sedia_topic_record(url)
    if not rec:
        return None
    res, md = rec
    title = fallback_title or _meta_first(md, "title") or res.get("content") or "Topic"
    esc = html.escape

    def section(h2: str, body: Optional[str]) -> str:
        if not body or not str(body).strip():
            return ""
        return (
            f'<section class="fts-sedia"><h2>{esc(h2)}</h2>'
            f'<div class="fts-body">{body}</div></section>'
        )

    parts: list[str] = []
    parts.append(
        f'<header class="fts-sedia-header"><h1>{esc(title)}</h1>'
        f'<p class="source-url"><a href="{esc(url)}">{esc(url)}</a></p>'
        f'<p><strong>Identifier:</strong> <code>{esc(_meta_first(md, "identifier") or "")}</code></p>'
        "</header>"
    )

    summary_dl = []
    for label, key in (
        ("Programme", "frameworkProgramme"),
        ("Call", "callIdentifier"),
        ("Call title", "callTitle"),
        ("Type of action", "typesOfAction"),
        ("Deadline model", "deadlineModel"),
        ("Start date", "startDate"),
        ("Deadline", "deadlineDate"),
    ):
        val = _meta_first(md, key)
        if val:
            summary_dl.append(f"<dt>{esc(label)}</dt><dd>{esc(val)}</dd>")
    if summary_dl:
        parts.append(f'<dl class="fts-meta">{"".join(summary_dl)}</dl>')

    parts.append(section("Topic description", _meta_first(md, "descriptionByte")))
    parts.append(
        section("Destination", _meta_first(md, "destinationDetails"))
        or section(
            "Destination (short)",
            _meta_first(md, "destinationDescription"),
        )
    )
    parts.append(section("Conditions and eligibility", _meta_first(md, "topicConditions")))
    parts.append(section("Latest information", _meta_first(md, "latestInfos")))
    parts.append(section("Support", _meta_first(md, "supportInfo")))

    bo = _meta_first(md, "budgetOverview")
    if bo:
        try:
            pretty = json.dumps(json.loads(bo), indent=2, ensure_ascii=False)
            parts.append(
                f'<section class="fts-sedia"><h2>Budget overview</h2>'
                f'<pre class="fts-json">{esc(pretty)}</pre></section>'
            )
        except Exception:
            parts.append(
                f'<section class="fts-sedia"><h2>Budget overview</h2>'
                f'<pre class="fts-json">{esc(bo[:50000])}</pre></section>'
            )

    main = "\n".join(p for p in parts if p)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{esc(title)}</title>
  <meta name="generator" content="MAPIT build_topic_html_from_sedia"/>
</head>
<body>
<main>
{main}
</main>
</body>
</html>
"""


def fetch_call_details_from_sedia(
    url: str, fallback_title: Optional[str] = None
) -> Optional[dict[str, Any]]:
    """
    Load topic/call details from the same SEDIA Search API the portal uses.
    Avoids Shadow DOM — fields are populated from structured metadata.
    """
    rec = query_sedia_topic_record(url)
    if not rec:
        return None
    res, md = rec

    title = fallback_title or _meta_first(md, "title") or res.get("content") or "No title"
    fp_code = _meta_first(md, "frameworkProgramme")
    programme = _FRAMEWORK_NAMES.get(fp_code or "", fp_code)

    call_id = _meta_first(md, "callIdentifier") or ""
    call_title = _meta_first(md, "callTitle") or ""
    call_field = " — ".join(p for p in [call_id, call_title] if p).strip() or None

    mga_code = _meta_first(md, "typeOfMGAs")
    mga_label = f"Model grant agreement id {mga_code}" if mga_code else None

    deadline_model = _meta_first(md, "deadlineModel")
    planned = _format_date_iso(_meta_first(md, "startDate"))
    deadline = _format_date_iso(_meta_first(md, "deadlineDate"))

    desc_html = _meta_first(md, "descriptionByte") or ""
    dest_html = _meta_first(md, "destinationDetails") or ""
    topic_description = _strip_html(desc_html) or None
    topic_destination = _strip_html(dest_html) or _strip_html(_meta_first(md, "destinationDescription") or "")

    cond_html = _meta_first(md, "topicConditions") or ""
    conditions: list = []
    if cond_html:
        chunk = _strip_html(cond_html)
        if len(chunk) > 80:
            conditions.append(chunk)

    budget_raw = _meta_first(md, "budgetOverview")
    budget = None
    if budget_raw:
        try:
            bj = json.loads(budget_raw)
            budget = json.dumps(bj, ensure_ascii=False)[:8000]
        except Exception:
            budget = budget_raw[:8000]

    documents = _extract_document_links_from_html(
        cond_html, desc_html, dest_html
    )
    meta_links = _meta_first(md, "links")
    if meta_links and meta_links not in ("[]", ""):
        try:
            lj = json.loads(meta_links)
            if isinstance(lj, list):
                for item in lj:
                    if isinstance(item, dict) and item.get("url"):
                        documents.append(
                            {
                                "text": item.get("label") or item["url"].split("/")[-1],
                                "url": item["url"],
                            }
                        )
        except json.JSONDecodeError:
            pass

    return {
        "url": url,
        "title": title,
        "programme": programme,
        "call": call_field,
        "type_of_action": _meta_first(md, "typesOfAction"),
        "type_of_mga": mga_label,
        "deadline_model": deadline_model,
        "planned_opening_date": planned,
        "deadline_date": deadline,
        "topic_description": topic_description,
        "topic_destination": topic_destination or None,
        "conditions": conditions,
        "documents": documents,
        "budget": budget,
        "partner_search_announcements": [],
        "qa_links": [],
    }

def setup_driver():
    """Setup and return a configured Chrome driver."""
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    return driver

def close_cookie_banner(driver):
    """Close cookie banner if present."""
    try:
        cookie_buttons = driver.find_elements(By.XPATH, 
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]")
        for btn in cookie_buttons:
            if btn.is_displayed() and btn.is_enabled():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
                break
    except Exception as e:
        pass

def expand_show_more_sections(driver):
    """Click all 'Show more' links to expand sections and get complete information."""
    # Look for "Show more" links and click them
    show_more_selectors = [
        "//button[contains(text(), 'Show more')]",
        "//a[contains(text(), 'Show more')]",
        "//span[contains(text(), 'Show more')]",
        "//*[contains(text(), 'Show more')]"
    ]
    
    for selector in show_more_selectors:
        try:
            show_more_buttons = driver.find_elements(By.XPATH, selector)
            for button in show_more_buttons:
                if button.is_displayed() and button.is_enabled():
                    try:
                        # Scroll to the button
                        driver.execute_script("arguments[0].scrollIntoView(true);", button)
                        time.sleep(1)
                        # Click the button
                        driver.execute_script("arguments[0].click();", button)
                        time.sleep(2)  # Wait for content to load
                    except Exception as e:
                        pass
        except Exception as e:
            pass

def extract_text_by_label(driver, label_text):
    """Extract text that follows a specific label."""
    try:
        # Look for the label and get the next sibling or parent's next sibling
        label_elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{label_text}')]")
        for label_elem in label_elements:
            # Try to get the next sibling
            try:
                next_sibling = label_elem.find_element(By.XPATH, "following-sibling::*[1]")
                if next_sibling.text.strip():
                    return next_sibling.text.strip()
            except:
                pass
            
            # Try to get the parent's next sibling
            try:
                parent = label_elem.find_element(By.XPATH, "..")
                next_sibling = parent.find_element(By.XPATH, "following-sibling::*[1]")
                if next_sibling.text.strip():
                    return next_sibling.text.strip()
            except:
                pass
            
            # Try to get text from the same element if it contains more than just the label
            full_text = label_elem.text.strip()
            if full_text != label_text and len(full_text) > len(label_text):
                # Extract the part after the label
                if label_text in full_text:
                    return full_text.split(label_text, 1)[1].strip()
        
        return None
    except Exception as e:
        logger.debug(f"Error extracting text for label '{label_text}': {e}")
        return None

def extract_call_details_selenium(driver, url, title=None):
    """Extract detailed information from a call details page via browser DOM (legacy)."""
    try:
        driver.get(url)
        time.sleep(5)
        
        # Close cookie banner
        close_cookie_banner(driver)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Expand all "Show more" sections to get complete information
        expand_show_more_sections(driver)
        
        # Initialize result dictionary
        call_details = {
            'url': url,
            'title': title,  # Use the title from the source JSON
            'programme': None,
            'call': None,
            'type_of_action': None,
            'type_of_mga': None,
            'deadline_model': None,
            'planned_opening_date': None,
            'deadline_date': None,
            'topic_description': None,
            'topic_destination': None,
            'conditions': [],
            'documents': [],
            'budget': None,
            'partner_search_announcements': [],
            'qa_links': []
        }
        
        # Extract basic information using more robust selectors
        
        # Programme - look for various programme types including CEF, Horizon Europe, etc.
        programme_keywords = [
            'Horizon Europe', 'HORIZON', 'CEF', 'Connecting Europe Facility', 
            'Digital Europe Programme', 'DIGITAL', 'LIFE', 'Creative Europe',
            'Erasmus+', 'ERASMUS', 'European Innovation Council', 'EIC'
        ]
        
        programme_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in programme_keywords]) + "]")
        
        if programme_elements:
            for elem in programme_elements:
                text = elem.text.strip()
                # Look for the most specific programme match
                for keyword in programme_keywords:
                    if keyword in text:
                        # Try to get the full programme name from the element or its context
                        if len(text) < 100:  # If it's a short text, try to get more context
                            try:
                                parent = elem.find_element(By.XPATH, "..")
                                parent_text = parent.text.strip()
                                if keyword in parent_text and len(parent_text) > len(text):
                                    text = parent_text
                            except:
                                pass
                        
                        # Clean up the programme name
                        if 'Horizon Europe (HORIZON)' in text:
                            call_details['programme'] = 'Horizon Europe (HORIZON)'
                        elif 'CEF' in text and 'Connecting Europe Facility' in text:
                            call_details['programme'] = 'Connecting Europe Facility (CEF)'
                        elif 'CEF' in text:
                            call_details['programme'] = 'Connecting Europe Facility (CEF)'
                        elif 'Digital Europe Programme' in text:
                            call_details['programme'] = 'Digital Europe Programme'
                        else:
                            call_details['programme'] = text
                        break
                if call_details['programme']:
                    break
        
        # Call - look for call titles more broadly
        call_keywords = [
            'MSCA Choose Europe for Science 2025', 'HORIZON-CL5-2026', 'HORIZON-',
            'CEF-DIG-2025', 'CEF-', 'DIGITAL-', 'LIFE-', 'ERASMUS-', 'EIC-'
        ]
        
        call_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in call_keywords]) + "]")
        
        if call_elements:
            for elem in call_elements:
                text = elem.text.strip()
                if any(keyword in text for keyword in call_keywords):
                    call_details['call'] = text
                    break
        
        # Type of action - look for action types more broadly
        action_keywords = [
            'HORIZON-TMA-MSCA-Cofund-P', 'HORIZON-TMA', 'Type of action',
            'Research and Innovation Action', 'Innovation Action', 'Coordination and Support Action',
            'CEF Action', 'Action Grant', 'Grant Agreement'
        ]
        
        action_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in action_keywords]) + "]")
        
        if action_elements:
            for elem in action_elements:
                text = elem.text.strip()
                if any(keyword in text for keyword in action_keywords):
                    call_details['type_of_action'] = text
                    break
        
        # Type of MGA - look for MGA types more broadly
        mga_keywords = ['Type of MGA', 'Model Grant Agreement', 'MGA', 'Grant Agreement']
        mga_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in mga_keywords]) + "]")
        
        if mga_elements:
            for elem in mga_elements:
                try:
                    # Look for the next sibling that contains the actual MGA value
                    next_sibling = elem.find_element(By.XPATH, "following-sibling::*[1]")
                    sibling_text = next_sibling.text.strip()
                    if any(keyword in sibling_text for keyword in ['HORIZON Unit Grant', 'MGA', 'Model Grant Agreement', 'HORIZON-AG-UN', 'CEF', 'Grant Agreement']):
                        call_details['type_of_mga'] = sibling_text
                        break
                except:
                    # Fallback: look for MGA values directly
                    mga_value_keywords = ['HORIZON Unit Grant', 'HORIZON-AG-UN', 'Model Grant Agreement', 'CEF', 'Grant Agreement']
                    mga_value_elements = driver.find_elements(By.XPATH, 
                        "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in mga_value_keywords]) + "]")
                    for value_elem in mga_value_elements:
                        text = value_elem.text.strip()
                        if any(keyword in text for keyword in mga_value_keywords):
                            call_details['type_of_mga'] = text
                            break
        
        # Deadline model - look for "single-stage" or other models
        deadline_model_keywords = ['single-stage', 'two-stage', 'Deadline model', 'Evaluation model']
        deadline_model_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in deadline_model_keywords]) + "]")
        
        if deadline_model_elements:
            for elem in deadline_model_elements:
                text = elem.text.strip()
                if 'single-stage' in text:
                    call_details['deadline_model'] = 'single-stage'
                    break
                elif 'two-stage' in text:
                    call_details['deadline_model'] = 'two-stage'
                    break
                elif 'Deadline model' in text:
                    # Try to extract the model from the same element or next sibling
                    try:
                        if any(model in text for model in ['single-stage', 'two-stage']):
                            if 'single-stage' in text:
                                call_details['deadline_model'] = 'single-stage'
                            elif 'two-stage' in text:
                                call_details['deadline_model'] = 'two-stage'
                        else:
                            # Try next sibling
                            next_sibling = elem.find_element(By.XPATH, "following-sibling::*[1]")
                            sibling_text = next_sibling.text.strip()
                            if 'single-stage' in sibling_text:
                                call_details['deadline_model'] = 'single-stage'
                            elif 'two-stage' in sibling_text:
                                call_details['deadline_model'] = 'two-stage'
                    except:
                        pass
        
        # Dates - improved extraction for both "Planned opening date" and "Opening date"
        date_keywords = [
            'Planned opening date', 'Opening date', 'Deadline date', 'Deadline',
            'opening', 'deadline', 'Call opening', 'Call deadline'
        ]
        date_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in date_keywords]) + "]")
        
        for elem in date_elements:
            text = elem.text.strip()
            
            # Look for opening dates (both "Planned opening date" and "Opening date")
            if any(keyword in text for keyword in ['Planned opening date', 'Opening date', 'Call opening']):
                # Try to extract the date from the same element or next sibling
                try:
                    # Check if the date is in the same element
                    if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']) and any(year in text for year in ['2025', '2026', '2027']):
                        # Extract just the date part
                        date_match = re.search(r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+202[567]', text)
                        if date_match:
                            call_details['planned_opening_date'] = date_match.group()
                    else:
                        # Try next sibling
                        next_sibling = elem.find_element(By.XPATH, "following-sibling::*[1]")
                        sibling_text = next_sibling.text.strip()
                        if any(month in sibling_text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']) and any(year in sibling_text for year in ['2025', '2026', '2027']):
                            call_details['planned_opening_date'] = sibling_text
                except:
                    pass
            
            # Look for deadline dates
            if any(keyword in text for keyword in ['Deadline date', 'Deadline', 'Call deadline']):
                # Try to extract the date from the same element or next sibling
                try:
                    # Check if the date is in the same element
                    if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']) and any(year in text for year in ['2025', '2026', '2027']):
                        # Extract just the date part
                        date_match = re.search(r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+202[567](?:\s+\d{1,2}:\d{2}:\d{2}\s+Brussels time)?', text)
                        if date_match:
                            call_details['deadline_date'] = date_match.group()
                    else:
                        # Try next sibling
                        next_sibling = elem.find_element(By.XPATH, "following-sibling::*[1]")
                        sibling_text = next_sibling.text.strip()
                        if any(month in sibling_text for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']) and any(year in sibling_text for year in ['2025', '2026', '2027']):
                            call_details['deadline_date'] = sibling_text
                except:
                    pass
        
        # Extract topic description - robustly capture all relevant text
        desc_texts = []
        desc_keywords = ['Expected Outcome', 'Scope:', 'Description', 'Objective', 'Background']
        desc_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in desc_keywords]) + "]")
        
        for elem in desc_elements:
            # Try to find a common parent section/div with substantial text
            parent = elem
            for _ in range(3):  # Traverse up to 3 levels up
                try:
                    parent = parent.find_element(By.XPATH, "..")
                    parent_text = parent.text.strip()
                    if any(keyword in parent_text for keyword in desc_keywords) and len(parent_text) > 500:
                        desc_texts.append(parent_text)
                        break
                except Exception:
                    break
            else:
                # If no large parent found, collect element and siblings as before
                text = elem.text.strip()
                if text:
                    desc_texts.append(text)
                for i in range(1, 6):
                    try:
                        sib = elem.find_element(By.XPATH, f"following-sibling::*[{i}]")
                        sib_text = sib.text.strip()
                        if sib_text and sib_text not in desc_texts:
                            desc_texts.append(sib_text)
                    except Exception:
                        break
        
        # Fallback: extract all large text blocks from main content area
        if not desc_texts or sum(len(t) for t in desc_texts) < 500:
            main_content_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'content') or contains(@class, 'description') or contains(@class, 'details')]")
            for div in main_content_divs:
                text = div.text.strip()
                if any(keyword in text for keyword in desc_keywords) and len(text) > 500:
                    desc_texts.append(text)
        
        # Join all collected description parts
        if desc_texts:
            full_desc = "\n\n".join(desc_texts)
            if len(full_desc) > 200:
                call_details['topic_description'] = full_desc
        
        # Extract topic destination - look for content with various destination patterns
        dest_keywords = [
            'MSCA Co-funding of regional, national and international programmes',
            'Expected impact', 'Destination', 'Climate, Energy and Mobility',
            'Digital, Industry and Space', 'Health', 'Food, Bioeconomy',
            'Civil Security for Society', 'General', 'CEF', 'Digital Europe'
        ]
        dest_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in dest_keywords]) + "]")
        
        if dest_elements:
            for elem in dest_elements:
                try:
                    parent = elem.find_element(By.XPATH, "..")
                    text = parent.text.strip()
                    if len(text) > 200 and any(keyword in text for keyword in dest_keywords):
                        call_details['topic_destination'] = text
                        break
                except:
                    text = elem.text.strip()
                    if len(text) > 200 and any(keyword in text for keyword in dest_keywords):
                        call_details['topic_destination'] = text
                        break
        
        # Extract documents and links
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute('href')
            text = link.text.strip()
            
            if href:
                # Document links
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xlsx', '.xls']):
                    call_details['documents'].append({
                        'text': text,
                        'url': href
                    })
                
                # Partner search announcements
                if 'partner' in text.lower() or 'announcement' in text.lower():
                    call_details['partner_search_announcements'].append({
                        'text': text,
                        'url': href
                    })
                
                # Q&A links
                if 'q&a' in text.lower() or 'question' in text.lower() or 'answer' in text.lower():
                    call_details['qa_links'].append({
                        'text': text,
                        'url': href
                    })
        
        # Extract budget information
        budget_keywords = ['€', 'EUR', 'budget', 'funding', 'total', 'amount', 'allocation']
        budget_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in budget_keywords]) + "]")
        
        for elem in budget_elements:
            text = elem.text.strip()
            if any(keyword in text.lower() for keyword in budget_keywords) and len(text) > 10:
                call_details['budget'] = text
                break
        
        # Extract conditions
        conditions_keywords = ['condition', 'eligibility', 'requirement', 'criteria', 'admissibility']
        conditions_elements = driver.find_elements(By.XPATH, 
            "//*[" + " or ".join([f"contains(text(), '{kw}')" for kw in conditions_keywords]) + "]")
        
        for elem in conditions_elements:
            text = elem.text.strip()
            if len(text) > 50 and any(keyword in text.lower() for keyword in conditions_keywords):
                call_details['conditions'].append(text)
        
        return call_details
        
    except Exception as e:
        logger.error(f"Error extracting details from {url}: {e}")
        return {
            'url': url,
            'error': str(e),
            'title': title,
            'programme': None,
            'call': None,
            'type_of_action': None,
            'type_of_mga': None,
            'deadline_model': None,
            'planned_opening_date': None,
            'deadline_date': None,
            'topic_description': None,
            'topic_destination': None,
            'conditions': [],
            'documents': [],
            'budget': None,
            'partner_search_announcements': [],
            'qa_links': []
        }

def scrape_call_details(call_links_file, output_file, max_calls=None, use_sedia=True):
    """Scrape detailed information from call links.

    By default uses the EC SEDIA Search API (structured fields, no Shadow DOM issues),
    then falls back to Selenium for URLs the API does not resolve.
    Pass use_sedia=False to use only the legacy browser scraper.
    """
    mode = "SEDIA API (+ Selenium fallback)" if use_sedia else "Selenium only"
    print(f"Starting call details scraping from {call_links_file} [{mode}]")
    
    # Load call links
    try:
        with open(call_links_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle different file structures
            if 'links' in data:
                call_links = data['links']
            else:
                call_links = data
    except Exception as e:
        print(f"Error loading call links file: {e}")
        return
    
    if not call_links:
        print("No call links found in the file")
        return
    
    # Load existing results if output file exists
    existing_results = []
    processed_urls = set()
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_results = json.load(f)
                processed_urls = {result['url'] for result in existing_results if 'url' in result}
                print(f"Found existing results file with {len(existing_results)} calls already processed")
        except Exception as e:
            print(f"Could not load existing results file: {e}")
            existing_results = []
            processed_urls = set()
    
    # Filter out already processed URLs
    remaining_links = []
    for call_link in call_links:
        if isinstance(call_link, dict):
            url = call_link.get('url')
        else:
            url = call_link
        
        if url and url not in processed_urls:
            remaining_links.append(call_link)
    
    print(f"Found {len(remaining_links)} calls remaining to process (out of {len(call_links)} total)")
    
    # Limit number of calls if specified (only for remaining calls)
    if max_calls:
        remaining_links = remaining_links[:max_calls]
        print(f"Limited to {max_calls} remaining calls")
    
    if not remaining_links:
        print("No new calls to process. All calls have been completed.")
        return
    
    driver = None
    try:
        all_call_details = existing_results.copy()

        pbar = tqdm(remaining_links, desc="Scraping calls", unit="call")

        for call_link in pbar:
            if isinstance(call_link, dict):
                url = call_link.get("url")
                title = call_link.get("title", "")
            else:
                url = call_link
                title = ""

            if not url:
                continue

            short_title = title[:50] + "..." if len(title) > 50 else title
            pbar.set_description(f"Scraping: {short_title}")

            call_details = None
            if use_sedia:
                call_details = fetch_call_details_from_sedia(url, title)
            if call_details is None:
                if driver is None:
                    driver = setup_driver()
                call_details = extract_call_details_selenium(driver, url, title)
                time.sleep(2)
            else:
                time.sleep(0.15)

            all_call_details.append(call_details)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_call_details, f, indent=2, ensure_ascii=False)

        print(f"\nScraping completed! Results saved to {output_file}")

    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        if driver is not None:
            driver.quit()

if __name__ == "__main__":
    import sys

    raw = sys.argv[1:]
    selenium_only = "--selenium-only" in raw
    raw = [a for a in raw if a != "--selenium-only"]

    if len(raw) < 2:
        print(
            "Usage: python scrape_call_details.py <call_links_file> <output_file> [max_calls] [--selenium-only]"
        )
        print(
            "  Default: SEDIA Search API (fast, structured), then browser fallback if needed."
        )
        print(
            "  --selenium-only : only legacy DOM scraping (slower, often incomplete)."
        )
        print("Example: python scrape_call_details.py call_links.json call_details.json 10")
        sys.exit(1)

    call_links_file = raw[0]
    output_file = raw[1]
    max_calls = int(raw[2]) if len(raw) > 2 else None

    scrape_call_details(
        call_links_file, output_file, max_calls, use_sedia=not selenium_only
    ) 