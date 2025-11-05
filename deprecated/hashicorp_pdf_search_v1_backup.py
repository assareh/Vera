"""HashiCorp Validated Designs PDF Search with Semantic Search."""
import os
import json
import logging
import hashlib
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import requests
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from bs4 import BeautifulSoup

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("[PDF_SEARCH] Selenium not available, PDF downloads will be skipped")

# Configure logging
logger = logging.getLogger(__name__)

# HashiCorp Validated Designs catalog
VALIDATED_DESIGNS = [
    {
        "name": "Boundary: Operating Guide for Adoption",
        "slug": "boundary-operating-guides-adoption",
        "product": "boundary",
        "type": "operating-guide"
    },
    {
        "name": "Boundary: Operating Guide for Standardization",
        "slug": "boundary-operating-guides-standardization",
        "product": "boundary",
        "type": "operating-guide"
    },
    {
        "name": "Boundary: Solution Design Guide",
        "slug": "boundary-solution-design-guides-boundary-enterprise",
        "product": "boundary",
        "type": "solution-design"
    },
    {
        "name": "Consul: Operating Guide for Adoption",
        "slug": "consul-operating-guides-adoption",
        "product": "consul",
        "type": "operating-guide"
    },
    {
        "name": "Consul: Operating Guide for Scaling",
        "slug": "consul-operating-guides-scaling",
        "product": "consul",
        "type": "operating-guide"
    },
    {
        "name": "Consul: Operating Guide for Standardization",
        "slug": "consul-operating-guides-standardization",
        "product": "consul",
        "type": "operating-guide"
    },
    {
        "name": "Consul: Solution Design Guide",
        "slug": "consul-solution-design-guides-consul-enterprise-self-hosted",
        "product": "consul",
        "type": "solution-design"
    },
    {
        "name": "Nomad: Operating Guide",
        "slug": "nomad-operating-guides-nomad-enterprise",
        "product": "nomad",
        "type": "operating-guide"
    },
    {
        "name": "Nomad: Solution Design Guide",
        "slug": "nomad-solution-design-guides-nomad-enterprise",
        "product": "nomad",
        "type": "solution-design"
    },
    {
        "name": "Terraform: Operating Guide for Adoption",
        "slug": "terraform-operating-guides-adoption",
        "product": "terraform",
        "type": "operating-guide"
    },
    {
        "name": "Terraform: Operating Guide for Scaling",
        "slug": "terraform-operating-guides-scaling",
        "product": "terraform",
        "type": "operating-guide"
    },
    {
        "name": "Terraform: Operating Guide for Standardization",
        "slug": "terraform-operating-guides-standardization",
        "product": "terraform",
        "type": "operating-guide"
    },
    {
        "name": "Terraform: Solution Design Guide",
        "slug": "terraform-solution-design-guides-terraform-enterprise",
        "product": "terraform",
        "type": "solution-design"
    },
    {
        "name": "Vault: Operating Guide for Adoption",
        "slug": "vault-operating-guides-adoption",
        "product": "vault",
        "type": "operating-guide"
    },
    {
        "name": "Vault: Operating Guide for Scaling",
        "slug": "vault-operating-guides-scaling",
        "product": "vault",
        "type": "operating-guide"
    },
    {
        "name": "Vault: Operating Guide for Standardization",
        "slug": "vault-operating-guides-standardization",
        "product": "vault",
        "type": "operating-guide"
    },
    {
        "name": "Vault: Solution Design Guide",
        "slug": "vault-solution-design-guides-vault-enterprise",
        "product": "vault",
        "type": "solution-design"
    },
    {
        "name": "HCP Vault Radar: Operating Guide",
        "slug": "vault-radar-operating-guides-hcp-vault-radar",
        "product": "vault-radar",
        "type": "operating-guide"
    }
]


class HashiCorpPDFSearchIndex:
    """Manages PDF downloads, indexing, and semantic search for HashiCorp Validated Designs."""

    def __init__(
        self,
        cache_dir: str = "./hashicorp_pdfs",
        model_name: str = "all-MiniLM-L6-v2",
        update_check_interval_hours: int = 168,  # 7 days (guides update ~twice/year)
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """Initialize the PDF search index.

        Args:
            cache_dir: Directory to cache PDFs and index
            model_name: Sentence transformer model name
            update_check_interval_hours: Hours between update checks (default: 7 days)
            chunk_size: Number of words per chunk
            chunk_overlap: Number of overlapping words between chunks
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.pdfs_dir = self.cache_dir / "pdfs"
        self.pdfs_dir.mkdir(exist_ok=True)

        self.index_dir = self.cache_dir / "index"
        self.index_dir.mkdir(exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata.json"
        self.index_file = self.index_dir / "faiss.index"
        self.chunks_file = self.index_dir / "chunks.json"

        self.model_name = model_name
        self.update_check_interval = timedelta(hours=update_check_interval_hours)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.IndexFlatL2] = None
        self.chunks: List[Dict[str, Any]] = []

        logger.info(f"[PDF_SEARCH] Initialized with cache_dir={cache_dir}")

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from cache."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except Exception as e:
                logger.warning(f"[PDF_SEARCH] Failed to load metadata: {e}")
        return {}

    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save metadata to cache."""
        try:
            self.metadata_file.write_text(json.dumps(metadata, indent=2))
        except Exception as e:
            logger.error(f"[PDF_SEARCH] Failed to save metadata: {e}")

    def _needs_update(self) -> bool:
        """Check if index needs updating."""
        metadata = self._load_metadata()

        # If no last update time, need to build index
        if "last_update" not in metadata:
            logger.info("[PDF_SEARCH] No previous index found, needs initial build")
            return True

        # Check if enough time has passed
        last_update = datetime.fromisoformat(metadata["last_update"])
        time_since_update = datetime.now() - last_update

        needs_update = time_since_update >= self.update_check_interval

        if needs_update:
            logger.info(f"[PDF_SEARCH] Update check interval exceeded ({time_since_update} >= {self.update_check_interval})")
        else:
            logger.info(f"[PDF_SEARCH] Recent update found ({time_since_update} ago), skipping update check")

        return needs_update

    def _scrape_pdf_link(self, url: str) -> Optional[str]:
        """Scrape the page for PDF download link using BeautifulSoup.

        Args:
            url: The validated design page URL

        Returns:
            PDF download URL if found, None otherwise
        """
        try:
            logger.debug(f"[PDF_SEARCH] Scraping page for PDF link: {url}")

            # Fetch the page
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for PDF download link
            # HashiCorp uses CloudFront with aria-label="Download as PDF. Opens in a new tab."
            pdf_link = soup.find('a', {'aria-label': 'Download as PDF. Opens in a new tab.'})

            if pdf_link and pdf_link.get('href'):
                pdf_url = pdf_link['href']
                logger.info(f"[PDF_SEARCH] Found PDF link via scraping: {pdf_url}")
                return pdf_url

            # Try alternative selectors
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Look for CloudFront PDF links
                if 'cloudfront.net' in href and href.endswith('.pdf'):
                    logger.info(f"[PDF_SEARCH] Found CloudFront PDF link: {href}")
                    return href
                # Look for direct PDF links
                if href.endswith('.pdf') and ('hashicorp' in href or 'download' in link.get_text().lower()):
                    logger.info(f"[PDF_SEARCH] Found PDF link: {href}")
                    return href

            logger.debug(f"[PDF_SEARCH] No PDF link found via scraping")
            return None

        except Exception as e:
            logger.debug(f"[PDF_SEARCH] Error scraping page: {e}")
            return None

    def _create_selenium_driver(self) -> Optional[webdriver.Chrome]:
        """Create a headless Chrome driver for PDF downloads.

        Returns:
            Configured Chrome WebDriver or None if failed
        """
        if not SELENIUM_AVAILABLE:
            return None

        try:
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")

            # Set download directory
            prefs = {
                "download.default_directory": str(self.pdfs_dir.absolute()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True
            }
            chrome_options.add_experimental_option("prefs", prefs)

            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            logger.debug("[PDF_SEARCH] Selenium Chrome driver created successfully")
            return driver

        except Exception as e:
            logger.error(f"[PDF_SEARCH] Failed to create Selenium driver: {e}")
            return None

    def _download_pdf(self, design: Dict[str, str]) -> Optional[Path]:
        """Download a PDF using Selenium if not cached.

        Args:
            design: Design metadata dict

        Returns:
            Path to downloaded PDF, or None if failed
        """
        slug = design["slug"]
        url = f"https://developer.hashicorp.com/validated-designs/{slug}"
        pdf_path = self.pdfs_dir / f"{slug}.pdf"

        # Check if PDF already exists
        if pdf_path.exists():
            logger.debug(f"[PDF_SEARCH] PDF already cached: {slug}")
            return pdf_path

        try:
            logger.info(f"[PDF_SEARCH] Downloading PDF: {design['name']}")
            logger.info(f"[PDF_SEARCH] URL: {url}")

            # STEP 1: Try scraping the page for PDF link first (fast, no browser needed)
            pdf_url = self._scrape_pdf_link(url)

            if pdf_url:
                # Download the PDF directly
                logger.info(f"[PDF_SEARCH] Downloading from: {pdf_url}")
                response = requests.get(pdf_url, timeout=60, allow_redirects=True)

                if response.status_code == 200:
                    pdf_path.write_bytes(response.content)
                    logger.info(f"[PDF_SEARCH] Successfully downloaded via scraping: {slug}")
                    return pdf_path

            # STEP 2: If scraping didn't work, fall back to Selenium
            if not SELENIUM_AVAILABLE:
                logger.warning(f"[PDF_SEARCH] Scraping failed and Selenium not available: {slug}")
                return None

            logger.info(f"[PDF_SEARCH] Falling back to Selenium for: {slug}")

        except Exception as e:
            logger.warning(f"[PDF_SEARCH] Scraping attempt failed: {e}, trying Selenium...")

        # Selenium fallback
        if not SELENIUM_AVAILABLE:
            logger.warning(f"[PDF_SEARCH] Selenium not available, skipping: {slug}")
            return None

        driver = None
        try:
            logger.info(f"[PDF_SEARCH] Using Selenium for: {design['name']}")
            logger.info(f"[PDF_SEARCH] URL: {url}")

            # Create Selenium driver
            driver = self._create_selenium_driver()
            if not driver:
                logger.error(f"[PDF_SEARCH] Failed to create driver for: {slug}")
                return None

            # Navigate to the page
            driver.get(url)

            # Wait longer for JavaScript to load
            logger.debug(f"[PDF_SEARCH] Waiting for page to load...")
            time_module.sleep(5)

            # Log page status
            logger.debug(f"[PDF_SEARCH] Page title: {driver.title}")
            logger.debug(f"[PDF_SEARCH] Current URL: {driver.current_url}")

            # Wait specifically for sidebar navigation to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "aside, nav, .sidebar"))
                )
                logger.debug(f"[PDF_SEARCH] Sidebar loaded")
            except Exception as e:
                logger.debug(f"[PDF_SEARCH] Sidebar wait failed: {e}")

            # Try to find the "Download as PDF" link
            # HashiCorp uses CloudFront for PDFs with specific aria-label
            download_selectors = [
                "//a[@aria-label='Download as PDF. Opens in a new tab.']",
                "//a[contains(text(), 'Download as PDF')]",
                "//a[contains(@href, 'cloudfront.net')]",
                "//a[contains(@href, '.pdf')]",
                "//button[contains(text(), 'Download PDF')]"
            ]

            pdf_url = None
            for selector in download_selectors:
                try:
                    logger.debug(f"[PDF_SEARCH] Trying selector: {selector}")
                    # Don't wait for clickable, just wait for presence
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )

                    # Extract the href attribute (don't try to click)
                    if element.tag_name == 'a' and element.get_attribute('href'):
                        pdf_url = element.get_attribute('href')
                        logger.info(f"[PDF_SEARCH] Found PDF URL via Selenium: {pdf_url}")
                        break

                except Exception as e:
                    logger.debug(f"[PDF_SEARCH] Selector failed: {selector} - {e}")
                    continue

            # If we found a PDF URL, download it
            if pdf_url:
                logger.info(f"[PDF_SEARCH] Downloading from: {pdf_url}")
                response = requests.get(pdf_url, timeout=60, allow_redirects=True)
                if response.status_code == 200:
                    pdf_path.write_bytes(response.content)
                    logger.info(f"[PDF_SEARCH] Successfully downloaded via Selenium: {slug}")
                    return pdf_path

            # If no PDF URL found via selectors, try direct download URLs
            logger.debug(f"[PDF_SEARCH] No download button found, trying direct URLs")
            pdf_url_patterns = [
                f"https://developer.hashicorp.com/validated-designs/{slug}.pdf",
                f"https://developer.hashicorp.com/api/pdf/validated-designs/{slug}",
            ]

            for pdf_url in pdf_url_patterns:
                try:
                    logger.debug(f"[PDF_SEARCH] Trying direct URL: {pdf_url}")
                    response = requests.get(pdf_url, timeout=30, allow_redirects=True)

                    if response.status_code == 200 and response.headers.get('content-type', '').startswith('application/pdf'):
                        pdf_path.write_bytes(response.content)
                        logger.info(f"[PDF_SEARCH] Successfully downloaded: {slug}")
                        return pdf_path
                except Exception as e:
                    logger.debug(f"[PDF_SEARCH] Failed to download from {pdf_url}: {e}")
                    continue

            logger.warning(f"[PDF_SEARCH] Could not download PDF for: {slug}")
            logger.warning(f"[PDF_SEARCH] Manual download may be needed from {url}")
            return None

        except Exception as e:
            logger.error(f"[PDF_SEARCH] Error downloading PDF {slug}: {e}")
            return None

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.debug(f"[PDF_SEARCH] Error closing driver: {e}")

    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from a PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text content
        """
        try:
            reader = PdfReader(pdf_path)
            text_parts = []

            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"[PDF_SEARCH] Failed to extract page {page_num} from {pdf_path.name}: {e}")

            full_text = "\n\n".join(text_parts)
            logger.info(f"[PDF_SEARCH] Extracted {len(full_text)} characters from {pdf_path.name}")
            return full_text

        except Exception as e:
            logger.error(f"[PDF_SEARCH] Failed to read PDF {pdf_path.name}: {e}")
            return ""

    def _chunk_text(self, text: str, document_name: str, product: str, slug: str) -> List[Dict[str, Any]]:
        """Split text into overlapping chunks.

        Args:
            text: Text to chunk
            document_name: Name of the document
            product: Product name
            slug: Document slug for URL generation

        Returns:
            List of chunk dictionaries
        """
        words = text.split()
        chunks = []

        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = " ".join(chunk_words)

            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "document": document_name,
                    "product": product,
                    "slug": slug,
                    "chunk_index": len(chunks),
                    "start_word": i,
                    "end_word": i + len(chunk_words)
                })

        logger.debug(f"[PDF_SEARCH] Created {len(chunks)} chunks from {document_name}")
        return chunks

    def _load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            logger.info(f"[PDF_SEARCH] Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("[PDF_SEARCH] Model loaded successfully")

    def _build_index(self):
        """Build FAISS index from all cached PDFs."""
        logger.info("[PDF_SEARCH] Building FAISS index from PDFs")

        # Load model
        self._load_model()

        # Collect all chunks from all PDFs
        all_chunks = []

        for design in VALIDATED_DESIGNS:
            slug = design["slug"]
            pdf_path = self.pdfs_dir / f"{slug}.pdf"

            if not pdf_path.exists():
                logger.warning(f"[PDF_SEARCH] PDF not found, skipping: {slug}")
                continue

            # Extract text
            text = self._extract_text_from_pdf(pdf_path)
            if not text:
                logger.warning(f"[PDF_SEARCH] No text extracted, skipping: {slug}")
                continue

            # Chunk text
            chunks = self._chunk_text(text, design["name"], design["product"], design["slug"])
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.error("[PDF_SEARCH] No chunks to index!")
            return

        logger.info(f"[PDF_SEARCH] Collected {len(all_chunks)} chunks from {len(VALIDATED_DESIGNS)} documents")

        # Generate embeddings
        logger.info("[PDF_SEARCH] Generating embeddings...")
        texts = [chunk["text"] for chunk in all_chunks]
        embeddings = self.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        # Create FAISS index
        dimension = embeddings.shape[1]
        logger.info(f"[PDF_SEARCH] Creating FAISS index with dimension {dimension}")
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)

        # Save index and chunks
        faiss.write_index(index, str(self.index_file))
        self.chunks_file.write_text(json.dumps(all_chunks, indent=2))

        # Update in-memory references
        self.index = index
        self.chunks = all_chunks

        logger.info(f"[PDF_SEARCH] Index built successfully with {len(all_chunks)} chunks")

    def _load_index(self):
        """Load FAISS index from disk."""
        if not self.index_file.exists() or not self.chunks_file.exists():
            logger.warning("[PDF_SEARCH] Index files not found")
            return False

        try:
            self.index = faiss.read_index(str(self.index_file))
            self.chunks = json.loads(self.chunks_file.read_text())
            logger.info(f"[PDF_SEARCH] Loaded index with {len(self.chunks)} chunks")
            return True
        except Exception as e:
            logger.error(f"[PDF_SEARCH] Failed to load index: {e}")
            return False

    def initialize(self, force_update: bool = False):
        """Initialize the search index.

        Downloads PDFs if needed, builds/updates the index.

        Args:
            force_update: Force update even if recent update exists
        """
        logger.info("[PDF_SEARCH] Initializing search index")

        # Check if we need to update
        if not force_update and not self._needs_update():
            # Try to load existing index
            if self._load_index():
                self._load_model()
                logger.info("[PDF_SEARCH] Using cached index")
                return
            else:
                logger.warning("[PDF_SEARCH] Failed to load cached index, will rebuild")

        # Download PDFs (only new/changed ones)
        logger.info("[PDF_SEARCH] Checking for PDF updates...")
        downloaded = 0
        for design in VALIDATED_DESIGNS:
            pdf_path = self._download_pdf(design)
            if pdf_path:
                downloaded += 1

        logger.info(f"[PDF_SEARCH] {downloaded}/{len(VALIDATED_DESIGNS)} PDFs available")

        # Build index
        self._build_index()

        # Update metadata
        metadata = {
            "last_update": datetime.now().isoformat(),
            "pdf_count": downloaded,
            "chunk_count": len(self.chunks),
            "model_name": self.model_name
        }
        self._save_metadata(metadata)

        logger.info("[PDF_SEARCH] Initialization complete")

    def search(self, query: str, top_k: int = 5, product_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search the index using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product name to filter results

        Returns:
            List of search results with text, document, product, and score
        """
        if self.index is None or self.model is None:
            logger.error("[PDF_SEARCH] Index not initialized")
            return []

        # Generate query embedding
        query_embedding = self.model.encode([query], convert_to_numpy=True)

        # Search index
        # We'll search for more results than needed to account for filtering
        search_k = top_k * 3 if product_filter else top_k
        distances, indices = self.index.search(query_embedding, search_k)

        # Collect results
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]

            # Apply product filter if specified
            if product_filter and chunk["product"].lower() != product_filter.lower():
                continue

            # Convert L2 distance to similarity score (inverse)
            # Lower distance = higher similarity
            similarity_score = 1.0 / (1.0 + distance)

            results.append({
                "text": chunk["text"],
                "document": chunk["document"],
                "product": chunk["product"],
                "slug": chunk["slug"],
                "chunk_index": chunk["chunk_index"],
                "score": float(similarity_score),
                "distance": float(distance)
            })

            # Stop if we have enough results
            if len(results) >= top_k:
                break

        logger.info(f"[PDF_SEARCH] Found {len(results)} results for query: {query}")
        return results


# Global instance
_pdf_search_index: Optional[HashiCorpPDFSearchIndex] = None


def get_pdf_search_index() -> HashiCorpPDFSearchIndex:
    """Get or create the global PDF search index."""
    global _pdf_search_index
    if _pdf_search_index is None:
        _pdf_search_index = HashiCorpPDFSearchIndex()
    return _pdf_search_index


def initialize_pdf_search(force_update: bool = False):
    """Initialize the PDF search index (call on startup)."""
    index = get_pdf_search_index()
    index.initialize(force_update=force_update)


def search_pdfs(query: str, top_k: int = 5, product: str = "") -> str:
    """Search HashiCorp validated design PDFs.

    Args:
        query: Search query
        top_k: Number of results to return
        product: Optional product filter (terraform, vault, consul, etc.)

    Returns:
        Formatted search results
    """
    index = get_pdf_search_index()

    if index.index is None:
        return "PDF search index not initialized. Please wait for initialization to complete."

    # Perform search
    results = index.search(query, top_k=top_k, product_filter=product if product else None)

    if not results:
        return f"No results found in HashiCorp validated design PDFs for query: '{query}'"

    # Format output
    output = [f"Found {len(results)} result(s) in HashiCorp Validated Designs for '{query}':\n"]
    output.append("⚠️  IMPORTANT: Use ONLY the URLs provided below. Do NOT generate or hallucinate URLs.\n")

    for idx, result in enumerate(results, 1):
        url = f"https://developer.hashicorp.com/validated-designs/{result['slug']}"
        output.append(f"\n{idx}. [{result['product'].upper()}] {result['document']}")
        output.append(f"   URL: {url}")
        output.append(f"   Relevance: {result['score']:.2f}")

        # Truncate text for preview
        text_preview = result['text'][:300]
        if len(result['text']) > 300:
            text_preview += "..."

        output.append(f"   Content: {text_preview}")
        output.append("")

    return "\n".join(output)
