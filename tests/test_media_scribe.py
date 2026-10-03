import json
from pathlib import Path

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
    monkeypatch.setattr(ms, "transcribe", lambda *_args: (
        "测试内容", [{"start": 0.0, "end": 1.0, "text": "测试内容"}]
    ))
    status, text, files = ms.process(str(audio), "音频转文字", "均衡 · small", "中文")
    assert "完成" in status
    assert text == "测试内容"
    assert len(files) == 3
    assert all(Path(path).is_file() for path in files)
