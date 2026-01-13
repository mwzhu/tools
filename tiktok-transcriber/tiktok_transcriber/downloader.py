"""Download audio from TikTok videos using yt-dlp."""

import os
import tempfile
import time
from typing import Optional, Tuple

import yt_dlp


class TikTokDownloader:
    """Downloads audio from TikTok videos."""

    def __init__(self, output_dir: Optional[str] = None, max_retries: int = 3):
        self.output_dir = output_dir or tempfile.mkdtemp(prefix="tiktok_audio_")
        self.max_retries = max_retries
        os.makedirs(self.output_dir, exist_ok=True)

    def download_audio(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Download audio from a TikTok URL.

        Args:
            url: TikTok video URL

        Returns:
            Tuple of (audio_path, error_message)
            - On success: (path_to_audio, None)
            - On failure: (None, error_message)
        """
        video_id = self._extract_video_id(url)
        output_path = os.path.join(self.output_dir, f"{video_id}.mp3")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(self.output_dir, f"{video_id}.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "cookiesfrombrowser": ("chrome",),
        }

        for attempt in range(self.max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                if os.path.exists(output_path):
                    return output_path, None
                else:
                    return None, "Audio file not created"

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if "Private video" in error_msg or "Video unavailable" in error_msg:
                    return None, "Video is private or unavailable"
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None, f"Download failed: {error_msg}"

            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None, f"Unexpected error: {str(e)}"

        return None, "Max retries exceeded"

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from TikTok or Instagram URL for filename."""
        # Handle various URL formats:
        # TikTok: https://www.tiktok.com/@user/video/1234567890
        # TikTok: https://vm.tiktok.com/XXXXXX/
        # Instagram: https://www.instagram.com/reel/ABC123XYZ/
        # Instagram: https://www.instagram.com/p/ABC123XYZ/
        import re
        import hashlib

        # Try to extract TikTok numeric video ID
        match = re.search(r"/video/(\d+)", url)
        if match:
            return match.group(1)

        # Try to extract Instagram reel/post ID
        match = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", url)
        if match:
            return match.group(1)

        # For short URLs or unknown formats, use hash of URL
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def cleanup(self, audio_path: str) -> None:
        """Remove downloaded audio file."""
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except OSError:
            pass
