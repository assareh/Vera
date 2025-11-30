"""Ivan - A HashiCorp documentation assistant using LLM API Server."""

import json
import os
import signal
import sys
from datetime import datetime

import click
from dotenv import load_dotenv

# Load .env early so DEBUG_LLM_REQUESTS is available
load_dotenv()

print("Loading Ivan...\n")

# Monkey-patch backend calls to log LLM request payloads
if os.getenv("DEBUG_LLM_REQUESTS", "").lower() == "true":
    import llm_api_server.backends as backends

    _original_call_ollama = backends.call_ollama
    _original_call_lmstudio = backends.call_lmstudio
    _request_log_file = os.getenv("DEBUG_LLM_REQUESTS_FILE", "llm_requests.json")

    def _log_request(backend: str, payload: dict):
        """Log LLM request payload to file (JSON Lines format for jq compatibility)."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "backend": backend,
            "payload": payload,
        }
        with open(_request_log_file, "a") as f:
            # JSON Lines format: one JSON object per line (no indent, no separator)
            f.write(json.dumps(log_entry, default=str) + "\n")
        print(f"[DEBUG] LLM request logged to {_request_log_file}")

    def _patched_call_ollama(messages, tools, config, temperature=0.0, stream=False, tool_choice=None):
        # Build payload same way as original
        openai_tools = []
        for tool in tools:
            schema = backends.get_tool_schema(tool)
            tool_def = {
                "type": "function",
                "function": {"name": tool.name, "description": tool.description, "parameters": schema},
            }
            openai_tools.append(tool_def)

        payload = {
            "model": config.BACKEND_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if tool_choice == "none":
            payload["tool_choice"] = "none"
        elif openai_tools:
            payload["tools"] = openai_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        _log_request("ollama", payload)
        return _original_call_ollama(messages, tools, config, temperature, stream, tool_choice)

    def _patched_call_lmstudio(messages, tools, config, temperature=0.0, stream=False, tool_choice=None):
        # Build payload same way as original
        openai_tools = []
        for tool in tools:
            schema = backends.get_tool_schema(tool)
            tool_def = {
                "type": "function",
                "function": {"name": tool.name, "description": tool.description, "parameters": schema},
            }
            openai_tools.append(tool_def)

        payload = {
            "model": config.BACKEND_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if tool_choice == "none":
            payload["tool_choice"] = "none"
        elif openai_tools:
            payload["tools"] = openai_tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        _log_request("lmstudio", payload)
        return _original_call_lmstudio(messages, tools, config, temperature, stream, tool_choice)

    backends.call_ollama = _patched_call_ollama
    backends.call_lmstudio = _patched_call_lmstudio

    # Also patch in the server module (it imports them directly)
    import llm_api_server.server as server
    server.call_ollama = _patched_call_ollama
    server.call_lmstudio = _patched_call_lmstudio
    print("[DEBUG] LLM request logging enabled")

from llm_api_server import LLMServer

import config
from tools import ALL_TOOLS, get_all_tools, initialize_rag_at_startup

# Global server reference for the init hook
_server = None


def initialize_ivan():
    """Initialization hook called during server startup."""
    global _server

    # Initialize RAG index (this creates the doc_search tool)
    if config.config.RAG_ENABLED:
        initialize_rag_at_startup()
        print()

    # Update the server's tools list with the dynamically created doc_search tool
    if _server is not None:
        _server.tools = get_all_tools()


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\nShutting down Ivan...")
    sys.exit(0)


@click.command()
@click.option("--port", default=config.config.DEFAULT_PORT, help="Port to run Ivan on")
@click.option(
    "--backend", type=click.Choice(["ollama", "lmstudio"]), default=config.config.BACKEND_TYPE, help="Backend to use"
)
@click.option("--model", default=config.config.BACKEND_MODEL, help="Model name to use with backend")
@click.option("--no-webui", is_flag=True, help="Don't start Open Web UI")
@click.option("--debug", is_flag=True, help="Run in debug mode")
def main(port: int, backend: str, model: str, no_webui: bool, debug: bool):
    """Start Ivan chatbot server."""
    global _server

    # Update config with CLI options
    config.config.BACKEND_TYPE = backend
    config.config.BACKEND_MODEL = model

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create server instance
    _server = LLMServer(
        name="Ivan",
        model_name=config.config.MODEL_NAME,
        tools=ALL_TOOLS,
        config=config.config,
        default_system_prompt="You are Ivan, a helpful AI assistant specializing in HashiCorp technologies.",
        init_hook=initialize_ivan,
        logger_names=["ivan.tools", "tools"],
    )

    # Run the server
    _server.run(
        port=port,
        debug=debug,
        start_webui=not no_webui,
    )


if __name__ == "__main__":
    main()
