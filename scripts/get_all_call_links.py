#!/usr/bin/env python3
"""
EU Funding & Tenders — collect call/topic URLs for downstream scraping.

Default: Official SEDIA Search API (same index the portal uses). Reliable and fast.

Optional: Legacy Selenium scraping (--use-selenium). The SPA often mounts rows inside
Shadow DOM; use deep DOM collection there (embedded JS).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from typing import Any, Optional

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Traverse open + shadow DOM; EU portal lists are usually inside web components.
_JS_COLLECT_DETAIL_LINKS = """
return (function() {
    var rx = /(topic-details|call-details|opportunity-details|opportunity-detail|callIdentifier=)/i;
    var out = [];
    var seen = new Set();

    function considerAnchor(a) {
        var href = (a.href || '').trim();
        if (!href || seen.has(href) || !rx.test(href)) return;
        try {
            var path = new URL(href).pathname;
            if (path.indexOf('calls-for-proposals') >= 0 && href.indexOf('callIdentifier=') < 0
                && href.indexOf('topic-details') < 0 && href.indexOf('call-details') < 0
                && href.indexOf('opportunity-detail') < 0) {
                return;
            }
        } catch (e) { return; }
        seen.add(href);
        var title = (a.innerText || '').trim();
        if (!title) title = (a.getAttribute('title') || a.getAttribute('aria-label') || '').trim();
        out.push({url: href, title: title || 'No title'});
    }

    function walk(node) {
        if (!node) return;
        if (node.nodeType !== 1) return;

        try {
            if (node.shadowRoot) walk(node.shadowRoot);
        } catch (e0) {}

        if (node.tagName && node.tagName.toUpperCase() === 'A') {
            considerAnchor(node);
        }
        var children = node.children;
        if (!children) return;
        for (var i = 0; i < children.length; i++) walk(children[i]);
    }

    walk(document.documentElement || document.body);
    return out;
})(); 
"""

SEDIA_SEARCH_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"


def _write_calls_links_json(
    filepath: str,
    links: list,
    *,
    source_url: str,
    extras: Optional[dict] = None,
) -> None:
    meta = {
        "total_links": len(links),
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_url": source_url,
    }
    if extras:
        meta.update(extras)
    out = {"metadata": meta, "links": links}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    logger.info("Links saved to %s", filepath)


def fetch_call_links_via_sedia(
    *,
    page_size: int = 100,
    statuses: Optional[list[str]] = None,
    programme_period: str = "2021 - 2027",
    sort_field: str = "startDate",
    sort_order: str = "DESC",
    type_codes: Optional[list[str]] = None,
    max_pages: int = 500,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Paginate EC SEDIA Search API. Returns (links as dicts compatible with scrape_call_details chain, stats).

    Matches the portal's open/forthcoming + Horizon period filters used in the UI.
    Omitting type_codes mirrors 'all programme types' in that period (excluding pure procurement tenders).
    """
    if statuses is None:
        statuses = ["31094501", "31094502"]

    must: list[dict[str, Any]] = [
        {"terms": {"status": statuses}},
        {"term": {"programmePeriod": programme_period}},
    ]
    if type_codes:
        must.insert(0, {"terms": {"type": type_codes}})

    query = {"bool": {"must": must}}
    languages = ["en"]
    sort = {"field": sort_field, "order": sort_order.upper()}

    detail_re = re.compile(
        r"(topic-details/|call-details/|calls-for-proposals\?[^\s]*callIdentifier=|"
        r"(?:opportunity-detail|opportunity-details)/)",
        re.IGNORECASE,
    )

    collected: dict[str, dict[str, Any]] = {}
    total_reported = 0

    page_number = 1
    while page_number <= max_pages:
        params = {
            "apiKey": "SEDIA",
            "text": "*",
            "pageSize": str(page_size),
            "pageNumber": str(page_number),
        }
        resp = requests.post(
            SEDIA_SEARCH_URL,
            params=params,
            files={
                "query": ("blob", json.dumps(query), "application/json"),
                "languages": ("blob", json.dumps(languages), "application/json"),
                "sort": ("blob", json.dumps(sort), "application/json"),
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        total_reported = int(data.get("totalResults") or 0)
        results = data.get("results") or []
        logger.info(
            "SEDIA page %s: %s results (reported total %s)",
            page_number,
            len(results),
            total_reported,
        )

        if not results:
            break

        for res in results:
            url = (res.get("url") or "").strip()
            if not url or not detail_re.search(url):
                continue
            title_raw = res.get("content") or res.get("title") or ""
            title = str(title_raw).strip() if title_raw else "No title"
            collected[url] = {
                "url": url,
                "title": title or "No title",
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

        if len(results) < page_size:
            break

        page_number += 1

    links = list(collected.values())
    stats = {
        "total_items_expected": total_reported,
        "sedia_pages_fetched": page_number,
        "unique_detail_links": len(links),
    }
    logger.info(
        "SEDIA ingestion done: unique scrapeable URLs %s (SEDIA reported %s hits)",
        len(links),
        total_reported,
    )
    return links, stats


class CallLinksScraper:
    def __init__(self, headless=True, page_load_timeout_sec=120, implicit_wait_sec=0):
        """Initialize the scraper with Chrome options."""
        self.base_url = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/calls-for-proposals"
        self.links = []
        self.total_items = 0
        self.page_load_timeout_sec = page_load_timeout_sec

        chrome_options = ChromeOptions()
        if headless:
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
        chrome_options.page_load_strategy = "eager"

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_page_load_timeout(page_load_timeout_sec)
        if implicit_wait_sec > 0:
            self.driver.implicitly_wait(implicit_wait_sec)
        self.wait = WebDriverWait(self.driver, page_load_timeout_sec)

    def _wait_document_ready(self, extra_quiet_sec=2.0):
        """Wait for document.readyState and a short settle time (SPA paint)."""
        try:
            WebDriverWait(self.driver, self.page_load_timeout_sec).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning("document.readyState did not reach complete in time")
        time.sleep(extra_quiet_sec)

    def _dismiss_cookie_banner(self):
        try:
            cookie_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
            )
            for btn in cookie_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    self.driver.execute_script("arguments[0].click();", btn)
                    logger.info("Dismissed cookie banner.")
                    time.sleep(1.5)
                    break
        except Exception as e:
            logger.debug("Cookie banner: %s", e)

    def _wait_for_result_links(self, max_wait_sec: Optional[float] = None) -> bool:
        """
        Poll until any known result link pattern appears, with scroll nudges.
        The portal can take 30–90s on first load; a single 20s fixed wait is often too short.
        """
        budget = float(max_wait_sec if max_wait_sec is not None else self.page_load_timeout_sec)
        deadline = time.monotonic() + budget
        selectors = [
            "a[href*='topic-details']",
            "a[href*='call-details']",
            "a[href*='opportunity-detail']",
            "a[href*='opportunity-details']",
        ]
        attempt = 0
        while time.monotonic() < deadline:
            self._dismiss_cookie_banner()
            for sel in selectors:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if els:
                        logger.info("Result links detected via selector: %s (%s elements)", sel, len(els))
                        return True
                except Exception:
                    pass
            # JS pass: sometimes links exist before Selenium visibility heuristics settle
            try:
                found = self.driver.execute_script(_JS_COLLECT_DETAIL_LINKS)
                if found:
                    logger.info("Result links detected via JS scan: %s", len(found))
                    return True
            except Exception as e:
                logger.debug("JS link scan: %s", e)
            attempt += 1
            if attempt % 4 == 0:
                try:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                except Exception:
                    pass
            time.sleep(2.0)
        return False
    
    def get_total_items(self):
        """Extract the total number of items from the page."""
        try:
            # Look for text that contains the total number of items
            page_text = self.driver.page_source
            # Pattern to match "X items found" or similar
            pattern = r'(\d+)\s+items?\s+found'
            match = re.search(pattern, page_text, re.IGNORECASE)
            
            if match:
                self.total_items = int(match.group(1))
                logger.info(f"Total items found: {self.total_items}")
            else:
                # Try to find pagination info in various formats
                try:
                    # Look for elements containing numbers that might be total items
                    results_elements = self.driver.find_elements(By.XPATH, 
                        "//*[contains(text(), 'items') or contains(text(), 'results') or contains(text(), 'showing')]")
                    
                    for elem in results_elements:
                        text = elem.text.strip()
                        if text:
                            # Look for patterns like "showing 1-50 of 5449"
                            patterns = [
                                r'showing\s+\d+-\d+\s+of\s+(\d+)',
                                r'(\d+)\s+items?\s+total',
                                r'(\d+)\s+results?\s+found',
                                r'(\d+)\s+items?\s+available'
                            ]
                            
                            for pattern in patterns:
                                match = re.search(pattern, text, re.IGNORECASE)
                                if match:
                                    self.total_items = int(match.group(1))
                                    logger.info(f"Total items found from text '{text}': {self.total_items}")
                                    return
                    
                    # If still not found, try to estimate from URL parameters
                    current_url = self.driver.current_url
                    if 'pageSize=50' in current_url:
                        logger.info("Website is using pageSize=50 (not 100 as expected)")
                        # We'll need to scrape more pages to get all items
                        self.total_items = 0  # Will scrape until no more pages
                    else:
                        logger.warning("Could not determine total items, will scrape until no more pages")
                        self.total_items = 0
                        
                except Exception as e:
                    logger.warning(f"Could not determine total items: {e}")
                    self.total_items = 0
                    
        except Exception as e:
            logger.error(f"Error getting total items: {e}")
            self.total_items = 0
    
    def extract_links_from_page(self):
        """Extract all call / topic detail links from the current page."""
        try:
            if not self._wait_for_result_links():
                logger.warning(
                    "Timeout waiting for page content (no matching links). "
                    "Increase --timeout or retry with --no-headless."
                )
                return []

            page_links: list = []
            by_url: dict[str, dict] = {}

            raw = self.driver.execute_script(_JS_COLLECT_DETAIL_LINKS) or []
            for item in raw:
                href = (item.get("url") or "").strip()
                if not href:
                    continue
                title = (item.get("title") or "No title").strip() or "No title"
                by_url[href] = {
                    "url": href,
                    "title": title,
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }

            # Fallback: visible anchors matching legacy / new fragments
            if not by_url:
                fallback_selectors = [
                    "a[href*='topic-details']",
                    "a[href*='call-details']",
                    "a[href*='opportunity-detail']",
                    "a[href*='callIdentifier=']",
                ]
                for sel in fallback_selectors:
                    for element in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        href = (element.get_attribute("href") or "").strip()
                        if not href:
                            continue
                        text = element.text.strip()
                        if not text:
                            text = (
                                element.get_attribute("title")
                                or element.get_attribute("aria-label")
                                or "No title"
                            )
                        by_url[href] = {
                            "url": href,
                            "title": text.strip() or "No title",
                            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }

            page_links = list(by_url.values())
            logger.info("Found %s unique links on current page", len(page_links))
            return page_links

        except Exception as e:
            logger.error("Error extracting links from page: %s", e)
            return []
    
    def go_to_next_page(self):
        """Navigate to the next page using the pagination buttons, handling overlays and click interception."""
        try:
            self._dismiss_cookie_banner()

            # Find the parent button for next page
            next_button = None
            try:
                next_button = self.driver.find_element(By.XPATH, "//button[.//eui-icon-svg[@aria-label='Go to next page'] and not(@aria-disabled='true')]")
                logger.info("Found next page button (parent of icon)")
            except:
                selectors = [
                    "button[aria-label='Go to next page']:not([aria-disabled='true'])",
                    ".eui-paginator__page-navigation-item:last-child button:not([aria-disabled='true'])",
                    "[class*='next'] button:not([aria-disabled='true'])",
                    "button:has(eui-icon-svg[aria-label='Go to next page']):not([aria-disabled='true'])"
                ]
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                next_button = element
                                break
                        if next_button:
                            break
                    except Exception:
                        continue
            if not next_button:
                try:
                    next_button = self.driver.find_element(By.XPATH, "//button[@aria-label='Go to next page' and not(@aria-disabled='true')]")
                except:
                    pass
            if not next_button:
                try:
                    next_icon = self.driver.find_element(By.XPATH, "//eui-icon-svg[@aria-label='Go to next page']")
                    next_button = next_icon.find_element(By.XPATH, "./ancestor::button[1][not(@aria-disabled='true')]")
                except:
                    pass
            if next_button:
                logger.info("Found next page button, clicking it with ActionChains...")
                # Scroll to center of viewport
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)
                try:
                    ActionChains(self.driver).move_to_element(next_button).pause(0.5).click(next_button).perform()
                except Exception as click_error:
                    logger.info(f"ActionChains click failed, trying JavaScript click: {click_error}")
                    self.driver.execute_script("arguments[0].click();", next_button)
                self._wait_document_ready(extra_quiet_sec=2.0)
                pag_wait = min(90.0, float(self.page_load_timeout_sec))
                if self._wait_for_result_links(max_wait_sec=pag_wait):
                    raw = self.driver.execute_script(_JS_COLLECT_DETAIL_LINKS) or []
                    logger.info("Successfully navigated to next page (%s detail links in DOM)", len(raw))
                    return True
                logger.info("Next page did not expose expected links in time; stopping pagination")
                return False
            else:
                logger.warning("Could not find next page button")
                return False
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False
    
    def scrape_all_links(self):
        """Main method to scrape all call links from all pages."""
        try:
            initial_url = (
                f"{self.base_url}?order=DESC&pageNumber=1&pageSize=50&sortBy=startDate"
                "&isExactMatch=true&programmePeriod=2021%20-%202027&status=31094501,31094502"
            )
            logger.info("Navigating to: %s", initial_url)

            self.driver.get(initial_url)
            self._wait_document_ready(extra_quiet_sec=4.0)

            self.get_total_items()
            
            page_number = 1
            total_links = 0
            
            while True:
                logger.info(f"Scraping page {page_number}")
                
                # Extract links from current page
                page_links = self.extract_links_from_page()
                self.links.extend(page_links)
                total_links += len(page_links)
                
                logger.info(f"Total links collected so far: {total_links}")
                
                # Check if we should continue to next page
                if self.total_items > 0 and total_links >= self.total_items:
                    logger.info(f"Reached expected total of {self.total_items} items")
                    break
                
                # If we got 0 items on this page, it's definitely the last page
                if len(page_links) == 0:
                    logger.info("Got 0 items on this page, reached the end")
                    break
                
                # Try to go to next page
                if not self.go_to_next_page():
                    logger.info("No more pages available")
                    break
                
                page_number += 1

                max_pages = 500
                if page_number > max_pages:
                    logger.warning("Reached maximum page limit (%s), stopping", max_pages)
                    break

            logger.info("Scraping completed. Total links collected: %s", len(self.links))

        except Exception as e:
            logger.error("Error during scraping: %s", e)
    
    def save_to_json(self, filename='calls_links.json'):
        """Save the collected links to a JSON file."""
        extras = {"fetch_mode": "selenium", "total_items_expected": self.total_items}
        _write_calls_links_json(
            filename, self.links, source_url=self.base_url, extras=extras
        )


def main():
    parser = argparse.ArgumentParser(
        description="Collect EU Funding & Tenders call/topic links into JSON (default: SEDIA API)."
    )
    parser.add_argument(
        "--use-selenium",
        action="store_true",
        help="Use browser scraping instead of SEDIA API (slower; for debugging only).",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="With --use-selenium: show Chrome window.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        metavar="SEC",
        help="With --use-selenium: max seconds to wait per page (default: 120).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="calls_links.json",
        help="Output JSON path (default: calls_links.json)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="SEDIA API page size per request (default: 100).",
    )
    parser.add_argument(
        "--programme-period",
        default="2021 - 2027",
        metavar="TEXT",
        help='SEDIA programmePeriod filter (default: \"2021 - 2027\").',
    )
    parser.add_argument(
        "--status",
        default="31094501,31094502",
        metavar="CODES",
        help="Comma-separated SEDIA status codes (default: 31094501,31094502 open/forthcoming).",
    )
    parser.add_argument(
        "--types",
        default=None,
        metavar="CODES",
        help="Optional comma-separated SEDIA type codes (e.g. 1,2 topics only). "
        "Default: omit = all programme types matching status & period (~ topic-style results).",
    )
    args = parser.parse_args()

    if args.use_selenium:
        logger.info("Using Selenium (legacy browser scraper)...")
        scraper = CallLinksScraper(
            headless=not args.no_headless,
            page_load_timeout_sec=max(45, args.timeout),
        )
        try:
            scraper.scrape_all_links()
            scraper.save_to_json(args.output)
            logger.info("Scraping completed successfully!")
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
        except Exception as e:
            logger.error("Unexpected error: %s", e)
        finally:
            try:
                if getattr(scraper, "driver", None) is not None:
                    scraper.driver.quit()
            except Exception:
                pass
        return

    logger.info(
        "Using EC SEDIA Search API (recommended). "
        "No browser — same index the portal UI uses behind the SPA / Shadow DOM."
    )
    try:
        statuses = [x.strip() for x in args.status.split(",") if x.strip()]
        type_codes = None
        if args.types:
            type_codes = [x.strip() for x in args.types.split(",") if x.strip()]
        links, stats = fetch_call_links_via_sedia(
            page_size=max(10, min(500, args.page_size)),
            statuses=statuses,
            programme_period=args.programme_period,
            type_codes=type_codes,
        )
        extras = {"fetch_mode": "sedia_search_api", **stats}
        _write_calls_links_json(
            args.output,
            links,
            source_url=SEDIA_SEARCH_URL,
            extras=extras,
        )
        logger.info("Done. Saved %s unique URLs to %s", len(links), args.output)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error("SEDIA fetch failed: %s", e)
        logger.info("Tip: retry with --use-selenium if you hit a firewall or SSL issue.")


if __name__ == "__main__":
    main()
