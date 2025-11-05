"""HashiCorp Developer Documentation Web Crawler - LangChain Implementation.

Crawls developer.hashicorp.com using the sitemap, extracts content from HTML pages,
and builds a searchable FAISS index using LangChain.
"""
import os
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import requests
from bs4 import BeautifulSoup

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
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        max_pages: Optional[int] = None,  # For testing, limit pages crawled
        rate_limit_delay: float = 0.05,  # Delay between requests (seconds)
        max_workers: int = 10  # Parallel workers for fetching
    ):
        """Initialize the web search index.

        Args:
            cache_dir: Directory to cache content and index
            model_name: Sentence transformer model name
            update_check_interval_hours: Hours between update checks (default: 7 days)
            chunk_size: Characters per chunk
            chunk_overlap: Overlapping characters between chunks
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

        logger.info(f"[DOC_SEARCH] Initialized with cache_dir={cache_dir}")

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
            logger.info("[DOC_SEARCH] Discovering validated-designs pages...")
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
                if '/validated-designs/' in href:
                    # Make absolute URL
                    if href.startswith('/'):
                        href = base_url + href
                    guide_links.add(href)

            logger.info(f"[DOC_SEARCH] Found {len(guide_links)} validated-designs guide links")

            if not guide_links:
                logger.warning("[DOC_SEARCH] No guide links found, skipping validated-designs discovery")
                return []

            # For each guide, crawl to find all pages
            for idx, guide_url in enumerate(guide_links, 1):
                try:
                    logger.debug(f"[DOC_SEARCH] Crawling guide {idx}/{len(guide_links)}: {guide_url}")
                    time.sleep(self.rate_limit_delay)

                    response = requests.get(guide_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    logger.debug(f"[DOC_SEARCH] Got guide page: {len(response.text)} bytes")

                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Find all links within this guide
                    links_found = 0
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/validated-designs/' in href:
                            # Make absolute URL
                            if href.startswith('/'):
                                href = base_url + href

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

    def _extract_main_content(self, html: str, url: str) -> Optional[str]:
        """Extract main documentation content from HTML page.

        Preserves structure including headings and code blocks for better context.

        Args:
            html: Raw HTML content
            url: URL of the page (for logging)

        Returns:
            Extracted text content or None
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
                # Process content to preserve structure
                text_parts = []

                for element in main_content.descendants:
                    if element.name == 'h1':
                        text_parts.append(f"\n# {element.get_text(strip=True)}\n")
                    elif element.name == 'h2':
                        text_parts.append(f"\n## {element.get_text(strip=True)}\n")
                    elif element.name == 'h3':
                        text_parts.append(f"\n### {element.get_text(strip=True)}\n")
                    elif element.name in ['pre', 'code']:
                        # Preserve code blocks
                        code_text = element.get_text(strip=False)
                        if code_text.strip():
                            text_parts.append(f"\n```\n{code_text}\n```\n")
                    elif element.name == 'p':
                        para_text = element.get_text(strip=True)
                        if para_text:
                            text_parts.append(f"{para_text}\n")
                    elif element.name in ['li']:
                        li_text = element.get_text(strip=True)
                        if li_text:
                            text_parts.append(f"- {li_text}\n")

                # Join and clean up excessive whitespace
                text = ''.join(text_parts)
                # Collapse multiple newlines into max 2
                import re
                text = re.sub(r'\n{3,}', '\n\n', text)

                return text.strip()

            return None

        except Exception as e:
            logger.warning(f"[DOC_SEARCH] Failed to extract content from {url}: {e}")
            return None

    def _fetch_page_content(self, url_info: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Fetch and extract content from a single page.

        Args:
            url_info: Dictionary with 'url', 'product', and 'lastmod'

        Returns:
            Dictionary with extracted content and metadata or None
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

            # Extract main content
            content = self._extract_main_content(response.text, url)

            if not content:
                logger.warning(f"[DOC_SEARCH] No content extracted from {url}")
                return None

            return {
                "url": url,
                "product": url_info["product"],
                "lastmod": url_info["lastmod"],
                "content": content,
                "length": len(content)
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

    def _create_documents(self, url_list: List[Dict[str, str]]) -> List[Document]:
        """Create LangChain Document objects from web pages using parallel fetching.

        Args:
            url_list: List of URL info dicts from sitemap

        Returns:
            List of LangChain Documents
        """
        documents = []
        total = len(url_list)

        logger.info(f"[DOC_SEARCH] Fetching content from {total} pages with {self.max_workers} parallel workers...")
        logger.info(f"[DOC_SEARCH] Progress will be logged every 100 pages...")

        # Use ThreadPoolExecutor for parallel fetching
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all fetch tasks
            future_to_url = {
                executor.submit(self._fetch_with_cache, url_info): url_info
                for url_info in url_list
            }

            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_url):
                completed += 1
                if completed % 100 == 0:
                    logger.info(f"[DOC_SEARCH] Progress: {completed}/{total} pages ({100*completed/total:.1f}%)")

                try:
                    page_data = future.result()
                    if page_data:
                        doc = Document(
                            page_content=page_data["content"],
                            metadata={
                                "url": page_data["url"],
                                "product": page_data["product"],
                                "source": "web",
                                "lastmod": page_data.get("lastmod")
                            }
                        )
                        documents.append(doc)
                except Exception as e:
                    url_info = future_to_url[future]
                    logger.warning(f"[DOC_SEARCH] Failed to process {url_info['url']}: {e}")

        logger.info(f"[DOC_SEARCH] Created {len(documents)} documents from {completed} pages")
        return documents

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
            # Create documents
            logger.info("[DOC_SEARCH] No cached chunks found, creating from documents...")
            documents = self._create_documents(url_list)

            if not documents:
                logger.error("[DOC_SEARCH] No documents to index!")
                return

            # Split documents into chunks
            logger.info("[DOC_SEARCH] Splitting documents into chunks...")
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"[DOC_SEARCH] Created {len(chunks)} chunks")

            # Save chunks to disk
            self._save_chunks(chunks)
        else:
            logger.info(f"[DOC_SEARCH] Using {len(chunks)} cached chunks")

        # Create FAISS index with batching for progress tracking
        logger.info("[DOC_SEARCH] Creating FAISS vector store (this may take a while)...")
        logger.info(f"[DOC_SEARCH] Generating embeddings for {len(chunks)} chunks...")
        logger.info("[DOC_SEARCH] Building index in batches to allow resumption...")

        # Build index in batches
        batch_size = 10000  # Process 10k chunks at a time
        total_batches = (len(chunks) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(chunks))
            batch_chunks = chunks[start_idx:end_idx]

            logger.info(f"[DOC_SEARCH] Processing batch {batch_idx + 1}/{total_batches} ({start_idx}-{end_idx}, {len(batch_chunks)} chunks)...")

            if batch_idx == 0:
                # Create initial index
                self.vectorstore = FAISS.from_documents(batch_chunks, self.embeddings)
            else:
                # Add to existing index
                batch_vectorstore = FAISS.from_documents(batch_chunks, self.embeddings)
                self.vectorstore.merge_from(batch_vectorstore)

            # Save progress after each batch
            logger.info(f"[DOC_SEARCH] Saving progress after batch {batch_idx + 1}...")
            self.vectorstore.save_local(str(self.index_dir))
            self._save_embedding_progress(end_idx, len(chunks))

            logger.info(f"[DOC_SEARCH] ✓ Batch {batch_idx + 1}/{total_batches} complete ({end_idx}/{len(chunks)} chunks)")

        logger.info(f"[DOC_SEARCH] ✓ Index built successfully!")
        logger.info(f"[DOC_SEARCH] ✓ {len(chunks)} chunks indexed")

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
        logger.info("[DOC_SEARCH] Initializing search index")

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
            # Download sitemap
            logger.info("[DOC_SEARCH] Step 1: Downloading sitemap...")
            if not self._download_sitemap():
                logger.error("[DOC_SEARCH] Failed to download sitemap")
                return

            # Parse sitemap
            logger.info("[DOC_SEARCH] Step 2: Parsing sitemap...")
            url_list = self._parse_sitemap()
            if not url_list:
                logger.error("[DOC_SEARCH] No URLs found in sitemap")
                return
            logger.info(f"[DOC_SEARCH] Found {len(url_list)} URLs in sitemap")

            # Discover validated-designs pages (not in sitemap)
            logger.info("[DOC_SEARCH] Step 3: Discovering validated-designs pages...")
            validated_designs = self._discover_validated_designs()
            if validated_designs:
                logger.info(f"[DOC_SEARCH] Adding {len(validated_designs)} validated-designs pages")
                # Merge with sitemap, deduplicating by URL
                all_urls = {url_info["url"]: url_info for url_info in url_list}
                for url_info in validated_designs:
                    all_urls[url_info["url"]] = url_info
                url_list = list(all_urls.values())
                logger.info(f"[DOC_SEARCH] Total URLs after merging: {len(url_list)}")

            # Save URL list for resume capability
            self._save_url_list(url_list)
        else:
            logger.info(f"[DOC_SEARCH] ✓ Resuming with {len(url_list)} URLs from cache")

        # Check if we have cached chunks (scraping already done)
        chunks = self._load_chunks()
        if chunks:
            logger.info(f"[DOC_SEARCH] ✓ Found {len(chunks)} cached chunks (scraping complete)")
            logger.info("[DOC_SEARCH] Skipping to embedding generation...")

        # Check embedding progress
        progress = self._load_embedding_progress()
        if progress:
            logger.info(f"[DOC_SEARCH] ✓ Previous embedding progress: {progress['completed']}/{progress['total']} chunks")
            logger.info(f"[DOC_SEARCH] Last saved: {progress['timestamp']}")

        # Build index (will resume from cache if available)
        logger.info("[DOC_SEARCH] Step 4: Building FAISS index...")
        if not chunks:
            logger.info(f"[DOC_SEARCH] This will fetch {len(url_list)} pages and create embeddings...")
        self._build_index(url_list)

        # Update metadata
        metadata = {
            "last_update": datetime.now().isoformat(),
            "page_count": len(url_list),
            "model_name": self.model_name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap
        }
        self._save_metadata(metadata)

        logger.info("[DOC_SEARCH] Initialization complete")

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

                # Boost validated-designs URLs (authoritative content)
                url = doc.metadata.get("url", "")
                if "validated-designs" in url:
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
                    "distance": 0.0  # Not applicable for hybrid
                })

            # Re-sort by boosted scores (validated-designs should rank slightly higher)
            results.sort(key=lambda x: x["score"], reverse=True)

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
            for doc, score in docs_and_scores[:top_k]:
                # Convert L2 distance to similarity score
                similarity = 1.0 / (1.0 + score)

                results.append({
                    "text": doc.page_content,
                    "url": doc.metadata.get("url", ""),
                    "product": doc.metadata.get("product", "unknown"),
                    "source": doc.metadata.get("source", "web"),
                    "score": float(similarity),
                    "distance": float(score)
                })

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
