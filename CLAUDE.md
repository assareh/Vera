# Ivan Project Documentation for Claude Code

## Project Overview

Ivan is a Flask-based AI chatbot application that provides an OpenAI-compatible API for local LLM backends (Ollama and LM Studio). It features tool calling capabilities, optional Open Web UI integration, and a Chrome extension for automating SE Weekly Updates in Salesforce.

**Model Name**: `wwtfo/ivan` (advertised in API responses)

## Architecture

### Core Components

1. **ivan.py** - Main Flask application
   - Handles OpenAI-compatible `/v1/chat/completions` endpoint
   - Manages tool calling and function execution
   - Implements smart system prompt caching based on file modification time
   - Starts optional Open Web UI integration

2. **config.py** - Configuration management
   - Environment variable loading
   - Backend configuration (LM Studio/Ollama)
   - Default settings and paths
   - Customer name aliases

3. **tools.py** - Tool definitions using LangChain
   - Current date/time tool
   - Customer notes search (hierarchical directory search)
   - Customer note reader
   - File search tool
   - Web search tool (DuckDuckGo)
   - All tools use LangChain's Tool and BaseModel (pydantic_v1)

4. **system_prompt.md** - Customizable system prompt
   - Cached and auto-reloaded on modification
   - Defines Ivan's personality and behavior

### Chrome Extension (ivan-extension/)

Browser extension for automating SE Weekly Updates with AI assistance.

**Key Files**:
- `manifest.json` - Extension configuration
- `popup.html/js/css` - Extension UI (chat interface)
- `content.js/css` - Page interaction (extracts context, fills forms)
- `background.js` - Background service worker

**Features**:
- Quick action buttons for common tasks
- Context-aware (extracts opportunity title, user initials from page)
- Chat interface for refinement
- Auto-fill capability for Salesforce fields

## Directory Structure

```
Ivan/
├── ivan.py                      # Main Flask application
├── config.py                    # Configuration management
├── tools.py                     # Tool definitions (LangChain)
├── hashicorp_web_search.py      # Web crawler search (LangChain FAISS)
├── system_prompt.md             # System prompt (auto-cached)
├── requirements.txt             # Python dependencies (includes open-webui)
├── setup.sh                     # Automated setup script (Python + venv + deps)
├── .env.example                 # Example environment variables
├── .python-version              # Python version (3.12.0)
│
├── notes/                       # Personal notes directory
├── Customer_Notes/              # Symlink to customer meeting notes (optional)
│   └── [A-Z]/                   # Alphabetically organized by customer
│       └── [Customer]/
│           └── 10_Meetings/
│               └── *.md         # Meeting notes (YYYY-MM-DD_Title.md)
│
├── hashicorp_web_docs/          # HashiCorp web documentation cache
│   ├── pages/                   # Cached HTML content
│   ├── index/                   # LangChain FAISS vector index
│   │   ├── index.faiss          # FAISS vector index
│   │   └── index.pkl            # Document metadata
│   ├── metadata.json            # Index metadata & update tracking
│   ├── sitemap.xml              # Cached sitemap
│   └── chunks.json              # Document chunks
│
├── tests/                       # Test suite (see tests/README.md)
│   ├── README.md                # Test documentation
│   ├── test_comparison.py       # Primary regression test (REQUIRED)
│   ├── test_debug_chunks.py     # Debug tool for search results
│   └── test_validated_designs.py
│
├── ivan-extension/              # Chrome extension
│   ├── manifest.json
│   ├── popup.html/js/css
│   ├── content.js/css
│   ├── background.js
│   └── icon*.png
│
├── venv/                        # Python virtual environment (3.12.0)
├── deprecated/                  # Deprecated code (old PDF search, etc.)
└── docs/                        # Documentation and images
```

## Technology Stack

### Backend
- **Flask 3.0.0** - Web framework
- **LangChain 0.1.0** - Tool calling framework
- **Requests** - HTTP client for LLM backends
- **Click** - CLI argument parsing
- **python-dotenv** - Environment variable management

### AI/ML Features
- **sentence-transformers** - Semantic search embeddings
- **faiss-cpu** - Vector similarity search
- **duckduckgo-search** - Web search integration

### Web Scraping
- **beautifulsoup4** - HTML parsing and content extraction
- **requests** - HTTP client for web crawling

### Optional
- **open-webui** - Web UI (requires Python 3.11-3.12)

### Extension
- Vanilla JavaScript (no build step)
- Chrome Extension Manifest V3

## Environment Configuration

### Environment Variables

```bash
# Backend Selection
IVAN_BACKEND=lmstudio          # or "ollama"
BACKEND_MODEL=openai/gpt-oss-20b  # Model name for backend

# Backend Endpoints
LMSTUDIO_ENDPOINT=http://localhost:1234/v1
OLLAMA_ENDPOINT=http://localhost:11434

# Ivan Settings
IVAN_PORT=8000
IVAN_TEMPERATURE=0.0
SYSTEM_PROMPT_PATH=system_prompt.md
NOTES_DIR=notes
CUSTOMER_NOTES_DIR=Customer_Notes  # Or absolute path
```

### Configuration Defaults (config.py:6-38)
- Default backend: LM Studio
- Default model: `openai/gpt-oss-20b`
- Default port: 8000
- Default temperature: 0.0

## Development Setup

### Python Version Requirements
- **Core functionality**: Python 3.8+
- **With Open Web UI**: Python 3.11-3.12 (not compatible with 3.14+)
- **Current setup**: Python 3.12.0 (via pyenv, see .python-version)

### Quick Start

**First-time setup (or after Python version updates):**
```bash
# Run setup script to create venv with correct Python version
# This automatically installs all dependencies and applies HashiCorp branding
./setup.sh

# Activate virtual environment
source venv/bin/activate
```

**Subsequent runs:**
```bash
# Just activate the virtual environment
source venv/bin/activate

# Run Ivan
python ivan.py                           # Default: LM Studio, port 8000, with Web UI
python ivan.py --backend ollama          # Use Ollama backend
python ivan.py --no-webui                # Skip Web UI
python ivan.py --port 8080               # Custom port
python ivan.py --debug                   # Debug mode
```

**What setup.sh does:**
- Ensures Python 3.12.0 is used via pyenv
- Creates virtual environment with correct Python version
- Installs all dependencies including Open Web UI
- Applies HashiCorp branding automatically
- If you manually upgrade Open Web UI later, reapply branding with `./apply_branding.sh`

### Extension Development

```bash
cd ivan-extension

# Load in Chrome:
# 1. Navigate to chrome://extensions
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Select ivan-extension/ directory
```

## Common Tasks

### Adding New Tools

Tools are defined in `tools.py` using LangChain's framework:

```python
from langchain.tools import Tool
from langchain.pydantic_v1 import BaseModel, Field

class MyToolInput(BaseModel):
    param: str = Field(description="Parameter description")

def my_tool_function(param: str) -> str:
    # Implementation
    return "result"

my_tool = Tool(
    name="my_tool",
    description="Description for the LLM",
    func=my_tool_function,
    args_schema=MyToolInput
)

# Add to ALL_TOOLS list at end of file
```

**Important**: Always use `langchain.pydantic_v1` (not pydantic directly) for compatibility.

### Modifying System Prompt

1. Edit `system_prompt.md`
2. Changes are automatically detected and cached
3. No restart required (cache uses file mtime)

### Customer Notes Setup

```bash
# Option 1: Symlink
ln -s /path/to/Customer_Notes ./Customer_Notes

# Option 2: Environment variable
export CUSTOMER_NOTES_DIR=/path/to/Customer_Notes
```

**Expected structure**: `Customer_Notes/[A-Z]/[Customer_Name]/10_Meetings/*.md`

**Search features**:
- Converts spaces to underscores automatically
- Case-insensitive substring matching
- Supports custom aliases in `config.py:CUSTOMER_ALIASES`

## API Endpoints

### Health Check
```bash
GET /health
```

### List Models
```bash
GET /v1/models
# Returns: {"data": [{"id": "wwtfo/ivan", ...}]}
```

### Chat Completions (OpenAI-compatible)
```bash
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "wwtfo/ivan",
  "messages": [{"role": "user", "content": "..."}],
  "temperature": 0
}
```

## Testing

All tests are located in the `tests/` directory. See `tests/README.md` for detailed documentation.

### Regression Tests (REQUIRED)

**IMPORTANT**: Before deploying changes to search functionality, you MUST run regression tests and ensure they pass.

#### Primary Regression Test
```bash
source venv/bin/activate
python tests/test_comparison.py
```

**Expected output**: `V2 (LangChain): ✅ PASS`

This test validates the HashiCorp web documentation search implementation against known correct answers. It ensures:
- Semantic search finds the correct documents and sections
- Chunking strategy preserves important information
- Results include enough context for the LLM to answer accurately

**Critical test case**: Consul stale reads default configuration
- **Query**: "what's the consul default for stale reads"
- **Expected answer**: "By default, Consul enables stale reads and sets the max_stale value to 10 years"
- **Source**: Consul Operating Guide for Adoption, section 8.3.6
- **Why it matters**: This specific case caught a bug where the previous implementation returned incorrect information

### Running All Tests

```bash
# Activate venv first
source venv/bin/activate

# Run primary regression test
python tests/test_comparison.py

# Run all tests
for test in tests/test_*.py; do
    echo "Running $test..."
    python "$test" || echo "FAILED: $test"
done
```

### Test Files

Located in `tests/` directory:
- `test_comparison.py` - **Primary regression test** for search quality (REQUIRED)
- `test_debug_chunks.py` - Debug tool to inspect chunk content
- `test_validated_designs.py` - Web crawler validation tests

### When to Run Regression Tests

Run `tests/test_comparison.py` before committing changes to:
- `hashicorp_web_search.py` - Web crawler search implementation
- `tools.py` - Tool definitions (especially `search_hashicorp_docs`)
- Embedding models or chunking strategies
- FAISS index configuration
- Any RAG-related code

### Adding New Regression Tests

When fixing search quality bugs:
1. Create a test with the problematic query and expected answer
2. Add it to `tests/test_comparison.py` or create a new test file
3. Verify the fix makes the test pass
4. Document the test in `tests/README.md`
5. Update this section if the test becomes critical

### Test Implementation Details

The current regression test (`test_comparison.py`) uses:
- **LangChain FAISS** for vector search
- **RecursiveCharacterTextSplitter** (1000 chars, 200 overlap)
- **all-MiniLM-L6-v2** embeddings
- **900 character** result preview (ensures LLM gets enough context)

Changes to these parameters may require updating test expectations.

## Important Patterns and Conventions

### System Prompt Caching
The system prompt is cached based on file modification time (ivan.py):
- Reads `system_prompt.md` on first request
- Subsequent requests check `os.path.getmtime()`
- Auto-reloads when file changes

### Tool Response Format
Tools return plain strings. The Flask app converts them to OpenAI-compatible function call responses.

### Customer Notes Naming
- Meetings directory: `10_Meetings/`
- File format: `YYYY-MM-DD_Title_With_Underscores.md`
- Customer names: `Title_Case_With_Underscores`

### Extension-Backend Communication
- Extension calls `http://localhost:8000/v1/chat/completions`
- Configurable endpoint in extension settings
- Uses streaming responses for chat interface

## Security Considerations

### API Security
- No authentication required (local development tool)
- Binds to localhost only
- CORS enabled for local development

### Extension Permissions
- `activeTab` - Read current Salesforce page
- `storage` - Save settings
- Host permission for Ivan backend URL

## Troubleshooting

### Common Issues

**Backend Connection Failed**
- Check backend is running (Ollama/LM Studio)
- Verify endpoint URL in config
- Confirm model name matches loaded model

**Tools Not Working**
- Verify system prompt enables tool usage
- Check backend model supports function calling
- For customer notes: verify directory exists and structure is correct

**Open Web UI Won't Start**
- Ensure Python 3.11-3.12 (not 3.14+)
- Install manually: `pip install open-webui`
- Or use `--no-webui` flag

**Extension Not Loading**
- Check manifest.json is valid
- Verify all referenced files exist
- Check Chrome console for errors

**Dependency Installation Issues**

*ImportError: cannot import name 'cached_download' from 'huggingface_hub'*
- This occurs when sentence-transformers is too old (< 2.3.0)
- **Fixed in requirements.txt** (now uses `sentence-transformers>=2.3.0`)
- If you still see this after fresh install: `pip install --upgrade sentence-transformers`
- Verified working with sentence-transformers 5.1.2 + huggingface-hub 0.36.0

**Web Documentation Index Build Fails or Hangs**
- Check logs in terminal output for specific errors
- Verify internet connection and access to developer.hashicorp.com
- Check available disk space (index requires ~500MB-1GB)
- To force complete re-scrape: `python ivan.py --force-scrape`
- To rebuild with cached pages: `python ivan.py --rebuild-index`
- To delete everything and start fresh: `rm -rf hashicorp_web_docs/` then run `python ivan.py`

## Related Documentation

- **README.md** - User-facing documentation with setup instructions
- **SEARCH_ALTERNATIVES.md** - Documentation on search implementation alternatives
- **ivan-extension/README.md** - Extension-specific documentation
- **docs/** - Additional documentation and images

## Git Workflow

Current branch: `main`

Recent development focus (from git log):
- Customer notes search refinement
- Extension UI improvements (commit button persistence, layout fixes)
- WARMER assessment integration
- Chat input handling in quick actions

## CLI Reference

```bash
python ivan.py [OPTIONS]

Options:
  --port INTEGER                 Port to run Ivan on (default: 8000)
  --backend [ollama|lmstudio]   Backend to use (default: from config)
  --model TEXT                   Model name for backend (default: from config)
  --no-webui                     Don't start Open Web UI
  --rebuild-index                Force rebuild of HashiCorp documentation index
  --force-scrape                 Clear page cache and re-scrape all pages (implies --rebuild-index)
  --debug                        Run in debug mode
  --help                         Show help message
```

### Index Rebuild Options

**Normal rebuild** (uses cached HTML pages, fast):
```bash
python ivan.py --rebuild-index
```
- Re-discovers URLs (finds new pages)
- Uses cached HTML if available
- Re-chunks and re-indexes all content
- ~5-10 minutes

**Force scrape** (re-downloads all pages, slow):
```bash
python ivan.py --force-scrape
```
- Deletes all cached HTML pages
- Re-scrapes all ~12,000+ pages from scratch
- Re-chunks and re-indexes everything
- ~20-30 minutes

## Notes for Claude Code

- Always check `config.py` for current default values
- When adding tools, follow the LangChain pattern in `tools.py`
- Extension changes require manual reload in Chrome
- System prompt changes are auto-detected (no restart needed)
- Customer notes structure is hierarchical and case-sensitive for directories
- The project uses Python 3.12.0 specifically (see .python-version)
