# Ivan Project Documentation for Claude Code

## Project Overview

Ivan is a Flask-based AI chatbot application that provides an OpenAI-compatible API for local LLM backends (Ollama and LM Studio). It features:
- **RAG (Retrieval-Augmented Generation)** for HashiCorp documentation search
- **Tool calling** for customer notes and web search
- **Open Web UI integration** for a chat interface
- **Chrome extension** for automating SE Weekly Updates in Salesforce

Ivan is built on [llm-api-server](https://github.com/assareh/llm-api-server), which provides the `ServerConfig` base class and RAG infrastructure.

**Model Name**: `wwtfo/ivan` (advertised in API responses)

## Architecture

### Core Components

1. **ivan.py** (~540 lines) - Main Flask application
   - OpenAI-compatible `/v1/chat/completions` endpoint
   - Tool calling loop with streaming support
   - RAG context augmentation (injects relevant docs into user messages)
   - Open Web UI subprocess management
   - System prompt caching based on file modification time

2. **config.py** (~70 lines) - Fully environment-driven configuration
   - Extends `ServerConfig` from llm-api-server
   - Uses `ServerConfig.from_env("IVAN_")` pattern
   - All settings come from `.env` file - **no user edits to config.py needed**

3. **tools.py** (~310 lines) - Tool definitions and RAG functions
   - Customer notes search/read tools (using `@tool` decorator)
   - Web search tool (from llm-api-server)
   - RAG initialization (`initialize_rag_at_startup()`)
   - RAG context retrieval (`get_rag_context()`)

4. **system_prompt.md** - Customizable system prompt
   - Cached and auto-reloaded on modification
   - Defines Ivan's personality and behavior

### How RAG Works (Not a Tool)

RAG is **automatic context augmentation**, not a tool:
1. On every user message, `get_rag_context(query)` searches the HashiCorp docs index
2. Relevant documentation snippets are appended to the user's message
3. The LLM sees this context and can reference it naturally
4. No explicit "search docs" tool call needed

### Chrome Extension (ivan-extension/)

Browser extension for automating SE Weekly Updates with AI assistance.

**Key Files**:
- `manifest.json` - Extension configuration (Manifest V3)
- `popup.html/js/css` - Extension UI (chat interface)
- `content.js/css` - Page interaction (extracts context, fills forms)
- `background.js` - Background service worker

## Directory Structure

```
Ivan/
├── ivan.py                  # Main Flask application
├── config.py                # Configuration (extends ServerConfig)
├── tools.py                 # Tools + RAG context functions
├── system_prompt.md         # System prompt (auto-cached)
├── pyproject.toml           # Dependencies and project config
├── .env.example             # Configuration template (copy to .env)
├── .python-version          # Python version (3.12.0)
│
├── Customer_Notes/          # Symlink to customer meeting notes (optional)
│   └── [A-Z]/               # Alphabetically organized
│       └── [Customer]/
│           └── 10_Meetings/
│               └── *.md     # Meeting notes (YYYY-MM-DD_Title.md)
│
├── hashicorp_docs_index/    # RAG index cache (auto-generated)
│
├── ivan-extension/          # Chrome extension
│   ├── manifest.json
│   ├── popup.html/js/css
│   ├── content.js/css
│   └── background.js
│
├── tests/                   # Test suite
└── docs/                    # Documentation and images
```

## Technology Stack

- **Flask 3.0** - Web framework
- **llm-api-server** - ServerConfig, RAG module, builtin tools
- **LangChain** - Tool definitions, RAG infrastructure
- **FAISS** - Vector similarity search
- **sentence-transformers** - Embeddings
- **Click** - CLI argument parsing
- **python-dotenv** - Environment variable management
- **open-webui** - Optional chat UI

## Configuration

### Environment Variables (.env)

All configuration is done via environment variables. Copy `.env.example` to `.env` and customize:

```bash
# Backend
IVAN_BACKEND=lmstudio        # or "ollama"
BACKEND_MODEL=openai/gpt-oss-20b
LMSTUDIO_ENDPOINT=http://localhost:1234/v1
OLLAMA_ENDPOINT=http://localhost:11434

# Server
IVAN_PORT=8000
IVAN_TEMPERATURE=0.0
SYSTEM_PROMPT_PATH=system_prompt.md

# RAG (HashiCorp docs)
RAG_ENABLED=true
RAG_CACHE_DIR=hashicorp_docs_index
RAG_DOC_SOURCES=https://developer.hashicorp.com
RAG_UPDATE_INTERVAL_HOURS=168  # 7 days

# Customer Notes
CUSTOMER_NOTES_DIR=Customer_Notes

# WebUI
WEBUI_PORT=8001
WEBUI_AUTH=false

# Debug - Tool logging
DEBUG_TOOLS=true                    # Enable tool call logging
DEBUG_TOOLS_LOG_FILE=debug_tools.json  # Log file path
DEBUG_LOG_FORMAT=json               # Format: text, json, or yaml
DEBUG_LOG_MAX_RESPONSE_LENGTH=0     # 0 = no truncation

# Debug - LLM request logging
DEBUG_LLM_REQUESTS=true             # Log full LLM requests/responses
DEBUG_LLM_REQUESTS_FILE=llm_requests.json

# Tool loop settings
MAX_TOOL_ITERATIONS=5               # Max tool calls per request
TOOL_LOOP_TIMEOUT=120               # Seconds before timeout
FIRST_ITERATION_TOOL_CHOICE=auto    # auto or required
```

See `.env.example` for all available options with descriptions.

### Configuration Pattern

**Important**: `config.py` should NOT be edited by users. It uses the `from_env()` pattern:

```python
class IvanConfig(ServerConfig):
    @classmethod
    def load(cls):
        config = cls.from_env("IVAN_")
        config.RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
        # ... more settings from env vars
        return config

config = IvanConfig.load()
```

## Development Setup

### Quick Start

```bash
# First-time setup
./setup.sh
# OR manually:
uv sync --extra webui

# Run Ivan
uv run python ivan.py                    # Default settings
uv run python ivan.py --backend ollama   # Use Ollama
uv run python ivan.py --no-webui         # Skip Web UI
uv run python ivan.py --debug            # Debug mode
```

### CLI Options

```bash
python ivan.py [OPTIONS]

Options:
  --port INTEGER               Port to run Ivan on (default: 8000)
  --backend [ollama|lmstudio]  Backend to use
  --model TEXT                 Model name for backend
  --no-webui                   Don't start Open Web UI
  --debug                      Run in debug mode
  --help                       Show help message
```

## Code Quality

### Linting

```bash
# Install dev dependencies
uv sync --extra dev

# Run linter
uv run ruff check ivan.py config.py tools.py

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run black .
```

Configuration is in `pyproject.toml` (120 char line length, Python 3.11+).

## Adding New Tools

Tools use LangChain's `@tool` decorator:

```python
from langchain_core.tools import tool

@tool
def my_tool(param: str) -> str:
    """Tool description for the LLM.

    Args:
        param: Parameter description

    Returns:
        Result string
    """
    return f"Result: {param}"

# Add to ALL_TOOLS list at end of tools.py
ALL_TOOLS = [
    search_customer_notes,
    read_customer_note,
    web_search,
    my_tool,  # Add here
]
```

## API Endpoints

### Health Check
```bash
GET /health
# Returns: {"status": "healthy", "backend": "lmstudio", "model": "wwtfo/ivan"}
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
  "temperature": 0,
  "stream": true
}
```

## RAG Index Management

The RAG index is automatically built/updated on startup:

- **First run**: Crawls HashiCorp docs and builds index (~15-30 min)
- **Subsequent runs**: Loads cached index (fast)
- **Auto-update**: Rebuilds if older than `RAG_UPDATE_INTERVAL_HOURS`

Index location: `hashicorp_docs_index/` (configurable via `RAG_CACHE_DIR`)

To force rebuild, delete the index directory:
```bash
rm -rf hashicorp_docs_index/
uv run python ivan.py
```

## Troubleshooting

**Backend Connection Failed**
- Check backend is running (Ollama/LM Studio)
- Verify endpoint URL in `.env`
- Confirm model name matches loaded model

**RAG Not Working**
- Check `RAG_ENABLED=true` in `.env`
- Verify `RAG_DOC_SOURCES` is set
- Check index exists in `hashicorp_docs_index/`

**Tools Not Working**
- Verify backend model supports function calling
- Enable debug logging to see what's happening:
  ```bash
  DEBUG_TOOLS=true
  DEBUG_TOOLS_LOG_FILE=debug_tools.json
  DEBUG_LOG_FORMAT=json
  ```
- Check `debug_tools.json` for tool calls and responses
- Enable `DEBUG_LLM_REQUESTS=true` to see full LLM payloads

**Open Web UI Won't Start**
- Ensure Python 3.11-3.12 (not 3.14+)
- Install with: `uv sync --extra webui`
- Or use `--no-webui` flag

## Notes for Claude Code

- **Config**: All settings via `.env` - never edit `config.py`
- **Tools**: Use `@tool` decorator, add to `ALL_TOOLS` list
- **RAG**: Not a tool - automatic context injection via `get_rag_context()`
- **System prompt**: Edit `system_prompt.md` (auto-reloads)
- **Extension**: Changes require manual reload in Chrome
- **Python**: 3.12.0 specifically (see `.python-version`)
- **Linting**: `uv run ruff check` before commits
