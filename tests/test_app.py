import asyncio
import tempfile
import unittest
from pathlib import Path

from ninja_music.app import NinjaMusicApp, Track
from ninja_music.services import PlaybackHistory
from textual.widgets import Label, ListItem


class FakePlayer:
    def __init__(self) -> None:
        self.active = False
        self.played_urls: list[str] = []

    def play(self, url: str) -> None:
        self.active = True
        self.played_urls.append(url)

    def toggle_pause(self) -> bool:
        return False

    def set_mute(self, _muted: bool) -> None:
        pass

    def stop(self) -> None:
        self.active = False

    def get_property(self, _name: str) -> None:
        return None


class NinjaMusicAppTest(unittest.TestCase):
    def test_app_mounts_and_changes_track(self) -> None:
        async def run() -> None:
            app = NinjaMusicApp(enable_cava=False)
            app.player = FakePlayer()
            async with app.run_test(size=(140, 42)) as pilot:
                self.assertEqual(app.current_index, 0)
                await pilot.press("n")
                self.assertEqual(app.current_index, 1)
                self.assertFalse(app.playing)
                await pilot.press("space")
                self.assertFalse(app.playing)

        asyncio.run(run())

    def test_finished_track_advances_to_next_track(self) -> None:
        async def run() -> None:
            app = NinjaMusicApp(enable_cava=False)
            fake_player = FakePlayer()
            app.player = fake_player
            app.tracks = [
                Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                Track("Dos", "Artista", "0:01", "YouTube", "https://example.test/dos"),
            ]
            async with app.run_test(size=(140, 42)):
                app.current_index = 0
                app.playing = True
                fake_player.active = False
                app._advance_after_track_finished()

                self.assertEqual(app.current_index, 1)
                self.assertTrue(app.playing)
                self.assertEqual(fake_player.played_urls[-1], "https://example.test/dos")

        asyncio.run(run())

    def test_finished_last_track_stops_playback(self) -> None:
        async def run() -> None:
            app = NinjaMusicApp(enable_cava=False)
            app.player = FakePlayer()
            app.tracks = [
                Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
            ]
            async with app.run_test(size=(140, 42)):
                app.current_index = 0
                app.playing = True
                app._advance_after_track_finished()

                self.assertEqual(app.current_index, 0)
                self.assertFalse(app.playing)

        asyncio.run(run())

    def test_time_formatting(self) -> None:
        self.assertEqual(NinjaMusicApp._format_time(0), "0:00")
        self.assertEqual(NinjaMusicApp._format_time(68.9), "1:08")
        self.assertEqual(NinjaMusicApp._format_time(3661), "1:01:01")
        self.assertEqual(NinjaMusicApp._parse_duration("3:08"), 188.0)

    def test_navigation_item_text_uses_textual_render_api(self) -> None:
        async def run() -> None:
            app = NinjaMusicApp(enable_cava=False)
            app.player = FakePlayer()
            async with app.run_test(size=(140, 42)):
                nav = app.query_one("#nav-list")
                item = nav.children[4]
                self.assertIsInstance(item, ListItem)
                self.assertIn("Historial", NinjaMusicApp._list_item_text(item))

        asyncio.run(run())

    def test_playback_history_persists_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            history = PlaybackHistory(path=path)
            track = {
                "title": "Canción de prueba",
                "artist": "Artista",
                "duration": "3:10",
                "album": "YouTube",
                "url": "https://example.test/song",
            }

            history.add(track)
            history.add(track)

            entries = history.load()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["title"], "Canción de prueba")
            self.assertEqual(entries[0]["url"], "https://example.test/song")


if __name__ == "__main__":
    unittest.main()
