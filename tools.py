"""Tool definitions for Ivan - customer notes search and documentation search."""

import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from llm_api_server import BUILTIN_TOOLS, create_web_search_tool

from config import config

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Customer Notes Tools
# =============================================================================


@tool
def search_customer_notes(
    customer_name: str = "",
    content_query: str = "",
    limit: int = 10,
    sort_by_date: bool = True,
) -> str:
    """Search through customer meeting notes.

    Searches the hierarchical Customer_Notes directory structure
    (Customer_Notes/[A-Z,0-9]/[Customer]/10_Meetings/*.md) to find relevant
    meeting notes.

    Args:
        customer_name: Filter by customer/account name (case-insensitive)
        content_query: Search for specific content within notes
        limit: Maximum number of results to return (default 10, max 50)
        sort_by_date: Sort by date, newest first (default True)

    Returns:
        A formatted string with matching notes, their paths, dates, and previews
    """
    notes_path = Path(config.CUSTOMER_NOTES_DIR)

    logger.info(f"[CUSTOMER_NOTES_SEARCH] Directory: {notes_path.absolute()}")
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Customer: {customer_name or 'ALL'}")
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Content query: {content_query or 'NONE'}")

    # Normalize customer name: replace spaces with underscores
    search_terms = []
    if customer_name:
        customer_lower = customer_name.lower().strip()
        normalized_name = customer_lower.replace(" ", "_")
        search_terms.append(normalized_name)
        if normalized_name != customer_lower:
            search_terms.append(customer_lower)

    if not notes_path.exists():
        return (
            f"Customer notes directory '{config.CUSTOMER_NOTES_DIR}' does not exist.\n\n"
            f"To set up customer notes:\n"
            f"1. Create a symlink: ln -s /path/to/your/Customer_Notes {config.CUSTOMER_NOTES_DIR}\n"
            f"2. Or set CUSTOMER_NOTES_DIR environment variable to your notes path"
        )

    limit = min(max(1, limit), 50)
    results: list[dict[str, Any]] = []

    for letter_dir in notes_path.iterdir():
        if not letter_dir.is_dir():
            continue

        for customer_dir in letter_dir.iterdir():
            if not customer_dir.is_dir():
                continue

            if search_terms:
                customer_dir_lower = customer_dir.name.lower()
                if not any(term in customer_dir_lower for term in search_terms):
                    continue

            meetings_dirs = [d for d in customer_dir.iterdir() if d.is_dir() and "meeting" in d.name.lower()]

            for meetings_dir in meetings_dirs:
                for file_path in meetings_dir.glob("*.md"):
                    try:
                        content = file_path.read_text(encoding="utf-8")

                        if content_query and content_query.lower() not in content.lower():
                            continue

                        date_str = ""
                        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", file_path.name)
                        if date_match:
                            date_str = date_match.group(1)

                        relative_path = file_path.relative_to(notes_path)
                        preview_lines = content.split("\n")[:5]
                        preview = "\n".join(line for line in preview_lines if line.strip())

                        results.append(
                            {
                                "customer": customer_dir.name,
                                "file": str(relative_path),
                                "full_path": str(file_path),
                                "date": date_str,
                                "preview": preview[:200] + "..." if len(preview) > 200 else preview,
                            }
                        )

                    except Exception as e:
                        logger.error(f"[CUSTOMER_NOTES_SEARCH] Error reading {file_path}: {e}")
                        continue

    logger.info(f"[CUSTOMER_NOTES_SEARCH] Found {len(results)} results")

    if not results:
        search_terms_display = []
        if customer_name:
            search_terms_display.append(f"customer '{customer_name}'")
        if content_query:
            search_terms_display.append(f"content '{content_query}'")

        if search_terms_display:
            return f"No customer meeting notes found matching {' and '.join(search_terms_display)}."
        else:
            return "No customer meeting notes found in the directory."

    if sort_by_date:
        results.sort(key=lambda x: x["date"], reverse=True)

    results = results[:limit]

    output = [f"Found {len(results)} customer meeting note(s):\n"]

    for idx, result in enumerate(results, 1):
        output.append(f"\n{idx}. [{result['customer']}] {result['file']}")
        if result["date"]:
            output.append(f"   Date: {result['date']}")
        output.append(f"   Preview: {result['preview']}")
        output.append("")

    output.append("\nTo read full content, use read_customer_note with the file path.")

    return "\n".join(output)


@tool
def read_customer_note(file_path: str) -> str:
    """Read the full content of a customer meeting note.

    Args:
        file_path: Relative path from Customer_Notes directory
                  (e.g., 'A/Adobe/10_Meetings/2025-01-15_Discovery_Call.md')

    Returns:
        The full content of the note file
    """
    notes_path = Path(config.CUSTOMER_NOTES_DIR)

    if not notes_path.exists():
        return (
            f"Customer notes directory '{config.CUSTOMER_NOTES_DIR}' does not exist.\n\n"
            f"To set up customer notes:\n"
            f"1. Create a symlink: ln -s /path/to/your/Customer_Notes {config.CUSTOMER_NOTES_DIR}\n"
            f"2. Or set CUSTOMER_NOTES_DIR environment variable to your notes path"
        )

    full_path = notes_path / file_path

    if not full_path.exists():
        return f"Note file not found: {file_path}"

    if not full_path.is_file():
        return f"Path is not a file: {file_path}"

    try:
        content = full_path.read_text(encoding="utf-8")
        return f"--- {file_path} ---\n\n{content}"
    except Exception as e:
        return f"Error reading note file: {e!s}"


# =============================================================================
# Documentation Search Tool
# =============================================================================

_doc_index = None
_doc_search_tool = None


def initialize_rag_at_startup() -> None:
    """Initialize RAG index at startup if enabled.

    This ensures the index is built before the first request,
    avoiding delays for the first user. Creates a doc_search tool
    that the model can use to search HashiCorp documentation.
    """
    if not config.RAG_ENABLED:
        print("RAG disabled (set RAG_ENABLED=true to enable)")
        return

    try:
        from llm_api_server.rag import DocSearchIndex, RAGConfig

        global _doc_index, _doc_search_tool

        # Validate that RAG sources are configured
        if not config.RAG_DOC_SOURCES or not config.RAG_DOC_SOURCES[0]:
            print("\nWarning: RAG_ENABLED=true but RAG_DOC_SOURCES not configured")
            print("  Set RAG_DOC_SOURCES in .env (comma-separated URLs)")
            return

        print("")
        print("=" * 60)
        print("⏳ PLEASE WAIT: Loading indexes may take several minutes")
        print("=" * 60)
        print("")
        print("Initializing HashiCorp documentation search index...")
        print(f"  Sources: {', '.join(config.RAG_DOC_SOURCES)}")

        # Combine any extra doc sources with explicit manual URLs
        manual_urls = list(config.RAG_MANUAL_URLS)
        if len(config.RAG_DOC_SOURCES) > 1:
            manual_urls.extend(config.RAG_DOC_SOURCES[1:])

        rag_config = RAGConfig(
            base_url=config.RAG_DOC_SOURCES[0],
            cache_dir=config.RAG_CACHE_DIR,
            manual_urls=manual_urls,
            manual_urls_only=False,
            max_crawl_depth=config.RAG_MAX_CRAWL_DEPTH,
            rate_limit_delay=config.RAG_RATE_LIMIT_DELAY,
            max_workers=config.RAG_MAX_WORKERS,
            max_pages=config.RAG_MAX_PAGES,
            url_include_patterns=config.RAG_URL_INCLUDE_PATTERNS,
            url_exclude_patterns=config.RAG_URL_EXCLUDE_PATTERNS,
            hybrid_bm25_weight=config.RAG_BM25_WEIGHT,
            hybrid_semantic_weight=config.RAG_SEMANTIC_WEIGHT,
            search_top_k=config.RAG_TOP_K,
            rerank_enabled=config.RAG_RERANK_ENABLED,
            update_check_interval_hours=config.RAG_UPDATE_INTERVAL_HOURS,
        )

        _doc_index = DocSearchIndex(rag_config)

        if _doc_index.needs_update():
            print("Building RAG index (this may take several minutes)...")
            _doc_index.crawl_and_index()
            print("✓ RAG index built successfully")
        else:
            print("Loading cached RAG index...")
            _doc_index.load_index()
            print("✓ RAG index loaded successfully")

        # Track doc search calls per session (resets after 5 min of inactivity)
        import time as _time

        _doc_search_state = {"call_count": 0, "last_call": 0}
        _DOC_SEARCH_LIMIT = 2  # Allow 2 searches before forcing web_search
        _SESSION_TIMEOUT = 300  # 5 minutes - reset counter after this

        # Create a custom doc search tool with fallback reminder after 2nd search
        @tool
        def hashicorp_doc_search(query: str, top_k: int = 5) -> str:
            """Search HashiCorp documentation for technical information about Terraform, Vault, Consul,
            Nomad, Packer, Boundary, Waypoint, and other HashiCorp products. Returns relevant text
            excerpts with source URLs. You can try up to 2 different searches, then use web_search.

            Args:
                query: The search query to find relevant documentation
                top_k: Number of results to return (default 5)

            Returns:
                Relevant documentation excerpts with source URLs
            """
            nonlocal _doc_search_state

            # Reset counter if session timed out (new conversation)
            current_time = _time.time()
            if current_time - _doc_search_state["last_call"] > _SESSION_TIMEOUT:
                _doc_search_state["call_count"] = 0

            _doc_search_state["call_count"] += 1
            _doc_search_state["last_call"] = current_time
            call_count = _doc_search_state["call_count"]

            results = _doc_index.search(query, top_k=top_k)

            if not results:
                if call_count >= _DOC_SEARCH_LIMIT:
                    return (
                        "No relevant documentation found.\n\n"
                        "⚠️ STOP: You've searched documentation twice with no good results. "
                        "Use web_search NOW to find the answer."
                    )
                return (
                    "No relevant documentation found for this query.\n"
                    f"You have {_DOC_SEARCH_LIMIT - call_count} doc search(es) remaining before you must use web_search."
                )

            # Format results - search() returns list of dicts with keys: text, url, heading_path, metadata, score
            output_parts = []
            for i, result in enumerate(results, 1):
                source = result.get("url", "Unknown source")
                content = result.get("text", "")
                heading = result.get("heading_path", "")
                if heading:
                    output_parts.append(f"[{i}] Source: {source}\nSection: {heading}\n{content}")
                else:
                    output_parts.append(f"[{i}] Source: {source}\n{content}")

            formatted_results = "\n\n---\n\n".join(output_parts)

            # Add reminder based on call count
            if call_count >= _DOC_SEARCH_LIMIT:
                reminder = (
                    "\n\n" + "=" * 60 + "\n"
                    "⚠️ STOP: This is your 2nd doc search. If these results don't answer "
                    "the question, you MUST use web_search now. No more doc searches allowed.\n"
                    + "=" * 60
                )
            else:
                remaining = _DOC_SEARCH_LIMIT - call_count
                reminder = (
                    f"\n\n[Doc search {call_count}/{_DOC_SEARCH_LIMIT}. "
                    f"If not helpful, you can try {remaining} more, then must use web_search.]"
                )

            return formatted_results + reminder

        _doc_search_tool = hashicorp_doc_search

    except ImportError as e:
        print(f"\nWarning: RAG dependencies not available: {e}")
        print("  Install with: uv sync")
    except Exception as e:
        print(f"\nError initializing RAG: {e}")


# =============================================================================
# Tool Exports
# =============================================================================

# Create web search tool (requires config for API key)
web_search = create_web_search_tool(config)

# Ivan-specific tools
IVAN_TOOLS = [
    search_customer_notes,
    read_customer_note,
]


def get_all_tools():
    """Get all available tools, including dynamically initialized ones.

    Combines:
    - BUILTIN_TOOLS from llm-api-server (get_current_datetime, calculate, etc.)
    - Ivan-specific tools (customer notes)
    - Config-dependent tools (web_search)
    - Dynamically initialized tools (hashicorp_doc_search)
    """
    tools = list(BUILTIN_TOOLS)  # Start with builtin tools from llm-api-server
    tools.extend(IVAN_TOOLS)  # Add Ivan-specific tools
    tools.append(web_search)  # Add web search (requires config)

    # Add doc search tool if RAG is enabled and initialized
    if _doc_search_tool is not None:
        tools.append(_doc_search_tool)

    return tools


# For backward compatibility - basic tools available at import time
ALL_TOOLS = list(BUILTIN_TOOLS) + IVAN_TOOLS + [web_search]
