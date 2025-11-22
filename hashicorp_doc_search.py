"""HashiCorp Developer Documentation Web Crawler - LangChain Implementation.

Crawls developer.hashicorp.com using the sitemap, extracts content from HTML pages,
and builds a searchable FAISS index using LangChain.
"""

import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
import tiktoken
from bs4 import BeautifulSoup
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# LangChain imports
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Cross-encoder for re-ranking
from sentence_transformers import CrossEncoder

# Parent-child semantic chunking
from chunking_utils import semantic_chunk_html

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging

# Add console handler with formatting if not already added
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Sitemap URL
SITEMAP_URL = "https://developer.hashicorp.com/server-sitemap.xml"

# User agent for crawling
USER_AGENT = "IvanBot/1.0 (+https://github.com/yourusername/ivan; bot@example.com)"

# Query expansion dictionary - HashiCorp domain-specific synonyms
QUERY_EXPANSION_TERMS = {
    # Performance & Hardware
    "throughput": ["IOPS", "MB/s", "disk performance", "IO performance", "disk IO"],
    "performance": ["throughput", "IOPS", "latency", "speed", "optimization"],
    "disk": ["storage", "disk IO", "persistent storage", "volume"],
    "hardware": ["system requirements", "infrastructure", "server specs", "compute resources"],
    "requirements": ["sizing", "specifications", "recommendations", "prerequisites"],
    "needed": ["required", "recommended", "minimum", "suggested"],
    "run": ["deploy", "operate", "production", "install", "configure"],
    # Vault-specific
    "vault": ["vault server", "vault cluster", "vault enterprise", "vault deployment"],
    "seal": ["unseal", "auto-unseal", "seal/unseal"],
    "secret": ["secrets engine", "kv", "dynamic secrets", "credentials"],
    "auth": ["authentication", "auth method", "login", "identity"],
    # Consul-specific
    "consul": ["consul server", "consul agent", "consul cluster", "service mesh"],
    "service": ["service discovery", "service mesh", "service registration"],
    "dns": ["service discovery", "DNS forwarding", "DNS query"],
    "stale": ["consistency", "staleness", "eventual consistency"],
    # Terraform-specific
    "terraform": ["terraform cli", "terraform cloud", "terraform enterprise", "tf"],
    "state": ["state file", "remote state", "state backend", "state locking"],
    "provider": ["provider plugin", "terraform provider"],
    "module": ["terraform module", "registry module"],
    # General technical terms
    "default": ["default value", "default setting", "default configuration", "out of the box"],
    "configuration": ["config", "settings", "parameters", "options"],
    "install": ["installation", "setup", "deploy", "deployment"],
    "cluster": ["multi-node", "distributed", "high availability", "HA"],
}


class HashiCorpDocSearchIndex:
    """Manages web documentation crawling, indexing, and semantic search using LangChain."""

    def __init__(
        self,
        cache_dir: str = "./hashicorp_web_docs",
        model_name: str = "all-MiniLM-L6-v2",
        update_check_interval_hours: int = 168,  # 7 days
        chunk_size: int = 800,  # Default: tokens for concept/how-to docs
        chunk_overlap: int = 120,  # Default: ~15% overlap
        max_pages: int | None = None,  # For testing, limit pages crawled
        rate_limit_delay: float = 0.1,  # Delay between requests (seconds) - increased for rate limiting
        max_workers: int = 5,  # Parallel workers for fetching - reduced to avoid rate limits
        enable_reranking: bool = True,  # Enable two-stage cross-encoder re-ranking
        rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",  # Heavy cross-encoder (final ranking)
        light_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",  # Lightweight cross-encoder (first pass)
        rerank_top_k: int = 80,  # Candidates for final heavy reranking
        light_rerank_top_k: int = 80,  # Candidates after lightweight reranking (reduces from ~535 to 80)
        enable_query_expansion: bool = False,  # Enable query expansion with domain synonyms (disabled - too aggressive for technical queries)
        max_expansion_terms: int = 1,  # Max number of expansion terms to add per keyword
    ):
        """Initialize the web search index.

        Args:
            cache_dir: Directory to cache content and index
            model_name: Sentence transformer model name
            update_check_interval_hours: Hours between update checks (default: 7 days)
            chunk_size: Tokens per chunk (default for concept/how-to docs)
            chunk_overlap: Overlapping tokens between chunks
            max_pages: Maximum pages to crawl (None = unlimited, for testing)
            rate_limit_delay: Delay between HTTP requests to be respectful
            max_workers: Number of parallel workers for fetching pages
            enable_reranking: Enable two-stage cross-encoder re-ranking (default: True)
            rerank_model: Heavy cross-encoder model for final ranking (L-12)
            light_rerank_model: Lightweight cross-encoder model for first pass (L-6)
            rerank_top_k: Number of candidates for final heavy reranking
            light_rerank_top_k: Number of candidates after lightweight reranking
            enable_query_expansion: Enable query expansion with domain synonyms (default: False)
            max_expansion_terms: Max number of expansion terms to add per keyword
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.content_dir = self.cache_dir / "pages"
        self.content_dir.mkdir(exist_ok=True)

        self.index_dir = self.cache_dir / "index"
        self.index_dir.mkdir(exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata.json"
        self.sitemap_file = self.cache_dir / "sitemap.xml"
        self.chunks_file = self.cache_dir / "chunks.json"
        self.url_list_file = self.cache_dir / "url_list.json"
        self.embedding_progress_file = self.cache_dir / "embedding_progress.json"

        self.model_name = model_name
        self.update_check_interval = timedelta(hours=update_check_interval_hours)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_pages = max_pages
        self.rate_limit_delay = rate_limit_delay
        self.max_workers = max_workers

        # Re-ranking configuration
        self.enable_reranking = enable_reranking
        self.rerank_model = rerank_model
        self.light_rerank_model = light_rerank_model
        self.rerank_top_k = rerank_top_k
        self.light_rerank_top_k = light_rerank_top_k

        # Query expansion configuration
        self.enable_query_expansion = enable_query_expansion
        self.max_expansion_terms = max_expansion_terms

        # LangChain components
        self.embeddings: HuggingFaceEmbeddings | None = None
        self.vectorstore: FAISS | None = None
        self.text_splitter: RecursiveCharacterTextSplitter | None = None
        self.bm25_retriever: BM25Retriever | None = None
        self.ensemble_retriever: EnsembleRetriever | None = None
        self.chunks: list[Document] | None = None  # Store chunks for BM25
        self.cross_encoder: CrossEncoder | None = None  # Heavy cross-encoder (L-12) for final ranking
        self.light_cross_encoder: CrossEncoder | None = None  # Lightweight cross-encoder (L-6) for first pass

        # Parent-child chunking storage
        self.parent_chunks: dict[str, dict[str, Any]] = {}  # chunk_id -> parent content/metadata
        self.child_to_parent: dict[str, str] = {}  # child_chunk_id -> parent_chunk_id

        # Robots.txt parser
        self.robot_parser = RobotFileParser()
        self.robot_parser.set_url("https://developer.hashicorp.com/robots.txt")
        try:
            self.robot_parser.read()
            logger.info("[DOC_SEARCH] Loaded robots.txt")
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to load robots.txt: {e}")

        # Initialize tokenizer for token-based chunking
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
            logger.info("[DOC_SEARCH] Initialized tiktoken tokenizer")
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to load tiktoken: {e}")
            self.tokenizer = None

        logger.info(f"[DOC_SEARCH] Initialized with cache_dir={cache_dir}, chunk_size={chunk_size} tokens")

    def _load_metadata(self) -> dict[str, Any]:
        """Load metadata from cache."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except Exception as e:
                logger.warning(f"[DOC_SEARCH] Failed to load metadata: {e}")
        return {}

    def _save_metadata(self, metadata: dict[str, Any]):
        """Save metadata to cache."""
        try:
            self.metadata_file.write_text(json.dumps(metadata, indent=2))
        except Exception as e:
            logger.error(f"[DOC_SEARCH] Failed to save metadata: {e}")

    def _needs_update(self) -> bool:
        """Check if index needs updating."""
        metadata = self._load_metadata()

        if "last_update" not in metadata:
            logger.info("[DOC_SEARCH] No previous index found, needs initial build")
            return True

        # Check version - force rebuild if chunking strategy changed
        current_version = "4.0.0-parent-child"  # Semantic parent-child chunking with token awareness
        if metadata.get("version") != current_version:
            logger.info(
                f"[DOC_SEARCH] Index version changed (old: {metadata.get('version', 'unknown')}, new: {current_version}), needs rebuild"
            )
            return True

        last_update = datetime.fromisoformat(metadata["last_update"])
        time_since_update = datetime.now() - last_update
        needs_update = time_since_update >= self.update_check_interval

        if needs_update:
            logger.info(f"[DOC_SEARCH] Update interval exceeded ({time_since_update})")
        else:
            logger.info(f"[DOC_SEARCH] Recent update found ({time_since_update} ago)")

        return needs_update

    def _download_sitemap(self) -> bool:
        """Download the sitemap XML."""
        try:
            logger.info(f"[DOC_SEARCH] Downloading sitemap from {SITEMAP_URL}")
            response = requests.get(SITEMAP_URL, timeout=30)
            response.raise_for_status()

            self.sitemap_file.write_bytes(response.content)
            logger.info(f"[DOC_SEARCH] Sitemap downloaded ({len(response.content)} bytes)")
            return True

        except Exception as e:
            logger.error(f"[DOC_SEARCH] Failed to download sitemap: {e}")
            return False

    def _parse_sitemap(self) -> list[dict[str, str]]:
        """Parse sitemap XML and extract URLs with metadata."""
        if not self.sitemap_file.exists():
            logger.error("[DOC_SEARCH] Sitemap file not found")
            return []

        try:
            tree = ET.parse(self.sitemap_file)
            root = tree.getroot()

            # Handle XML namespace
            namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            urls = []
            for url_elem in root.findall("ns:url", namespace):
                loc = url_elem.find("ns:loc", namespace)
                lastmod = url_elem.find("ns:lastmod", namespace)

                if loc is not None:
                    url = loc.text
                    # Normalize URL (remove anchors if present)
                    url = self._normalize_url(url)

                    # Skip URLs containing /partials/
                    if "/partials/" in url:
                        continue

                    parsed = urlparse(url)
                    path_parts = parsed.path.strip("/").split("/")

                    # Extract product from URL path
                    product = path_parts[0] if path_parts else "unknown"

                    urls.append(
                        {"url": url, "product": product, "lastmod": lastmod.text if lastmod is not None else None}
                    )

            logger.info(f"[DOC_SEARCH] Parsed {len(urls)} URLs from sitemap")

            if self.max_pages:
                urls = urls[: self.max_pages]
                logger.info(f"[DOC_SEARCH] Limited to {self.max_pages} pages for testing")

            return urls

        except Exception as e:
            logger.error(f"[DOC_SEARCH] Failed to parse sitemap: {e}")
            return []

    def _discover_validated_designs(self) -> list[dict[str, str]]:
        """Discover all validated-designs pages by crawling the index and guides.

        Returns:
            List of URL info dicts for validated-designs pages
        """
        discovered_urls = []
        base_url = "https://developer.hashicorp.com"

        try:
            logger.info("[DOC_SEARCH] " + "=" * 70)
            logger.info("[DOC_SEARCH] PHASE: Discovering validated-designs pages")
            logger.info("[DOC_SEARCH] " + "=" * 70)
            logger.debug(f"[DOC_SEARCH] Fetching {base_url}/validated-designs")

            # Fetch the index page
            headers = {"User-Agent": USER_AGENT}

            logger.debug("[DOC_SEARCH] Requesting validated-designs index page...")
            response = requests.get(f"{base_url}/validated-designs", headers=headers, timeout=30)
            response.raise_for_status()
            logger.debug(f"[DOC_SEARCH] Got response: {response.status_code}, {len(response.text)} bytes")

            soup = BeautifulSoup(response.text, "html.parser")

            # Find all links to validated-designs guides
            guide_links = set()
            for link in soup.find_all("a", href=True):
                href = link["href"]

                # Skip external links and non-http(s) links
                if href.startswith("http") and not href.startswith(base_url):
                    continue
                if href.startswith(("mailto:", "tel:", "#")):
                    continue

                # Make absolute URL first
                if href.startswith("/"):
                    href = base_url + href
                elif not href.startswith("http"):
                    # Relative URL
                    href = urljoin(f"{base_url}/validated-designs", href)

                # NOW check if it's a validated-designs URL
                if "/validated-designs/" in href:
                    # Normalize URL (remove anchors)
                    href = self._normalize_url(href)
                    guide_links.add(href)

            logger.info(f"[DOC_SEARCH] Found {len(guide_links)} validated-designs guide links")

            if not guide_links:
                logger.warning("[DOC_SEARCH] No guide links found, skipping validated-designs discovery")
                return []

            # For each guide, crawl to find all pages
            logger.info(f"[DOC_SEARCH] Crawling {len(guide_links)} guide pages for subpage links...")
            for idx, guide_url in enumerate(guide_links, 1):
                try:
                    progress_pct = (idx / len(guide_links)) * 100
                    logger.info(
                        f"[DOC_SEARCH] [{progress_pct:5.1f}%] Crawling guide {idx}/{len(guide_links)}: {guide_url}"
                    )
                    time.sleep(self.rate_limit_delay)

                    response = requests.get(guide_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    logger.debug(f"[DOC_SEARCH] Got guide page: {len(response.text)} bytes")

                    soup = BeautifulSoup(response.text, "html.parser")

                    # Find all links within this guide
                    links_found = 0
                    for link in soup.find_all("a", href=True):
                        href = link["href"]

                        # Skip external links and non-http(s) links
                        if href.startswith("http") and not href.startswith(base_url):
                            continue
                        if href.startswith(("mailto:", "tel:", "#")):
                            continue

                        # Make absolute URL first
                        if href.startswith("/"):
                            href = base_url + href
                        elif not href.startswith("http"):
                            # Relative URL - resolve relative to guide_url
                            href = urljoin(guide_url, href)

                        # NOW check if it's a validated-designs URL
                        if "/validated-designs/" in href:
                            # Normalize URL (remove anchors)
                            href = self._normalize_url(href)

                            # Extract product from URL
                            path_parts = href.replace(base_url, "").strip("/").split("/")
                            product = path_parts[1].split("-")[0] if len(path_parts) > 1 else "unknown"

                            discovered_urls.append({"url": href, "product": product, "lastmod": None})
                            links_found += 1

                    logger.debug(f"[DOC_SEARCH] Found {links_found} links in guide {idx}/{len(guide_links)}")

                except Exception as e:
                    logger.warning(f"[DOC_SEARCH] Failed to crawl guide {guide_url}: {e}")
                    continue

            # Deduplicate
            logger.debug(f"[DOC_SEARCH] Deduplicating {len(discovered_urls)} URLs...")
            unique_urls = {url_info["url"]: url_info for url_info in discovered_urls}
            result = list(unique_urls.values())

            logger.info(f"[DOC_SEARCH] Discovered {len(result)} unique validated-designs pages")
            return result

        except Exception as e:
            logger.error(f"[DOC_SEARCH] Failed to discover validated-designs: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return []

    def _discover_release_notes(self) -> list[dict[str, str]]:
        """Discover version-specific release notes pages for all products.

        Release notes aren't in the sitemap, so we generate URLs based on known patterns:
        - Vault: /vault/docs/v{version}/updates/release-notes
        - Consul: /consul/docs/v{version}/release-notes
        - Terraform: /terraform/docs/v{version}/language/v1-compatibility-promises
        - Other products: similar patterns

        Returns:
            List of URL info dicts for release notes pages
        """
        discovered_urls = []
        base_url = "https://developer.hashicorp.com"
        headers = {"User-Agent": USER_AGENT}

        # Product configurations: (product_name, url_pattern, versions_to_try)
        # versions_to_try: range of minor versions to check (e.g., range(15, 22) for 1.15-1.21)
        products = [
            ("vault", "/vault/docs/v1.{minor}.x/updates/release-notes", range(15, 22)),
            ("consul", "/consul/docs/v1.{minor}.x/release-notes", range(15, 22)),
            ("terraform", "/terraform/docs/v1.{minor}.x/language/upgrade-guides", range(5, 11)),
            ("nomad", "/nomad/docs/release-notes/nomad/v1_{minor}_x", range(5, 11)),
            ("boundary", "/boundary/docs/v0.{minor}.x/release-notes", range(10, 18)),
            ("waypoint", "/waypoint/docs/v0.{minor}.x/release-notes", range(8, 12)),
            ("packer", "/packer/docs/v1.{minor}.x/whats-new", range(8, 12)),
        ]

        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info("[DOC_SEARCH] PHASE: Discovering version-specific release notes")
        logger.info("[DOC_SEARCH] " + "=" * 70)

        total_checked = 0
        total_found = 0

        for product, url_pattern, versions in products:
            logger.info(f"[DOC_SEARCH] Checking {product} release notes...")
            product_found = 0

            for minor in versions:
                url = base_url + url_pattern.format(minor=minor)
                total_checked += 1

                try:
                    # Test if URL exists
                    response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)

                    if response.status_code == 200:
                        discovered_urls.append({"url": url, "product": product, "lastmod": None})
                        product_found += 1
                        logger.debug(f"[DOC_SEARCH]   ✓ Found: {url}")

                    time.sleep(self.rate_limit_delay)

                except Exception:
                    logger.debug(f"[DOC_SEARCH]   ✗ Not found: {url}")
                    continue

            if product_found > 0:
                logger.info(f"[DOC_SEARCH]   ✓ {product}: found {product_found} versions")
                total_found += product_found
            else:
                logger.warning(f"[DOC_SEARCH]   ✗ {product}: no release notes found")

        logger.info(f"[DOC_SEARCH] Release notes discovery: found {total_found}/{total_checked} URLs")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        return discovered_urls

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing anchors/fragments.

        Args:
            url: URL to normalize

        Returns:
            URL without anchor fragment
        """
        # Split URL and remove fragment (anchor)
        parsed = urlparse(url)
        # Reconstruct without fragment
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if self.tokenizer is None:
            # Fallback: rough estimate (1 token ≈ 4 chars)
            return len(text) // 4

        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Token counting failed: {e}, using estimate")
            return len(text) // 4

    def _get_chunk_config(self, url: str) -> dict[str, int]:
        """Get adaptive chunk configuration based on document type.

        Args:
            url: Page URL to determine type

        Returns:
            Dictionary with 'size' (tokens) and 'overlap' (tokens)
        """
        # API reference and CLI command pages - smaller chunks
        if "/api/" in url or "/api-docs/" in url or "/commands/" in url:
            return {"size": 500, "overlap": 75}  # ~15% overlap

        # Configuration-heavy pages - medium chunks with more overlap
        elif "/configuration/" in url or re.search(r"/docs/.*config", url):
            return {"size": 400, "overlap": 80}  # ~20% overlap

        # Release notes and changelogs - medium chunks
        elif "/release-notes" in url or "/changelog" in url or "/releases/" in url:
            return {"size": 600, "overlap": 60}  # ~10% overlap

        # Tutorials and guides - larger chunks
        elif "/tutorials/" in url or "/guides/" in url:
            return {"size": 900, "overlap": 135}  # ~15% overlap

        # Concept/how-to documentation (default) - standard chunks
        else:
            return {"size": 800, "overlap": 120}  # ~15% overlap

    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt.

        Override robots.txt for validated-designs content as requested.

        Args:
            url: URL to check

        Returns:
            True if allowed, False otherwise
        """
        # Always allow validated-designs pages regardless of robots.txt
        if "/validated-designs" in url or "/validated-patterns" in url:
            return True

        try:
            return self.robot_parser.can_fetch(USER_AGENT, url)
        except:
            # If robots.txt parsing fails, be conservative and allow
            return True

    def _extract_table_as_markdown(self, table_element) -> str | None:
        """Convert HTML table to markdown format.

        Args:
            table_element: BeautifulSoup table element

        Returns:
            Markdown-formatted table string or None if table is empty
        """
        try:
            rows = []

            # Extract headers from thead or first row
            headers = []
            thead = table_element.find("thead")
            if thead:
                header_row = thead.find("tr")
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

            # If no thead, check if first row in tbody has th elements
            if not headers:
                tbody = table_element.find("tbody") or table_element
                first_row = tbody.find("tr")
                if first_row:
                    ths = first_row.find_all("th")
                    if ths:
                        headers = [th.get_text(strip=True) for th in ths]
                    else:
                        # First row might be headers even if using td
                        headers = [td.get_text(strip=True) for td in first_row.find_all("td")]

            if not headers:
                return None

            # Build markdown header
            markdown_parts = []
            markdown_parts.append("| " + " | ".join(headers) + " |")
            markdown_parts.append("| " + " | ".join(["---"] * len(headers)) + " |")

            # Extract data rows from tbody
            tbody = table_element.find("tbody") or table_element
            data_rows = tbody.find_all("tr")

            # Skip first row if it was used for headers
            start_idx = 1 if not thead and data_rows else 0
            if thead:
                start_idx = 0

            for row in data_rows[start_idx:]:
                cells = row.find_all(["td", "th"])
                if cells:
                    cell_texts = [cell.get_text(strip=True).replace("|", "\\|") for cell in cells]
                    # Pad with empty cells if needed
                    while len(cell_texts) < len(headers):
                        cell_texts.append("")
                    markdown_parts.append("| " + " | ".join(cell_texts[: len(headers)]) + " |")

            # Only return if we have at least one data row
            if len(markdown_parts) > 2:
                return "\n".join(markdown_parts)

            return None

        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to extract table: {e}")
            return None

    def _extract_main_content(self, html: str, url: str) -> dict[str, Any] | None:
        """Extract main documentation content from HTML page with section anchors.

        Preserves structure including headings, anchors, code blocks, and tables for better context.

        Args:
            html: Raw HTML content
            url: URL of the page (for logging)

        Returns:
            Dictionary with 'content' (text) and 'sections' (list of section info) or None
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted elements
            for element in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
                element.decompose()

            # Try to find main content area
            # HashiCorp docs typically use main, article, or specific content divs
            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.find("div", {"id": "content"})
                or soup.find("div", {"class": "content"})
                or soup.body
            )

            if main_content:
                # Track sections (H2/H3 with anchors)
                sections = []
                text_parts = []
                current_section = None
                current_h2_anchor = None

                # Process content and extract section anchors
                processed_elements = set()  # Track processed elements to avoid duplicates

                for element in main_content.descendants:
                    # Skip if already processed (avoid duplicating nested content)
                    if id(element) in processed_elements:
                        continue

                    if element.name == "h1":
                        heading_text = element.get_text(strip=True)
                        anchor_id = element.get("id", "")
                        text_parts.append(f"\n# {heading_text}\n")
                        if anchor_id:
                            sections.append(
                                {
                                    "level": 1,
                                    "text": heading_text,
                                    "anchor": anchor_id,
                                    "position": len("".join(text_parts)),
                                }
                            )
                        processed_elements.add(id(element))

                    elif element.name == "h2":
                        heading_text = element.get_text(strip=True)
                        anchor_id = element.get("id", "")
                        text_parts.append(f"\n## {heading_text}\n")
                        current_h2_anchor = anchor_id  # Track for H3s
                        if anchor_id:
                            current_section = {
                                "level": 2,
                                "text": heading_text,
                                "anchor": anchor_id,
                                "position": len("".join(text_parts)),
                            }
                            sections.append(current_section)
                        processed_elements.add(id(element))

                    elif element.name == "h3":
                        heading_text = element.get_text(strip=True)
                        anchor_id = element.get("id", "")
                        text_parts.append(f"\n### {heading_text}\n")
                        # Use H3 anchor if available, otherwise fall back to parent H2
                        section_anchor = anchor_id if anchor_id else current_h2_anchor
                        if section_anchor:
                            sections.append(
                                {
                                    "level": 3,
                                    "text": heading_text,
                                    "anchor": section_anchor,
                                    "position": len("".join(text_parts)),
                                    "parent_anchor": current_h2_anchor if anchor_id else None,
                                }
                            )
                        processed_elements.add(id(element))

                    elif element.name in ["pre", "code"] and element.parent.name != "pre":
                        # Preserve code blocks (avoid duplicating code inside pre)
                        code_text = element.get_text(strip=False)
                        if code_text.strip():
                            text_parts.append(f"\n```\n{code_text}\n```\n")
                        processed_elements.add(id(element))

                    elif element.name == "p" and not any(p.name in ["pre", "code"] for p in element.parents):
                        para_text = element.get_text(strip=True)
                        if para_text:
                            text_parts.append(f"{para_text}\n")
                        processed_elements.add(id(element))

                    elif element.name == "li" and element.parent.name in ["ul", "ol"]:
                        li_text = element.get_text(strip=True)
                        if li_text:
                            text_parts.append(f"- {li_text}\n")
                        processed_elements.add(id(element))

                    elif element.name == "table":
                        # Extract table and convert to markdown format
                        table_markdown = self._extract_table_as_markdown(element)
                        if table_markdown:
                            text_parts.append(f"\n{table_markdown}\n")
                        # Mark all table descendants as processed
                        for descendant in element.descendants:
                            processed_elements.add(id(descendant))
                        processed_elements.add(id(element))

                # Join and clean up excessive whitespace
                text = "".join(text_parts)
                # Collapse multiple newlines into max 2
                import re

                text = re.sub(r"\n{3,}", "\n\n", text)

                return {"content": text.strip(), "sections": sections}

            return None

        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to extract content from {url}: {e}")
            return None

    def _fetch_page_content(self, url_info: dict[str, str]) -> dict[str, Any] | None:
        """Fetch and extract content from a single page.

        Args:
            url_info: Dictionary with 'url', 'product', and 'lastmod'

        Returns:
            Dictionary with extracted content, sections, and metadata or None
        """
        url = url_info["url"]

        # Check robots.txt
        if not self._can_fetch(url):
            logger.info(f"[DOC_SEARCH] Skipping {url} (disallowed by robots.txt)")
            return None

        try:
            # Fetch the page with proper User-Agent
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Extract main content with sections
            extracted = self._extract_main_content(response.text, url)

            if not extracted:
                logger.warning(f"[DOC_SEARCH] No content extracted from {url}")
                return None

            return {
                "url": url,
                "product": url_info["product"],
                "lastmod": url_info["lastmod"],
                "content": extracted["content"],
                "sections": extracted["sections"],
                "length": len(extracted["content"]),
                "html": response.text,  # Store raw HTML for parent-child chunking
            }

        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to fetch {url}: {e}")
            return None

    def _get_page_cache_path(self, url: str) -> Path:
        """Get cache file path for a URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.content_dir / f"{url_hash}.json"

    def _load_cached_page(self, url: str, lastmod: str | None) -> dict[str, Any] | None:
        """Load cached page content if still valid.

        Args:
            url: Page URL
            lastmod: Last modification date from sitemap

        Returns:
            Cached page data or None if cache invalid
        """
        cache_path = self._get_page_cache_path(url)
        if not cache_path.exists():
            return None

        try:
            cached = json.loads(cache_path.read_text())
            # Check if lastmod matches
            if lastmod and cached.get("lastmod") != lastmod:
                return None
            return cached
        except:
            return None

    def _save_cached_page(self, page_data: dict[str, Any]):
        """Save page content to cache."""
        try:
            cache_path = self._get_page_cache_path(page_data["url"])
            cache_path.write_text(json.dumps(page_data))
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to cache page: {e}")

    def _save_url_list(self, url_list: list[dict[str, str]]):
        """Save URL list to disk for resume capability."""
        try:
            self.url_list_file.write_text(json.dumps(url_list, indent=2))
            logger.debug(f"[DOC_SEARCH] Saved {len(url_list)} URLs to {self.url_list_file}")
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to save URL list: {e}")

    def _load_url_list(self) -> list[dict[str, str]] | None:
        """Load URL list from disk."""
        if not self.url_list_file.exists():
            return None
        try:
            url_list = json.loads(self.url_list_file.read_text())
            logger.info(f"[DOC_SEARCH] Loaded {len(url_list)} URLs from cache")
            return url_list
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to load URL list: {e}")
            return None

    def _save_chunks(self, chunks: list[Document]):
        """Save chunks to disk for resume capability."""
        try:
            # Convert Document objects to serializable dicts
            chunk_dicts = [{"page_content": chunk.page_content, "metadata": chunk.metadata} for chunk in chunks]
            self.chunks_file.write_text(json.dumps(chunk_dicts))
            logger.info(f"[DOC_SEARCH] Saved {len(chunks)} chunks to {self.chunks_file}")
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to save chunks: {e}")

    def _load_chunks(self) -> list[Document] | None:
        """Load chunks from disk."""
        if not self.chunks_file.exists():
            return None
        try:
            chunk_dicts = json.loads(self.chunks_file.read_text())
            chunks = [
                Document(page_content=chunk_dict["page_content"], metadata=chunk_dict["metadata"])
                for chunk_dict in chunk_dicts
            ]
            logger.info(f"[DOC_SEARCH] Loaded {len(chunks)} chunks from cache")
            return chunks
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to load chunks: {e}")
            return None

    def _save_embedding_progress(self, completed_count: int, total_count: int):
        """Save embedding progress."""
        try:
            progress = {"completed": completed_count, "total": total_count, "timestamp": datetime.now().isoformat()}
            self.embedding_progress_file.write_text(json.dumps(progress))
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to save embedding progress: {e}")

    def _load_embedding_progress(self) -> dict[str, Any] | None:
        """Load embedding progress."""
        if not self.embedding_progress_file.exists():
            return None
        try:
            return json.loads(self.embedding_progress_file.read_text())
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to load embedding progress: {e}")
            return None

    def _fetch_with_cache(self, url_info: dict[str, str]) -> dict[str, Any] | None:
        """Fetch page with caching support."""
        # Try cache first
        cached = self._load_cached_page(url_info["url"], url_info.get("lastmod"))
        if cached:
            return cached

        # Fetch fresh content
        page_data = self._fetch_page_content(url_info)
        if page_data:
            self._save_cached_page(page_data)

        return page_data

    def _split_into_sections(self, page_data: dict[str, Any]) -> list[Document]:
        """Split page content into parent-child semantic chunks.

        Uses semantic_chunk_html for token-aware hierarchical chunking.
        Stores parent chunks separately and indexes only child chunks.

        Args:
            page_data: Page data with HTML, content, sections, and metadata

        Returns:
            List of Document chunks (child chunks only, for indexing)
        """
        url = page_data["url"]
        product = page_data["product"]
        html = page_data.get("html")

        if not html:
            # Fallback to old method if HTML not available (shouldn't happen with new fetch)
            logger.warning(f"[DOC_SEARCH] No HTML available for {url}, using content fallback")
            content = page_data["content"]
            # Use simple text splitter
            if self.text_splitter is None:
                self._initialize_components()

            split_docs = self.text_splitter.split_text(content)
            return [
                Document(
                    page_content=chunk,
                    metadata={"url": url, "product": product, "source": "web", "lastmod": page_data.get("lastmod")},
                )
                for chunk in split_docs
            ]

        try:
            # Use semantic chunking to create parent-child hierarchy
            result = semantic_chunk_html(html, url)
            parents = result.get("parents", [])
            children = result.get("children", [])

            if not children:
                logger.warning(f"[DOC_SEARCH] No children chunks created for {url}")
                # Fallback to content-based splitting
                content = page_data["content"]
                if self.text_splitter is None:
                    self._initialize_components()
                split_docs = self.text_splitter.split_text(content)
                return [
                    Document(
                        page_content=chunk,
                        metadata={"url": url, "product": product, "source": "web", "lastmod": page_data.get("lastmod")},
                    )
                    for chunk in split_docs
                ]

            # Store parent chunks in the parent_chunks dict
            for parent in parents:
                chunk_id = parent["chunk_id"]
                self.parent_chunks[chunk_id] = {
                    "content": parent["content"],
                    "metadata": parent["metadata"],
                    "url": url,
                    "product": product,
                    "lastmod": page_data.get("lastmod"),
                }

            # Create LangChain Documents from child chunks
            child_docs = []
            for child in children:
                chunk_id = child["chunk_id"]
                parent_id = child["metadata"].parent_id

                # Store child-to-parent mapping
                self.child_to_parent[chunk_id] = parent_id

                # Create Document with enriched metadata
                doc = Document(
                    page_content=child["content"],
                    metadata={
                        "url": url,
                        "product": product,
                        "source": "web",
                        "lastmod": page_data.get("lastmod"),
                        "chunk_id": chunk_id,
                        "parent_id": parent_id,
                        "heading": child["metadata"].heading_path_joined,
                        "doc_type": child["metadata"].doc_type,
                        "version": child["metadata"].version,
                    },
                )
                child_docs.append(doc)

            logger.debug(f"[DOC_SEARCH] {url}: {len(parents)} parents, {len(children)} children")
            return child_docs

        except Exception as e:
            logger.error(f"[DOC_SEARCH] Semantic chunking failed for {url}: {e}")
            # Fallback to content-based splitting
            content = page_data["content"]
            if self.text_splitter is None:
                self._initialize_components()
            split_docs = self.text_splitter.split_text(content)
            return [
                Document(
                    page_content=chunk,
                    metadata={"url": url, "product": product, "source": "web", "lastmod": page_data.get("lastmod")},
                )
                for chunk in split_docs
            ]

    def _split_large_section(
        self, content: str, heading: str, anchor: str, chunk_size_tokens: int, overlap_tokens: int
    ) -> list[str]:
        """Split a large section into smaller token-based chunks with overlap.

        Args:
            content: Section content to split
            heading: Section heading for context
            anchor: Section anchor ID
            chunk_size_tokens: Maximum tokens per chunk
            overlap_tokens: Overlap tokens between chunks

        Returns:
            List of chunk strings
        """
        chunks = []

        # Use TokenTextSplitter for token-based splitting
        from langchain_text_splitters import TokenTextSplitter

        token_splitter = TokenTextSplitter(chunk_size=chunk_size_tokens, chunk_overlap=overlap_tokens)

        # Split the content
        split_docs = token_splitter.split_text(content)

        # Add heading context to each chunk
        for chunk_text in split_docs:
            # Only add heading if not already present
            if not chunk_text.strip().startswith(f"## {heading}"):
                chunk_with_context = f"## {heading}\n\n{chunk_text}"
            else:
                chunk_with_context = chunk_text
            chunks.append(chunk_with_context)

        return chunks

    def _fetch_pages(self, url_list: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Fetch page content from URLs using parallel fetching.

        Args:
            url_list: List of URL info dicts from sitemap

        Returns:
            List of page data dicts with content and sections
        """
        pages = []
        total = len(url_list)
        start_time = time.time()

        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info(f"[DOC_SEARCH] PHASE 2/4: Fetching {total:,} pages")
        logger.info(f"[DOC_SEARCH] Workers: {self.max_workers} parallel threads")
        logger.info("[DOC_SEARCH] " + "=" * 70)

        # Use ThreadPoolExecutor for parallel fetching
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all fetch tasks
            future_to_url = {executor.submit(self._fetch_with_cache, url_info): url_info for url_info in url_list}

            # Process completed tasks
            completed = 0
            failed = 0
            last_log_time = start_time

            for future in as_completed(future_to_url):
                completed += 1
                current_time = time.time()

                # Log progress every 50 pages or every 5 seconds
                if completed % 50 == 0 or (current_time - last_log_time) >= 5:
                    elapsed = current_time - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta_seconds = (total - completed) / rate if rate > 0 else 0
                    eta_mins = eta_seconds / 60

                    progress_pct = (completed / total) * 100
                    logger.info(
                        f"[DOC_SEARCH] [{progress_pct:5.1f}%] {completed}/{total} pages | "
                        f"Rate: {rate:.1f} pages/sec | ETA: {eta_mins:.1f} min"
                    )
                    last_log_time = current_time

                try:
                    page_data = future.result()
                    if page_data:
                        pages.append(page_data)
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    url_info = future_to_url[future]
                    logger.warning(f"[DOC_SEARCH] Failed to process {url_info['url']}: {e}")

        elapsed = time.time() - start_time
        logger.info("[DOC_SEARCH] " + "-" * 70)
        logger.info(f"[DOC_SEARCH] ✓ Fetched {len(pages)} pages successfully ({failed} failed) in {elapsed:.1f}s")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        return pages

    def _create_chunks(self, pages: list[dict[str, Any]]) -> list[Document]:
        """Create section-aware chunks from fetched pages.

        Args:
            pages: List of page data dicts with content and sections

        Returns:
            List of LangChain Document chunks
        """
        all_chunks = []
        total = len(pages)
        start_time = time.time()

        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info(f"[DOC_SEARCH] PHASE 3/4: Creating section-aware chunks from {total:,} pages")
        logger.info("[DOC_SEARCH] " + "=" * 70)

        last_log_time = start_time
        for idx, page_data in enumerate(pages, 1):
            current_time = time.time()

            # Log progress every 50 pages or every 5 seconds
            if idx % 50 == 0 or (current_time - last_log_time) >= 5:
                elapsed = current_time - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                eta_seconds = (total - idx) / rate if rate > 0 else 0
                eta_mins = eta_seconds / 60

                progress_pct = (idx / total) * 100
                logger.info(
                    f"[DOC_SEARCH] [{progress_pct:5.1f}%] {idx}/{total} pages | "
                    f"Chunks: {len(all_chunks)} | Rate: {rate:.1f} pages/sec | ETA: {eta_mins:.1f} min"
                )
                last_log_time = current_time

            try:
                page_chunks = self._split_into_sections(page_data)
                all_chunks.extend(page_chunks)
            except Exception as e:
                logger.warning(f"[DOC_SEARCH] Failed to chunk page {page_data.get('url', 'unknown')}: {e}")

        elapsed = time.time() - start_time
        avg_chunks_per_page = len(all_chunks) / total if total > 0 else 0
        logger.info("[DOC_SEARCH] " + "-" * 70)
        logger.info(
            f"[DOC_SEARCH] ✓ Created {len(all_chunks)} section-aware chunks from {total} pages in {elapsed:.1f}s"
        )
        logger.info(f"[DOC_SEARCH] Average: {avg_chunks_per_page:.1f} chunks per page")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        return all_chunks

    def _expand_query(self, query: str) -> str:
        """Expand query with domain-specific synonyms.

        Args:
            query: Original search query

        Returns:
            Expanded query with synonyms appended
        """
        if not self.enable_query_expansion:
            return query

        # Tokenize query (simple word splitting, lowercase)
        query_lower = query.lower()
        words = query_lower.split()

        # Find expansion terms (limit to max 5 total expansion terms to avoid overwhelming)
        expansion_terms = []
        max_total_expansions = 5

        for word in words:
            if len(expansion_terms) >= max_total_expansions:
                break

            if word in QUERY_EXPANSION_TERMS:
                # Add up to max_expansion_terms synonyms for this word
                synonyms = QUERY_EXPANSION_TERMS[word][: self.max_expansion_terms]
                for syn in synonyms:
                    if len(expansion_terms) < max_total_expansions:
                        expansion_terms.append(syn)

        if not expansion_terms:
            logger.debug("[DOC_SEARCH] No query expansion applied")
            return query

        # Append expansion terms to original query
        expanded = f"{query} {' '.join(expansion_terms)}"
        logger.debug(f"[DOC_SEARCH] Query expansion: '{query}' → added {len(expansion_terms)} terms")
        logger.debug(f"[DOC_SEARCH] Expanded query: '{expanded}'")

        return expanded

    def _rerank_results(self, query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Re-rank search results using cross-encoder.

        Args:
            query: Search query
            results: List of search results to re-rank

        Returns:
            Re-ranked list of results with updated scores
        """
        if not self.cross_encoder or not results:
            return results

        logger.debug(f"[DOC_SEARCH] Re-ranking {len(results)} results with cross-encoder...")

        # Prepare query-document pairs for scoring
        pairs = [[query, result["text"]] for result in results]

        # Score all pairs
        scores = self.cross_encoder.predict(pairs)

        # Update results with new scores, preserving URL boost
        for result, score in zip(results, scores):
            result["rerank_score"] = float(score)
            result["original_score"] = result["score"]

            # Apply URL boost to cross-encoder score (for release notes)
            base_url = result.get("url", "")
            boosted_score = float(score)

            # Check if this is a release notes URL
            is_release_notes = (
                "/release-notes/" in base_url or "/releases/" in base_url or "/updates/release-notes" in base_url
            )

            if is_release_notes:
                # Check if we have version info and this URL matches the exact version
                version_info = getattr(self, "_current_version_info", None)
                if version_info and version_info.get("is_version_query"):
                    version = version_info.get("version_major_minor") or version_info.get("version")
                    product = version_info.get("product")

                    # Check if URL contains the exact version (e.g., "v1_9_x" or "v1.9")
                    # Handle both underscore (v1_9_x) and dot (v1.9.x) formats
                    version_patterns = [
                        f"v{version.replace('.', '_')}",  # e.g., "v1_9"
                        f"v{version}",  # e.g., "v1.9"
                        f"/{version}.",  # e.g., "/1.9."
                        f"/{version}/",  # e.g., "/1.9/"
                    ]

                    # Also check product match
                    product_match = product and product in base_url.lower()
                    version_match = any(pattern in base_url for pattern in version_patterns)

                    if product_match and version_match:
                        # VERY STRONG boost for exact version match (4.0x = 300% boost)
                        boosted_score = boosted_score * 4.0
                        logger.debug(
                            f"[DOC_SEARCH]   🎯 Exact version match boost: {score:.3f} -> {boosted_score:.3f} | {base_url[:80]}"
                        )
                    else:
                        # Regular boost for release notes (2.0x = 100% boost)
                        boosted_score = boosted_score * 2.0
                        logger.debug(
                            f"[DOC_SEARCH]   URL boost applied: {score:.3f} -> {boosted_score:.3f} | {base_url[:80]}"
                        )
                else:
                    # Regular boost for release notes when not a version query (2.0x = 100% boost)
                    boosted_score = boosted_score * 2.0
                    logger.debug(
                        f"[DOC_SEARCH]   URL boost applied: {score:.3f} -> {boosted_score:.3f} | {base_url[:80]}"
                    )

            result["score"] = boosted_score

        # Sort by new scores (descending)
        reranked = sorted(results, key=lambda x: x["score"], reverse=True)

        logger.debug("[DOC_SEARCH] Re-ranking complete. Score changes:")
        for i, (orig, new) in enumerate(zip(results[:5], reranked[:5]), 1):
            logger.debug(
                f"[DOC_SEARCH]   Position {i}: score {orig['original_score']:.3f} -> {new['score']:.3f} | {new['url'][:60]}"
            )

        return reranked

    def _initialize_components(self):
        """Initialize LangChain components."""
        if self.embeddings is None:
            logger.info(f"[DOC_SEARCH] Loading embeddings model: {self.model_name}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name, model_kwargs={"device": "cpu"}, encode_kwargs={"normalize_embeddings": True}
            )

        if self.text_splitter is None:
            logger.info(f"[DOC_SEARCH] Creating text splitter (chunk_size={self.chunk_size})")
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )

        if self.enable_reranking and self.cross_encoder is None:
            logger.info(f"[DOC_SEARCH] Loading heavy cross-encoder for final ranking: {self.rerank_model}")
            self.cross_encoder = CrossEncoder(self.rerank_model)
            logger.info("[DOC_SEARCH] Heavy cross-encoder (L-12) loaded")

        if self.enable_reranking and self.light_cross_encoder is None:
            logger.info(
                f"[DOC_SEARCH] Loading lightweight cross-encoder for first-pass ranking: {self.light_rerank_model}"
            )
            self.light_cross_encoder = CrossEncoder(self.light_rerank_model)
            logger.info(
                f"[DOC_SEARCH] Lightweight cross-encoder (L-6) loaded (will reduce candidates to {self.light_rerank_top_k})"
            )

    def _build_index(self, url_list: list[dict[str, str]]):
        """Build FAISS index using LangChain with resume capability.

        Args:
            url_list: List of URL info dicts from sitemap
        """
        logger.info("[DOC_SEARCH] Building FAISS index")

        # Initialize components
        self._initialize_components()

        # Try to load cached chunks first
        chunks = self._load_chunks()

        if chunks is None:
            # Fetch pages
            logger.info("[DOC_SEARCH] No cached chunks found, fetching pages...")
            pages = self._fetch_pages(url_list)

            if not pages:
                logger.error("[DOC_SEARCH] No pages fetched!")
                return

            # Create section-aware chunks
            logger.info("[DOC_SEARCH] Creating section-aware chunks...")
            chunks = self._create_chunks(pages)
            logger.info(f"[DOC_SEARCH] Created {len(chunks)} section-aware chunks")

            # Save chunks to disk
            self._save_chunks(chunks)
        else:
            logger.info(f"[DOC_SEARCH] Using {len(chunks)} cached chunks")

        # Create FAISS index with batching for progress tracking
        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info(f"[DOC_SEARCH] PHASE 4/4: Generating embeddings for {len(chunks):,} chunks")
        logger.info("[DOC_SEARCH] This is usually the slowest phase (5-15 minutes)")
        logger.info("[DOC_SEARCH] " + "=" * 70)

        # Build index in batches
        batch_size = 10000  # Process 10k chunks at a time
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        embedding_start_time = time.time()

        for batch_idx in range(total_batches):
            batch_start_time = time.time()
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(chunks))
            batch_chunks = chunks[start_idx:end_idx]

            progress_pct = (start_idx / len(chunks)) * 100
            logger.info(
                f"[DOC_SEARCH] [{progress_pct:5.1f}%] Batch {batch_idx + 1}/{total_batches} | "
                f"Processing chunks {start_idx:,}-{end_idx:,} ({len(batch_chunks):,} chunks)"
            )

            if batch_idx == 0:
                # Create initial index
                self.vectorstore = FAISS.from_documents(batch_chunks, self.embeddings)
            else:
                # Add to existing index
                batch_vectorstore = FAISS.from_documents(batch_chunks, self.embeddings)
                self.vectorstore.merge_from(batch_vectorstore)

            # Save progress after each batch
            self.vectorstore.save_local(str(self.index_dir))
            self._save_embedding_progress(end_idx, len(chunks))

            # Calculate timing stats
            batch_elapsed = time.time() - batch_start_time
            total_elapsed = time.time() - embedding_start_time
            avg_batch_time = total_elapsed / (batch_idx + 1)
            remaining_batches = total_batches - (batch_idx + 1)
            eta_seconds = remaining_batches * avg_batch_time
            eta_mins = eta_seconds / 60

            logger.info(
                f"[DOC_SEARCH] ✓ Batch complete in {batch_elapsed:.1f}s | "
                f"Total: {end_idx:,}/{len(chunks):,} chunks | ETA: {eta_mins:.1f} min"
            )

        embedding_elapsed = time.time() - embedding_start_time
        logger.info("[DOC_SEARCH] " + "-" * 70)
        logger.info(
            f"[DOC_SEARCH] ✓ All embeddings generated in {embedding_elapsed:.1f}s ({embedding_elapsed/60:.1f} min)"
        )
        logger.info(f"[DOC_SEARCH] ✓ {len(chunks):,} chunks indexed successfully")
        logger.info("[DOC_SEARCH] " + "=" * 70)

    def _load_index(self) -> bool:
        """Load FAISS index from disk and create hybrid retriever."""
        index_path = self.index_dir / "index.faiss"

        if not index_path.exists():
            logger.warning("[DOC_SEARCH] Index file not found")
            return False

        try:
            self._initialize_components()

            # Load FAISS index
            logger.info("[DOC_SEARCH] Loading FAISS index from disk...")
            self.vectorstore = FAISS.load_local(
                str(self.index_dir), self.embeddings, allow_dangerous_deserialization=True
            )
            logger.info("[DOC_SEARCH] Index loaded successfully")

            # Load chunks for BM25
            logger.info("[DOC_SEARCH] Loading chunks for BM25...")
            self.chunks = self._load_chunks()
            if not self.chunks:
                logger.warning("[DOC_SEARCH] No chunks loaded, BM25 disabled")
                return True

            # Create BM25 retriever
            logger.info(f"[DOC_SEARCH] Creating BM25 retriever with {len(self.chunks)} chunks...")
            self.bm25_retriever = BM25Retriever.from_documents(self.chunks)
            self.bm25_retriever.k = 10  # Retrieve top 10 for BM25

            # Create FAISS retriever
            faiss_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 10})

            # Create ensemble (hybrid) retriever
            logger.info("[DOC_SEARCH] Creating hybrid retriever (50% BM25, 50% semantic)...")
            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[self.bm25_retriever, faiss_retriever],
                weights=[0.5, 0.5],  # 50% keyword, 50% semantic (balanced for technical queries)
            )

            logger.info("[DOC_SEARCH] Hybrid search enabled!")
            return True

        except Exception as e:
            logger.error(f"[DOC_SEARCH] Failed to load index: {e}")
            return False

    def initialize(self, force_update: bool = False):
        """Initialize the search index with resume capability.

        Args:
            force_update: Force rebuild even if cache is fresh
        """
        init_start_time = time.time()
        logger.info("")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info("[DOC_SEARCH] HASHICORP DOCUMENTATION SEARCH - INDEX INITIALIZATION")
        logger.info("[DOC_SEARCH] " + "=" * 70)

        # Check if we need to update
        needs_update = force_update or self._needs_update()

        # Check if version changed (which requires URL rediscovery)
        metadata = self._load_metadata()
        current_version = "3.1.0-release-notes"
        version_changed = metadata.get("version") != current_version

        if not needs_update:
            if self._load_index():
                logger.info("[DOC_SEARCH] Using cached index")
                return
            else:
                logger.warning("[DOC_SEARCH] Failed to load cache, rebuilding")
                needs_update = True

        # Try to resume from saved URL list (but not if version changed - need to rediscover)
        url_list = None if version_changed else self._load_url_list()

        # If version changed, also invalidate chunks cache (new URLs need to be fetched)
        if version_changed and self.chunks_file.exists():
            logger.info("[DOC_SEARCH] Version changed, clearing chunks cache to fetch new pages...")
            self.chunks_file.unlink()

        if url_list is None or force_update:
            logger.info("[DOC_SEARCH] " + "=" * 70)
            logger.info("[DOC_SEARCH] PHASE 1/4: Discovering URLs")
            logger.info("[DOC_SEARCH] " + "=" * 70)

            # Download sitemap
            logger.info("[DOC_SEARCH] Downloading sitemap...")
            if not self._download_sitemap():
                logger.error("[DOC_SEARCH] Failed to download sitemap")
                return

            # Parse sitemap
            logger.info("[DOC_SEARCH] Parsing sitemap...")
            url_list = self._parse_sitemap()
            if not url_list:
                logger.error("[DOC_SEARCH] No URLs found in sitemap")
                return
            logger.info(f"[DOC_SEARCH] ✓ Found {len(url_list):,} URLs in sitemap")

            # Discover validated-designs pages (not in sitemap)
            validated_designs = self._discover_validated_designs()
            if validated_designs:
                logger.info(f"[DOC_SEARCH] ✓ Adding {len(validated_designs):,} validated-designs pages")
                # Merge with sitemap, deduplicating by URL
                all_urls = {url_info["url"]: url_info for url_info in url_list}
                for url_info in validated_designs:
                    all_urls[url_info["url"]] = url_info
                url_list = list(all_urls.values())
                logger.info(f"[DOC_SEARCH] ✓ Total: {len(url_list):,} unique URLs")

            # Discover version-specific release notes (not in sitemap)
            release_notes = self._discover_release_notes()
            if release_notes:
                logger.info(f"[DOC_SEARCH] ✓ Adding {len(release_notes):,} release notes pages")
                # Merge with existing URLs, deduplicating by URL
                all_urls = {url_info["url"]: url_info for url_info in url_list}
                for url_info in release_notes:
                    all_urls[url_info["url"]] = url_info
                url_list = list(all_urls.values())
                logger.info(f"[DOC_SEARCH] ✓ Total: {len(url_list):,} unique URLs")

            # Save URL list for resume capability
            self._save_url_list(url_list)
            logger.info("[DOC_SEARCH] " + "=" * 70)
        else:
            logger.info(f"[DOC_SEARCH] ✓ Resuming with {len(url_list):,} URLs from cache")

        # Check if we have cached chunks (scraping already done)
        chunks = self._load_chunks()
        if chunks:
            logger.info(f"[DOC_SEARCH] ✓ Found {len(chunks):,} cached chunks (Phases 2-3 already complete)")

        # Check embedding progress
        progress = self._load_embedding_progress()
        if progress:
            logger.info(
                f"[DOC_SEARCH] ✓ Previous embedding progress: {progress['completed']:,}/{progress['total']:,} chunks"
            )
            logger.info(f"[DOC_SEARCH] Last saved: {progress['timestamp']}")

        # Build index (will resume from cache if available)
        if not chunks:
            logger.info(f"[DOC_SEARCH] Building index from {len(url_list):,} URLs (Phases 2-4)...")
        self._build_index(url_list)

        # Update metadata
        metadata = {
            "version": "3.1.0-release-notes",
            "last_update": datetime.now().isoformat(),
            "page_count": len(url_list),
            "model_name": self.model_name,
            "chunk_size_tokens": self.chunk_size,  # Now tokens, not chars
            "chunk_overlap_tokens": self.chunk_overlap,
        }
        self._save_metadata(metadata)

        # Final summary
        init_elapsed = time.time() - init_start_time
        logger.info("")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info("[DOC_SEARCH] ✅ INDEX INITIALIZATION COMPLETE")
        logger.info(f"[DOC_SEARCH] Total time: {init_elapsed:.1f}s ({init_elapsed/60:.1f} minutes)")
        logger.info(f"[DOC_SEARCH] Pages indexed: {len(url_list):,}")
        logger.info(f"[DOC_SEARCH] Model: {self.model_name}")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        logger.info("")

    def _detect_version_query(self, query: str) -> dict[str, Any] | None:
        """Detect version-specific queries and extract product/version metadata.

        Args:
            query: Search query string

        Returns:
            Dictionary with product, version, and flags, or None if not a version query
        """
        query_lower = query.lower()

        # Pattern 1: "what's new in {product} {version}" or "{product} {version}"
        # Matches: vault 1.20, consul 1.21, nomad 1.9, boundary 0.18, terraform 1.10
        version_pattern = r"(vault|consul|nomad|boundary|terraform|waypoint|packer|vagrant)\s+v?(\d+\.\d+(?:\.\d+)?)"
        match = re.search(version_pattern, query_lower)

        if match:
            product = match.group(1)
            version = match.group(2)
            logger.debug(f"[DOC_SEARCH] ✓ Detected version query: product={product}, version={version}")
            return {
                "product": product,
                "version": version,
                "is_version_query": True,
                "version_major_minor": ".".join(version.split(".")[:2]),  # e.g., "1.20" from "1.20.3"
            }

        # Pattern 2: "latest {product}" or "{product} latest"
        latest_pattern = r"latest\s+(vault|consul|nomad|boundary|terraform|waypoint|packer|vagrant)|(vault|consul|nomad|boundary|terraform|waypoint|packer|vagrant)\s+latest"
        match = re.search(latest_pattern, query_lower)

        if match:
            product = match.group(1) or match.group(2)
            logger.debug(f"[DOC_SEARCH] ✓ Detected 'latest' query: product={product}")
            return {"product": product, "version": "latest", "is_version_query": True, "is_latest_query": True}

        return None

    def _prefilter_version_candidates(
        self, docs: list[Document], version_info: dict[str, Any], max_candidates: int = 100
    ) -> list[Document]:
        """Pre-filter candidates for version queries to reduce re-ranking time.

        For version queries, we can dramatically reduce the candidate pool before
        expensive cross-encoder re-ranking by prioritizing documents with exact
        version matches in their URLs.

        Args:
            docs: List of documents from hybrid search
            version_info: Version query metadata from _detect_version_query()
            max_candidates: Maximum candidates to return for re-ranking (default: 100)

        Returns:
            Filtered list of documents prioritizing version-specific URLs
        """
        version = version_info.get("version_major_minor") or version_info.get("version")
        product = version_info.get("product")

        if not version or not product:
            return docs[:max_candidates]

        # Build version pattern variations
        # Different products use different URL formats:
        # - Nomad: /v1_9_x or /v1-9-x
        # - Vault: /v1.20.x
        # - Consul: /v1_21_x or /v1.21.x
        version_patterns = [
            f"v{version.replace('.', '_')}",  # e.g., "v1_9" or "v1_20"
            f"v{version}",  # e.g., "v1.9" or "v1.20"
            f"/v{version}.",  # e.g., "/v1.9." or "/v1.20."
            f"/{version}.",  # e.g., "/1.9." or "/1.20."
            f"/{version}/",  # e.g., "/1.9/" or "/1.20/"
        ]

        # Split documents into priority groups
        exact_matches = []  # URLs with exact version match
        top_candidates = []  # Top-scored from hybrid search

        for i, doc in enumerate(docs):
            url = doc.metadata.get("url", "")

            # Check for exact version match
            has_version_match = any(pattern in url for pattern in version_patterns)

            if has_version_match:
                exact_matches.append(doc)
            elif i < max_candidates // 2:  # Keep top half of max_candidates as backup
                top_candidates.append(doc)

        # Combine: exact matches first, then top candidates
        filtered = exact_matches + top_candidates

        # Limit to max_candidates
        filtered = filtered[:max_candidates]

        logger.debug(
            f"[DOC_SEARCH] 🎯 Pre-filtered version candidates: {len(docs)} → {len(filtered)} "
            f"({len(exact_matches)} exact matches + {len(top_candidates)} top candidates)"
        )

        return filtered

    def _light_rerank(self, query: str, results: list[dict[str, Any]], top_k: int = 80) -> list[dict[str, Any]]:
        """Fast first-pass reranking using lightweight cross-encoder.

        Reduces candidate count before heavy cross-encoder reranking.
        This is the first stage of two-stage reranking (Phase 2).

        Args:
            query: Search query
            results: List of search results to rerank
            top_k: Number of top results to keep

        Returns:
            Top k results after lightweight reranking
        """
        if not self.light_cross_encoder or not results:
            return results

        logger.debug(f"[DOC_SEARCH] 🔸 Stage 1: Lightweight reranking {len(results)} results → top {top_k}")

        # Prepare query-document pairs for scoring
        pairs = [[query, result["text"]] for result in results]

        # Score all pairs with lightweight model (fast)
        scores = self.light_cross_encoder.predict(pairs)

        # Update results with lightweight scores
        for result, score in zip(results, scores):
            result["light_rerank_score"] = float(score)

        # Sort by lightweight scores (descending)
        reranked = sorted(results, key=lambda x: x["light_rerank_score"], reverse=True)

        # Return top k
        top_results = reranked[:top_k]

        logger.debug(f"[DOC_SEARCH] ✓ Stage 1 complete: kept top {len(top_results)} candidates")

        return top_results

    def search(self, query: str, top_k: int = 5, product_filter: str | None = None) -> list[dict[str, Any]]:
        """Search the index using hybrid search (BM25 + semantic) with optional query expansion.

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product name to filter results

        Returns:
            List of search results with text, metadata, and score
        """
        logger.debug("[DOC_SEARCH] === SEARCH QUERY ===")
        logger.debug(f"[DOC_SEARCH] Original query: '{query}'")
        logger.debug(f"[DOC_SEARCH] top_k: {top_k}")
        logger.debug(f"[DOC_SEARCH] product_filter: {product_filter}")

        if self.vectorstore is None:
            logger.error("[DOC_SEARCH] Vector store not initialized")
            return []

        # Detect version-specific queries
        version_info = self._detect_version_query(query)
        # Store version info as instance variable so _rerank_results can access it
        self._current_version_info = version_info

        # Expand query with domain synonyms (if enabled)
        original_query = query
        query = self._expand_query(query)

        # Use hybrid search if available, otherwise fall back to FAISS only
        if self.ensemble_retriever is not None:
            logger.debug("[DOC_SEARCH] Using hybrid search (BM25 + semantic)")
            # EnsembleRetriever doesn't support metadata filtering,
            # so retrieve more results and filter afterward
            # Retrieve many more when filtering (product filter removes ~80% of results)
            # If re-ranking enabled, retrieve rerank_top_k candidates for re-scoring
            if self.enable_reranking:
                # For version queries, retrieve MORE candidates (20x instead of 10x = 1600 candidates)
                # This ensures version-specific release notes have a better chance of being retrieved
                if version_info and version_info.get("is_version_query"):
                    k = self.rerank_top_k * 20 if product_filter else self.rerank_top_k * 2
                    logger.debug(
                        f"[DOC_SEARCH] ⚡ Version query detected: increased to {k} candidates (20x multiplier)"
                    )
                else:
                    k = self.rerank_top_k * 10 if product_filter else self.rerank_top_k
                logger.debug(f"[DOC_SEARCH] Re-ranking enabled: retrieving {k} candidates for cross-encoder")
            else:
                k = top_k * 10 if product_filter else top_k * 3

            # Update k for both retrievers
            self.bm25_retriever.k = k
            self.ensemble_retriever.retrievers[1].search_kwargs["k"] = k

            docs = self.ensemble_retriever.invoke(query)
            logger.debug(f"[DOC_SEARCH] Ensemble retriever returned {len(docs)} documents")

            # Filter by product if specified
            if product_filter:
                before_filter = len(docs)
                docs = [d for d in docs if d.metadata.get("product", "").lower() == product_filter.lower()]
                logger.debug(
                    f"[DOC_SEARCH] After product filter ({product_filter}): {len(docs)} docs (removed {before_filter - len(docs)})"
                )

            # Pre-filter for version queries to reduce re-ranking time
            if version_info and version_info.get("is_version_query") and self.enable_reranking:
                docs = self._prefilter_version_candidates(docs, version_info, max_candidates=100)

            # Format results (ensemble doesn't return scores, so assign based on rank)
            results = []
            for idx, doc in enumerate(docs):
                # Score based on rank with better differentiation
                # Exponential decay: 1.0, 0.91, 0.83, 0.75, 0.68...
                rank_score = 1.0 / (1.0 + idx * 0.1)

                # Build URL with anchor if available
                base_url = doc.metadata.get("url", "")
                section_anchor = doc.metadata.get("section_anchor", "")
                url = f"{base_url}#{section_anchor}" if section_anchor else base_url

                # Boost validated-designs URLs (authoritative content)
                if "validated-designs" in base_url:
                    # Modest boost for authoritative docs (1.15x = 15% boost)
                    rank_score = rank_score * 1.15

                # Boost release notes URLs (version-specific documentation)
                if "/release-notes/" in base_url or "/releases/" in base_url or "/updates/release-notes" in base_url:
                    # Strong boost for release notes (2.0x = 100% boost)
                    rank_score = rank_score * 2.0

                # Cap at 1.0 for cleaner presentation
                rank_score = min(1.0, rank_score)

                results.append(
                    {
                        "text": doc.page_content,
                        "url": url,
                        "product": doc.metadata.get("product", "unknown"),
                        "source": doc.metadata.get("source", "web"),
                        "score": float(rank_score),
                        "distance": 0.0,  # Not applicable for hybrid
                        "section_heading": doc.metadata.get("section_heading", ""),
                    }
                )

            # Re-sort by boosted scores (validated-designs should rank slightly higher)
            results.sort(key=lambda x: x["score"], reverse=True)

            # Deduplicate by base URL (keep highest-scoring chunk per page, but multiple sections per page allowed)
            # We keep top 2 sections per page to provide context
            url_counts = {}
            deduplicated_results = []
            for r in results:
                # Extract base URL (without anchor)
                base_url = r["url"].split("#")[0]
                count = url_counts.get(base_url, 0)

                # Keep top 2 sections per page
                if count < 2:
                    url_counts[base_url] = count + 1
                    deduplicated_results.append(r)

            results = deduplicated_results

            logger.debug(f"[DOC_SEARCH] After deduplication: {len(results)} results (max 2 sections per page)")

            # Apply two-stage re-ranking if enabled (Phase 2)
            if self.enable_reranking:
                # Stage 1: Lightweight reranking to reduce candidates (e.g., 535 → 80)
                if self.light_cross_encoder:
                    results = self._light_rerank(original_query, results, top_k=self.light_rerank_top_k)

                # Stage 2: Heavy reranking for final ranking (e.g., 80 → top_k)
                if self.cross_encoder:
                    results = self._rerank_results(original_query, results)

            # Limit to top_k after re-ranking
            results = results[:top_k]

            logger.debug(f"[DOC_SEARCH] Final results (top_k={top_k}):")
            for i, r in enumerate(results, 1):
                is_vd = "validated-designs" in r["url"]
                rerank_info = f" [rerank={r.get('rerank_score', 0):.3f}]" if "rerank_score" in r else ""
                logger.debug(f"[DOC_SEARCH]   {i}. [score={r['score']:.3f}]{rerank_info} [VD={is_vd}] {r['url'][:80]}")
                logger.debug(f"[DOC_SEARCH]      Content preview: {r['text'][:150]}...")

        else:
            logger.debug("[DOC_SEARCH] Using semantic-only search (FAISS)")
            # Fall back to pure semantic search with filtering
            # If re-ranking enabled, retrieve more candidates for re-scoring
            if self.enable_reranking:
                k = self.rerank_top_k * 2 if product_filter else self.rerank_top_k
                logger.debug(f"[DOC_SEARCH] Re-ranking enabled: retrieving {k} candidates for cross-encoder")
            else:
                k = top_k * 2 if product_filter else top_k

            if product_filter:
                filter_dict = {"product": product_filter.lower()}
                docs_and_scores = self.vectorstore.similarity_search_with_score(query, k=k, filter=filter_dict)
            else:
                docs_and_scores = self.vectorstore.similarity_search_with_score(query, k=k)

            # Format results
            results = []
            for doc, score in docs_and_scores:
                # Convert L2 distance to similarity score
                similarity = 1.0 / (1.0 + score)

                # Build URL with anchor if available
                base_url = doc.metadata.get("url", "")
                section_anchor = doc.metadata.get("section_anchor", "")
                url = f"{base_url}#{section_anchor}" if section_anchor else base_url

                results.append(
                    {
                        "text": doc.page_content,
                        "url": url,
                        "product": doc.metadata.get("product", "unknown"),
                        "source": doc.metadata.get("source", "web"),
                        "score": float(similarity),
                        "distance": float(score),
                        "section_heading": doc.metadata.get("section_heading", ""),
                    }
                )

            # Deduplicate by base URL (keep highest-scoring chunk per page, but multiple sections per page allowed)
            # We keep top 2 sections per page to provide context
            url_counts = {}
            deduplicated_results = []
            for r in results:
                # Extract base URL (without anchor)
                base_url = r["url"].split("#")[0]
                count = url_counts.get(base_url, 0)

                # Keep top 2 sections per page
                if count < 2:
                    url_counts[base_url] = count + 1
                    deduplicated_results.append(r)

            results = deduplicated_results

            logger.debug(f"[DOC_SEARCH] After deduplication: {len(results)} results (max 2 sections per page)")

            # Apply two-stage re-ranking if enabled (Phase 2)
            if self.enable_reranking:
                # Stage 1: Lightweight reranking to reduce candidates (e.g., 535 → 80)
                if self.light_cross_encoder:
                    results = self._light_rerank(original_query, results, top_k=self.light_rerank_top_k)

                # Stage 2: Heavy reranking for final ranking (e.g., 80 → top_k)
                if self.cross_encoder:
                    results = self._rerank_results(original_query, results)

            # Limit to top_k after re-ranking
            results = results[:top_k]

        logger.info(f"[DOC_SEARCH] Found {len(results)} results for: {query}")
        logger.debug(f"[DOC_SEARCH] === FINAL RESULTS ({len(results)} total) ===")
        for i, r in enumerate(results, 1):
            logger.debug(f"[DOC_SEARCH] Result #{i}: {r['product'].upper()} - {r['url']}")
            logger.debug(f"[DOC_SEARCH]   Score: {r['score']:.3f}, Length: {len(r['text'])} chars")
        logger.debug("[DOC_SEARCH] === END SEARCH RESULTS ===")
        return results


# Global instance
_doc_search_index: HashiCorpDocSearchIndex | None = None


def get_doc_search_index() -> HashiCorpDocSearchIndex:
    """Get or create the global doc search index."""
    global _doc_search_index
    if _doc_search_index is None:
        _doc_search_index = HashiCorpDocSearchIndex()
    return _doc_search_index


def initialize_doc_search(force_update: bool = False, max_pages: int | None = None):
    """Initialize the doc search index (call on startup).

    Args:
        force_update: Force rebuild even if cache is fresh
        max_pages: Limit number of pages (for testing)
    """
    global _doc_search_index
    if max_pages is not None:
        _doc_search_index = HashiCorpDocSearchIndex(max_pages=max_pages)

    index = get_doc_search_index()
    index.initialize(force_update=force_update)


def search_docs(query: str, top_k: int = 5, product: str = "") -> str:
    """Search HashiCorp developer documentation.

    Args:
        query: Search query
        top_k: Number of results to return
        product: Optional product filter

    Returns:
        Formatted search results
    """
    index = get_doc_search_index()

    # Auto-initialize if not already done
    if index.vectorstore is None:
        logger.info("[DOC_SEARCH] Auto-initializing index on first search")
        index.initialize()

    # Check again after initialization attempt
    if index.vectorstore is None:
        return "Documentation search index not initialized. Please wait for initialization."

    # Perform search
    results = index.search(query, top_k=top_k, product_filter=product if product else None)

    if not results:
        return f"No results found in HashiCorp developer documentation for: '{query}'"

    # Format output
    output = [f"Found {len(results)} result(s) in HashiCorp Developer Documentation:\n"]

    for idx, result in enumerate(results, 1):
        output.append(f"\n{idx}. [{result['product'].upper()}]")
        output.append(f"   URL: {result['url']}")
        output.append(f"   Relevance: {result['score']:.2f}")

        # Show preview
        text_preview = result["text"][:900]
        if len(result["text"]) > 900:
            text_preview += "..."

        output.append(f"   Content: {text_preview}")
        output.append("")

    return "\n".join(output)
