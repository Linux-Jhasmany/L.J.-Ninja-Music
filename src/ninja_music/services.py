from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import time
from contextlib import closing
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
        default_dir = state_home / "ninja-music"
        self.path = path or default_dir / "history.db"
        self.legacy_json_path = default_dir / "history.json" if path is None else None
        self.limit = limit

    def load(self) -> list[dict[str, Any]]:
        self._ensure_database()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT played_at, title, artist, duration, album, url
                FROM playback_history
                ORDER BY played_at DESC, id DESC
                LIMIT ?
                """,
                (self.limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add(self, track: dict[str, str]) -> None:
        entry = {
            "played_at": int(time.time()),
            "title": track.get("title", ""),
            "artist": track.get("artist", ""),
            "duration": track.get("duration", ""),
            "album": track.get("album", ""),
            "url": track.get("url", ""),
        }
        self._ensure_database()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO playback_history
                        (track_key, played_at, title, artist, duration, album, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(track_key) DO UPDATE SET
                        played_at = excluded.played_at,
                        title = excluded.title,
                        artist = excluded.artist,
                        duration = excluded.duration,
                        album = excluded.album,
                        url = excluded.url
                    """,
                    (
                        self._track_key(entry),
                        entry["played_at"],
                        entry["title"],
                        entry["artist"],
                        entry["duration"],
                        entry["album"],
                        entry["url"],
                    ),
                )
                connection.execute(
                    """
                    DELETE FROM playback_history
                    WHERE id NOT IN (
                        SELECT id
                        FROM playback_history
                        ORDER BY played_at DESC, id DESC
                        LIMIT ?
                    )
                    """,
                    (self.limit,),
                )

    @staticmethod
    def _track_key(entry: dict[str, Any]) -> str:
        return str(entry.get("url") or f"{entry.get('title')}::{entry.get('artist')}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_database(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS playback_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        track_key TEXT NOT NULL UNIQUE,
                        played_at INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        artist TEXT NOT NULL,
                        duration TEXT NOT NULL,
                        album TEXT NOT NULL,
                        url TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_playback_history_played_at
                    ON playback_history (played_at DESC)
                    """
                )
        self._migrate_legacy_json()

    def _migrate_legacy_json(self) -> None:
        if self.legacy_json_path is None or not self.legacy_json_path.exists():
            return
        try:
            data = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, list):
            return

        with closing(self._connect()) as connection:
            count = connection.execute("SELECT COUNT(*) FROM playback_history").fetchone()[0]
            if count:
                return
            with connection:
                for item in data[: self.limit]:
                    if not isinstance(item, dict):
                        continue
                    entry = {
                        "played_at": int(item.get("played_at") or time.time()),
                        "title": str(item.get("title") or ""),
                        "artist": str(item.get("artist") or ""),
                        "duration": str(item.get("duration") or ""),
                        "album": str(item.get("album") or ""),
                        "url": str(item.get("url") or ""),
                    }
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO playback_history
                            (track_key, played_at, title, artist, duration, album, url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            self._track_key(entry),
                            entry["played_at"],
                            entry["title"],
                            entry["artist"],
                            entry["duration"],
                            entry["album"],
                            entry["url"],
                        ),
                    )


class PlaylistStore:
    FAVORITES_NAME = "Favoritos"

    def __init__(self, path: Path | None = None) -> None:
        state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        self.path = path or state_home / "ninja-music" / "history.db"

    def list_playlists(self) -> list[dict[str, Any]]:
        self._ensure_database()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    playlists.id,
                    playlists.name,
                    playlists.created_at,
                    COUNT(playlist_tracks.id) AS track_count
                FROM playlists
                LEFT JOIN playlist_tracks
                    ON playlist_tracks.playlist_id = playlists.id
                WHERE playlists.name != ?
                GROUP BY playlists.id
                ORDER BY playlists.created_at DESC, playlists.id DESC
                """,
                (self.FAVORITES_NAME,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_playlist(self, name: str) -> dict[str, Any]:
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("El nombre de la lista no puede estar vacío")

        self._ensure_database()
        created_at = int(time.time())
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO playlists (name, created_at)
                    VALUES (?, ?)
                    ON CONFLICT(name) DO NOTHING
                    """,
                    (clean_name, created_at),
                )
                row = connection.execute(
                    """
                    SELECT id, name, created_at
                    FROM playlists
                    WHERE name = ?
                    """,
                    (clean_name,),
                ).fetchone()
        return dict(row)

    def get_or_create_favorites(self) -> dict[str, Any]:
        return self.create_playlist(self.FAVORITES_NAME)

    def list_favorites(self) -> list[dict[str, Any]]:
        favorites = self.get_or_create_favorites()
        return self.list_tracks(int(favorites["id"]))

    def add_favorite(self, track: dict[str, str]) -> None:
        favorites = self.get_or_create_favorites()
        self.add_track(int(favorites["id"]), track)

    def remove_favorite(self, track: dict[str, str]) -> None:
        favorites = self.get_or_create_favorites()
        self.remove_track(int(favorites["id"]), track)

    def is_favorite(self, track: dict[str, str]) -> bool:
        favorites = self.get_or_create_favorites()
        track_key = self._track_key(track)
        return any(entry["track_key"] == track_key for entry in self.list_tracks(int(favorites["id"])))

    def toggle_favorite(self, track: dict[str, str]) -> bool:
        if self.is_favorite(track):
            self.remove_favorite(track)
            return False
        self.add_favorite(track)
        return True

    def get_playlist(self, playlist_id: int) -> dict[str, Any] | None:
        self._ensure_database()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT id, name, created_at
                FROM playlists
                WHERE id = ?
                """,
                (playlist_id,),
            ).fetchone()
        return None if row is None else dict(row)

    def list_tracks(self, playlist_id: int) -> list[dict[str, Any]]:
        self._ensure_database()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT track_key, title, artist, duration, album, url, added_at, position
                FROM playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position ASC, id ASC
                """,
                (playlist_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_track(self, playlist_id: int, track: dict[str, str]) -> None:
        entry = {
            "track_key": self._track_key(track),
            "title": track.get("title", ""),
            "artist": track.get("artist", ""),
            "duration": track.get("duration", ""),
            "album": track.get("album", ""),
            "url": track.get("url", ""),
            "added_at": int(time.time()),
        }
        self._ensure_database()
        with closing(self._connect()) as connection:
            with connection:
                position = connection.execute(
                    """
                    SELECT COALESCE(MAX(position), 0) + 1
                    FROM playlist_tracks
                    WHERE playlist_id = ?
                    """,
                    (playlist_id,),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO playlist_tracks
                        (
                            playlist_id, track_key, title, artist, duration,
                            album, url, added_at, position
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(playlist_id, track_key) DO UPDATE SET
                        title = excluded.title,
                        artist = excluded.artist,
                        duration = excluded.duration,
                        album = excluded.album,
                        url = excluded.url,
                        added_at = excluded.added_at
                    """,
                    (
                        playlist_id,
                        entry["track_key"],
                        entry["title"],
                        entry["artist"],
                        entry["duration"],
                        entry["album"],
                        entry["url"],
                        entry["added_at"],
                        position,
                    ),
                )
                self._normalize_positions(connection, playlist_id)

    def remove_track(self, playlist_id: int, track: dict[str, str]) -> None:
        self._ensure_database()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    DELETE FROM playlist_tracks
                    WHERE playlist_id = ? AND track_key = ?
                    """,
                    (playlist_id, self._track_key(track)),
                )
                self._normalize_positions(connection, playlist_id)

    def move_track(self, playlist_id: int, track: dict[str, str], offset: int) -> bool:
        self._ensure_database()
        with closing(self._connect()) as connection:
            with connection:
                self._normalize_positions(connection, playlist_id)
                rows = connection.execute(
                    """
                    SELECT id, track_key, position
                    FROM playlist_tracks
                    WHERE playlist_id = ?
                    ORDER BY position ASC, id ASC
                    """,
                    (playlist_id,),
                ).fetchall()
                track_key = self._track_key(track)
                current_index = next(
                    (index for index, row in enumerate(rows) if row["track_key"] == track_key),
                    None,
                )
                if current_index is None:
                    return False

                target_index = current_index + offset
                if target_index < 0 or target_index >= len(rows):
                    return False

                current = rows[current_index]
                target = rows[target_index]
                connection.execute(
                    "UPDATE playlist_tracks SET position = ? WHERE id = ?",
                    (target["position"], current["id"]),
                )
                connection.execute(
                    "UPDATE playlist_tracks SET position = ? WHERE id = ?",
                    (current["position"], target["id"]),
                )
        return True

    @staticmethod
    def _track_key(track: dict[str, str]) -> str:
        return str(track.get("url") or f"{track.get('title')}::{track.get('artist')}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_database(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS playlists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS playlist_tracks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        playlist_id INTEGER NOT NULL,
                        track_key TEXT NOT NULL,
                        title TEXT NOT NULL,
                        artist TEXT NOT NULL,
                        duration TEXT NOT NULL,
                        album TEXT NOT NULL,
                        url TEXT NOT NULL,
                        added_at INTEGER NOT NULL,
                        position INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                        UNIQUE (playlist_id, track_key)
                    )
                    """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(playlist_tracks)").fetchall()
                }
                if "position" not in columns:
                    connection.execute(
                        "ALTER TABLE playlist_tracks ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
                    )
                playlist_ids = connection.execute("SELECT id FROM playlists").fetchall()
                for row in playlist_ids:
                    self._normalize_positions(connection, int(row["id"]))

    @staticmethod
    def _normalize_positions(connection: sqlite3.Connection, playlist_id: int) -> None:
        rows = connection.execute(
            """
            SELECT id
            FROM playlist_tracks
            WHERE playlist_id = ?
            ORDER BY position ASC, id ASC
            """,
            (playlist_id,),
        ).fetchall()
        for position, row in enumerate(rows, start=1):
            connection.execute(
                "UPDATE playlist_tracks SET position = ? WHERE id = ?",
                (position, row["id"]),
            )


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
