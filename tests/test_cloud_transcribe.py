import json
from pathlib import Path

import httpx

import cloud_transcribe as cloud


def test_chunk_ranges_avoid_tiny_final_part():
    assert cloud.chunk_ranges(600) == [(0.0, 300), (298.0, 302.0)]
    assert cloud.chunk_ranges(0) == [(0.0, None)]


def test_groq_request_keeps_key_on_server(tmp_path):
    audio = tmp_path / "sample.flac"
    audio.write_bytes(b"audio")
    observed = {}

    def respond(request):
        observed["url"] = str(request.url)
        observed["body"] = request.content
        observed["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"text": "你好", "segments": []})

    with httpx.Client(transport=httpx.MockTransport(respond),
                      headers={"Authorization": "Bearer secret"}) as client:
        result = cloud.request_chunk(client, audio, "whisper-large-v3-turbo",
                                     "zh", "声刻", True)
    assert result["text"] == "你好"
    assert observed["url"] == cloud.GROQ_URL
    assert observed["auth"] == "Bearer secret"
    assert b"timestamp_granularities[]" in observed["body"]
    assert b"whisper-large-v3-turbo" in observed["body"]


def test_cloud_merges_chunk_timestamps(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"test")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def fake_prepare(_source, destination, _start, _length):
        destination.write_bytes(b"audio")
        return destination

    def fake_request(_client, path, _model, _language, _terms, _words):
        if path.stem.endswith("000"):
            return {"segments": [
                {"start": 10, "end": 12, "text": "第一段"},
                {"start": 299, "end": 300, "text": "交界重复"},
            ]}
        return {"segments": [{"start": 1, "end": 3, "text": "第二段"}],
                "words": [{"start": 1, "end": 2, "word": "第二"}]}

    monkeypatch.setattr(cloud, "prepare_chunk", fake_prepare)
    monkeypatch.setattr(cloud, "request_chunk", fake_request)
    text, segments = cloud.transcribe_cloud(
        source, 600, "whisper-large-v3-turbo", "zh", "", True,
    )
    assert text == "第一段\n第二段"
    assert [item["start"] for item in segments] == [10, 299]
    assert segments[1]["words"][0]["start"] == 299
