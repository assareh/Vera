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

# Export all tools
ALL_TOOLS = [current_date_tool, notes_search_tool]
