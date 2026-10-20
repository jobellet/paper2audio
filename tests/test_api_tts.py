import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from paper2audio import run
from paper2audio.audio import render
from paper2audio.cli import main
from paper2audio.tts import ApiTTS, get_backend
from paper2audio.tts.api import split_text
from fixtures import build_single_column


def test_split_text_respects_limit_and_keeps_words():
    text = "\n\n".join(["Short paragraph."] * 3 + ["Word " * 300 + "end.", "A. " * 50])
    chunks = split_text(text, limit=200)
    assert all(len(c) <= 200 for c in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())
    assert chunks[0].count("Short paragraph.") == 3  # small paragraphs are packed together


@pytest.fixture
def speech_server(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    tone = tmp_path / "tone.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "libmp3lame", str(tone)], check=True)
    audio = tone.read_bytes()
    requests: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            body["auth"] = self.headers.get("Authorization")
            requests.append(body)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.end_headers()
            self.wfile.write(audio)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1/audio/speech", requests
    server.shutdown()


def test_api_backend_parallel_render(tmp_path, speech_server):
    url, requests = speech_server
    pdf = tmp_path / "one.pdf"
    build_single_column(pdf)
    script = run(str(pdf))
    backend = ApiTTS(voice="nova", rate=1.25, url=url, key="secret", model="kokoro")
    out = render(script, backend, tmp_path / "one.mp3", progress=lambda m: None, jobs=4)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_chapters", str(out)],
                           capture_output=True, text=True, check=True).stdout
    titles = [line.split("=", 1)[1] for line in probe.splitlines() if line.startswith("TAG:title=")]
    assert titles == ["Title"] + [s.title or "Text" for s in script.sections]  # order kept
    assert len(requests) >= len(titles)
    assert {(r["voice"], r["speed"], r["model"], r["auth"]) for r in requests} == {("nova", 1.25, "kokoro", "Bearer secret")}


def test_fast_defaults_to_espeak_and_respects_engine(tmp_path, monkeypatch):
    chosen = []
    monkeypatch.setattr("paper2audio.cli.get_backend", lambda name, **kw: chosen.append(name) or get_backend("espeak"))
    monkeypatch.setattr("paper2audio.audio.render", lambda *a, **kw: None)
    pdf = tmp_path / "one.pdf"
    build_single_column(pdf)
    main([str(pdf), "--fast", "-o", str(tmp_path / "a.mp3")])
    main([str(pdf), "--fast", "-e", "api", "-o", str(tmp_path / "b.mp3")])
    main([str(pdf), "-o", str(tmp_path / "c.mp3")])
    assert chosen == ["espeak", "api", "edge"]
