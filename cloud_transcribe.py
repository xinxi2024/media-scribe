"""Optional server-side Groq transcription. The API key never reaches the browser."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import httpx
import imageio_ffmpeg

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
CHUNK_SECONDS = 300
OVERLAP_SECONDS = 2
MAX_CHUNK_BYTES = 24_000_000  # Keep below Groq's 25 MB free-tier upload cap.


def chunk_ranges(duration: float) -> list[tuple[float, float | None]]:
    if duration <= 0:
        return [(0.0, None)]
    ranges = []
    start = 0.0
    while start < duration:
        remaining = duration - start
        length = (remaining if remaining <= CHUNK_SECONDS + 2 * OVERLAP_SECONDS
                  else CHUNK_SECONDS)
        ranges.append((start, length))
        if start + length >= duration:
            break
        start += CHUNK_SECONDS - OVERLAP_SECONDS
    return ranges


def prepare_chunk(source: Path, destination: Path,
                  start: float, length: float | None) -> Path:
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel",
               "error", "-y"]
    if start:
        command.extend(["-ss", str(start)])
    command.extend(["-i", str(source)])
    if length is not None:
        command.extend(["-t", str(length)])
    command.extend(["-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000",
                    "-codec:a", "flac", str(destination)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode or not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("云端转写前的音频提取失败，请检查文件是否包含音轨。")
    if destination.stat().st_size <= MAX_CHUNK_BYTES:
        return destination

    # Very noisy lossless audio may exceed the free upload cap.
    compressed = destination.with_suffix(".mp3")
    result = subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-y", "-i", str(destination), "-codec:a", "libmp3lame", "-b:a",
        "64k", str(compressed),
    ], capture_output=True, text=True, check=False)
    if result.returncode or not compressed.is_file() or compressed.stat().st_size > MAX_CHUNK_BYTES:
        raise RuntimeError("音频片段超过免费接口的 25 MB 限制，请使用更短的文件。")
    destination.unlink(missing_ok=True)
    return compressed


def request_chunk(client: httpx.Client, file_path: Path, model: str,
                  language: str | None, terms: str, word_timestamps: bool) -> dict:
    data: list[tuple[str, str]] = [
        ("model", model), ("response_format", "verbose_json"),
        ("temperature", "0"), ("timestamp_granularities[]", "segment"),
    ]
    if word_timestamps:
        data.append(("timestamp_granularities[]", "word"))
    if language:
        data.append(("language", language))
    if terms.strip():
        data.append(("prompt", terms.strip()[:160]))
    mime = "audio/flac" if file_path.suffix == ".flac" else "audio/mpeg"
    with file_path.open("rb") as audio:
        multipart = [(name, (None, value)) for name, value in data]
        multipart.append(("file", (file_path.name, audio, mime)))
        try:
            response = client.post(GROQ_URL, files=multipart)
        except httpx.HTTPError as exc:
            raise RuntimeError("云端语音识别服务暂不可用，请稍后重试。") from exc
    if response.status_code == 429:
        raise RuntimeError("云端免费额度或速率已达到上限，请稍后再试。")
    if response.status_code in {401, 403}:
        raise RuntimeError("云端语音识别密钥无效或没有权限，请检查服务端配置。")
    if response.status_code >= 400:
        raise RuntimeError(f"云端语音识别失败（HTTP {response.status_code}）。")
    return response.json()


def transcribe_cloud(source: Path, duration: float, model: str,
                     language: str | None, terms: str, word_timestamps: bool,
                     progress: Callable[[str], None] | None = None
                     ) -> tuple[str, list[dict]]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("服务端尚未配置 GROQ_API_KEY。")
    ranges = chunk_ranges(duration)
    items: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="media_scribe_cloud_") as temp_dir:
        with httpx.Client(headers={"Authorization": f"Bearer {key}"},
                          timeout=httpx.Timeout(180.0, connect=15.0)) as client:
            for index, (start, length) in enumerate(ranges):
                if progress:
                    progress(f"正在云端识别第 {index + 1}/{len(ranges)} 段…")
                chunk = prepare_chunk(source, Path(temp_dir) / f"part_{index:03}.flac",
                                      start, length)
                data = request_chunk(client, chunk, model, language, terms,
                                     word_timestamps)
                boundary_before = start + (OVERLAP_SECONDS / 2 if index else 0)
                boundary_after = (start + length - OVERLAP_SECONDS / 2
                                  if length is not None and index < len(ranges) - 1
                                  else float("inf"))
                words = data.get("words") or []
                for segment in data.get("segments") or []:
                    rel_start = float(segment.get("start", 0))
                    rel_end = float(segment.get("end", rel_start))
                    midpoint = start + (rel_start + rel_end) / 2
                    if not (boundary_before <= midpoint < boundary_after):
                        continue
                    text = str(segment.get("text", "")).strip()
                    if not text:
                        continue
                    item = {"start": start + rel_start, "end": start + rel_end,
                            "text": text}
                    if word_timestamps:
                        item["words"] = [
                            {"start": start + float(word.get("start", 0)),
                             "end": start + float(word.get("end", 0)),
                             "word": word.get("word", "")}
                            for word in words
                            if rel_start <= float(word.get("start", -1)) < rel_end
                        ]
                    items.append(item)
                if not data.get("segments") and data.get("text"):
                    items.append({"start": start, "end": start + (length or 0),
                                  "text": str(data["text"]).strip()})
    items.sort(key=lambda item: item["start"])
    return "\n".join(item["text"] for item in items), items
