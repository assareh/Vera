# Vera Project Documentation for Claude Code

## Project Overview

Vera is a Flask-based AI chatbot application that provides an OpenAI-compatible API for local LLM backends (Ollama and LM Studio). It features tool calling capabilities, optional Open Web UI integration, and a Chrome extension for automating SE Weekly Updates in Salesforce.

**Model Name**: `wwtfo/vera` (advertised in API responses)

## Architecture

### Core Components

1. **vera.py** - Main Flask application
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
   - Defines Vera's personality and behavior

### Chrome Extension (vera-extension/)

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
Vera/
├── vera.py                 # Main Flask application
├── config.py              # Configuration management
├── tools.py               # Tool definitions (LangChain)
├── system_prompt.md       # System prompt (auto-cached)
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment variables
├── .python-version       # Python version (3.12.0)
│
├── notes/                # Personal notes directory
├── Customer_Notes/       # Symlink to customer meeting notes (optional)
│   └── [A-Z]/           # Alphabetically organized by customer
│       └── [Customer]/
│           └── 10_Meetings/
│               └── *.md  # Meeting notes (YYYY-MM-DD_Title.md)
│
├── hashicorp_pdfs/      # HashiCorp PDF documentation cache
├── vera-extension/      # Chrome extension
│   ├── manifest.json
│   ├── popup.html/js/css
│   ├── content.js/css
│   ├── background.js
│   └── icon*.png
│
├── venv/                # Python virtual environment (3.12.0)
└── docs/                # Documentation and images
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
- **pypdf** - PDF text extraction
- **duckduckgo-search** - Web search integration

### Automation
- **selenium** - Browser automation (PDF downloads)
- **beautifulsoup4** - HTML parsing

### Optional
- **open-webui** - Web UI (requires Python 3.11-3.12)

### Extension
- Vanilla JavaScript (no build step)
- Chrome Extension Manifest V3

## Environment Configuration

### Environment Variables

```bash
# Backend Selection
VERA_BACKEND=lmstudio          # or "ollama"
BACKEND_MODEL=openai/gpt-oss-20b  # Model name for backend

# Backend Endpoints
LMSTUDIO_ENDPOINT=http://localhost:1234/v1
OLLAMA_ENDPOINT=http://localhost:11434

# Vera Settings
VERA_PORT=8000
VERA_TEMPERATURE=0.0
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

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install Open Web UI
pip install open-webui

# Run Vera
python vera.py                           # Default: LM Studio, port 8000, with Web UI
python vera.py --backend ollama          # Use Ollama backend
python vera.py --no-webui                # Skip Web UI (for Python 3.14+)
python vera.py --port 8080               # Custom port
python vera.py --debug                   # Debug mode
```

### Extension Development

```bash
cd vera-extension

# Load in Chrome:
# 1. Navigate to chrome://extensions
# 2. Enable "Developer mode"
# 3. Click "Load unpacked"
# 4. Select vera-extension/ directory
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
# Returns: {"data": [{"id": "wwtfo/vera", ...}]}
```

### Chat Completions (OpenAI-compatible)
```bash
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "wwtfo/vera",
  "messages": [{"role": "user", "content": "..."}],
  "temperature": 0
}
```

## Testing

### Test Files
- `test_hashicorp_search.py` - HashiCorp documentation search tests
- `test_pdf_search.py` - PDF semantic search tests
- `test_selenium_download.py` - PDF download automation tests

### Running Tests
```bash
# Activate venv first
source venv/bin/activate

# Run specific test
python test_hashicorp_search.py
```

## Important Patterns and Conventions

### System Prompt Caching
The system prompt is cached based on file modification time (vera.py):
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
- Host permission for Vera backend URL

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

## Related Documentation

- **README.md** - User-facing documentation with setup instructions
- **SEARCH_ALTERNATIVES.md** - Documentation on search implementation alternatives
- **vera-extension/README.md** - Extension-specific documentation
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
python vera.py [OPTIONS]

Options:
  --port INTEGER                 Port to run Vera on (default: 8000)
  --backend [ollama|lmstudio]   Backend to use (default: from config)
  --model TEXT                   Model name for backend (default: from config)
  --no-webui                     Don't start Open Web UI
  --debug                        Run in debug mode
  --help                         Show help message
```

## Notes for Claude Code

- Always check `config.py` for current default values
- When adding tools, follow the LangChain pattern in `tools.py`
- Extension changes require manual reload in Chrome
- System prompt changes are auto-detected (no restart needed)
- Customer notes structure is hierarchical and case-sensitive for directories
- The project uses Python 3.12.0 specifically (see .python-version)
