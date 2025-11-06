"""Tool definitions for Ivan."""
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from langchain_core.tools import Tool
from pydantic.v1 import BaseModel, Field
from duckduckgo_search import DDGS
import ollama
import config
from hashicorp_doc_search import search_docs

# Configure logging
logger = logging.getLogger(__name__)


class CurrentDateInput(BaseModel):
    """Input schema for current date tool."""
    format: str = Field(
        default="%Y-%m-%d",
        description="The date format string (strftime format). Default is YYYY-MM-DD"
    )


def get_current_date(format: str = "%Y-%m-%d") -> str:
    """Get the current date and time.

    Args:
        format: The date format string (strftime format)

    Returns:
        The current date formatted as a string
    """
    return datetime.now().strftime(format)


class CustomerNotesSearchInput(BaseModel):
    """Input schema for customer notes search tool."""
    customer_name: str = Field(
        default="",
        description="The customer/account name to search for (e.g., 'Adobe', 'Microsoft'). Leave empty to search all customers."
    )
    content_query: str = Field(
        default="",
        description="Search for specific content within meeting notes. Leave empty to just list notes."
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return. Default is 10, max is 50."
    )
    sort_by_date: bool = Field(
        default=True,
        description="Sort results by date (newest first). Default is True."
    )


class ReadCustomerNoteInput(BaseModel):
    """Input schema for reading a customer note file."""
    file_path: str = Field(
        description="The relative path to the note file within Customer_Notes directory (e.g., 'A/Adobe/10_Meetings/2025-01-15_Discovery_Call.md')"
    )


def search_customer_notes(
    customer_name: str = "",
    content_query: str = "",
    limit: int = 10,
    sort_by_date: bool = True
) -> str:
    """Search through customer meeting notes.

    This tool searches the hierarchical customer notes directory structure
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

    logger.info(f"[CUSTOMER_NOTES_SEARCH] Starting search")
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Directory: {notes_path.absolute()}")
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Customer (original): {customer_name or 'ALL'}")
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Content query: {content_query or 'NONE'}")

    # Normalize customer name: replace spaces with underscores and handle aliases
    search_terms = []
    if customer_name:
        # Convert to lowercase for comparison
        customer_lower = customer_name.lower().strip()

        # Replace spaces with underscores (e.g., "Hewlett Packard" -> "hewlett_packard")
        normalized_name = customer_lower.replace(" ", "_")
        search_terms.append(normalized_name)

        # Check if it's an alias and add the full name
        if customer_lower in config.CUSTOMER_ALIASES:
            full_name = config.CUSTOMER_ALIASES[customer_lower]
            search_terms.append(full_name)
            logger.info(f"[CUSTOMER_NOTES_SEARCH] Alias detected: '{customer_name}' -> '{full_name}'")

        # Also add the original term with spaces replaced (for direct matches)
        if normalized_name not in search_terms:
            search_terms.append(normalized_name)

        logger.info(f"[CUSTOMER_NOTES_SEARCH] Search terms: {search_terms}")

    if not notes_path.exists():
        logger.warning(f"[CUSTOMER_NOTES_SEARCH] Directory does not exist: {notes_path.absolute()}")
        return (
            f"Customer notes directory '{config.CUSTOMER_NOTES_DIR}' does not exist.\n\n"
            f"To set up customer notes:\n"
            f"1. Create a symlink: ln -s /path/to/your/Customer_Notes {config.CUSTOMER_NOTES_DIR}\n"
            f"2. Or set CUSTOMER_NOTES_DIR environment variable to your notes path"
        )

    # Limit results
    limit = min(max(1, limit), 50)

    results: List[Dict[str, Any]] = []

    # Search through the hierarchical structure
    # Pattern: Customer_Notes/[Letter]/[Customer]/10_Meetings/*.md
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Scanning directory structure...")
    for letter_dir in notes_path.iterdir():
        if not letter_dir.is_dir():
            logger.debug(f"[CUSTOMER_NOTES_SEARCH] Skipping non-directory: {letter_dir.name}")
            continue

        logger.debug(f"[CUSTOMER_NOTES_SEARCH] Scanning letter directory: {letter_dir.name}")

        for customer_dir in letter_dir.iterdir():
            if not customer_dir.is_dir():
                logger.debug(f"[CUSTOMER_NOTES_SEARCH] Skipping non-directory: {customer_dir.name}")
                continue

            logger.debug(f"[CUSTOMER_NOTES_SEARCH] Found customer directory: {customer_dir.name}")

            # Filter by customer name if provided
            if search_terms:
                # Check if any search term matches this customer directory
                customer_dir_lower = customer_dir.name.lower()
                matches = any(term in customer_dir_lower for term in search_terms)

                if not matches:
                    logger.debug(f"[CUSTOMER_NOTES_SEARCH] Customer '{customer_dir.name}' doesn't match any search terms {search_terms}, skipping")
                    continue
                else:
                    logger.debug(f"[CUSTOMER_NOTES_SEARCH] Customer '{customer_dir.name}' matches search terms")

            # Look for meetings directory (could be "10_Meetings" or similar)
            meetings_dirs = [d for d in customer_dir.iterdir() if d.is_dir() and "meeting" in d.name.lower()]
            logger.info(f"[CUSTOMER_NOTES_SEARCH] Customer '{customer_dir.name}': found {len(meetings_dirs)} meeting directories")

            for meetings_dir in meetings_dirs:
                logger.debug(f"[CUSTOMER_NOTES_SEARCH] Scanning meeting directory: {meetings_dir.name}")

                # Search through markdown files
                md_files = list(meetings_dir.glob("*.md"))
                logger.info(f"[CUSTOMER_NOTES_SEARCH] Found {len(md_files)} markdown files in {meetings_dir.name}")

                for file_path in md_files:
                    logger.debug(f"[CUSTOMER_NOTES_SEARCH] Reading file: {file_path.name}")
                    try:
                        content = file_path.read_text(encoding="utf-8")

                        # If content query is provided, check if it matches
                        if content_query and content_query.lower() not in content.lower():
                            logger.debug(f"[CUSTOMER_NOTES_SEARCH] File '{file_path.name}' doesn't match content query, skipping")
                            continue

                        # Extract date from filename if possible (format: YYYY-MM-DD_...)
                        date_str = ""
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
                        if date_match:
                            date_str = date_match.group(1)

                        # Get relative path from Customer_Notes
                        relative_path = file_path.relative_to(notes_path)

                        # Get first few lines as preview
                        preview_lines = content.split('\n')[:5]
                        preview = '\n'.join(line for line in preview_lines if line.strip())

                        results.append({
                            "customer": customer_dir.name,
                            "file": str(relative_path),
                            "full_path": str(file_path),
                            "date": date_str,
                            "preview": preview[:200] + "..." if len(preview) > 200 else preview
                        })
                        logger.info(f"[CUSTOMER_NOTES_SEARCH] Added result: {file_path.name} (date: {date_str})")

                    except Exception as e:
                        logger.error(f"[CUSTOMER_NOTES_SEARCH] Error reading file {file_path}: {e}")
                        continue

    logger.info(f"[CUSTOMER_NOTES_SEARCH] Search complete. Found {len(results)} total results before sorting/limiting")

    if not results:
        search_terms = []
        if customer_name:
            search_terms.append(f"customer '{customer_name}'")
        if content_query:
            search_terms.append(f"content '{content_query}'")

        if search_terms:
            return f"No customer meeting notes found matching {' and '.join(search_terms)}."
        else:
            return "No customer meeting notes found in the directory."

    # Sort by date if requested
    if sort_by_date:
        results.sort(key=lambda x: x["date"], reverse=True)
        logger.debug(f"[CUSTOMER_NOTES_SEARCH] Results sorted by date")

    # Limit results
    results = results[:limit]
    logger.info(f"[CUSTOMER_NOTES_SEARCH] Returning {len(results)} results after limiting to {limit}")

    # Format output
    output = [f"Found {len(results)} customer meeting note(s):\n"]

    for idx, result in enumerate(results, 1):
        output.append(f"\n{idx}. [{result['customer']}] {result['file']}")
        if result['date']:
            output.append(f"   Date: {result['date']}")
        output.append(f"   Preview: {result['preview']}")
        output.append("")

    output.append(f"\nTo read full content, use read_customer_note with the file path.")

    return "\n".join(output)


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

    # Construct full path
    full_path = notes_path / file_path

    if not full_path.exists():
        return f"Note file not found: {file_path}"

    if not full_path.is_file():
        return f"Path is not a file: {file_path}"

    try:
        content = full_path.read_text(encoding="utf-8")
        return f"📄 {file_path}\n\n{content}"
    except Exception as e:
        return f"Error reading note file: {str(e)}"


class HashiCorpDocsSearchInput(BaseModel):
    """Input schema for HashiCorp docs search tool."""
    query: str = Field(
        description="The search query for HashiCorp documentation (e.g., 'Terraform module syntax', 'Vault authentication methods', 'Consul service mesh')"
    )
    product: str = Field(
        default="",
        description="Optional: Specific HashiCorp product to search (e.g., 'terraform', 'vault', 'consul', 'nomad', 'packer', 'waypoint'). Leave empty to search all products."
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return. Default is 5, max is 10."
    )


def search_hashicorp_docs(query: str, product: str = "", max_results: int = 5) -> str:
    """Search HashiCorp product documentation with web search fallback.

    This tool searches developer.hashicorp.com including all product documentation,
    validated designs, and technical guides. If local index confidence is low,
    automatically falls back to live web search for better coverage.

    ⚠️  CRITICAL: When citing HashiCorp resources:
    - Use ONLY the URLs provided in the search results
    - Do NOT generate, infer, or hallucinate URLs
    - If a URL is not provided in the results, do not make one up

    Args:
        query: The search query
        product: Optional specific product to search (terraform, vault, consul, etc.)
        max_results: Maximum number of results (default 5, max 10)

    Returns:
        Formatted search results from HashiCorp developer documentation with actual URLs
    """
    logger.info(f"[HASHICORP_SEARCH] Starting search")
    logger.info(f"[HASHICORP_SEARCH] Query: {query}")
    logger.info(f"[HASHICORP_SEARCH] Product: {product or 'ALL'}")

    # Limit results
    max_results = min(max(1, max_results), 10)

    # Confidence threshold for web search fallback
    CONFIDENCE_THRESHOLD = 6.0

    # Search using the doc crawler
    try:
        from hashicorp_doc_search import get_doc_search_index

        # Get raw results to check confidence scores
        index = get_doc_search_index()
        if index.vectorstore is None:
            index.initialize()

        raw_results = index.search(query, top_k=max_results, product_filter=product if product else None)

        # Check if we need web search fallback
        use_web_fallback = False
        if not raw_results:
            logger.info(f"[HASHICORP_SEARCH] No results from local index, falling back to web search")
            use_web_fallback = True
        elif raw_results[0]['score'] < CONFIDENCE_THRESHOLD:
            logger.info(f"[HASHICORP_SEARCH] Low confidence ({raw_results[0]['score']:.2f} < {CONFIDENCE_THRESHOLD}), falling back to web search")
            use_web_fallback = True

        # Format local results
        local_output = []
        if raw_results:
            local_output.append(f"Found {len(raw_results)} result(s) in HashiCorp Developer Documentation:\n")
            for idx, result in enumerate(raw_results, 1):
                local_output.append(f"\n{idx}. [{result['product'].upper()}]")
                local_output.append(f"   URL: {result['url']}")
                local_output.append(f"   Relevance: {result['score']:.2f}")
                text_preview = result['text'][:900]
                if len(result['text']) > 900:
                    text_preview += "..."
                local_output.append(f"   Content: {text_preview}")
                local_output.append("")

        # If confidence is high, return local results only
        if not use_web_fallback:
            results = "\n".join(local_output)
            logger.info(f"[HASHICORP_SEARCH] High confidence results, returning local index only")
            logger.debug(f"[HASHICORP_SEARCH] === TOOL RETURNING TO LLM ===")
            logger.debug(f"[HASHICORP_SEARCH] First 500 chars: {results[:500]}")
            logger.debug(f"[HASHICORP_SEARCH] === END TOOL RETURN ===")
            return results

        # Add web search fallback
        try:
            logger.info(f"[HASHICORP_SEARCH] Fetching web search results...")
            # Add site filter for HashiCorp docs
            web_query = f"{query} site:developer.hashicorp.com"

            # Try DuckDuckGo first (free, no API key needed)
            try:
                web_results = ddg_web_search(web_query, max_results=5)
            except Exception as ddg_error:
                logger.warning(f"[HASHICORP_SEARCH] DuckDuckGo search failed: {ddg_error}")
                # DuckDuckGo failed, return local results only
                web_results = []

            if web_results:
                logger.info(f"[HASHICORP_SEARCH] Found {len(web_results)} web results")

                # Format combined results
                output = []
                if local_output:
                    output.extend(local_output)
                    output.append("\n" + "="*80)
                    output.append("⚠️  Note: Local index confidence was low. Adding live web search results below:")
                    output.append("="*80 + "\n")
                else:
                    output.append("No results in local index. Showing live web search results:\n")

                for idx, result in enumerate(web_results, 1):
                    output.append(f"\n{len(raw_results) + idx}. [WEB SEARCH]")
                    output.append(f"   URL: {result['url']}")
                    output.append(f"   Title: {result['title']}")
                    output.append(f"   Content: {result['description'][:600]}")
                    output.append("")

                combined_results = "\n".join(output)
                logger.debug(f"[HASHICORP_SEARCH] === TOOL RETURNING TO LLM (with web fallback) ===")
                logger.debug(f"[HASHICORP_SEARCH] First 500 chars: {combined_results[:500]}")
                logger.debug(f"[HASHICORP_SEARCH] === END TOOL RETURN ===")
                return combined_results
            else:
                logger.warning(f"[HASHICORP_SEARCH] Web search returned no results")
                if local_output:
                    return "\n".join(local_output)
                else:
                    return f"No results found for: '{query}'"

        except Exception as web_error:
            logger.error(f"[HASHICORP_SEARCH] Web search failed: {web_error}")
            # Fall back to local results if web search fails
            if local_output:
                return "\n".join(local_output)
            else:
                return f"Search completed but web fallback failed: {str(web_error)}"

    except Exception as e:
        logger.error(f"[HASHICORP_SEARCH] Search failed: {e}")
        return f"Error searching HashiCorp documentation: {str(e)}"


def ollama_web_search(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search the web using Ollama's search API.

    Args:
        query: The search query
        max_results: Maximum number of results (not enforced by API, but used for consistency)

    Returns:
        List of search result dictionaries with 'title', 'url', and 'description' keys

    Raises:
        Exception: If API key is not configured or API call fails
    """
    if not config.OLLAMA_API_KEY:
        raise ValueError("OLLAMA_API_KEY not configured")

    logger.info(f"[OLLAMA_SEARCH] Searching with query: {query}")

    try:
        # Create client with API key
        client = ollama.Client(headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"})

        # Use the official web_search method
        response = client.web_search(query)

        results = []

        # Parse response: response is a dict with 'results' key containing list of results
        if hasattr(response, 'get'):
            items = response.get('results', [])
        elif hasattr(response, 'results'):
            items = response.results
        else:
            # If response is already a list
            items = response if isinstance(response, list) else []

        # Limit to max_results
        for item in items[:max_results]:
            results.append({
                "title": item.get("title", "No title"),
                "url": item.get("url", ""),
                "description": item.get("content", "No description")
            })

        logger.info(f"[OLLAMA_SEARCH] Found {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"[OLLAMA_SEARCH] Search failed: {e}")
        import traceback
        logger.error(f"[OLLAMA_SEARCH] Traceback: {traceback.format_exc()}")
        raise


def ddg_web_search(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search the web using DuckDuckGo (free, rate-limited).

    Args:
        query: The search query
        max_results: Maximum number of results

    Returns:
        List of search result dictionaries with 'title', 'url', and 'description' keys

    Raises:
        Exception: If search fails
    """
    logger.info(f"[DDG_SEARCH] Searching with query: {query}")

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*AsyncSession.*")
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))

        results = []
        for item in raw_results:
            results.append({
                "title": item.get("title", "No title"),
                "url": item.get("href", ""),
                "description": item.get("body", "No description")
            })

        logger.info(f"[DDG_SEARCH] Found {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"[DDG_SEARCH] Search failed: {e}")
        raise


def web_search(query: str, max_results: int = 10, site: str = "") -> str:
    """Search the web using Ollama API if available, otherwise fall back to DuckDuckGo.

    Args:
        query: The search query
        max_results: Maximum number of results (default 10)
        site: Optional site restriction (e.g., 'hashicorp.com')

    Returns:
        Formatted string with search results
    """
    # Build search query with site restriction if provided
    search_query = f"site:{site} {query}" if site else query

    results = []
    search_method = "unknown"

    # Try Ollama first if API key is configured
    if config.OLLAMA_API_KEY:
        try:
            logger.info("[WEB_SEARCH] Using Ollama search API")
            results = ollama_web_search(search_query, max_results)
            search_method = "Ollama"
        except Exception as e:
            logger.warning(f"[WEB_SEARCH] Ollama search failed, falling back to DuckDuckGo: {e}")
            # Fall through to DuckDuckGo

    # Fall back to DuckDuckGo if Ollama not available or failed
    if not results:
        try:
            logger.info("[WEB_SEARCH] Using DuckDuckGo search")
            results = ddg_web_search(search_query, max_results)
            search_method = "DuckDuckGo"
        except Exception as e:
            error_str = str(e)
            if "ratelimit" in error_str.lower():
                return "Web search is currently rate-limited. Please try again in a few moments or configure OLLAMA_API_KEY in your .env file for unlimited searches."
            else:
                return f"Web search failed: {error_str}"

    # Format results
    if not results:
        return f"No web results found for query: '{query}'"

    output = [f"Found {len(results)} web result(s) via {search_method}:\n"]

    for idx, result in enumerate(results, 1):
        output.append(f"\n{idx}. {result['title']}")
        output.append(f"   URL: {result['url']}")
        output.append(f"   {result['description']}")
        output.append("")

    return "\n".join(output)


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""
    query: str = Field(
        description="The search query (e.g., 'Python async programming best practices', 'Docker container networking')"
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of results to return. Default is 10."
    )


# Define the tools
current_date_tool = Tool(
    name="get_current_date",
    description="Get the current date and time. Useful when you need to know what day it is or the current date. You can optionally specify a format string.",
    func=get_current_date,
    args_schema=CurrentDateInput
)

customer_notes_search_tool = Tool(
    name="search_customer_notes",
    description="Search through customer meeting notes in the hierarchical Customer_Notes directory. Use this when preparing SE weekly updates to gather recent customer activity, or when the user asks about specific customer meetings. Searches by customer name, content, and returns notes sorted by date (newest first).",
    func=search_customer_notes,
    args_schema=CustomerNotesSearchInput
)

read_customer_note_tool = Tool(
    name="read_customer_note",
    description="Read the full content of a specific customer meeting note. Use this after finding relevant notes with search_customer_notes to get complete details about a meeting.",
    func=read_customer_note,
    args_schema=ReadCustomerNoteInput
)

hashicorp_docs_search_tool = Tool(
    name="search_hashicorp_docs",
    description="Search HashiCorp product documentation including validated design PDFs and online docs (Terraform, Vault, Consul, Nomad, Packer, Waypoint, etc.). Provides comprehensive results from both official validated design documents and web documentation. Use this when users ask questions about HashiCorp products, features, configurations, best practices, or architecture patterns.",
    func=search_hashicorp_docs,
    args_schema=HashiCorpDocsSearchInput
)

web_search_tool = Tool(
    name="web_search",
    description="Search the web for general information using Ollama API (if configured) or DuckDuckGo. Use this for finding current information, documentation, tutorials, Stack Overflow answers, or any online resources. Returns titles, URLs, and descriptions of relevant pages.",
    func=web_search,
    args_schema=WebSearchInput
)

# Export all tools
ALL_TOOLS = [
    current_date_tool,
    customer_notes_search_tool,
    read_customer_note_tool,
    hashicorp_docs_search_tool,
    web_search_tool
]
