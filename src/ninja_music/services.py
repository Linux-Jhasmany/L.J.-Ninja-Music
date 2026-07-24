from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SearchResult:
    video_id: str
    title: str
    artist: str
    duration_seconds: int

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def duration(self) -> str:
        minutes, seconds = divmod(self.duration_seconds, 60)
        return f"{minutes}:{seconds:02d}"


class YouTubeSearch:
    def search(self, query: str, limit: int = 15) -> list[SearchResult]:
        command = [
            "yt-dlp",
            "--force-ipv4",
            "--socket-timeout",
            "10",
            "--flat-playlist",
            "--dump-json",
            "--no-warnings",
            f"ytsearch{limit}:{query}",
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "YouTube no respondió")

        results: list[SearchResult] = []
        for line in completed.stdout.splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            video_id = str(data.get("id") or "")
            if not video_id:
                continue
            results.append(
                SearchResult(
                    video_id=video_id,
                    title=str(data.get("title") or "Sin título"),
                    artist=str(data.get("channel") or data.get("uploader") or "Desconocido"),
                    duration_seconds=int(data.get("duration") or 0),
                )
            )
        return results


class PlaybackHistory:
    def __init__(self, path: Path | None = None, limit: int = 200) -> None:
        state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        self.path = path or state_home / "ninja-music" / "history.json"
        self.limit = limit

    def load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        return [entry for entry in data if isinstance(entry, dict)]

    def add(self, track: dict[str, str]) -> None:
        entry = {
            "played_at": int(time.time()),
            "title": track.get("title", ""),
            "artist": track.get("artist", ""),
            "duration": track.get("duration", ""),
            "album": track.get("album", ""),
            "url": track.get("url", ""),
        }
        entries = [entry, *self.load()]
        entries = self._deduplicate_recent(entries)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(entries[: self.limit], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _deduplicate_recent(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for entry in entries:
            key = str(entry.get("url") or f"{entry.get('title')}::{entry.get('artist')}")
            if key in seen:
                continue
            seen.add(key)
            unique.append(entry)
        return unique


class MpvPlayer:
    def __init__(self) -> None:
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
        self.socket_path = runtime_dir / f"ninja-music-{os.getuid()}.sock"
        self.process: subprocess.Popen[str] | None = None

    @property
    def active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def play(self, url: str) -> None:
        self.stop()
        self.process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--force-window=no",
                "--no-resume-playback",
                "--ytdl-format=bestaudio/best",
                f"--input-ipc-server={self.socket_path}",
                "--audio-display=no",
                "--volume=70",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def toggle_pause(self) -> bool | None:
        response = self.command({"command": ["cycle", "pause"]})
        if response is None:
            return None
        paused = self.get_property("pause")
        return None if paused is None else not bool(paused)

    def set_mute(self, muted: bool) -> None:
        self.command({"command": ["set_property", "mute", muted]})

    def get_property(self, name: str) -> object | None:
        response = self.command({"command": ["get_property", name]})
        return None if response is None else response.get("data")

    def command(self, payload: dict[str, object]) -> dict[str, object] | None:
        if not self.active:
            return None
        encoded = (json.dumps(payload) + "\n").encode()
        for _ in range(20):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(1)
                    client.connect(str(self.socket_path))
                    client.sendall(encoded)
                    response = client.recv(65536)
                return json.loads(response.decode().splitlines()[0])
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(0.05)
            except (OSError, json.JSONDecodeError, IndexError):
                return None
        return None

    def stop(self) -> None:
        if self.active:
            self.command({"command": ["quit"]})
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
        self.process = None


class CavaAnalyzer:
    def __init__(self) -> None:
        self.config_path = Path(__file__).with_name("cava.conf")
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> subprocess.Popen[str]:
        if self.process is not None and self.process.poll() is None:
            return self.process
        self.process = subprocess.Popen(
            ["cava", "-p", str(self.config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        return self.process

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
