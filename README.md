# Vera 🤖

A Flask-based chatbot application with tool calling capabilities, providing an OpenAI-compatible API for local LLM backends.

## Features

- 🔧 **Tool Calling**: Built-in tools for current date/time, notes search, and customer meeting notes
- 🔌 **OpenAI-Compatible API**: Works with any OpenAI-compatible client
- 🎯 **Multiple Backends**: Supports both Ollama and LM Studio
- 📝 **Smart Caching**: Efficient system prompt caching based on file modification time
- 🌐 **Optional Web UI**: Integrated Open Web UI for easy interaction
- ⚙️ **Configurable**: Flexible CLI and environment variable configuration

## Quick Start

### Installation

```bash
# Clone or navigate to the project directory
cd Vera

# Install dependencies
pip install -r requirements.txt
```

### Running Vera

**Basic usage (with Ollama):**
```bash
python vera.py
```

**With LM Studio:**
```bash
python vera.py --backend lmstudio --model your-model-name
```

**Without Web UI:**
```bash
python vera.py --no-webui
```

**Custom port:**
```bash
python vera.py --port 8080
```

### Configuration

Vera can be configured via environment variables:

```bash
# Backend configuration
export VERA_BACKEND=ollama          # or lmstudio
export BACKEND_MODEL=llama3.2       # your model name
export OLLAMA_ENDPOINT=http://localhost:11434
export LMSTUDIO_ENDPOINT=http://localhost:1234/v1

# Vera settings
export VERA_PORT=8000
export VERA_TEMPERATURE=0.0
export SYSTEM_PROMPT_PATH=system_prompt.md
export NOTES_DIR=notes
export CUSTOMER_NOTES_DIR=Customer_Notes  # Path to customer meeting notes
```

## Usage

### With Open Web UI

1. Start Vera: `python vera.py`
2. Open Web UI will automatically start on port 8001 (or port + 1)
3. Access the Web UI at `http://localhost:8001`
4. Configure Open Web UI to use Vera at `http://localhost:8000/v1`

### With API Clients

Vera provides an OpenAI-compatible API:

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="wwtfo/vera",
    messages=[
        {"role": "user", "content": "What's the current date?"}
    ]
)

print(response.choices[0].message.content)
```

### With curl

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "wwtfo/vera",
    "messages": [{"role": "user", "content": "What day is it?"}],
    "temperature": 0
  }'
```

## Tools

Vera comes with built-in tools:

### 1. Current Date Tool
Get the current date and time in any format.

**Example**: "What's today's date?" or "What's the current time?"

### 2. Notes Search Tool
Search through your notes in the `notes/` directory.

**Example**: "Search my notes for project ideas"

### 3. Customer Notes Search Tool
Search through customer meeting notes organized in a hierarchical directory structure.

**Setup**: Create a symbolic link to your customer notes:
```bash
ln -s /path/to/your/Customer_Notes ./Customer_Notes
```

Or set the `CUSTOMER_NOTES_DIR` environment variable to point to your notes location.

**Expected Structure**:
```
Customer_Notes/
├── 0-9/
├── A/
│   └── Adobe/
│       └── 10_Meetings/
│           └── 2025-01-15_Discovery_Call.md
├── B/
└── ...
```

**Example**: "Show me recent Adobe meetings" or "Search customer notes for Vault discussions"

### 4. Read Customer Note Tool
Read the full content of a specific customer meeting note.

**Example**: Used automatically after searching to get full meeting details

## Customization

### System Prompt

Edit `system_prompt.md` to customize Vera's behavior. The file is automatically cached and reloaded when modified.

### Adding Notes

Place any `.txt`, `.md`, or `.markdown` files in the `notes/` directory. Vera will search through them when asked.

### Adding Tools

Add new tools in `tools.py`:

```python
from langchain.tools import Tool
from langchain.pydantic_v1 import BaseModel, Field

class MyToolInput(BaseModel):
    param: str = Field(description="Parameter description")

def my_tool_function(param: str) -> str:
    # Your tool logic here
    return f"Result: {param}"

my_tool = Tool(
    name="my_tool",
    description="Description of what the tool does",
    func=my_tool_function,
    args_schema=MyToolInput
)

# Add to ALL_TOOLS list
ALL_TOOLS.append(my_tool)
```

## API Endpoints

- `GET /health` - Health check
- `GET /v1/models` - List available models
- `POST /v1/chat/completions` - Chat completion endpoint

## CLI Options

```bash
python vera.py --help

Options:
  --port INTEGER                 Port to run Vera on (default: 8000)
  --backend [ollama|lmstudio]   Backend to use (default: ollama)
  --model TEXT                   Model name to use with backend
  --no-webui                     Don't start Open Web UI
  --debug                        Run in debug mode
  --help                         Show this message and exit
```

## Requirements

- **Python 3.8+** for Vera core functionality
- **Python 3.11-3.12** for Open Web UI integration (optional)
  - If you have Python 3.14+, use `--no-webui` flag or set up a separate Python 3.11/3.12 environment
- Ollama or LM Studio running locally
- A compatible model loaded in your backend

### Python Version Setup

**If you need Python 3.11/3.12 for Web UI:**

Using pyenv:
```bash
# Install pyenv if you don't have it
brew install pyenv

# Install Python 3.12
pyenv install 3.12.0

# Create virtual environment with Python 3.12
pyenv local 3.12.0
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install open-webui
```

**If using Python 3.14+ (without Web UI):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Run with: python vera.py --no-webui
```

## Architecture

```
Vera
├── vera.py           # Main Flask application
├── config.py         # Configuration management
├── tools.py          # Tool definitions
├── system_prompt.md  # System prompt (customizable)
├── notes/            # Notes directory for search
├── Customer_Notes/   # Symlink to customer meeting notes (optional)
└── requirements.txt  # Python dependencies
```

## Troubleshooting

**Vera can't connect to Ollama/LM Studio:**
- Ensure your backend is running
- Check the endpoint configuration matches your backend
- Verify the model name is correct

**Tools not working:**
- Check the notes directory exists
- Ensure your system prompt allows tool usage
- Verify the backend model supports function calling

**Open Web UI not starting:**
- Install it manually: `pip install open-webui`
- Or run with `--no-webui` and start it separately

## License

MIT

## Contributing

Contributions welcome! Feel free to open issues or submit pull requests.
