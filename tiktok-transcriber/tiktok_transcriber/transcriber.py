"""Transcribe audio using OpenAI Whisper."""

from typing import Dict, Any, Optional, List

import whisper


class WhisperTranscriber:
    """Transcribes audio files using local Whisper model."""

    def __init__(self, model_name: str = "medium"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            print(f"Loading Whisper {self.model_name} model (this may take a moment)...")
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to the audio file

        Returns:
            Dictionary with transcript text, segments with timestamps, and language
        """
        try:
            result = self.model.transcribe(
                audio_path,
                verbose=False,
                word_timestamps=True,
            )

            segments = self._format_segments(result.get("segments", []))

            return {
                "text": result.get("text", "").strip(),
                "segments": segments,
                "language": result.get("language", "unknown"),
            }

        except Exception as e:
            return {
                "error": f"Transcription failed: {str(e)}",
                "text": "",
                "segments": [],
                "language": "unknown",
            }

    def _format_segments(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """Format segments with timestamps."""
        formatted = []
        for seg in segments:
            formatted.append({
                "start": round(seg.get("start", 0), 2),
                "end": round(seg.get("end", 0), 2),
                "text": seg.get("text", "").strip(),
            })
        return formatted
