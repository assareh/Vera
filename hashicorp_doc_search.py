"""HashiCorp Developer Documentation Web Crawler - LangChain Implementation.

Crawls developer.hashicorp.com using the sitemap, extracts content from HTML pages,
and builds a searchable FAISS index using LangChain.
"""
import os
import json
import logging
import time
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import requests
from bs4 import BeautifulSoup
import tiktoken

# LangChain imports
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging

# Add console handler with formatting if not already added
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Sitemap URL
SITEMAP_URL = "https://developer.hashicorp.com/server-sitemap.xml"

# User agent for crawling
USER_AGENT = "IvanBot/1.0 (+https://github.com/yourusername/ivan; bot@example.com)"


class HashiCorpDocSearchIndex:
    """Manages web documentation crawling, indexing, and semantic search using LangChain."""

    def __init__(
        self,
        cache_dir: str = "./hashicorp_web_docs",
        model_name: str = "all-MiniLM-L6-v2",
        update_check_interval_hours: int = 168,  # 7 days
        chunk_size: int = 800,  # Default: tokens for concept/how-to docs
        chunk_overlap: int = 120,  # Default: ~15% overlap
        max_pages: Optional[int] = None,  # For testing, limit pages crawled
        rate_limit_delay: float = 0.05,  # Delay between requests (seconds)
        max_workers: int = 10  # Parallel workers for fetching
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

        # LangChain components
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.vectorstore: Optional[FAISS] = None
        self.text_splitter: Optional[RecursiveCharacterTextSplitter] = None
        self.bm25_retriever: Optional[BM25Retriever] = None
        self.ensemble_retriever: Optional[EnsembleRetriever] = None
        self.chunks: Optional[List[Document]] = None  # Store chunks for BM25

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

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from cache."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except Exception as e:
                logger.warning(f"[DOC_SEARCH] Failed to load metadata: {e}")
        return {}

    def _save_metadata(self, metadata: Dict[str, Any]):
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
        current_version = "3.0.0-token-adaptive"  # Token-based adaptive chunking by doc type
        if metadata.get("version") != current_version:
            logger.info(f"[DOC_SEARCH] Index version changed (old: {metadata.get('version', 'unknown')}, new: {current_version}), needs rebuild")
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

    def _parse_sitemap(self) -> List[Dict[str, str]]:
        """Parse sitemap XML and extract URLs with metadata."""
        if not self.sitemap_file.exists():
            logger.error("[DOC_SEARCH] Sitemap file not found")
            return []

        try:
            tree = ET.parse(self.sitemap_file)
            root = tree.getroot()

            # Handle XML namespace
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            urls = []
            for url_elem in root.findall('ns:url', namespace):
                loc = url_elem.find('ns:loc', namespace)
                lastmod = url_elem.find('ns:lastmod', namespace)

                if loc is not None:
                    url = loc.text
                    # Normalize URL (remove anchors if present)
                    url = self._normalize_url(url)
                    parsed = urlparse(url)
                    path_parts = parsed.path.strip('/').split('/')

                    # Extract product from URL path
                    product = path_parts[0] if path_parts else "unknown"

                    urls.append({
                        "url": url,
                        "product": product,
                        "lastmod": lastmod.text if lastmod is not None else None
                    })

            logger.info(f"[DOC_SEARCH] Parsed {len(urls)} URLs from sitemap")

            if self.max_pages:
                urls = urls[:self.max_pages]
                logger.info(f"[DOC_SEARCH] Limited to {self.max_pages} pages for testing")

            return urls

        except Exception as e:
            logger.error(f"[DOC_SEARCH] Failed to parse sitemap: {e}")
            return []

    def _discover_validated_designs(self) -> List[Dict[str, str]]:
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
            headers = {'User-Agent': USER_AGENT}

            logger.debug("[DOC_SEARCH] Requesting validated-designs index page...")
            response = requests.get(f"{base_url}/validated-designs", headers=headers, timeout=30)
            response.raise_for_status()
            logger.debug(f"[DOC_SEARCH] Got response: {response.status_code}, {len(response.text)} bytes")

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all links to validated-designs guides
            guide_links = set()
            for link in soup.find_all('a', href=True):
                href = link['href']

                # Skip external links and non-http(s) links
                if href.startswith('http') and not href.startswith(base_url):
                    continue
                if href.startswith(('mailto:', 'tel:', '#')):
                    continue

                # Make absolute URL first
                if href.startswith('/'):
                    href = base_url + href
                elif not href.startswith('http'):
                    # Relative URL
                    href = urljoin(f"{base_url}/validated-designs", href)

                # NOW check if it's a validated-designs URL
                if '/validated-designs/' in href:
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
                    logger.info(f"[DOC_SEARCH] [{progress_pct:5.1f}%] Crawling guide {idx}/{len(guide_links)}: {guide_url}")
                    time.sleep(self.rate_limit_delay)

                    response = requests.get(guide_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    logger.debug(f"[DOC_SEARCH] Got guide page: {len(response.text)} bytes")

                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find all links within this guide
                    links_found = 0
                    for link in soup.find_all('a', href=True):
                        href = link['href']

                        # Skip external links and non-http(s) links
                        if href.startswith('http') and not href.startswith(base_url):
                            continue
                        if href.startswith(('mailto:', 'tel:', '#')):
                            continue

                        # Make absolute URL first
                        if href.startswith('/'):
                            href = base_url + href
                        elif not href.startswith('http'):
                            # Relative URL - resolve relative to guide_url
                            href = urljoin(guide_url, href)

                        # NOW check if it's a validated-designs URL
                        if '/validated-designs/' in href:
                            # Normalize URL (remove anchors)
                            href = self._normalize_url(href)

                            # Extract product from URL
                            path_parts = href.replace(base_url, '').strip('/').split('/')
                            product = path_parts[1].split('-')[0] if len(path_parts) > 1 else "unknown"

                            discovered_urls.append({
                                "url": href,
                                "product": product,
                                "lastmod": None
                            })
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

    def _get_chunk_config(self, url: str) -> Dict[str, int]:
        """Get adaptive chunk configuration based on document type.

        Args:
            url: Page URL to determine type

        Returns:
            Dictionary with 'size' (tokens) and 'overlap' (tokens)
        """
        # API reference and CLI command pages - smaller chunks
        if '/api/' in url or '/api-docs/' in url or '/commands/' in url:
            return {'size': 500, 'overlap': 75}  # ~15% overlap

        # Configuration-heavy pages - medium chunks with more overlap
        elif '/configuration/' in url or re.search(r'/docs/.*config', url):
            return {'size': 400, 'overlap': 80}  # ~20% overlap

        # Release notes and changelogs - medium chunks
        elif '/release-notes' in url or '/changelog' in url or '/releases/' in url:
            return {'size': 600, 'overlap': 60}  # ~10% overlap

        # Tutorials and guides - larger chunks
        elif '/tutorials/' in url or '/guides/' in url:
            return {'size': 900, 'overlap': 135}  # ~15% overlap

        # Concept/how-to documentation (default) - standard chunks
        else:
            return {'size': 800, 'overlap': 120}  # ~15% overlap

    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt.

        Override robots.txt for validated-designs content as requested.

        Args:
            url: URL to check

        Returns:
            True if allowed, False otherwise
        """
        # Always allow validated-designs pages regardless of robots.txt
        if '/validated-designs' in url or '/validated-patterns' in url:
            return True

        try:
            return self.robot_parser.can_fetch(USER_AGENT, url)
        except:
            # If robots.txt parsing fails, be conservative and allow
            return True

    def _extract_main_content(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        """Extract main documentation content from HTML page with section anchors.

        Preserves structure including headings, anchors, and code blocks for better context.

        Args:
            html: Raw HTML content
            url: URL of the page (for logging)

        Returns:
            Dictionary with 'content' (text) and 'sections' (list of section info) or None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()

            # Try to find main content area
            # HashiCorp docs typically use main, article, or specific content divs
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', {'id': 'content'}) or
                soup.find('div', {'class': 'content'}) or
                soup.body
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

                    if element.name == 'h1':
                        heading_text = element.get_text(strip=True)
                        anchor_id = element.get('id', '')
                        text_parts.append(f"\n# {heading_text}\n")
                        if anchor_id:
                            sections.append({
                                'level': 1,
                                'text': heading_text,
                                'anchor': anchor_id,
                                'position': len(''.join(text_parts))
                            })
                        processed_elements.add(id(element))

                    elif element.name == 'h2':
                        heading_text = element.get_text(strip=True)
                        anchor_id = element.get('id', '')
                        text_parts.append(f"\n## {heading_text}\n")
                        current_h2_anchor = anchor_id  # Track for H3s
                        if anchor_id:
                            current_section = {
                                'level': 2,
                                'text': heading_text,
                                'anchor': anchor_id,
                                'position': len(''.join(text_parts))
                            }
                            sections.append(current_section)
                        processed_elements.add(id(element))

                    elif element.name == 'h3':
                        heading_text = element.get_text(strip=True)
                        anchor_id = element.get('id', '')
                        text_parts.append(f"\n### {heading_text}\n")
                        # Use H3 anchor if available, otherwise fall back to parent H2
                        section_anchor = anchor_id if anchor_id else current_h2_anchor
                        if section_anchor:
                            sections.append({
                                'level': 3,
                                'text': heading_text,
                                'anchor': section_anchor,
                                'position': len(''.join(text_parts)),
                                'parent_anchor': current_h2_anchor if anchor_id else None
                            })
                        processed_elements.add(id(element))

                    elif element.name in ['pre', 'code'] and element.parent.name != 'pre':
                        # Preserve code blocks (avoid duplicating code inside pre)
                        code_text = element.get_text(strip=False)
                        if code_text.strip():
                            text_parts.append(f"\n```\n{code_text}\n```\n")
                        processed_elements.add(id(element))

                    elif element.name == 'p' and not any(p.name in ['pre', 'code'] for p in element.parents):
                        para_text = element.get_text(strip=True)
                        if para_text:
                            text_parts.append(f"{para_text}\n")
                        processed_elements.add(id(element))

                    elif element.name == 'li' and element.parent.name in ['ul', 'ol']:
                        li_text = element.get_text(strip=True)
                        if li_text:
                            text_parts.append(f"- {li_text}\n")
                        processed_elements.add(id(element))

                # Join and clean up excessive whitespace
                text = ''.join(text_parts)
                # Collapse multiple newlines into max 2
                import re
                text = re.sub(r'\n{3,}', '\n\n', text)

                return {
                    'content': text.strip(),
                    'sections': sections
                }

            return None

        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to extract content from {url}: {e}")
            return None

    def _fetch_page_content(self, url_info: Dict[str, str]) -> Optional[Dict[str, Any]]:
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
            headers = {'User-Agent': USER_AGENT}
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
                "length": len(extracted["content"])
            }

        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to fetch {url}: {e}")
            return None

    def _get_page_cache_path(self, url: str) -> Path:
        """Get cache file path for a URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.content_dir / f"{url_hash}.json"

    def _load_cached_page(self, url: str, lastmod: Optional[str]) -> Optional[Dict[str, Any]]:
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

    def _save_cached_page(self, page_data: Dict[str, Any]):
        """Save page content to cache."""
        try:
            cache_path = self._get_page_cache_path(page_data["url"])
            cache_path.write_text(json.dumps(page_data))
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to cache page: {e}")

    def _save_url_list(self, url_list: List[Dict[str, str]]):
        """Save URL list to disk for resume capability."""
        try:
            self.url_list_file.write_text(json.dumps(url_list, indent=2))
            logger.debug(f"[DOC_SEARCH] Saved {len(url_list)} URLs to {self.url_list_file}")
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to save URL list: {e}")

    def _load_url_list(self) -> Optional[List[Dict[str, str]]]:
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

    def _save_chunks(self, chunks: List[Document]):
        """Save chunks to disk for resume capability."""
        try:
            # Convert Document objects to serializable dicts
            chunk_dicts = [
                {
                    "page_content": chunk.page_content,
                    "metadata": chunk.metadata
                }
                for chunk in chunks
            ]
            self.chunks_file.write_text(json.dumps(chunk_dicts))
            logger.info(f"[DOC_SEARCH] Saved {len(chunks)} chunks to {self.chunks_file}")
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to save chunks: {e}")

    def _load_chunks(self) -> Optional[List[Document]]:
        """Load chunks from disk."""
        if not self.chunks_file.exists():
            return None
        try:
            chunk_dicts = json.loads(self.chunks_file.read_text())
            chunks = [
                Document(
                    page_content=chunk_dict["page_content"],
                    metadata=chunk_dict["metadata"]
                )
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
            progress = {
                "completed": completed_count,
                "total": total_count,
                "timestamp": datetime.now().isoformat()
            }
            self.embedding_progress_file.write_text(json.dumps(progress))
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to save embedding progress: {e}")

    def _load_embedding_progress(self) -> Optional[Dict[str, Any]]:
        """Load embedding progress."""
        if not self.embedding_progress_file.exists():
            return None
        try:
            return json.loads(self.embedding_progress_file.read_text())
        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to load embedding progress: {e}")
            return None

    def _fetch_with_cache(self, url_info: Dict[str, str]) -> Optional[Dict[str, Any]]:
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

    def _split_into_sections(self, page_data: Dict[str, Any]) -> List[Document]:
        """Split page content into section-aware chunks using token-based sizing.

        Chunks by H2/H3 boundaries with adaptive sizing based on doc type.
        Preserves section anchors and heading context.

        Args:
            page_data: Page data with content, sections, and metadata

        Returns:
            List of Document chunks with section metadata
        """
        content = page_data["content"]
        sections = page_data.get("sections", [])
        url = page_data["url"]
        product = page_data["product"]

        # Get adaptive chunk configuration for this doc type
        chunk_config = self._get_chunk_config(url)
        chunk_size_tokens = chunk_config['size']
        overlap_tokens = chunk_config['overlap']

        if not sections:
            # Fallback to token-based splitting if no sections found
            logger.debug(f"[DOC_SEARCH] No sections found for {url}, using token-based split")
            # Split by tokens using text splitter
            if self.text_splitter is None:
                self._initialize_components()

            # Temporarily update text splitter with adaptive config
            from langchain_text_splitters import TokenTextSplitter
            token_splitter = TokenTextSplitter(
                chunk_size=chunk_size_tokens,
                chunk_overlap=overlap_tokens
            )
            split_docs = token_splitter.split_text(content)

            return [Document(
                page_content=chunk,
                metadata={
                    "url": url,
                    "product": product,
                    "source": "web",
                    "lastmod": page_data.get("lastmod")
                }
            ) for chunk in split_docs]

        chunks = []

        # Group sections by H2 (major sections)
        h2_sections = [s for s in sections if s['level'] == 2]

        for i, section in enumerate(h2_sections):
            start_pos = section['position']

            # Find the end position (start of next H2 or end of content)
            if i + 1 < len(h2_sections):
                end_pos = h2_sections[i + 1]['position']
            else:
                end_pos = len(content)

            # Extract section content
            section_content = content[start_pos:end_pos].strip()
            section_heading = section['text']
            section_anchor = section['anchor']

            # Check token count instead of character count
            section_tokens = self._count_tokens(section_content)

            # If section is too large, split it by H3 subsections
            if section_tokens > chunk_size_tokens:
                # Find H3s within this H2 section
                h3_in_section = [
                    s for s in sections
                    if s['level'] == 3
                    and s['position'] >= start_pos
                    and s['position'] < end_pos
                ]

                if h3_in_section:
                    # Split by H3 boundaries
                    for j, h3 in enumerate(h3_in_section):
                        h3_start = h3['position']

                        # Find end of H3 section
                        if j + 1 < len(h3_in_section):
                            h3_end = h3_in_section[j + 1]['position']
                        else:
                            h3_end = end_pos

                        h3_content = content[h3_start:h3_end].strip()

                        # Include parent H2 heading as context
                        chunk_text = f"## {section_heading}\n\n{h3_content}"
                        chunk_tokens = self._count_tokens(chunk_text)

                        # If still too large, use token-based splitting with overlap
                        if chunk_tokens > chunk_size_tokens * 2:
                            # Split into smaller chunks
                            sub_chunks = self._split_large_section(
                                chunk_text,
                                section_heading,
                                h3['anchor'],
                                chunk_size_tokens,
                                overlap_tokens
                            )
                            for sub_chunk in sub_chunks:
                                chunks.append(Document(
                                    page_content=sub_chunk,
                                    metadata={
                                        "url": url,
                                        "product": product,
                                        "source": "web",
                                        "lastmod": page_data.get("lastmod"),
                                        "section_anchor": h3['anchor'],
                                        "section_heading": f"{section_heading} > {h3['text']}"
                                    }
                                ))
                        else:
                            chunks.append(Document(
                                page_content=chunk_text,
                                metadata={
                                    "url": url,
                                    "product": product,
                                    "source": "web",
                                    "lastmod": page_data.get("lastmod"),
                                    "section_anchor": h3['anchor'],
                                    "section_heading": f"{section_heading} > {h3['text']}"
                                }
                            ))
                else:
                    # No H3s, split the large H2 section by tokens
                    sub_chunks = self._split_large_section(
                        section_content,
                        section_heading,
                        section_anchor,
                        chunk_size_tokens,
                        overlap_tokens
                    )
                    for sub_chunk in sub_chunks:
                        chunks.append(Document(
                            page_content=sub_chunk,
                            metadata={
                                "url": url,
                                "product": product,
                                "source": "web",
                                "lastmod": page_data.get("lastmod"),
                                "section_anchor": section_anchor,
                                "section_heading": section_heading
                            }
                        ))
            else:
                # Section is small enough, keep as single chunk
                chunks.append(Document(
                    page_content=section_content,
                    metadata={
                        "url": url,
                        "product": product,
                        "source": "web",
                        "lastmod": page_data.get("lastmod"),
                        "section_anchor": section_anchor,
                        "section_heading": section_heading
                    }
                ))

        return chunks

    def _split_large_section(
        self,
        content: str,
        heading: str,
        anchor: str,
        chunk_size_tokens: int,
        overlap_tokens: int
    ) -> List[str]:
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
        token_splitter = TokenTextSplitter(
            chunk_size=chunk_size_tokens,
            chunk_overlap=overlap_tokens
        )

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

    def _fetch_pages(self, url_list: List[Dict[str, str]]) -> List[Dict[str, Any]]:
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
            future_to_url = {
                executor.submit(self._fetch_with_cache, url_info): url_info
                for url_info in url_list
            }

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

    def _create_chunks(self, pages: List[Dict[str, Any]]) -> List[Document]:
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
        logger.info(f"[DOC_SEARCH] ✓ Created {len(all_chunks)} section-aware chunks from {total} pages in {elapsed:.1f}s")
        logger.info(f"[DOC_SEARCH] Average: {avg_chunks_per_page:.1f} chunks per page")
        logger.info("[DOC_SEARCH] " + "=" * 70)
        return all_chunks

    def _initialize_components(self):
        """Initialize LangChain components."""
        if self.embeddings is None:
            logger.info(f"[DOC_SEARCH] Loading embeddings model: {self.model_name}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )

        if self.text_splitter is None:
            logger.info(f"[DOC_SEARCH] Creating text splitter (chunk_size={self.chunk_size})")
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )

    def _build_index(self, url_list: List[Dict[str, str]]):
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
        logger.info(f"[DOC_SEARCH] ✓ All embeddings generated in {embedding_elapsed:.1f}s ({embedding_elapsed/60:.1f} min)")
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
                str(self.index_dir),
                self.embeddings,
                allow_dangerous_deserialization=True
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
                weights=[0.5, 0.5]  # 50% keyword, 50% semantic (balanced for technical queries)
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
        if not force_update and not self._needs_update():
            if self._load_index():
                logger.info("[DOC_SEARCH] Using cached index")
                return
            else:
                logger.warning("[DOC_SEARCH] Failed to load cache, rebuilding")

        # Try to resume from saved URL list
        url_list = self._load_url_list()

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
            logger.info(f"[DOC_SEARCH] ✓ Previous embedding progress: {progress['completed']:,}/{progress['total']:,} chunks")
            logger.info(f"[DOC_SEARCH] Last saved: {progress['timestamp']}")

        # Build index (will resume from cache if available)
        if not chunks:
            logger.info(f"[DOC_SEARCH] Building index from {len(url_list):,} URLs (Phases 2-4)...")
        self._build_index(url_list)

        # Update metadata
        metadata = {
            "version": "3.0.0-token-adaptive",
            "last_update": datetime.now().isoformat(),
            "page_count": len(url_list),
            "model_name": self.model_name,
            "chunk_size_tokens": self.chunk_size,  # Now tokens, not chars
            "chunk_overlap_tokens": self.chunk_overlap
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

    def search(
        self,
        query: str,
        top_k: int = 5,
        product_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search the index using hybrid search (BM25 + semantic).

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product name to filter results

        Returns:
            List of search results with text, metadata, and score
        """
        logger.debug(f"[DOC_SEARCH] === SEARCH QUERY ===")
        logger.debug(f"[DOC_SEARCH] Query: '{query}'")
        logger.debug(f"[DOC_SEARCH] top_k: {top_k}")
        logger.debug(f"[DOC_SEARCH] product_filter: {product_filter}")

        if self.vectorstore is None:
            logger.error("[DOC_SEARCH] Vector store not initialized")
            return []

        # Use hybrid search if available, otherwise fall back to FAISS only
        if self.ensemble_retriever is not None:
            logger.debug("[DOC_SEARCH] Using hybrid search (BM25 + semantic)")
            # EnsembleRetriever doesn't support metadata filtering,
            # so retrieve more results and filter afterward
            # Retrieve many more when filtering (product filter removes ~80% of results)
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
                logger.debug(f"[DOC_SEARCH] After product filter ({product_filter}): {len(docs)} docs (removed {before_filter - len(docs)})")

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

                # Cap at 1.0 for cleaner presentation
                rank_score = min(1.0, rank_score)

                results.append({
                    "text": doc.page_content,
                    "url": url,
                    "product": doc.metadata.get("product", "unknown"),
                    "source": doc.metadata.get("source", "web"),
                    "score": float(rank_score),
                    "distance": 0.0,  # Not applicable for hybrid
                    "section_heading": doc.metadata.get("section_heading", "")
                })

            # Re-sort by boosted scores (validated-designs should rank slightly higher)
            results.sort(key=lambda x: x["score"], reverse=True)

            # Deduplicate by base URL (keep highest-scoring chunk per page, but multiple sections per page allowed)
            # We keep top 2 sections per page to provide context
            url_counts = {}
            deduplicated_results = []
            for r in results:
                # Extract base URL (without anchor)
                base_url = r["url"].split('#')[0]
                count = url_counts.get(base_url, 0)

                # Keep top 2 sections per page
                if count < 2:
                    url_counts[base_url] = count + 1
                    deduplicated_results.append(r)

            results = deduplicated_results

            logger.debug(f"[DOC_SEARCH] After deduplication: {len(results)} results (max 2 sections per page)")

            # Limit to top_k after boosting and re-ranking
            results = results[:top_k]

            logger.debug(f"[DOC_SEARCH] After boosting and limiting to top_k={top_k}:")
            for i, r in enumerate(results, 1):
                is_vd = "validated-designs" in r["url"]
                logger.debug(f"[DOC_SEARCH]   {i}. [score={r['score']:.3f}] [VD={is_vd}] {r['url'][:80]}")
                logger.debug(f"[DOC_SEARCH]      Content preview: {r['text'][:150]}...")

        else:
            logger.debug("[DOC_SEARCH] Using semantic-only search (FAISS)")
            # Fall back to pure semantic search with filtering
            if product_filter:
                filter_dict = {"product": product_filter.lower()}
                docs_and_scores = self.vectorstore.similarity_search_with_score(
                    query,
                    k=top_k * 2,
                    filter=filter_dict
                )
            else:
                docs_and_scores = self.vectorstore.similarity_search_with_score(
                    query,
                    k=top_k
                )

            # Format results
            results = []
            for doc, score in docs_and_scores:
                # Convert L2 distance to similarity score
                similarity = 1.0 / (1.0 + score)

                # Build URL with anchor if available
                base_url = doc.metadata.get("url", "")
                section_anchor = doc.metadata.get("section_anchor", "")
                url = f"{base_url}#{section_anchor}" if section_anchor else base_url

                results.append({
                    "text": doc.page_content,
                    "url": url,
                    "product": doc.metadata.get("product", "unknown"),
                    "source": doc.metadata.get("source", "web"),
                    "score": float(similarity),
                    "distance": float(score),
                    "section_heading": doc.metadata.get("section_heading", "")
                })

            # Deduplicate by base URL (keep highest-scoring chunk per page, but multiple sections per page allowed)
            # We keep top 2 sections per page to provide context
            url_counts = {}
            deduplicated_results = []
            for r in results:
                # Extract base URL (without anchor)
                base_url = r["url"].split('#')[0]
                count = url_counts.get(base_url, 0)

                # Keep top 2 sections per page
                if count < 2:
                    url_counts[base_url] = count + 1
                    deduplicated_results.append(r)

            results = deduplicated_results[:top_k]

            logger.debug(f"[DOC_SEARCH] After deduplication: {len(results)} results (max 2 sections per page)")

        logger.info(f"[DOC_SEARCH] Found {len(results)} results for: {query}")
        logger.debug(f"[DOC_SEARCH] === FINAL RESULTS ({len(results)} total) ===")
        for i, r in enumerate(results, 1):
            logger.debug(f"[DOC_SEARCH] Result #{i}: {r['product'].upper()} - {r['url']}")
            logger.debug(f"[DOC_SEARCH]   Score: {r['score']:.3f}, Length: {len(r['text'])} chars")
        logger.debug(f"[DOC_SEARCH] === END SEARCH RESULTS ===")
        return results


# Global instance
_doc_search_index: Optional[HashiCorpDocSearchIndex] = None


def get_doc_search_index() -> HashiCorpDocSearchIndex:
    """Get or create the global doc search index."""
    global _doc_search_index
    if _doc_search_index is None:
        _doc_search_index = HashiCorpDocSearchIndex()
    return _doc_search_index


def initialize_doc_search(force_update: bool = False, max_pages: Optional[int] = None):
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
    results = index.search(
        query,
        top_k=top_k,
        product_filter=product if product else None
    )

    if not results:
        return f"No results found in HashiCorp developer documentation for: '{query}'"

    # Format output
    output = [f"Found {len(results)} result(s) in HashiCorp Developer Documentation:\n"]

    for idx, result in enumerate(results, 1):
        output.append(f"\n{idx}. [{result['product'].upper()}]")
        output.append(f"   URL: {result['url']}")
        output.append(f"   Relevance: {result['score']:.2f}")

        # Show preview
        text_preview = result['text'][:900]
        if len(result['text']) > 900:
            text_preview += "..."

        output.append(f"   Content: {text_preview}")
        output.append("")

    return "\n".join(output)
