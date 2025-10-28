"""Tool definitions for Vera."""
import os
import re
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from langchain.tools import Tool
from pydantic import BaseModel, Field
from duckduckgo_search import DDGS
import config

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
    """Search HashiCorp product documentation.

    This tool searches hashicorp.com domain for documentation and returns
    relevant results with titles, URLs, and descriptions. Use this when
    users ask questions about HashiCorp products like Terraform, Vault,
    Consul, Nomad, Packer, or Waypoint.

    Args:
        query: The search query
        product: Optional specific product to search (terraform, vault, consul, etc.)
        max_results: Maximum number of results (default 5, max 10)

    Returns:
        Formatted search results with titles, URLs, and descriptions
    """
    logger.info(f"[HASHICORP_SEARCH] Starting search")
    logger.info(f"[HASHICORP_SEARCH] Query: {query}")
    logger.info(f"[HASHICORP_SEARCH] Product: {product or 'ALL'}")

    # Limit results
    max_results = min(max(1, max_results), 10)

    # Build search query with site restriction
    search_query = f"site:hashicorp.com {query}"

    # If specific product is requested, add it to the query
    if product:
        product_lower = product.lower().strip()
        search_query = f"site:hashicorp.com/{product_lower} {query}"
        logger.info(f"[HASHICORP_SEARCH] Product-specific search: {search_query}")

    # Perform search with retry logic for rate limits
    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"[HASHICORP_SEARCH] Executing search (attempt {attempt + 1}/{max_retries}): {search_query}")

            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=max_results))

            logger.info(f"[HASHICORP_SEARCH] Found {len(results)} results")

            if not results:
                return f"No HashiCorp documentation found for query: '{query}'"

            # Format output
            output = [f"Found {len(results)} HashiCorp documentation result(s) for '{query}':\n"]

            for idx, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("href", "")
                description = result.get("body", "No description")

                output.append(f"\n{idx}. {title}")
                output.append(f"   URL: {url}")
                output.append(f"   {description}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            error_str = str(e)
            logger.warning(f"[HASHICORP_SEARCH] Attempt {attempt + 1} failed: {error_str}")

            # Check if it's a rate limit error
            if "ratelimit" in error_str.lower() and attempt < max_retries - 1:
                logger.info(f"[HASHICORP_SEARCH] Rate limit detected, waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue

            # If it's the last attempt or not a rate limit error, return error message
            error_msg = f"Unable to search HashiCorp docs at this time. "
            if "ratelimit" in error_str.lower():
                error_msg += "The search service is temporarily rate-limited. Please try again in a moment."
            else:
                error_msg += f"Error: {error_str}"

            logger.error(f"[HASHICORP_SEARCH] {error_msg}")
            return error_msg

    return "Unable to complete search after multiple attempts. Please try again later."


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
    description="Search HashiCorp product documentation (Terraform, Vault, Consul, Nomad, Packer, Waypoint, etc.). Use this when users ask questions about HashiCorp products, features, configurations, or best practices. Returns relevant documentation pages with titles, URLs, and descriptions.",
    func=search_hashicorp_docs,
    args_schema=HashiCorpDocsSearchInput
)

# Export all tools
ALL_TOOLS = [
    current_date_tool,
    customer_notes_search_tool,
    read_customer_note_tool,
    hashicorp_docs_search_tool
]
