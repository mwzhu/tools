from setuptools import setup, find_packages

setup(
    name="tiktok-transcriber",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "yt-dlp>=2024.1.0",
        "openai-whisper>=20231117",
        "tqdm>=4.66.0",
    ],
    entry_points={
        "console_scripts": [
            "tiktok-transcribe=tiktok_transcriber.cli:main",
        ],
    },
    python_requires=">=3.8",
    author="TikTok Transcriber",
    description="Bulk transcribe TikTok videos using Whisper",
)
