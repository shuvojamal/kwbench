"""
Fetch a competitor's sitemap (handles sitemap-index files one level deep),
turn URL slugs into candidate phrases, and optionally sample page <title> tags.
"""
import re
import requests
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

HEADERS = {"User-Agent": "Mozilla/5.0 (KeywordBench/1.0)"}
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def find_sitemap_url(domain: str) -> str:
    domain = domain.strip()
    if not domain.startswith("http"):
        domain = "https://" + domain
    base = f"{urlparse(domain).scheme}://{urlparse(domain).netloc}"

    try:
        robots = requests.get(f"{base}/robots.txt", headers=HEADERS, timeout=10)
        if robots.ok:
            for line in robots.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    return line.split(":", 1)[1].strip()
    except requests.RequestException:
        pass
    return f"{base}/sitemap.xml"


def _parse_urls(xml_bytes):
    root = ET.fromstring(xml_bytes)
    tag = root.tag.lower()
    if tag.endswith("sitemapindex"):
        return None, [el.text.strip() for el in root.findall(".//sm:loc", NS) if el.text]
    urls = [el.text.strip() for el in root.findall(".//sm:loc", NS) if el.text]
    return urls, None


def fetch_urls(domain: str, max_urls: int = 500) -> list:
    """Returns a flat list of page URLs from the sitemap (or sitemap-of-sitemaps)."""
    sitemap_url = find_sitemap_url(domain)
    resp = requests.get(sitemap_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    urls, child_sitemaps = _parse_urls(resp.content)

    if urls is None:  # was a sitemap index — pull from the first few child sitemaps
        urls = []
        for child in child_sitemaps[:5]:
            try:
                r = requests.get(child, headers=HEADERS, timeout=15)
                child_urls, _ = _parse_urls(r.content)
                if child_urls:
                    urls.extend(child_urls)
                if len(urls) >= max_urls:
                    break
            except (requests.RequestException, ET.ParseError):
                continue
    return urls[:max_urls]


def slugs_to_phrases(urls: list) -> list:
    """Turn /best-bathroom-tiles-2026/ into 'best bathroom tiles 2026'."""
    phrases = []
    for u in urls:
        path = urlparse(u).path.strip("/")
        if not path:
            continue
        last = path.split("/")[-1]
        last = re.sub(r"\.(html?|php|aspx?)$", "", last, flags=re.I)
        words = re.split(r"[-_]+", last)
        phrase = " ".join(w for w in words if w and not w.isdigit())
        if len(phrase.split()) >= 2:
            phrases.append(phrase)
    return list(dict.fromkeys(phrases))  # dedupe, keep order


def sample_titles(urls: list, limit: int = 40) -> list:
    """Fetch <title> for a sample of pages — slower, so kept to a small sample."""
    titles = []
    for u in urls[:limit]:
        try:
            r = requests.get(u, headers=HEADERS, timeout=8)
            m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.DOTALL)
            if m:
                titles.append(re.sub(r"\s+", " ", m.group(1)).strip())
        except requests.RequestException:
            continue
    return titles
