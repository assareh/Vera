"""Configuration management for Ivan - fully environment-driven."""

import os

from dotenv import load_dotenv
from llm_api_server import ServerConfig

# Load environment variables from .env file
load_dotenv()


class IvanConfig(ServerConfig):
    """Ivan-specific configuration extending ServerConfig."""

    @classmethod
    def load(cls):
        """Load Ivan configuration from environment variables."""
        config = cls.from_env("IVAN_")

        # Ivan-specific settings
        config.MODEL_NAME = os.getenv("IVAN_MODEL_NAME", "wwtfo/ivan")

        # Customer notes settings
        config.CUSTOMER_NOTES_DIR = os.getenv("CUSTOMER_NOTES_DIR", "Customer_Notes")

        # WebUI settings
        config.WEBUI_PORT = int(os.getenv("WEBUI_PORT", "8001"))
        config.WEBUI_AUTH = os.getenv("WEBUI_AUTH", "false").lower() == "true"

        # RAG settings
        config.RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"
        config.RAG_CACHE_DIR = os.getenv("RAG_CACHE_DIR", "hashicorp_docs_index")
        config.RAG_UPDATE_INTERVAL_HOURS = int(os.getenv("RAG_UPDATE_INTERVAL_HOURS", "168"))  # 7 days
        config.RAG_BM25_WEIGHT = float(os.getenv("RAG_BM25_WEIGHT", "0.4"))
        config.RAG_SEMANTIC_WEIGHT = float(os.getenv("RAG_SEMANTIC_WEIGHT", "0.6"))
        config.RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
        config.RAG_RERANK_ENABLED = os.getenv("RAG_RERANK_ENABLED", "true").lower() == "true"
        config.RAG_MAX_CRAWL_DEPTH = int(os.getenv("RAG_MAX_CRAWL_DEPTH", "3"))
        config.RAG_MAX_PAGES = int(os.getenv("RAG_MAX_PAGES")) if os.getenv("RAG_MAX_PAGES") else None
        config.RAG_RATE_LIMIT_DELAY = float(os.getenv("RAG_RATE_LIMIT_DELAY", "0.1"))
        config.RAG_MAX_WORKERS = int(os.getenv("RAG_MAX_WORKERS", "5"))

        # RAG documentation sources (comma-separated URLs)
        # Default to HashiCorp developer docs
        default_sources = "https://developer.hashicorp.com"
        config.RAG_DOC_SOURCES = os.getenv("RAG_DOC_SOURCES", default_sources).split(",")

        # Additional manual URLs to index (comma-separated)
        # These are indexed in addition to crawled content
        manual_urls_str = os.getenv("RAG_MANUAL_URLS", "")
        config.RAG_MANUAL_URLS = [u.strip() for u in manual_urls_str.split(",") if u.strip()]

        # RAG URL patterns (comma-separated)
        default_include = r"^https://developer\.hashicorp\.com/(terraform|vault|consul|nomad|packer|waypoint|boundary|vagrant)/,^https://developer\.hashicorp\.com/validated-(designs|patterns)"
        config.RAG_URL_INCLUDE_PATTERNS = (
            os.getenv("RAG_URL_INCLUDE_PATTERNS", default_include).split(",")
            if os.getenv("RAG_URL_INCLUDE_PATTERNS", default_include)
            else []
        )

        default_exclude = r"/partials/,/api-docs/,\?"
        config.RAG_URL_EXCLUDE_PATTERNS = (
            os.getenv("RAG_URL_EXCLUDE_PATTERNS", default_exclude).split(",")
            if os.getenv("RAG_URL_EXCLUDE_PATTERNS", default_exclude)
            else []
        )

        return config


# Create singleton config instance
config = IvanConfig.load()
