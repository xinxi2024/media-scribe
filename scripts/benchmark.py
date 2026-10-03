"""Measure upload + processing + download against a running Media Scribe site."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from gradio_client import Client, handle_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Site URL, such as http://127.0.0.1:7860")
    parser.add_argument("file", type=Path, help="Audio or video sample")
    parser.add_argument("--mode", default="音频转文字",
                        choices=["音频转文字", "视频转文字", "视频转音频"])
    parser.add_argument("--model", default="快速 · base",
                        help="Model label shown on the target site")
    parser.add_argument("--language", default="中文")
    args = parser.parse_args()
    if not args.file.is_file():
        parser.error("Sample file does not exist")

    password = os.getenv("MEDIA_SCRIBE_PASSWORD")
    client = Client(args.url, auth=("owner", password) if password else None)
    start = time.perf_counter()
    status, text, files = client.predict(
        handle_file(str(args.file)), args.mode, "原音轨 · 不转码",
        args.model, args.language, "", True, True, False,
        api_name="/run",
    )
    elapsed = time.perf_counter() - start
    print(f"Total upload + processing + download: {elapsed:.2f}s")
    print(f"Status: {status}")
    print(f"Text characters: {len(text)}; downloaded files: {len(files)}")


if __name__ == "__main__":
    main()
