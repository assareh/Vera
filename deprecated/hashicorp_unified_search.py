"""HashiCorp Unified Search - Combines PDF and Web Documentation.

Uses LangChain's EnsembleRetriever to search across both:
- Validated Design PDFs
- Developer documentation web pages
"""
import logging
from typing import List, Dict, Any, Optional

from langchain.retrievers import EnsembleRetriever
from langchain.schema import Document

from hashicorp_pdf_search import get_pdf_search_index, HashiCorpPDFSearchIndex
from hashicorp_web_search import get_web_search_index, HashiCorpWebSearchIndex

# Configure logging
logger = logging.getLogger(__name__)


class HashiCorpUnifiedSearch:
    """Unified search across PDF and web documentation using ensemble retrieval."""

    def __init__(
        self,
        pdf_weight: float = 0.5,
        web_weight: float = 0.5
    ):
        """Initialize unified search.

        Args:
            pdf_weight: Weight for PDF search results (0-1)
            web_weight: Weight for web search results (0-1)
        """
        self.pdf_index: Optional[HashiCorpPDFSearchIndex] = None
        self.web_index: Optional[HashiCorpWebSearchIndex] = None
        self.pdf_weight = pdf_weight
        self.web_weight = web_weight
        self.ensemble_retriever: Optional[EnsembleRetriever] = None

        logger.info(f"[UNIFIED_SEARCH] Initialized (pdf_weight={pdf_weight}, web_weight={web_weight})")

    def initialize(
        self,
        force_pdf_update: bool = False,
        force_web_update: bool = False,
        max_web_pages: Optional[int] = None
    ):
        """Initialize both search indices.

        Args:
            force_pdf_update: Force rebuild of PDF index
            force_web_update: Force rebuild of web index
            max_web_pages: Limit web pages (for testing)
        """
        logger.info("[UNIFIED_SEARCH] Initializing search indices...")

        # Initialize PDF index
        logger.info("[UNIFIED_SEARCH] Initializing PDF index...")
        self.pdf_index = get_pdf_search_index()
        self.pdf_index.initialize(force_update=force_pdf_update)

        # Initialize web index
        logger.info("[UNIFIED_SEARCH] Initializing web index...")
        if max_web_pages is not None:
            # For testing, create a new instance with limited pages
            from hashicorp_web_search import HashiCorpWebSearchIndex
            self.web_index = HashiCorpWebSearchIndex(max_pages=max_web_pages)
        else:
            self.web_index = get_web_search_index()

        self.web_index.initialize(force_update=force_web_update)

        # Create ensemble retriever
        if self.pdf_index.vectorstore and self.web_index.vectorstore:
            logger.info("[UNIFIED_SEARCH] Creating ensemble retriever...")
            pdf_retriever = self.pdf_index.vectorstore.as_retriever(search_kwargs={"k": 5})
            web_retriever = self.web_index.vectorstore.as_retriever(search_kwargs={"k": 5})

            self.ensemble_retriever = EnsembleRetriever(
                retrievers=[pdf_retriever, web_retriever],
                weights=[self.pdf_weight, self.web_weight]
            )

            logger.info("[UNIFIED_SEARCH] Ensemble retriever created successfully")
        else:
            logger.error("[UNIFIED_SEARCH] Failed to create ensemble retriever - indices not initialized")

        logger.info("[UNIFIED_SEARCH] Initialization complete")

    def search(
        self,
        query: str,
        top_k: int = 5,
        product_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search across both PDF and web documentation.

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product name to filter results

        Returns:
            List of search results with text, metadata, and source
        """
        if self.ensemble_retriever is None:
            logger.error("[UNIFIED_SEARCH] Ensemble retriever not initialized")
            return []

        try:
            # Use ensemble retriever
            docs = self.ensemble_retriever.get_relevant_documents(query)

            # Apply product filter if specified
            if product_filter:
                docs = [d for d in docs if d.metadata.get("product", "").lower() == product_filter.lower()]

            # Limit to top_k
            docs = docs[:top_k]

            # Format results
            results = []
            for doc in docs:
                result = {
                    "text": doc.page_content,
                    "product": doc.metadata.get("product", "unknown"),
                    "url": doc.metadata.get("url", ""),
                    "source": doc.metadata.get("source", "unknown"),
                }

                # Add source-specific fields
                if result["source"] == "pdf" or "document" in doc.metadata:
                    result["document"] = doc.metadata.get("document", "")
                    result["type"] = doc.metadata.get("type", "")

                results.append(result)

            logger.info(f"[UNIFIED_SEARCH] Found {len(results)} results for: {query}")
            return results

        except Exception as e:
            logger.error(f"[UNIFIED_SEARCH] Search failed: {e}")
            return []

    def search_pdf_only(
        self,
        query: str,
        top_k: int = 5,
        product_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search only PDF documentation.

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product filter

        Returns:
            List of search results from PDFs only
        """
        if self.pdf_index is None:
            logger.error("[UNIFIED_SEARCH] PDF index not initialized")
            return []

        return self.pdf_index.search(query, top_k, product_filter)

    def search_web_only(
        self,
        query: str,
        top_k: int = 5,
        product_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search only web documentation.

        Args:
            query: Search query
            top_k: Number of results to return
            product_filter: Optional product filter

        Returns:
            List of search results from web docs only
        """
        if self.web_index is None:
            logger.error("[UNIFIED_SEARCH] Web index not initialized")
            return []

        return self.web_index.search(query, top_k, product_filter)


# Global instance
_unified_search: Optional[HashiCorpUnifiedSearch] = None


def get_unified_search() -> HashiCorpUnifiedSearch:
    """Get or create the global unified search instance."""
    global _unified_search
    if _unified_search is None:
        _unified_search = HashiCorpUnifiedSearch()
    return _unified_search


def initialize_unified_search(
    force_pdf_update: bool = False,
    force_web_update: bool = False,
    max_web_pages: Optional[int] = None
):
    """Initialize unified search (call on startup).

    Args:
        force_pdf_update: Force rebuild of PDF index
        force_web_update: Force rebuild of web index
        max_web_pages: Limit web pages (for testing)
    """
    search = get_unified_search()
    search.initialize(
        force_pdf_update=force_pdf_update,
        force_web_update=force_web_update,
        max_web_pages=max_web_pages
    )


def search_hashicorp_docs(
    query: str,
    top_k: int = 5,
    product: str = "",
    source: str = "all"
) -> str:
    """Search HashiCorp documentation (PDF + Web).

    Args:
        query: Search query
        top_k: Number of results to return
        product: Optional product filter
        source: Source filter - "all", "pdf", or "web"

    Returns:
        Formatted search results
    """
    search = get_unified_search()

    if search.ensemble_retriever is None and source == "all":
        return "Search indices not initialized. Please wait for initialization."

    # Route to appropriate search
    if source == "pdf":
        results = search.search_pdf_only(query, top_k, product if product else None)
    elif source == "web":
        results = search.search_web_only(query, top_k, product if product else None)
    else:
        results = search.search(query, top_k, product if product else None)

    if not results:
        return f"No results found in HashiCorp documentation for: '{query}'"

    # Format output
    output = [f"Found {len(results)} result(s) in HashiCorp Documentation:\n"]
    output.append("⚠️  IMPORTANT: Use ONLY the URLs provided below.\n")

    for idx, result in enumerate(results, 1):
        source_label = result.get("source", "unknown").upper()
        product_label = result.get("product", "unknown").upper()

        output.append(f"\n{idx}. [{product_label}] ({source_label})")

        # Add document name for PDFs
        if "document" in result:
            output.append(f"   Document: {result['document']}")

        output.append(f"   URL: {result['url']}")

        # Show score if available
        if "score" in result:
            output.append(f"   Relevance: {result['score']:.2f}")

        # Show preview
        text_preview = result['text'][:900]
        if len(result['text']) > 900:
            text_preview += "..."

        output.append(f"   Content: {text_preview}")
        output.append("")

    return "\n".join(output)
