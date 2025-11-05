"""HashiCorp Validated Designs PDF Search - LangChain Implementation.

This is an improved version using LangChain's vector store abstractions
and better chunking strategies for more accurate retrieval.
"""
import os
import json
import logging
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from pypdf import PdfReader
from bs4 import BeautifulSoup

# LangChain imports
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

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
    """Manages PDF downloads, indexing, and semantic search using LangChain."""

    def __init__(
        self,
        cache_dir: str = "./hashicorp_pdfs",
        model_name: str = "all-MiniLM-L6-v2",
        update_check_interval_hours: int = 168,  # 7 days
        chunk_size: int = 1000,  # Characters, not words
        chunk_overlap: int = 200
    ):
        """Initialize the PDF search index.

        Args:
            cache_dir: Directory to cache PDFs and index
            model_name: Sentence transformer model name
            update_check_interval_hours: Hours between update checks (default: 7 days)
            chunk_size: Characters per chunk (more than word-based chunking)
            chunk_overlap: Overlapping characters between chunks
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.pdfs_dir = self.cache_dir / "pdfs"
        self.pdfs_dir.mkdir(exist_ok=True)

        self.index_dir = self.cache_dir / "index_v2"  # New version
        self.index_dir.mkdir(exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata_v2.json"

        self.model_name = model_name
        self.update_check_interval = timedelta(hours=update_check_interval_hours)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # LangChain components
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self.vectorstore: Optional[FAISS] = None
        self.text_splitter: Optional[RecursiveCharacterTextSplitter] = None

        logger.info(f"[PDF_SEARCH_V2] Initialized with cache_dir={cache_dir}")

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from cache."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except Exception as e:
                logger.warning(f"[PDF_SEARCH_V2] Failed to load metadata: {e}")
        return {}

    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save metadata to cache."""
        try:
            self.metadata_file.write_text(json.dumps(metadata, indent=2))
        except Exception as e:
            logger.error(f"[PDF_SEARCH_V2] Failed to save metadata: {e}")

    def _needs_update(self) -> bool:
        """Check if index needs updating."""
        metadata = self._load_metadata()

        if "last_update" not in metadata:
            logger.info("[PDF_SEARCH_V2] No previous index found, needs initial build")
            return True

        last_update = datetime.fromisoformat(metadata["last_update"])
        time_since_update = datetime.now() - last_update
        needs_update = time_since_update >= self.update_check_interval

        if needs_update:
            logger.info(f"[PDF_SEARCH_V2] Update interval exceeded ({time_since_update})")
        else:
            logger.info(f"[PDF_SEARCH_V2] Recent update found ({time_since_update} ago)")

        return needs_update

    def _scrape_pdf_link(self, url: str) -> Optional[str]:
        """Scrape the page for PDF download link using BeautifulSoup."""
        try:
            logger.debug(f"[PDF_SEARCH_V2] Scraping page for PDF link: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for PDF download link
            pdf_link = soup.find('a', {'aria-label': 'Download as PDF. Opens in a new tab.'})

            if pdf_link and pdf_link.get('href'):
                pdf_url = pdf_link['href']
                logger.info(f"[PDF_SEARCH_V2] Found PDF link: {pdf_url}")
                return pdf_url

            # Try alternative selectors
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'cloudfront.net' in href and href.endswith('.pdf'):
                    logger.info(f"[PDF_SEARCH_V2] Found CloudFront PDF: {href}")
                    return href
                if href.endswith('.pdf') and ('hashicorp' in href or 'download' in link.get_text().lower()):
                    logger.info(f"[PDF_SEARCH_V2] Found PDF link: {href}")
                    return href

            logger.debug(f"[PDF_SEARCH_V2] No PDF link found")
            return None

        except Exception as e:
            logger.debug(f"[PDF_SEARCH_V2] Error scraping: {e}")
            return None

    def _download_pdf(self, design: Dict[str, str]) -> Optional[Path]:
        """Download a PDF if not cached."""
        slug = design["slug"]
        url = f"https://developer.hashicorp.com/validated-designs/{slug}"
        pdf_path = self.pdfs_dir / f"{slug}.pdf"

        if pdf_path.exists():
            logger.debug(f"[PDF_SEARCH_V2] PDF already cached: {slug}")
            return pdf_path

        try:
            logger.info(f"[PDF_SEARCH_V2] Downloading PDF: {design['name']}")

            # Try scraping first
            pdf_url = self._scrape_pdf_link(url)

            if pdf_url:
                logger.info(f"[PDF_SEARCH_V2] Downloading from: {pdf_url}")
                response = requests.get(pdf_url, timeout=60, allow_redirects=True)

                if response.status_code == 200:
                    pdf_path.write_bytes(response.content)
                    logger.info(f"[PDF_SEARCH_V2] Downloaded: {slug}")
                    return pdf_path

            logger.warning(f"[PDF_SEARCH_V2] Could not download: {slug}")
            return None

        except Exception as e:
            logger.error(f"[PDF_SEARCH_V2] Error downloading {slug}: {e}")
            return None

    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from a PDF file."""
        try:
            reader = PdfReader(pdf_path)
            text_parts = []

            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"[PDF_SEARCH_V2] Failed to extract page {page_num}: {e}")

            full_text = "\n\n".join(text_parts)
            logger.info(f"[PDF_SEARCH_V2] Extracted {len(full_text)} chars from {pdf_path.name}")
            return full_text

        except Exception as e:
            logger.error(f"[PDF_SEARCH_V2] Failed to read PDF {pdf_path.name}: {e}")
            return ""

    def _create_documents(self) -> List[Document]:
        """Create LangChain Document objects from all PDFs."""
        documents = []

        for design in VALIDATED_DESIGNS:
            slug = design["slug"]
            pdf_path = self.pdfs_dir / f"{slug}.pdf"

            if not pdf_path.exists():
                logger.warning(f"[PDF_SEARCH_V2] PDF not found: {slug}")
                continue

            # Extract text
            text = self._extract_text_from_pdf(pdf_path)
            if not text:
                logger.warning(f"[PDF_SEARCH_V2] No text extracted: {slug}")
                continue

            # Create Document with metadata
            doc = Document(
                page_content=text,
                metadata={
                    "document": design["name"],
                    "product": design["product"],
                    "type": design["type"],
                    "slug": design["slug"],
                    "url": f"https://developer.hashicorp.com/validated-designs/{slug}"
                }
            )
            documents.append(doc)

        logger.info(f"[PDF_SEARCH_V2] Created {len(documents)} documents from PDFs")
        return documents

    def _initialize_components(self):
        """Initialize LangChain components."""
        if self.embeddings is None:
            logger.info(f"[PDF_SEARCH_V2] Loading embeddings model: {self.model_name}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )

        if self.text_splitter is None:
            logger.info(f"[PDF_SEARCH_V2] Creating text splitter (chunk_size={self.chunk_size})")
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]  # Respect semantic boundaries
            )

    def _build_index(self):
        """Build FAISS index using LangChain."""
        logger.info("[PDF_SEARCH_V2] Building FAISS index")

        # Initialize components
        self._initialize_components()

        # Create documents
        documents = self._create_documents()

        if not documents:
            logger.error("[PDF_SEARCH_V2] No documents to index!")
            return

        # Split documents into chunks
        logger.info("[PDF_SEARCH_V2] Splitting documents into chunks...")
        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"[PDF_SEARCH_V2] Created {len(chunks)} chunks")

        # Create FAISS index
        logger.info("[PDF_SEARCH_V2] Creating FAISS vector store...")
        self.vectorstore = FAISS.from_documents(chunks, self.embeddings)

        # Save to disk
        logger.info("[PDF_SEARCH_V2] Saving index to disk...")
        self.vectorstore.save_local(str(self.index_dir))

        logger.info(f"[PDF_SEARCH_V2] Index built with {len(chunks)} chunks")

    def _load_index(self) -> bool:
        """Load FAISS index from disk."""
        index_path = self.index_dir / "index.faiss"

        if not index_path.exists():
            logger.warning("[PDF_SEARCH_V2] Index file not found")
            return False

        try:
            self._initialize_components()
            logger.info("[PDF_SEARCH_V2] Loading FAISS index from disk...")
            self.vectorstore = FAISS.load_local(
                str(self.index_dir),
                self.embeddings,
                allow_dangerous_deserialization=True  # Safe since we created the index
            )
            logger.info("[PDF_SEARCH_V2] Index loaded successfully")
            return True

        except Exception as e:
            logger.error(f"[PDF_SEARCH_V2] Failed to load index: {e}")
            return False

    def initialize(self, force_update: bool = False):
        """Initialize the search index."""
        logger.info("[PDF_SEARCH_V2] Initializing search index")

        # Check if we need to update
        if not force_update and not self._needs_update():
            if self._load_index():
                logger.info("[PDF_SEARCH_V2] Using cached index")
                return
            else:
                logger.warning("[PDF_SEARCH_V2] Failed to load cache, rebuilding")

        # Download PDFs
        logger.info("[PDF_SEARCH_V2] Checking for PDF updates...")
        downloaded = 0
        for design in VALIDATED_DESIGNS:
            pdf_path = self._download_pdf(design)
            if pdf_path:
                downloaded += 1

        logger.info(f"[PDF_SEARCH_V2] {downloaded}/{len(VALIDATED_DESIGNS)} PDFs available")

        # Build index
        self._build_index()

        # Update metadata
        metadata = {
            "last_update": datetime.now().isoformat(),
            "pdf_count": downloaded,
            "model_name": self.model_name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap
        }
        self._save_metadata(metadata)

        logger.info("[PDF_SEARCH_V2] Initialization complete")

    def search(
        self,
        query: str,
        top_k: int = 5,
        product_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search the index using semantic similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product name to filter results

        Returns:
            List of search results with text, metadata, and score
        """
        if self.vectorstore is None:
            logger.error("[PDF_SEARCH_V2] Vector store not initialized")
            return []

        # Search with similarity scores
        if product_filter:
            # Filter by product in metadata
            filter_dict = {"product": product_filter.lower()}
            docs_and_scores = self.vectorstore.similarity_search_with_score(
                query,
                k=top_k * 2,  # Get more to account for filtering
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
            # Convert L2 distance to similarity score (lower is better for L2)
            # Normalize to 0-1 range where 1 is most similar
            similarity = 1.0 / (1.0 + score)

            results.append({
                "text": doc.page_content,
                "document": doc.metadata.get("document", "Unknown"),
                "product": doc.metadata.get("product", "unknown"),
                "type": doc.metadata.get("type", "unknown"),
                "slug": doc.metadata.get("slug", ""),
                "url": doc.metadata.get("url", ""),
                "score": float(similarity),
                "distance": float(score)
            })

        logger.info(f"[PDF_SEARCH_V2] Found {len(results)} results for: {query}")
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
        product: Optional product filter

    Returns:
        Formatted search results
    """
    index = get_pdf_search_index()

    if index.vectorstore is None:
        return "PDF search index not initialized. Please wait for initialization."

    # Perform search
    results = index.search(
        query,
        top_k=top_k,
        product_filter=product if product else None
    )

    if not results:
        return f"No results found in HashiCorp validated design PDFs for: '{query}'"

    # Format output
    output = [f"Found {len(results)} result(s) in HashiCorp Validated Designs:\n"]
    output.append("⚠️  IMPORTANT: Use ONLY the URLs provided below.\n")

    for idx, result in enumerate(results, 1):
        output.append(f"\n{idx}. [{result['product'].upper()}] {result['document']}")
        output.append(f"   URL: {result['url']}")
        output.append(f"   Relevance: {result['score']:.2f}")

        # Show most of the chunk (chunks are 1000 chars, show up to 900)
        # This ensures the LLM gets enough context to answer questions
        text_preview = result['text'][:900]
        if len(result['text']) > 900:
            text_preview += "..."

        output.append(f"   Content: {text_preview}")
        output.append("")

    return "\n".join(output)
