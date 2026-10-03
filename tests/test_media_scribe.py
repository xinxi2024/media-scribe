import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import pytest

import media_scribe as ms


def test_srt_and_unicode_exports(tmp_path):
    segments = [{"start": 1.25, "end": 3.5, "text": "你好，世界"}]
    paths = ms.save_transcript(tmp_path, "中文", "你好，世界", segments)
    assert Path(paths[0]).read_text(encoding="utf-8") == "你好，世界\n"
    assert "00:00:01,250 --> 00:00:03,500" in Path(paths[1]).read_text(encoding="utf-8")
    assert json.loads(Path(paths[2]).read_text(encoding="utf-8")) == segments


def test_mode_rejects_wrong_media_type(tmp_path):
    audio = tmp_path / "sample.mp3"
    audio.write_bytes(b"test")
    with pytest.raises(ValueError, match="格式"):
        ms.validate_input(audio, "视频转音频")


def test_process_with_stubbed_transcriber(tmp_path, monkeypatch):
    audio = tmp_path / "讲座.wav"
    audio.write_bytes(b"test")
    monkeypatch.setattr(ms, "new_output_dir", lambda: tmp_path / "result")
    (tmp_path / "result").mkdir()
    monkeypatch.setattr(ms, "transcribe", lambda *_args, **_kwargs: (
        "测试内容", [{"start": 0.0, "end": 1.0, "text": "测试内容"}]
    ))
    status, text, files = ms.process(str(audio), "音频转文字", "均衡 · small", "中文")
    assert "完成" in status
    assert text == "测试内容"
    assert len(files) == 3
    assert all(Path(path).is_file() for path in files)


def test_fast_profile_skips_fallback(tmp_path, monkeypatch):
    source = tmp_path / "voice.wav"
    source.write_bytes(b"test")
    seen = {}

    class Model:
        def transcribe(self, _source, **options):
            seen.update(options)
            return iter([]), None

    monkeypatch.setattr(ms, "get_model", lambda _size: Model())
    monkeypatch.setattr(ms, "media_duration", lambda _source: 3)
    ms.transcribe(source, "base", "zh")
    assert seen["beam_size"] == 1
    assert seen["temperature"] == 0.0


def test_long_file_uses_batch_with_timestamps(tmp_path, monkeypatch):
    import faster_whisper

    source = tmp_path / "long.wav"
    source.write_bytes(b"test")
    seen = {}

    class Pipeline:
        def __init__(self, model):
            seen["model"] = model

        def transcribe(self, _source, **options):
            seen.update(options)
            return iter([]), None

    model = object()
    monkeypatch.setattr(ms, "get_model", lambda _size: model)
    monkeypatch.setattr(ms, "media_duration", lambda _source: 90)
    monkeypatch.setattr(faster_whisper, "BatchedInferencePipeline", Pipeline, raising=False)
    ms.transcribe(source, "small", "zh")
    assert seen["model"] is model
    assert seen["batch_size"] == 8
    assert seen["without_timestamps"] is False
    assert seen["beam_size"] == 3
    assert "temperature" not in seen


def test_original_audio_export_copies_codec(tmp_path):
    video = tmp_path / "sample.mp4"
    subprocess.run([
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=black:s=160x120:r=10",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
        "-t", "1", "-c:v", "mpeg4", "-c:a", "aac", str(video),
    ], check=True)
    audio = ms.extract_audio(video, tmp_path, "sample", "copy")
    assert audio.suffix == ".m4a"
    assert audio.stat().st_size > 0
