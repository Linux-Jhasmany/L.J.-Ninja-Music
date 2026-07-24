import asyncio
import tempfile
import unittest
from pathlib import Path

from ninja_music.app import NinjaMusicApp, Track
from ninja_music.services import PlaybackHistory, PlaylistStore
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
    def test_app_mounts_with_favorites_as_initial_list(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")
                app.playlists.add_favorite(
                    {
                        "title": "Favorita inicial",
                        "artist": "Artista",
                        "duration": "0:01",
                        "album": "YouTube",
                        "url": "https://example.test/favorite-start",
                    }
                )

                async with app.run_test(size=(140, 42)) as pilot:
                    self.assertEqual(app.current_view, "favorites")
                    self.assertEqual(app.tracks[0].title, "Favorita inicial")
                    self.assertEqual(app.query_one("#results").row_count, 1)
                    await pilot.press("n")
                    self.assertEqual(app.current_index, 0)
                    self.assertTrue(app.playing)

        asyncio.run(run())

    def test_app_handles_empty_favorites_on_mount(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")
                async with app.run_test(size=(140, 42)) as pilot:
                    self.assertEqual(app.current_view, "favorites")
                    self.assertEqual(app.tracks, [])
                    self.assertEqual(app.query_one("#results").row_count, 0)
                    await pilot.press("space")
                    self.assertFalse(app.playing)

        asyncio.run(run())

    def test_footer_actions_change_by_view(self) -> None:
        app = NinjaMusicApp(enable_cava=False)

        app.current_view = "playlists"
        self.assertTrue(app.check_action("create_playlist", ()))
        self.assertTrue(app.check_action("focus_search", ()))
        self.assertFalse(app.check_action("add_to_playlist", ()))
        self.assertFalse(app.check_action("remove_from_playlist", ()))
        self.assertFalse(app.check_action("move_playlist_track_up", ()))

        app.current_view = "playlist_tracks"
        self.assertTrue(app.check_action("add_to_playlist", ()))
        self.assertTrue(app.check_action("remove_from_playlist", ()))
        self.assertTrue(app.check_action("move_playlist_track_up", ()))
        self.assertTrue(app.check_action("move_playlist_track_down", ()))

        app.current_view = "choose_playlist"
        self.assertFalse(app.check_action("create_playlist", ()))
        self.assertFalse(app.check_action("toggle_favorite", ()))
        self.assertFalse(app.check_action("remove_from_playlist", ()))

    def test_app_changes_loaded_track(self) -> None:
        async def run() -> None:
            app = NinjaMusicApp(enable_cava=False)
            app.player = FakePlayer()
            app.tracks = [
                Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                Track("Dos", "Artista", "0:01", "YouTube", "https://example.test/dos"),
            ]
            async with app.run_test(size=(140, 42)) as pilot:
                app.tracks = [
                    Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                    Track("Dos", "Artista", "0:01", "YouTube", "https://example.test/dos"),
                ]
                self.assertEqual(app.current_index, 0)
                await pilot.press("n")
                self.assertEqual(app.current_index, 1)
                self.assertTrue(app.playing)

        asyncio.run(run())

    def test_finished_track_advances_to_next_track(self) -> None:
        async def run() -> None:
            app = NinjaMusicApp(enable_cava=False)
            fake_player = FakePlayer()
            app.player = fake_player
            async with app.run_test(size=(140, 42)):
                app.tracks = [
                    Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                    Track("Dos", "Artista", "0:01", "YouTube", "https://example.test/dos"),
                ]
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
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")
                async with app.run_test(size=(140, 42)):
                    app.tracks = [
                        Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                    ]
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
            path = Path(directory) / "history.db"
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
            self.assertTrue(path.exists())

    def test_playlist_store_creates_and_lists_playlists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            playlists = PlaylistStore(path=path)

            playlists.create_playlist("  Favoritas para programar  ")
            playlists.create_playlist("Favoritas para programar")

            entries = playlists.list_playlists()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["name"], "Favoritas para programar")
            self.assertEqual(entries[0]["track_count"], 0)
            self.assertTrue(path.exists())

    def test_playlist_store_adds_tracks_to_playlist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            playlists = PlaylistStore(path=path)
            playlist = playlists.create_playlist("Favoritas")
            track = {
                "title": "Canción guardada",
                "artist": "Artista",
                "duration": "3:45",
                "album": "YouTube",
                "url": "https://example.test/saved",
            }

            playlists.add_track(int(playlist["id"]), track)
            playlists.add_track(int(playlist["id"]), track)

            tracks = playlists.list_tracks(int(playlist["id"]))
            self.assertEqual(len(tracks), 1)
            self.assertEqual(tracks[0]["title"], "Canción guardada")
            self.assertEqual(playlists.list_playlists()[0]["track_count"], 1)

    def test_playlist_store_removes_and_moves_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            playlists = PlaylistStore(path=path)
            playlist = playlists.create_playlist("Orden")
            playlist_id = int(playlist["id"])
            first = {
                "title": "Primera",
                "artist": "Artista",
                "duration": "1:00",
                "album": "YouTube",
                "url": "https://example.test/first",
            }
            second = {
                "title": "Segunda",
                "artist": "Artista",
                "duration": "2:00",
                "album": "YouTube",
                "url": "https://example.test/second",
            }

            playlists.add_track(playlist_id, first)
            playlists.add_track(playlist_id, second)
            self.assertEqual(
                [track["title"] for track in playlists.list_tracks(playlist_id)],
                ["Primera", "Segunda"],
            )

            self.assertTrue(playlists.move_track(playlist_id, second, -1))
            self.assertEqual(
                [track["title"] for track in playlists.list_tracks(playlist_id)],
                ["Segunda", "Primera"],
            )

            playlists.remove_track(playlist_id, second)
            self.assertEqual(
                [track["title"] for track in playlists.list_tracks(playlist_id)],
                ["Primera"],
            )

    def test_playlist_store_toggles_favorites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            playlists = PlaylistStore(path=path)
            track = {
                "title": "Favorita",
                "artist": "Artista",
                "duration": "1:00",
                "album": "YouTube",
                "url": "https://example.test/favorite",
            }

            self.assertTrue(playlists.toggle_favorite(track))
            self.assertEqual(len(playlists.list_favorites()), 1)
            self.assertTrue(playlists.is_favorite(track))
            self.assertFalse(playlists.toggle_favorite(track))
            self.assertEqual(playlists.list_favorites(), [])
            self.assertEqual(playlists.list_playlists(), [])

    def test_app_creates_playlist_from_input(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")

                async with app.run_test(size=(140, 42)) as pilot:
                    await pilot.press("c")
                    for key in "Rock":
                        await pilot.press(key)
                    await pilot.press("enter")

                    entries = app.playlists.list_playlists()
                    self.assertEqual(len(entries), 1)
                    self.assertEqual(entries[0]["name"], "Rock")
                    self.assertEqual(app.query_one("#results").row_count, 1)

        asyncio.run(run())

    def test_app_toggles_and_shows_favorites(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")

                async with app.run_test(size=(140, 42)) as pilot:
                    app.tracks = [
                        Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                    ]
                    await pilot.press("f")
                    self.assertEqual(len(app.playlists.list_favorites()), 1)

                    app._show_favorites()
                    self.assertEqual(app.current_view, "favorites")
                    self.assertEqual(app.query_one("#results").row_count, 1)

                    await pilot.press("f")
                    self.assertEqual(app.playlists.list_favorites(), [])

        asyncio.run(run())

    def test_app_removes_and_moves_song_inside_playlist(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")
                playlist = app.playlists.create_playlist("Orden")
                playlist_id = int(playlist["id"])
                app.playlists.add_track(
                    playlist_id,
                    {
                        "title": "Primera",
                        "artist": "Artista",
                        "duration": "1:00",
                        "album": "YouTube",
                        "url": "https://example.test/first",
                    },
                )
                app.playlists.add_track(
                    playlist_id,
                    {
                        "title": "Segunda",
                        "artist": "Artista",
                        "duration": "2:00",
                        "album": "YouTube",
                        "url": "https://example.test/second",
                    },
                )

                async with app.run_test(size=(140, 42)):
                    app._show_playlist_tracks(playlist_id, selected_index=1)
                    app.action_move_playlist_track_up()
                    self.assertEqual(
                        [track["title"] for track in app.playlists.list_tracks(playlist_id)],
                        ["Segunda", "Primera"],
                    )

                    app.action_remove_from_playlist()
                    self.assertEqual(
                        [track["title"] for track in app.playlists.list_tracks(playlist_id)],
                        ["Primera"],
                    )

        asyncio.run(run())

    def test_app_adds_song_to_single_playlist(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")
                playlist = app.playlists.create_playlist("Favoritas")

                async with app.run_test(size=(140, 42)) as pilot:
                    app.tracks = [
                        Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                    ]
                    await pilot.press("l")

                    tracks = app.playlists.list_tracks(int(playlist["id"]))
                    self.assertEqual(len(tracks), 1)
                    self.assertEqual(tracks[0]["title"], "Uno")
                    self.assertEqual(app.current_view, "playlist_tracks")

        asyncio.run(run())

    def test_app_chooses_playlist_when_multiple_exist(self) -> None:
        async def run() -> None:
            with tempfile.TemporaryDirectory() as directory:
                app = NinjaMusicApp(enable_cava=False)
                app.player = FakePlayer()
                app.playlists = PlaylistStore(path=Path(directory) / "history.db")
                app.playlists.create_playlist("Primera")
                app.playlists.create_playlist("Segunda")

                async with app.run_test(size=(140, 42)):
                    app.tracks = [
                        Track("Uno", "Artista", "0:01", "YouTube", "https://example.test/uno"),
                    ]
                    app.action_add_to_playlist()
                    self.assertEqual(app.current_view, "choose_playlist")
                    app._add_pending_track_to_playlist(int(app.playlists.list_playlists()[0]["id"]))

                    total_tracks = sum(
                        len(app.playlists.list_tracks(int(playlist["id"])))
                        for playlist in app.playlists.list_playlists()
                    )
                    self.assertEqual(total_tracks, 1)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
