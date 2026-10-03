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

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".mpeg", ".mpg", ".ts", ".m2ts", ".3gp", ".wmv",
}
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma",
    ".opus", ".aiff", ".aif", ".caf",
}
MODES = {"视频转音频", "视频转文字", "音频转文字"}
MODELS = {
    "极速 · tiny": "tiny",
    "快速 · base": "base",
    "均衡 · small": "small",
    "准确 · medium": "medium",
}
CLOUD_MODELS = {
    "快速 · Groq Turbo": "whisper-large-v3-turbo",
    "准确 · Groq Large V3": "whisper-large-v3",
}
BEAM_SIZES = {"tiny": 1, "base": 1, "small": 3, "medium": 5}
BATCH_THRESHOLD_SECONDS = 60
LANGUAGES = {"自动检测": None, "中文": "zh", "English": "en", "日本語": "ja", "한국어": "ko"}
AUDIO_EXPORTS = {
    "原音轨 · 不转码": "copy",
    "MP3 · 通用": "mp3",
    "FLAC · 无损": "flac",
}
COPY_EXTENSIONS = {
    "aac": ".m4a", "alac": ".m4a", "mp3": ".mp3", "opus": ".opus",
    "vorbis": ".ogg", "flac": ".flac", "ac3": ".ac3", "eac3": ".eac3",
}


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


def extract_audio(source: Path, out_dir: Path, stem: str, export: str) -> Path:
    """Copy a compatible original audio stream, or encode MP3/FLAC."""
    import av

    if export not in AUDIO_EXPORTS.values():
        raise ValueError("请选择有效的音频导出格式。")
    with av.open(str(source)) as container:
        streams = [stream for stream in container.streams if stream.type == "audio"]
        if not streams:
            raise ValueError("视频没有音轨，无法提取音频。")
        codec = streams[0].codec_context.name

    if export == "mp3":
        return extract_mp3(source, out_dir / f"{stem}.mp3")
    if export == "copy" and codec in COPY_EXTENSIONS:
        extension = COPY_EXTENSIONS[codec]
        destination = out_dir / f"{stem}{extension}"
        encode_options = ["-codec:a", "copy"]
    else:
        # Unknown source codecs are decoded to lossless FLAC for broad support.
        destination = out_dir / f"{stem}.flac"
        encode_options = ["-codec:a", "flac"]

    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel",
               "error", "-y", "-i", str(source), "-vn", "-map", "0:a:0",
               *encode_options, str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode or not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        detail = result.stderr.strip().splitlines()
        raise RuntimeError("音频提取失败。" + (f" {detail[-1]}" if detail else ""))
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
            if container.duration:
                return float(container.duration / av.time_base)
            for stream in container.streams:
                if stream.type == "audio" and stream.duration and stream.time_base:
                    return float(stream.duration * stream.time_base)
            return 0.0
    except (av.AVError, OSError):
        return 0.0


def transcribe(source: Path, model_size: str, language: str | None,
               progress: Callable[[str], None] | None = None, *,
               vad_filter: bool = True, batch_long: bool = True,
               word_timestamps: bool = False, terms: str = "") -> tuple[str, list[dict]]:
    if progress:
        progress("正在加载识别模型（首次使用会下载模型）…")
    model = get_model(model_size)
    options = dict(language=language, beam_size=BEAM_SIZES[model_size],
                   vad_filter=vad_filter, condition_on_previous_text=False,
                   word_timestamps=word_timestamps)
    if terms.strip():
        options["initial_prompt"] = terms.strip()[:300]
    if model_size in {"tiny", "base"}:
        # Skip costly fallback retries in the speed-focused profiles.
        options["temperature"] = 0.0
    pipeline_class = None
    if batch_long and media_duration(source) >= BATCH_THRESHOLD_SECONDS:
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
    items = []
    for segment in segments:
        if not segment.text.strip():
            continue
        item = {"start": segment.start, "end": segment.end,
                "text": segment.text.strip()}
        if word_timestamps and getattr(segment, "words", None):
            item["words"] = [
                {"start": word.start, "end": word.end,
                 "word": word.word, "probability": word.probability}
                for word in segment.words
            ]
        items.append(item)
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
            language_label: str, progress: Callable[[str], None] | None = None, *,
            audio_export: str = "原音轨 · 不转码", vad_filter: bool = True,
            batch_long: bool = True, word_timestamps: bool = False,
            terms: str = "", backend: str = "local"
            ) -> tuple[str, str, list[str]]:
    if not file_path:
        raise ValueError("请先上传文件。")
    source = validate_input(file_path, mode)
    if language_label not in LANGUAGES:
        raise ValueError("请检查模型和语言选项。")
    out_dir = new_output_dir()
    stem = safe_stem(source)
    if mode == "视频转音频":
        if progress:
            progress("正在提取音频…")
        if audio_export not in AUDIO_EXPORTS:
            raise ValueError("请选择有效的音频导出格式。")
        audio = extract_audio(source, out_dir, stem, AUDIO_EXPORTS[audio_export])
        return f"音频已提取，可以下载 {audio.suffix.upper().lstrip('.')}。", "", [str(audio)]

    if backend == "groq":
        if model_label not in CLOUD_MODELS:
            raise ValueError("请选择有效的云端识别模型。")
        from cloud_transcribe import transcribe_cloud

        text, segments = transcribe_cloud(
            source, media_duration(source), CLOUD_MODELS[model_label],
            LANGUAGES[language_label], terms, word_timestamps, progress,
        )
    elif backend == "local":
        if model_label not in MODELS:
            raise ValueError("请选择有效的本地识别模型。")
        text, segments = transcribe(source, MODELS[model_label],
                                    LANGUAGES[language_label], progress,
                                    vad_filter=vad_filter, batch_long=batch_long,
                                    word_timestamps=word_timestamps, terms=terms)
    else:
        raise ValueError("未知的识别后端。")
    files = save_transcript(out_dir, stem, text, segments)
    status = "转写完成：可下载 TXT、SRT 字幕和 JSON 时间轴。"
    if not segments:
        status = "未检测到清晰语音。已生成空的转写文件，请检查音量或改选语言后重试。"
    return status, text, files
