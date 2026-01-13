"""Extract metadata from TikTok videos using yt-dlp."""

from typing import Dict, Optional, Any

import yt_dlp


class MetadataExtractor:
    """Extracts metadata from TikTok videos."""

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Extract metadata from a TikTok URL.

        Args:
            url: TikTok video URL

        Returns:
            Dictionary with video metadata or error info
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "cookiesfrombrowser": ("chrome",),
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if info is None:
                    return {"error": "Could not extract video info"}

                return {
                    "title": info.get("title", ""),
                    "description": info.get("description", ""),
                    "author": info.get("uploader", info.get("creator", "")),
                    "author_id": info.get("uploader_id", info.get("channel_id", "")),
                    "likes": info.get("like_count"),
                    "views": info.get("view_count"),
                    "comments": info.get("comment_count"),
                    "duration": info.get("duration"),
                    "upload_date": self._format_date(info.get("upload_date")),
                    "thumbnail": info.get("thumbnail"),
                }

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if "Private video" in error_msg:
                return {"error": "Video is private"}
            if "Video unavailable" in error_msg:
                return {"error": "Video unavailable"}
            return {"error": f"Could not extract metadata: {error_msg}"}

        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}

    def _format_date(self, date_str: Optional[str]) -> Optional[str]:
        """Format YYYYMMDD to YYYY-MM-DD."""
        if date_str and len(date_str) == 8:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        return date_str
