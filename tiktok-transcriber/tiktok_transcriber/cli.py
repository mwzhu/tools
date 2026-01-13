"""CLI interface for TikTok Transcriber."""

import argparse
import json
import os
import signal
import sys
from datetime import datetime
from typing import List, Dict, Any

from tqdm import tqdm

from .downloader import TikTokDownloader
from .metadata import MetadataExtractor
from .transcriber import WhisperTranscriber
from .progress import ProgressTracker


class TikTokTranscriber:
    """Main orchestrator for TikTok transcription pipeline."""

    def __init__(
        self,
        model_name: str = "medium",
        progress_file: str = ".tiktok_progress.json",
    ):
        self.downloader = TikTokDownloader()
        self.metadata_extractor = MetadataExtractor()
        self.transcriber = WhisperTranscriber(model_name=model_name)
        self.progress = ProgressTracker(progress_file)
        self._interrupted = False

    def setup_signal_handler(self):
        """Setup graceful shutdown on Ctrl+C."""
        def handler(signum, frame):
            print("\n\nInterrupted! Saving progress...")
            self._interrupted = True

        signal.signal(signal.SIGINT, handler)

    def process_url(self, url: str) -> Dict[str, Any]:
        """Process a single TikTok URL."""
        result = {
            "url": url,
            "status": "success",
            "metadata": {},
            "transcript": {},
        }

        # Extract metadata
        metadata = self.metadata_extractor.extract(url)
        if "error" in metadata:
            result["status"] = "failed"
            result["error"] = metadata["error"]
            return result
        result["metadata"] = metadata

        # Download audio
        audio_path, error = self.downloader.download_audio(url)
        if error:
            result["status"] = "failed"
            result["error"] = error
            return result

        try:
            # Transcribe
            transcript = self.transcriber.transcribe(audio_path)
            if "error" in transcript:
                result["status"] = "failed"
                result["error"] = transcript["error"]
            else:
                result["transcript"] = transcript
        finally:
            # Cleanup audio file
            self.downloader.cleanup(audio_path)

        return result

    def process_batch(
        self,
        urls: List[str],
        resume: bool = False,
    ) -> List[Dict[str, Any]]:
        """Process a batch of TikTok URLs."""
        self.setup_signal_handler()

        # Load progress if resuming
        if resume and self.progress.load():
            stats = self.progress.get_stats()
            print(f"Resuming from previous session: {stats['processed']} already processed")
            urls_to_process = self.progress.get_pending_urls(urls)
        else:
            urls_to_process = urls

        if not urls_to_process:
            print("All URLs already processed!")
            return self.progress.results

        print(f"Processing {len(urls_to_process)} videos...")

        with tqdm(total=len(urls_to_process), unit="video") as pbar:
            for url in urls_to_process:
                if self._interrupted:
                    break

                result = self.process_url(url)

                if result["status"] == "success":
                    self.progress.mark_success(url, result)
                else:
                    self.progress.mark_failed(url, result.get("error", "Unknown error"))

                pbar.update(1)
                pbar.set_postfix(self.progress.get_stats())

        return self.progress.results


def load_urls(input_file: str) -> List[str]:
    """Load URLs from input file."""
    urls = []
    with open(input_file, "r") as f:
        for line in f:
            url = line.strip()
            if url and not url.startswith("#"):
                urls.append(url)
    return urls


def save_output(results: List[Dict[str, Any]], output_file: str) -> None:
    """Save results to JSON file."""
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = len(results) - successful

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_videos": len(results),
        "successful": successful,
        "failed": failed,
        "results": results,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Bulk transcribe TikTok videos using Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tiktok-transcribe -i urls.txt -o transcripts.json
  tiktok-transcribe -i urls.txt -o transcripts.json --model large-v3
  tiktok-transcribe -i urls.txt -o transcripts.json --resume
        """,
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Input text file with TikTok URLs (one per line)",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output JSON file for transcripts",
    )
    parser.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Whisper model size (default: medium)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous progress",
    )
    parser.add_argument(
        "--progress-file",
        default=".tiktok_progress.json",
        help="Progress file for resume capability (default: .tiktok_progress.json)",
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Load URLs
    urls = load_urls(args.input)
    if not urls:
        print("Error: No URLs found in input file", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(urls)} URLs to process")

    # Process
    transcriber = TikTokTranscriber(
        model_name=args.model,
        progress_file=args.progress_file,
    )

    results = transcriber.process_batch(urls, resume=args.resume)

    # Save output
    save_output(results, args.output)
    print(f"\nResults saved to: {args.output}")

    # Show summary
    successful = sum(1 for r in results if r.get("status") == "success")
    failed = len(results) - successful
    print(f"Summary: {successful} successful, {failed} failed out of {len(results)} total")

    # Cleanup progress file on full completion
    if not transcriber._interrupted:
        transcriber.progress.cleanup()


if __name__ == "__main__":
    main()
