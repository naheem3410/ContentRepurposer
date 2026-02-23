#!/usr/bin/env python3
"""
scrape_site.py

Pass a list of blog article URLs; fetches each and returns their content.
Produces a list of dicts: [{"url": "...", "title": "...", "content": "..."}]
"""

import json
import argparse
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ratelimit import limits, sleep_and_retry

# --------------------------------------------------------------
# Configuration
# --------------------------------------------------------------
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUESTS_PER_MINUTE = 30
REQUEST_TIMEOUT = 15
MAX_BLOG_POSTS = 5

# Blog can appear as path segment or subdomain under these names
BLOG_PATH_SLUGS = [
    "blog", "blogs", "news", "article", "articles", "post", "posts",
    "insights", "stories", "updates", "journal", "magazine", "read",
    "resources", "press", "media",
]
BLOG_SUBDOMAINS = ["blog", "news", "articles", "posts", "insights", "stories", "press"]

# Path segments that indicate non-article pages (filter out)
NON_ARTICLE_PATHS = [
    "tag", "tags", "category", "categories", "author", "page=",
    "search", "login", "signup", "about", "contact", "privacy",
    "feed", "rss", ".xml", "share", "comment",
]

ABOUT_PAGE_PATHS = ["/about", "/about-us", "/aboutme", "/about-us/"]

# --------------------------------------------------------------


def get_base_domain(netloc: str) -> str:
    """Return the registrable domain (e.g. example.com) for same-site checks."""
    if not netloc:
        return ""
    # Remove port
    host = netloc.split(":")[0].lower()
    # Simple: treat as same site if it ends with the base or is a known subdomain
    return host


def is_same_site(url: str, base_netloc: str) -> bool:
    """True if url belongs to the same site (including blog.example.com vs www.example.com)."""
    if not url:
        return False
    parsed = urlparse(url)
    other = (parsed.netloc or "").lower().split(":")[0]
    base = (base_netloc or "").lower().split(":")[0]
    if not base:
        return False
    if other == base:
        return True
    # Subdomain of base: e.g. blog.example.com and www.example.com
    if other.endswith("." + base) or base.endswith("." + other):
        return True
    # Same second-level domain (e.g. blog.site.com vs www.site.com)
    base_parts = base.split(".")
    other_parts = other.split(".")
    if len(base_parts) >= 2 and len(other_parts) >= 2:
        if base_parts[-2:] == other_parts[-2:]:
            return True
    return False


def looks_like_blog_url(parsed_path: str, parsed_netloc: str, base_netloc: str) -> bool:
    """True if path or subdomain suggests a blog/index page (not a single article)."""
    path = (parsed_path or "").lower().strip("/")
    netloc = (parsed_netloc or "").lower()
    # Subdomain: blog.example.com, news.example.com
    for sub in BLOG_SUBDOMAINS:
        if netloc.startswith(sub + ".") or netloc == sub:
            return True
    # Path: /blog, /news, /articles, /blog/, etc.
    first_segment = path.split("/")[0] if path else ""
    return first_segment in BLOG_PATH_SLUGS or any(
        slug in path for slug in BLOG_PATH_SLUGS
    )


def looks_like_article_url(path: str) -> bool:
    """True if path looks like a single article (not index, tag, category)."""
    if not path:
        return False
    path_lower = path.lower().strip("/")
    for bad in NON_ARTICLE_PATHS:
        if bad in path_lower:
            return False
    # Often articles have: /blog/2024/01/slug or /blog/some-article-slug (multiple segments)
    segments = [s for s in path_lower.split("/") if s]
    if len(segments) < 1:
        return False
    # Index-like: just one segment that is a blog slug (e.g. /blog, /news)
    if len(segments) == 1 and segments[0] in BLOG_PATH_SLUGS:
        return False
    return True


@sleep_and_retry
@limits(calls=REQUESTS_PER_MINUTE, period=60)
def fetch(url: str) -> requests.Response:
    """GET a URL with headers and timeout."""
    headers = {"User-Agent": USER_AGENT}
    return requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)


def clean_text(soup: BeautifulSoup) -> str:
    """Visible text from the main content (article or largest block)."""
    article = soup.find("article")
    if article:
        txt = article.get_text(separator=" ", strip=True)
        if txt:
            return " ".join(txt.split())
    candidates = soup.find_all(["div", "section"], recursive=True)
    best = ""
    for cand in candidates:
        txt = cand.get_text(separator=" ", strip=True)
        if len(txt) > len(best):
            best = txt
    return " ".join(best.split())


def get_title(soup: BeautifulSoup) -> str:
    """Page title from <title> or first h1."""
    if soup.title and soup.title.string:
        return (soup.title.string or "").strip()
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def extract_page(url: str) -> dict:
    """Download a page and return {url, title, content}."""
    resp = fetch(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return {
        "url": url,
        "title": get_title(soup),
        "content": clean_text(soup),
    }


def find_about_page(base_url: str) -> str:
    """Return first existing about URL or base_url."""
    for slug in ABOUT_PAGE_PATHS:
        candidate = urljoin(base_url, slug)
        try:
            r = fetch(candidate)
            if r.status_code == 200:
                return candidate
        except Exception:
            continue
    return base_url


def discover_blog_index_url(home_soup: BeautifulSoup, base_url: str) -> str | None:
    """
    From the home page, find a link that points to the blog index
    (subdomain or path: blog, news, articles, posts, etc.).
    Also tries common blog paths if no link found. Returns absolute URL or None.
    """
    base_parsed = urlparse(base_url)
    base_netloc = base_parsed.netloc or ""
    scheme = base_parsed.scheme or "https"

    candidates = []
    for a in home_soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        path = (parsed.path or "").strip("/")
        netloc = (parsed.netloc or "").lower()

        if not is_same_site(full, base_netloc):
            continue
        if looks_like_blog_url(parsed.path or "", netloc, base_netloc):
            segments = path.lower().split("/")
            first = segments[0] if segments else ""
            is_index = first in BLOG_PATH_SLUGS and len(segments) <= 2
            candidates.append((full, is_index))

    candidates.sort(key=lambda x: (not x[1], x[0]))
    seen = set()
    for full, _ in candidates:
        if full not in seen:
            seen.add(full)
            return full

    # Fallback: try common blog paths (e.g. /blog, /blogs, /news)
    for slug in ["blogs", "blog", "news", "articles", "posts", "insights"]:
        candidate = urljoin(base_url, f"/{slug}/")
        try:
            r = fetch(candidate)
            if r.status_code == 200:
                return candidate
        except Exception:
            continue
    return None


def discover_first_n_article_urls(
    blog_index_url: str, base_netloc: str, n: int = MAX_BLOG_POSTS
) -> list[str]:
    """
    Fetch the blog index page and collect the first n article URLs.
    Only links that belong to the blog section (same path prefix as index) and
    look like article permalinks are included. Uses final URL after redirects.
    """
    try:
        resp = fetch(blog_index_url)
        resp.raise_for_status()
    except Exception:
        return []
    # Use final URL after redirects (e.g. /blogs/ might redirect to blog.example.com)
    final_url = resp.url
    soup = BeautifulSoup(resp.text, "html.parser")
    parsed_index = urlparse(final_url)
    base_url = f"{parsed_index.scheme}://{parsed_index.netloc}"
    index_path = (parsed_index.path or "").strip("/")
    index_path_prefix = index_path + "/" if index_path else ""

    found = []
    seen = set()

    for a in soup.find_all("a", href=True):
        if len(found) >= n:
            break
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        path = (parsed.path or "").strip("/")

        if full in seen:
            continue
        if not is_same_site(full, base_netloc):
            continue
        # Prefer links under the blog section (e.g. /blogs/2024/01/slug)
        if index_path and index_path_prefix and not (path == index_path or path.startswith(index_path_prefix)):
            continue
        if not looks_like_article_url(path):
            continue
        if full.rstrip("/") == final_url.rstrip("/"):
            continue
        seen.add(full)
        found.append(full)

    return found[:n]


def scrape_site(article_urls) -> list:
    """
    Fetch each URL in the list of blog article links.
    Pass a list of URLs, e.g. ["https://...", "https://..."]
    Returns a list of dicts: [{"url": "...", "title": "...", "content": "..."}]
    """
    if isinstance(article_urls, str):
        article_urls = [article_urls]
    results = []
    for url in article_urls:
        try:
            results.append(extract_page(url))
        except Exception:
            continue
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch content from a list of article URLs.")
    parser.add_argument("urls", nargs="+", help="Article URLs to fetch")
    parser.add_argument("--json", action="store_true", help="Print result as JSON")
    args = parser.parse_args()
    data = scrape_site(args.urls)
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        for item in data:
            print(item.get("url", ""), "-", (item.get("title") or "")[:60])


if __name__ == "__main__":
    main()
