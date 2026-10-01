"""
HTML/data extraction tools (requests + BeautifulSoup). Used for pages
that don't need JS rendering or interaction - the fast path per spec
section 20's fallback priority (requests+bs4 before Selenium).
"""
from __future__ import annotations

from typing import Optional

from jarvis.tools.base import RiskLevel, Tool, ToolResult

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

HEADERS = {"User-Agent": "Mozilla/5.0 (JARVIS-Agent/1.0)"}
TIMEOUT = 10


def _fetch(url: str) -> "requests.Response":
    if requests is None:
        raise RuntimeError("requests is not installed")
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def extract_page_text(url: str, max_chars: int = 4000) -> ToolResult:
    if BeautifulSoup is None:
        return ToolResult(False, error="bs4_missing", observation="beautifulsoup4 is not installed")
    try:
        resp = _fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        truncated = text[:max_chars]
        return ToolResult(True, output=truncated, observation=f"Extracted {len(truncated)} chars of text from {url}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, error=str(exc), observation=f"Failed to extract text from {url}: {exc}")


def extract_links(url: str, max_links: int = 50) -> ToolResult:
    if BeautifulSoup is None:
        return ToolResult(False, error="bs4_missing", observation="beautifulsoup4 is not installed")
    try:
        resp = _fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            label = a.get_text(strip=True)
            links.append({"href": href, "text": label})
            if len(links) >= max_links:
                break
        return ToolResult(True, output=links, observation=f"Found {len(links)} link(s) on {url}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, error=str(exc), observation=f"Failed to extract links from {url}: {exc}")


def extract_metadata(url: str) -> ToolResult:
    if BeautifulSoup is None:
        return ToolResult(False, error="bs4_missing", observation="beautifulsoup4 is not installed")
    try:
        resp = _fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        description: Optional[str] = None
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            description = meta["content"].strip()
        data = {"title": title, "description": description, "url": url}
        return ToolResult(True, output=data, observation=f"Metadata for {url}: {data}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, error=str(exc), observation=f"Failed to extract metadata from {url}: {exc}")


def extract_tables(url: str) -> ToolResult:
    if BeautifulSoup is None:
        return ToolResult(False, error="bs4_missing", observation="beautifulsoup4 is not installed")
    try:
        resp = _fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return ToolResult(True, output=tables, observation=f"Found {len(tables)} table(s) on {url}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(False, error=str(exc), observation=f"Failed to extract tables from {url}: {exc}")


def register(registry) -> None:
    registry.register(Tool(
        name="web_extract_text", description="Fetch a URL via HTTP and extract its visible text (no JS execution).",
        parameters={"url": {"type": "str", "required": True}, "max_chars": {"type": "int"}},
        risk_level=RiskLevel.LOW, func=extract_page_text, category="web_extract"))
    registry.register(Tool(
        name="web_extract_links", description="Fetch a URL and extract its hyperlinks.",
        parameters={"url": {"type": "str", "required": True}, "max_links": {"type": "int"}},
        risk_level=RiskLevel.LOW, func=extract_links, category="web_extract"))
    registry.register(Tool(
        name="web_extract_metadata", description="Fetch a URL and extract its title/meta description.",
        parameters={"url": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=extract_metadata, category="web_extract"))
    registry.register(Tool(
        name="web_extract_tables", description="Fetch a URL and extract any HTML tables as rows of cell text.",
        parameters={"url": {"type": "str", "required": True}},
        risk_level=RiskLevel.LOW, func=extract_tables, category="web_extract"))
