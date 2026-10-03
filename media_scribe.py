"""Local audio extraction and speech transcription for the Gradio UI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Callable

import imageio_ffmpeg

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
MODES = {"视频转音频", "视频转文字", "音频转文字"}
MODELS = {
    "极速 · tiny": "tiny",
    "快速 · base": "base",
    "均衡 · small": "small",
    "准确 · medium": "medium",
}
BEAM_SIZES = {"tiny": 1, "base": 1, "small": 3, "medium": 5}
BATCH_THRESHOLD_SECONDS = 60
LANGUAGES = {"自动检测": None, "中文": "zh", "English": "en", "日本語": "ja", "한국어": "ko"}


def validate_input(path: str | Path, mode: str) -> Path:
    if mode not in MODES:
        raise ValueError("请选择一个处理方式。")
    source = Path(path)
    if not source.is_file():
        raise ValueError("请先上传文件。")
    allowed = VIDEO_EXTENSIONS if mode.startswith("视频") else AUDIO_EXTENSIONS
    if source.suffix.lower() not in allowed:
        raise ValueError(f"文件格式不适用于「{mode}」。支持：{', '.join(sorted(allowed))}")
    return source


def safe_stem(path: Path) -> str:
    """Keep readable file names without letting names become output paths."""
    stem = re.sub(r"[^\w\-]+", "_", path.stem, flags=re.UNICODE).strip("_-")
    return stem[:80] or "media"


def new_output_dir() -> Path:
    root = Path(__file__).resolve().parent / "outputs"
    root.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="job_", dir=root))


def extract_mp3(source: Path, destination: Path) -> Path:
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-y", "-i", str(source), "-vn", "-map", "0:a:0", "-codec:a",
        "libmp3lame", "-q:a", "2", str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode or not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        detail = result.stderr.strip().splitlines()
        raise RuntimeError("音频提取失败。请确认视频包含音轨。" + (f" {detail[-1]}" if detail else ""))
    return destination


def srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


@lru_cache(maxsize=2)
def get_model(size: str):
    from faster_whisper import WhisperModel

    # Keep CPU inference predictable on machines without a working CUDA runtime.
    return WhisperModel(size, device="cpu", compute_type="int8",
                        cpu_threads=min(8, os.cpu_count() or 4))


def media_duration(source: Path) -> float:
    """Return container duration in seconds; unknown duration uses normal decoding."""
    import av

    try:
        with av.open(str(source)) as container:
            return float(container.duration / av.time_base) if container.duration else 0.0
    except (av.AVError, OSError):
        return 0.0


def transcribe(source: Path, model_size: str, language: str | None,
               progress: Callable[[str], None] | None = None) -> tuple[str, list[dict]]:
    if progress:
        progress("正在加载识别模型（首次使用会下载模型）…")
    model = get_model(model_size)
    options = dict(language=language, beam_size=BEAM_SIZES[model_size],
                   vad_filter=True, condition_on_previous_text=False)
    if model_size in {"tiny", "base"}:
        # Skip costly fallback retries in the speed-focused profiles.
        options["temperature"] = 0.0
    pipeline_class = None
    if media_duration(source) >= BATCH_THRESHOLD_SECONDS:
        try:
            from faster_whisper import BatchedInferencePipeline as pipeline_class
        except ImportError:
            # Older installations still support normal transcription.
            pass
    if pipeline_class is not None:
        if progress:
            progress("正在批量识别语音…")
        pipeline = pipeline_class(model=model)
        segments, _info = pipeline.transcribe(
            str(source), batch_size=4 if model_size == "medium" else 8,
            without_timestamps=False, **options,
        )
    else:
        if progress:
            progress("正在识别语音…")
        segments, _info = model.transcribe(str(source), **options)
    items = [
        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for segment in segments if segment.text.strip()
    ]
    text = "\n".join(item["text"] for item in items)
    return text, items


def save_transcript(out_dir: Path, stem: str, text: str,
                    segments: list[dict]) -> list[str]:
    txt = out_dir / f"{stem}.txt"
    srt = out_dir / f"{stem}.srt"
    js = out_dir / f"{stem}.json"
    txt.write_text(text + ("\n" if text else ""), encoding="utf-8")
    srt.write_text("\n".join(
        f"{i}\n{srt_timestamp(item['start'])} --> {srt_timestamp(item['end'])}\n{item['text']}\n"
        for i, item in enumerate(segments, 1)
    ), encoding="utf-8")
    js.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [str(txt), str(srt), str(js)]


def process(file_path: str | None, mode: str, model_label: str,
            language_label: str, progress: Callable[[str], None] | None = None
            ) -> tuple[str, str, list[str]]:
    if not file_path:
        raise ValueError("请先上传文件。")
    source = validate_input(file_path, mode)
    if model_label not in MODELS or language_label not in LANGUAGES:
        raise ValueError("请检查模型和语言选项。")
    out_dir = new_output_dir()
    stem = safe_stem(source)
    if mode == "视频转音频":
        if progress:
            progress("正在提取音频…")
        mp3 = extract_mp3(source, out_dir / f"{stem}.mp3")
        return "音频已提取，可以下载 MP3。", "", [str(mp3)]

    text, segments = transcribe(source, MODELS[model_label],
                                LANGUAGES[language_label], progress)
    files = save_transcript(out_dir, stem, text, segments)
    status = "转写完成：可下载 TXT、SRT 字幕和 JSON 时间轴。"
    if not segments:
        status = "未检测到清晰语音。已生成空的转写文件，请检查音量或改选语言后重试。"
    return status, text, files
