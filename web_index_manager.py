#!/usr/bin/env python3
"""Background manager for HashiCorp web documentation index builds."""
import os
import json
import subprocess
import threading
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

class WebIndexManager:
    """Manages automatic building and updating of the web documentation index."""

    def __init__(
        self,
        cache_dir: str = "./hashicorp_web_docs",
        update_interval_hours: int = 168,  # 7 days
        auto_update: bool = True
    ):
        """Initialize the web index manager.

        Args:
            cache_dir: Directory where index is cached
            update_interval_hours: How often to check for updates (default: 7 days)
            auto_update: Whether to automatically update in background
        """
        self.cache_dir = Path(cache_dir)
        self.update_interval = timedelta(hours=update_interval_hours)
        self.auto_update = auto_update

        self.metadata_file = self.cache_dir / "metadata.json"
        self.index_file = self.cache_dir / "index" / "index.faiss"
        self.url_list_file = self.cache_dir / "url_list.json"
        self.chunks_file = self.cache_dir / "chunks.json"

        self.build_process: Optional[subprocess.Popen] = None
        self.update_thread: Optional[threading.Thread] = None
        self.shutdown_flag = threading.Event()

    def get_index_status(self) -> dict:
        """Get current status of the index.

        Returns:
            Dictionary with status information
        """
        status = {
            "index_exists": self.index_file.exists(),
            "needs_build": False,
            "needs_update": False,
            "last_update": None,
            "age_hours": None,
            "cached_pages": 0,
            "chunks_ready": self.chunks_file.exists(),
            "build_in_progress": self.is_building()
        }

        # Check cached pages
        pages_dir = self.cache_dir / "pages"
        if pages_dir.exists():
            status["cached_pages"] = len(list(pages_dir.glob("*.json")))

        # Check metadata
        if self.metadata_file.exists():
            try:
                metadata = json.loads(self.metadata_file.read_text())
                last_update = datetime.fromisoformat(metadata["last_update"])
                status["last_update"] = last_update.isoformat()

                age = datetime.now() - last_update
                status["age_hours"] = age.total_seconds() / 3600
                status["needs_update"] = age >= self.update_interval
            except:
                pass

        # Determine if build is needed
        if not status["index_exists"]:
            status["needs_build"] = True
        elif status["needs_update"]:
            status["needs_build"] = True

        return status

    def is_building(self) -> bool:
        """Check if a build process is currently running."""
        if self.build_process is None:
            return False

        # Check if process is still running
        if self.build_process.poll() is None:
            return True

        # Process has finished
        self.build_process = None
        return False

    def start_build(self, force: bool = False) -> bool:
        """Start a background build process.

        Args:
            force: Force rebuild even if cache is fresh

        Returns:
            True if build was started, False otherwise
        """
        # Check if already building
        if self.is_building():
            logger.info("Build already in progress, skipping")
            return False

        # Check if build is needed
        status = self.get_index_status()
        if not force and not status["needs_build"]:
            logger.info("Index is up to date, skipping build")
            return False

        try:
            # Prepare log file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"build_index_{timestamp}.log"

            # Start build process
            logger.info(f"Starting web index build process (log: {log_file})")

            with open(log_file, 'w') as log:
                self.build_process = subprocess.Popen(
                    ["python3", "build_web_index.py"],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True  # Detach from parent
                )

            logger.info(f"Build process started (PID: {self.build_process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to start build process: {e}")
            return False

    def initialize_on_startup(self, silent: bool = False):
        """Initialize index on application startup.

        This method:
        1. Checks if index exists and is up to date
        2. Launches background build if needed
        3. Returns immediately without blocking

        Args:
            silent: If True, suppress console output
        """
        status = self.get_index_status()

        if not silent:
            print("\n" + "="*60)
            print("HashiCorp Web Documentation Index Status")
            print("="*60)

        if status["index_exists"]:
            if status["last_update"]:
                age_str = f"{status['age_hours']:.1f} hours ago"
                if not silent:
                    print(f"✓ Index exists (last updated: {age_str})")
            else:
                if not silent:
                    print(f"✓ Index exists")

            if status["needs_update"]:
                if not silent:
                    print(f"⟳ Index is stale, scheduling background update...")
                self.start_build()
            else:
                if not silent:
                    print(f"✓ Index is up to date")
        else:
            if not silent:
                if status["cached_pages"] > 0:
                    print(f"⟳ Building index from {status['cached_pages']} cached pages...")
                elif status["chunks_ready"]:
                    print(f"⟳ Building index from cached chunks...")
                else:
                    print(f"⟳ Building index from scratch (this may take a while)...")
                    print(f"   Progress will be logged to: build_index_*.log")

            self.start_build()

        if not silent:
            print("="*60 + "\n")

        # Start background update checker if enabled
        if self.auto_update and self.update_thread is None:
            self.start_update_checker()

    def start_update_checker(self):
        """Start a background thread that periodically checks for updates."""
        def update_checker():
            logger.info("Starting periodic update checker")

            # Check every 24 hours
            check_interval = 86400  # seconds

            while not self.shutdown_flag.is_set():
                # Wait for check interval or shutdown
                if self.shutdown_flag.wait(timeout=check_interval):
                    break

                logger.info("Running periodic update check")
                status = self.get_index_status()

                if status["needs_update"] and not status["build_in_progress"]:
                    logger.info("Index is stale, starting automatic update")
                    self.start_build()

        self.update_thread = threading.Thread(
            target=update_checker,
            daemon=True,
            name="WebIndexUpdateChecker"
        )
        self.update_thread.start()

    def shutdown(self):
        """Gracefully shutdown the manager and any running builds."""
        logger.info("Shutting down web index manager")

        # Signal update checker to stop
        self.shutdown_flag.set()

        # Note: We intentionally don't kill the build process
        # It should continue running in the background and can be resumed
        if self.is_building():
            logger.info(f"Build process (PID {self.build_process.pid}) will continue in background")


# Global instance
_manager: Optional[WebIndexManager] = None


def get_manager() -> WebIndexManager:
    """Get or create the global web index manager."""
    global _manager
    if _manager is None:
        _manager = WebIndexManager()
    return _manager


def initialize_on_startup(silent: bool = False):
    """Initialize web index on application startup.

    This is the main entry point for automatic index management.
    Call this when your application starts.

    Args:
        silent: If True, suppress console output
    """
    manager = get_manager()
    manager.initialize_on_startup(silent=silent)


def get_status() -> dict:
    """Get current index status."""
    manager = get_manager()
    return manager.get_index_status()


def force_rebuild():
    """Force a complete rebuild of the index."""
    manager = get_manager()
    return manager.start_build(force=True)
