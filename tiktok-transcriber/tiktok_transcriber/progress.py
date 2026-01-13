"""Progress tracking for resumable batch processing."""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Set


class ProgressTracker:
    """Tracks progress of batch processing for resume capability."""

    def __init__(self, progress_file: str):
        self.progress_file = progress_file
        self.processed_urls: Set[str] = set()
        self.results: List[Dict[str, Any]] = []
        self.failed_urls: Dict[str, str] = {}  # url -> error message

    def load(self) -> bool:
        """
        Load progress from file.

        Returns:
            True if progress file exists and was loaded, False otherwise
        """
        if not os.path.exists(self.progress_file):
            return False

        try:
            with open(self.progress_file, "r") as f:
                data = json.load(f)
                self.processed_urls = set(data.get("processed_urls", []))
                self.results = data.get("results", [])
                self.failed_urls = data.get("failed_urls", {})
                return True
        except (json.JSONDecodeError, IOError):
            return False

    def save(self) -> None:
        """Save current progress to file."""
        data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "processed_urls": list(self.processed_urls),
            "results": self.results,
            "failed_urls": self.failed_urls,
        }

        # Write atomically
        temp_file = self.progress_file + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, self.progress_file)

    def mark_success(self, url: str, result: Dict[str, Any]) -> None:
        """Mark a URL as successfully processed."""
        self.processed_urls.add(url)
        self.results.append(result)
        self.save()

    def mark_failed(self, url: str, error: str) -> None:
        """Mark a URL as failed."""
        self.processed_urls.add(url)
        self.failed_urls[url] = error
        self.results.append({
            "url": url,
            "status": "failed",
            "error": error,
        })
        self.save()

    def is_processed(self, url: str) -> bool:
        """Check if a URL has already been processed."""
        return url in self.processed_urls

    def get_pending_urls(self, all_urls: List[str]) -> List[str]:
        """Get list of URLs that haven't been processed yet."""
        return [url for url in all_urls if url not in self.processed_urls]

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        successful = sum(1 for r in self.results if r.get("status") == "success")
        failed = len(self.failed_urls)
        return {
            "processed": len(self.processed_urls),
            "successful": successful,
            "failed": failed,
        }

    def cleanup(self) -> None:
        """Remove progress file after successful completion."""
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
        except OSError:
            pass
