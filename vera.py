"""Vera - A Flask chatbot with tool calling capabilities."""
import os
import json
import time
import subprocess
import signal
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Generator
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import requests
import click

import config
from tools import ALL_TOOLS


app = Flask(__name__)
CORS(app)

# Global variables for caching
_system_prompt_cache: Optional[str] = None
_system_prompt_mtime: Optional[float] = None
_webui_process: Optional[subprocess.Popen] = None


def get_system_prompt() -> str:
    """Load system prompt from markdown file with smart caching."""
    global _system_prompt_cache, _system_prompt_mtime

    prompt_path = Path(config.SYSTEM_PROMPT_PATH)

    if not prompt_path.exists():
        return "You are Vera, a helpful AI assistant."

    try:
        current_mtime = prompt_path.stat().st_mtime

        # Check if cache is valid
        if _system_prompt_cache is not None and _system_prompt_mtime == current_mtime:
            return _system_prompt_cache

        # Read and cache the prompt
        _system_prompt_cache = prompt_path.read_text(encoding="utf-8")
        _system_prompt_mtime = current_mtime

        return _system_prompt_cache
    except Exception as e:
        print(f"Error reading system prompt: {e}")
        return "You are Vera, a helpful AI assistant."


def get_backend_endpoint() -> str:
    """Get the appropriate backend endpoint based on configuration."""
    if config.BACKEND_TYPE == "lmstudio":
        return config.LMSTUDIO_ENDPOINT
    elif config.BACKEND_TYPE == "ollama":
        return config.OLLAMA_ENDPOINT
    else:
        raise ValueError(f"Unknown backend type: {config.BACKEND_TYPE}")


def call_ollama_with_tools(messages: list, tools: list, temperature: float = 0.0, stream: bool = False) -> Any:
    """Call Ollama with tool support."""
    endpoint = f"{config.OLLAMA_ENDPOINT}/api/chat"

    # Convert tools to Ollama format
    ollama_tools = []
    for tool in tools:
        tool_def = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.schema() if hasattr(tool.args_schema, "schema") else {}
            }
        }
        ollama_tools.append(tool_def)

    payload = {
        "model": config.BACKEND_MODEL,
        "messages": messages,
        "tools": ollama_tools,
        "stream": stream,
        "options": {
            "temperature": temperature
        }
    }

    response = requests.post(endpoint, json=payload, stream=stream)
    response.raise_for_status()

    return response


def call_lmstudio_with_tools(messages: list, tools: list, temperature: float = 0.0, stream: bool = False) -> Any:
    """Call LM Studio with tool support."""
    endpoint = f"{config.LMSTUDIO_ENDPOINT}/chat/completions"

    # Convert tools to OpenAI format
    openai_tools = []
    for tool in tools:
        tool_def = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.args_schema.schema() if hasattr(tool.args_schema, "schema") else {}
            }
        }
        openai_tools.append(tool_def)

    payload = {
        "model": config.BACKEND_MODEL,
        "messages": messages,
        "tools": openai_tools,
        "temperature": temperature,
        "stream": stream
    }

    response = requests.post(endpoint, json=payload, stream=stream)
    response.raise_for_status()

    return response


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Execute a tool by name with given input."""
    for tool in ALL_TOOLS:
        if tool.name == tool_name:
            try:
                result = tool.func(**tool_input)
                return str(result)
            except Exception as e:
                return f"Error executing tool {tool_name}: {str(e)}"

    return f"Tool {tool_name} not found"


def stream_chat_response(messages: list, temperature: float, max_iterations: int = 5) -> Generator[str, None, None]:
    """Stream chat completion with tool calling loop."""
    # Add system prompt
    system_prompt = get_system_prompt()
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    iteration = 0
    while iteration < max_iterations:
        iteration += 1

        # Call the backend (non-streaming for tool calls, then stream final response)
        if config.BACKEND_TYPE == "ollama":
            response = call_ollama_with_tools(full_messages, ALL_TOOLS, temperature, stream=False)
            response_data = response.json()
        else:  # lmstudio
            response = call_lmstudio_with_tools(full_messages, ALL_TOOLS, temperature, stream=False)
            response_data = response.json()

        # Handle Ollama response format
        if config.BACKEND_TYPE == "ollama":
            message = response_data.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, stream the final response
                content = message.get("content", "")

                # Stream the content in small chunks while preserving formatting
                # Split by words but keep newlines and formatting
                # Split on whitespace but keep the whitespace (including newlines)
                tokens = re.split(r'(\s+)', content)

                for token in tokens:
                    if token:  # Skip empty strings
                        chunk = {
                            "id": f"chatcmpl-{int(time.time())}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": config.VERA_MODEL_NAME,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                # Send final chunk
                final_chunk = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": config.VERA_MODEL_NAME,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Add assistant message with tool calls
            full_messages.append(message)

            # Execute tools and add results
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                tool_args = function.get("arguments", {})

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)

                # Add tool result to messages
                full_messages.append({
                    "role": "tool",
                    "content": tool_result
                })

        else:  # LM Studio (OpenAI format)
            choice = response_data.get("choices", [{}])[0]
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, stream the final response
                content = message.get("content", "")

                # Stream the content in small chunks while preserving formatting
                # Split by words but keep newlines and formatting
                # Split on whitespace but keep the whitespace (including newlines)
                tokens = re.split(r'(\s+)', content)

                for token in tokens:
                    if token:  # Skip empty strings
                        chunk = {
                            "id": f"chatcmpl-{int(time.time())}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": config.VERA_MODEL_NAME,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                # Send final chunk
                final_chunk = {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": config.VERA_MODEL_NAME,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Add assistant message with tool calls
            full_messages.append(message)

            # Execute tools and add results
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                tool_args = json.loads(function.get("arguments", "{}"))

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)

                # Add tool result to messages
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "content": tool_result
                })

    # Max iterations reached
    error_chunk = {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": config.VERA_MODEL_NAME,
        "choices": [{
            "index": 0,
            "delta": {"content": "I apologize, but I've reached the maximum number of tool calling iterations."},
            "finish_reason": "length"
        }]
    }
    yield f"data: {json.dumps(error_chunk)}\n\n"
    yield "data: [DONE]\n\n"


def process_chat_completion(messages: list, temperature: float, stream: bool, max_iterations: int = 5) -> Any:
    """Process chat completion with tool calling loop."""
    # Add system prompt
    system_prompt = get_system_prompt()
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    iteration = 0
    while iteration < max_iterations:
        iteration += 1

        # Call the backend
        if config.BACKEND_TYPE == "ollama":
            response = call_ollama_with_tools(full_messages, ALL_TOOLS, temperature, stream=False)
            response_data = response.json()
        else:  # lmstudio
            response = call_lmstudio_with_tools(full_messages, ALL_TOOLS, temperature, stream=False)
            response_data = response.json()

        # Handle Ollama response format
        if config.BACKEND_TYPE == "ollama":
            message = response_data.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, return the final response
                return {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": config.VERA_MODEL_NAME,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": message.get("content", "")
                        },
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                }

            # Add assistant message with tool calls
            full_messages.append(message)

            # Execute tools and add results
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                tool_args = function.get("arguments", {})

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)

                # Add tool result to messages
                full_messages.append({
                    "role": "tool",
                    "content": tool_result
                })

        else:  # LM Studio (OpenAI format)
            choice = response_data.get("choices", [{}])[0]
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # No tool calls, return the final response
                return response_data

            # Add assistant message with tool calls
            full_messages.append(message)

            # Execute tools and add results
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                tool_args = json.loads(function.get("arguments", "{}"))

                # Execute the tool
                tool_result = execute_tool(tool_name, tool_args)

                # Add tool result to messages
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id"),
                    "content": tool_result
                })

    # Max iterations reached
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": config.VERA_MODEL_NAME,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "I apologize, but I've reached the maximum number of tool calling iterations."
            },
            "finish_reason": "length"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


@app.route("/v1/models", methods=["GET"])
def list_models():
    """List available models."""
    return jsonify({
        "object": "list",
        "data": [{
            "id": config.VERA_MODEL_NAME,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "vera",
            "permission": [],
            "root": config.VERA_MODEL_NAME,
            "parent": None
        }]
    })


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    """Handle chat completion requests."""
    try:
        data = request.get_json()

        messages = data.get("messages", [])
        temperature = data.get("temperature", config.DEFAULT_TEMPERATURE)
        stream = data.get("stream", False)

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        if stream:
            # Return streaming response
            return Response(
                stream_with_context(stream_chat_response(messages, temperature)),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # Process the chat completion (non-streaming)
            result = process_chat_completion(messages, temperature, False)

            # Update model name in response
            if isinstance(result, dict):
                result["model"] = config.VERA_MODEL_NAME

            return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "backend": config.BACKEND_TYPE,
        "model": config.VERA_MODEL_NAME
    })


def start_webui(port: int):
    """Start Open Web UI as a subprocess."""
    global _webui_process

    try:
        # Check if open-webui is installed
        result = subprocess.run(["which", "open-webui"], capture_output=True, text=True)
        if result.returncode != 0:
            print("Warning: open-webui not found. Install with: pip install open-webui")
            return

        webui_port = port + 1
        print(f"Starting Open Web UI on port {webui_port}...")

        # Set up environment variables for Open Web UI to auto-discover Vera
        env = os.environ.copy()
        env["OPENAI_API_BASE_URLS"] = f"http://localhost:{port}/v1"
        env["OPENAI_API_KEYS"] = "sk-vera"  # Dummy key, not required by Vera

        # Set custom prompt suggestions for SE workflows
        # Note: title must be an array of strings per Open Web UI docs
        suggestions = json.dumps([
            {
                "title": ["Draft follow-up", "after client meeting"],
                "content": "Help me draft a follow-up email after today's client meeting"
            },
            {
                "title": ["Weekly SE update", "status report"],
                "content": "Help me complete my weekly SE status update for this week"
            },
            {
                "title": ["WARMER assessment", "account evaluation"],
                "content": "Guide me through completing a WARMER assessment for my account"
            }
        ])
        env["DEFAULT_PROMPT_SUGGESTIONS"] = suggestions
        # Disable persistent config so env vars are read every time
        env["ENABLE_PERSISTENT_CONFIG"] = "False"

        # Start open-webui
        _webui_process = subprocess.Popen(
            ["open-webui", "serve", "--port", str(webui_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        print(f"Open Web UI started at http://localhost:{webui_port}")
        print(f"Vera endpoint auto-configured at http://localhost:{port}/v1")

    except Exception as e:
        print(f"Failed to start Open Web UI: {e}")


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\nShutting down Vera...")
    if _webui_process:
        _webui_process.terminate()
        _webui_process.wait()
    sys.exit(0)


@click.command()
@click.option("--port", default=config.DEFAULT_PORT, help="Port to run Vera on")
@click.option("--backend", type=click.Choice(["ollama", "lmstudio"]), default=config.BACKEND_TYPE, help="Backend to use")
@click.option("--model", default=config.BACKEND_MODEL, help="Model name to use with backend")
@click.option("--no-webui", is_flag=True, help="Don't start Open Web UI")
@click.option("--debug", is_flag=True, help="Run in debug mode")
def main(port: int, backend: str, model: str, no_webui: bool, debug: bool):
    """Start Vera chatbot server."""
    # Update config
    config.BACKEND_TYPE = backend
    config.BACKEND_MODEL = model

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"""
╭────────────────────────────────────╮
│  Vera - AI Assistant with Tools   │
╰────────────────────────────────────╯

Backend: {backend}
Model: {model}
Port: {port}
API: http://localhost:{port}/v1
""")

    # Create notes directory if it doesn't exist
    Path(config.NOTES_DIR).mkdir(exist_ok=True)

    # Start Web UI if requested
    if not no_webui:
        start_webui(port)

    # Start Flask app
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    main()
