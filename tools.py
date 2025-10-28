"""Tool definitions for Vera."""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from langchain.tools import Tool
from langchain.pydantic_v1 import BaseModel, Field
import config


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


class NotesSearchInput(BaseModel):
    """Input schema for notes search tool."""
    query: str = Field(description="The search query to find in notes")


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

    if not notes_path.exists():
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
    for letter_dir in notes_path.iterdir():
        if not letter_dir.is_dir():
            continue

        for customer_dir in letter_dir.iterdir():
            if not customer_dir.is_dir():
                continue

            # Filter by customer name if provided
            if customer_name and customer_name.lower() not in customer_dir.name.lower():
                continue

            # Look for meetings directory (could be "10_Meetings" or similar)
            meetings_dirs = [d for d in customer_dir.iterdir() if d.is_dir() and "meeting" in d.name.lower()]

            for meetings_dir in meetings_dirs:
                # Search through markdown files
                for file_path in meetings_dir.glob("*.md"):
                    try:
                        content = file_path.read_text(encoding="utf-8")

                        # If content query is provided, check if it matches
                        if content_query and content_query.lower() not in content.lower():
                            continue

                        # Extract date from filename if possible (format: YYYY-MM-DD_...)
                        date_str = ""
                        import re
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

                    except Exception as e:
                        # Skip files that can't be read
                        continue

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

    # Limit results
    results = results[:limit]

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


def search_notes(query: str) -> str:
    """Search through notes in the notes directory.

    Args:
        query: The search query to find in notes

    Returns:
        A formatted string containing matching notes and their content
    """
    notes_path = Path(config.NOTES_DIR)

    if not notes_path.exists():
        return f"Notes directory '{config.NOTES_DIR}' does not exist."

    results: List[Dict[str, Any]] = []
    query_lower = query.lower()

    # Search through all text and markdown files
    for file_path in notes_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in [".txt", ".md", ".markdown"]:
            try:
                content = file_path.read_text(encoding="utf-8")

                # Find matching lines
                matching_lines = []
                for line_num, line in enumerate(content.splitlines(), 1):
                    if query_lower in line.lower():
                        matching_lines.append(f"  Line {line_num}: {line.strip()}")

                if matching_lines:
                    relative_path = file_path.relative_to(notes_path)
                    results.append({
                        "file": str(relative_path),
                        "matches": matching_lines
                    })
            except Exception as e:
                # Skip files that can't be read
                continue

    if not results:
        return f"No matches found for '{query}' in notes directory."

    # Format results
    output = [f"Found {len(results)} file(s) with matches for '{query}':\n"]
    for result in results:
        output.append(f"\n📄 {result['file']}")
        output.append("\n".join(result["matches"]))

    return "\n".join(output)


# Define the tools
current_date_tool = Tool(
    name="get_current_date",
    description="Get the current date and time. Useful when you need to know what day it is or the current date. You can optionally specify a format string.",
    func=get_current_date,
    args_schema=CurrentDateInput
)

notes_search_tool = Tool(
    name="search_notes",
    description="Search through notes stored in the notes directory. Use this when the user asks about their notes, wants to find information they've saved, or references something they may have written down.",
    func=search_notes,
    args_schema=NotesSearchInput
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

# Export all tools
ALL_TOOLS = [
    current_date_tool,
    notes_search_tool,
    customer_notes_search_tool,
    read_customer_note_tool
]
