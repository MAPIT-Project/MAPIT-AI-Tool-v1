#!/usr/bin/env python3
"""
Save topic/call pages as HTML for downstream Qdrant / Elasticsearch ingestion.

Primary: build HTML from EC SEDIA Search API metadata (same source as
`scrape_call_details.py`) — full topic text without Shadow DOM issues.

Fallback: Selenium renders the live portal page (`save_call_html_selenium`).

Usage:
  python save_call_htmls.py calls_links.json calls_htmls
  python save_call_htmls.py calls_links.json calls_htmls --selenium-only
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from typing import Any, Optional

# Allow `python /path/to/save_call_htmls.py` imports
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager

from scrape_call_details import build_topic_html_from_sedia

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def setup_driver():
    """Chrome with driver version match (webdriver-manager) and current headless mode."""
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)


def close_cookie_banner(driver):
    try:
        cookie_buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        )
        for btn in cookie_buttons:
            if btn.is_displayed() and btn.is_enabled():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)
                break
    except Exception:
        pass


def expand_show_more_sections(driver) -> int:
    show_more_selectors = [
        "//button[contains(text(), 'Show more')]",
        "//a[contains(text(), 'Show more')]",
        "//span[contains(text(), 'Show more')]",
        "//*[contains(text(), 'Show more')]",
    ]
    expanded_count = 0
    for selector in show_more_selectors:
        try:
            show_more_buttons = driver.find_elements(By.XPATH, selector)
            for button in show_more_buttons:
                if button.is_displayed() and button.is_enabled():
                    try:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", button
                        )
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", button)
                        time.sleep(1.5)
                        expanded_count += 1
                    except Exception:
                        pass
        except Exception:
            pass
    return expanded_count


def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    filename = re.sub(r"\s+", "_", filename)
    filename = re.sub(r"\.+", ".", filename)
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def get_filename_from_url(url: str, title: Optional[str] = None) -> str:
    from urllib.parse import urlparse  # local import kept for clarity

    parsed_url = urlparse(url)
    path_parts = [p for p in parsed_url.path.split("/") if p]
    call_id = None
    for part in reversed(path_parts):
        if "topic-details" in part.lower() or "call-details" in part.lower():
            continue
        if part and ("-" in part or "_" in part):
            call_id = part
            break
    if not call_id and path_parts:
        call_id = path_parts[-1]
    if call_id:
        call_id = sanitize_filename(call_id)
    else:
        call_id = "unknown_call"

    if title:
        title_part = sanitize_filename(title)[:120]
        return f"{call_id}_{title_part}.html"
    return f"{call_id}.html"


def save_call_html_selenium(
    driver,
    url: str,
    title: Optional[str] = None,
    output_dir: str = "calls_htmls",
    page_wait: int = 45,
) -> dict[str, Any]:
    """Save rendered page_source after expanding sections (legacy)."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        driver.set_page_load_timeout(max(30, page_wait))
        driver.get(url)
        time.sleep(4)
        close_cookie_banner(driver)
        try:
            WebDriverWait(driver, page_wait).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            pass
        wait = WebDriverWait(driver, page_wait)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        expanded_count = expand_show_more_sections(driver)
        expand_show_more_sections(driver)
        time.sleep(2)
        try:
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight / 2);"
            )
            time.sleep(1)
        except Exception:
            pass
        html_content = driver.page_source
        filename = get_filename_from_url(url, title)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        return {
            "url": url,
            "title": title,
            "filename": filename,
            "filepath": filepath,
            "expanded_sections": expanded_count,
            "html_size": len(html_content),
            "source": "selenium",
            "status": "success",
        }
    except Exception as e:
        logger.error("Error saving HTML from %s: %s", url, e)
        return {"url": url, "title": title, "error": str(e), "status": "error"}


def save_call_htmls(
    call_links_file: str,
    output_dir: str = "calls_htmls",
    max_calls: Optional[int] = None,
    use_sedia: bool = True,
    page_wait: int = 45,
):
    print(f"Starting HTML saving from {call_links_file}")
    if use_sedia:
        print("  Mode: SEDIA HTML assembly (+ Selenium fallback if needed)")
    else:
        print("  Mode: Selenium only")

    try:
        with open(call_links_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        call_links = data["links"] if "links" in data else data
    except Exception as e:
        print(f"Error loading call links file: {e}")
        return

    if not call_links:
        print("No call links found in the file")
        return

    results_file = os.path.join(output_dir, "saved_htmls_results.json")
    existing_results: list = []
    processed_urls: set = set()
    if os.path.exists(results_file):
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                existing_results = json.load(f)
            processed_urls = {
                r["url"]
                for r in existing_results
                if r.get("status") == "success"
            }
            print(
                f"Found existing results file with {len(existing_results)} entries "
                f"({len(processed_urls)} successful URLs)"
            )
        except Exception as e:
            print(f"Could not load existing results file: {e}")
            existing_results = []
            processed_urls = set()

    remaining_links = []
    for call_link in call_links:
        url = call_link.get("url") if isinstance(call_link, dict) else call_link
        if url and url not in processed_urls:
            remaining_links.append(call_link)

    print(
        f"Found {len(remaining_links)} calls remaining to process "
        f"(out of {len(call_links)} total)"
    )

    if max_calls:
        remaining_links = remaining_links[:max_calls]
        print(f"Limited to {max_calls} remaining calls")

    if not remaining_links:
        print("No new calls to process.")
        return

    driver = None
    try:
        all_results = existing_results.copy()
        pbar = tqdm(remaining_links, desc="Saving HTMLs", unit="call")

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
            pbar.set_description(f"Saving: {short_title}")

            result: Optional[dict[str, Any]] = None
            if use_sedia:
                html_doc = build_topic_html_from_sedia(url, title or None)
                if html_doc and len(html_doc) > 200:
                    os.makedirs(output_dir, exist_ok=True)
                    filename = get_filename_from_url(url, title)
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(html_doc)
                    result = {
                        "url": url,
                        "title": title,
                        "filename": filename,
                        "filepath": filepath,
                        "expanded_sections": 0,
                        "html_size": len(html_doc),
                        "source": "sedia_html",
                        "status": "success",
                    }

            if result is None:
                if driver is None:
                    driver = setup_driver()
                result = save_call_html_selenium(
                    driver, url, title, output_dir, page_wait=page_wait
                )
            all_results.append(result)

            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)

            if result.get("source") == "sedia_html":
                time.sleep(0.1)
            else:
                time.sleep(1.5)

        print(f"\nHTML saving completed! Results saved to {results_file}")

        successful = [r for r in all_results if r.get("status") == "success"]
        failed = [r for r in all_results if r.get("status") == "error"]
        sedia_n = sum(1 for r in successful if r.get("source") == "sedia_html")
        sel_n = sum(1 for r in successful if r.get("source") == "selenium")

        print("\nSummary:")
        print(f"  Total entries in log: {len(all_results)}")
        print(f"  Successful: {len(successful)} (SEDIA HTML: {sedia_n}, Selenium: {sel_n})")
        print(f"  Failed: {len(failed)}")

    except Exception as e:
        print(f"Error during HTML saving: {e}")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def main(argv: list[str]) -> None:
    raw = [a for a in argv if a != "--selenium-only"]
    selenium_only = "--selenium-only" in argv

    if len(raw) < 1:
        print(
            "Usage: python save_call_htmls.py <call_links_file> [output_dir] [max_calls] [--selenium-only]"
        )
        print(
            "  Default: build HTML from SEDIA metadata (recommended), Selenium if needed."
        )
        sys.exit(1)

    call_links_file = raw[0]
    output_dir = raw[1] if len(raw) > 1 else "calls_htmls"
    max_calls = int(raw[2]) if len(raw) > 2 else None

    save_call_htmls(
        call_links_file,
        output_dir,
        max_calls,
        use_sedia=not selenium_only,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
