"""Configuration management for Vera."""
import os
from typing import Literal

# Backend configuration
BACKEND_TYPE: Literal["lmstudio", "ollama"] = os.getenv("VERA_BACKEND", "lmstudio")

# LM Studio default endpoint
LMSTUDIO_ENDPOINT = os.getenv("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1")

# Ollama default endpoint
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")

# Model name to use with the backend
BACKEND_MODEL = os.getenv("BACKEND_MODEL", "openai/gpt-oss-20b")

# Vera configuration
DEFAULT_PORT = int(os.getenv("VERA_PORT", "8000"))
DEFAULT_TEMPERATURE = float(os.getenv("VERA_TEMPERATURE", "0.0"))
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", "system_prompt.md")

# Notes directory for search tool
NOTES_DIR = os.getenv("NOTES_DIR", "notes")

# Model identifier that Vera advertises
VERA_MODEL_NAME = "wwtfo/vera"
