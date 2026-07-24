from __future__ import annotations

from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual import work
from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Input, Label, ListItem, ListView, Static

from ninja_music.services import CavaAnalyzer, MpvPlayer, PlaybackHistory, SearchResult, YouTubeSearch


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    duration: str
    album: str
    url: str = ""


DEMO_TRACKS = (
    Track("Do I Wanna Know?", "Arctic Monkeys", "4:32", "AM"),
    Track("Blinding Lights", "The Weeknd", "3:20", "After Hours"),
    Track("Instant Crush", "Daft Punk", "5:37", "Random Access Memories"),
    Track("Feel Good Inc.", "Gorillaz", "3:42", "Demon Days"),
    Track("The Less I Know The Better", "Tame Impala", "3:36", "Currents"),
    Track("Nightcall", "Kavinsky", "4:18", "OutRun"),
    Track("Comfortably Numb", "Pink Floyd", "6:23", "The Wall"),
)


class Panel(Vertical):
    """Contenedor con borde y título al estilo btop."""


class NinjaMusicApp(App[None]):
    TITLE = "Ninja Music"
    SUB_TITLE = "TUI prototype"

    CSS = """
    Screen {
        background: #000000;
        color: #e2e2e9;
    }

    #main {
        height: 1fr;
    }

    Panel {
        border: round #636b92;
        background: #000000 70%;
        padding: 0 1;
    }

    .panel-title {
        color: #00aeef;
        text-style: bold;
        height: 1;
    }

    #navigation {
        width: 22%;
        min-width: 24;
    }

    #center {
        width: 48%;
        min-width: 48;
    }

    #right {
        width: 30%;
        min-width: 32;
    }

    #brand {
        height: 4;
        content-align: center middle;
        color: #58c7e8;
        text-style: bold;
    }

    ListView {
        height: 1fr;
        background: transparent;
    }

    ListItem {
        height: 2;
        padding: 0 1;
    }

    ListItem.--highlight {
        background: #003a4a;
        color: #ffffff;
    }

    Input {
        border: round #636b92;
        background: #05060d;
        margin-bottom: 1;
    }

    Input:focus {
        border: round #58c7e8;
    }

    DataTable {
        height: 1fr;
        background: transparent;
        scrollbar-color: #00aeef;
        scrollbar-background: #11131b;
    }

    DataTable > .datatable--header {
        color: #58c7e8;
        background: #090b12;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        color: #ffffff;
        background: #003a4a;
    }

    #queue-table {
        height: 55%;
    }

    #track-info {
        height: 45%;
    }

    #track-card {
        padding: 1;
        color: #bfc6dc;
    }

    #visualizer {
        height: 7;
        color: #58c7e8;
        content-align: center middle;
        text-align: center;
    }

    #player {
        height: 7;
        border: round #636b92;
        padding: 0 2;
        background: #000000 80%;
    }

    #now-playing {
        width: 32%;
        content-align: left middle;
    }

    #transport {
        width: 38%;
        content-align: center middle;
        color: #00aeef;
    }

    #volume {
        width: 30%;
        content-align: right middle;
        color: #58c7e8;
    }

    Footer {
        background: #05060d;
        color: #bfc6dc;
    }
    """

    BINDINGS = [
        Binding("/", "focus_search", "buscar", show=True),
        Binding("space", "toggle_play", "pausa", show=True),
        Binding("n", "next_track", "siguiente", show=True),
        Binding("b", "previous_track", "anterior", show=True),
        Binding("a", "add_queue", "añadir", show=True),
        Binding("m", "toggle_mute", "mute", show=True),
        Binding("q", "quit", "salir", show=True),
    ]

    def __init__(self, enable_cava: bool = True) -> None:
        super().__init__()
        self.current_index = 0
        self.playing = False
        self.muted = False
        self.tracks = list(DEMO_TRACKS)
        self.search_service = YouTubeSearch()
        self.player = MpvPlayer()
        self.history = PlaybackHistory()
        self.cava = CavaAnalyzer()
        self.enable_cava = enable_cava
        self.position_seconds = 0.0
        self.duration_seconds = 0.0

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with Panel(id="navigation"):
                yield Static("N I N J A\nM U S I C", id="brand")
                yield Label("NAVEGACIÓN", classes="panel-title")
                yield ListView(
                    ListItem(Label("⌕  Buscar")),
                    ListItem(Label("▷  Reproduciendo")),
                    ListItem(Label("☷  Cola")),
                    ListItem(Label("♡  Favoritos")),
                    ListItem(Label("◴  Historial")),
                    ListItem(Label("♫  Mis listas")),
                    id="nav-list",
                )
            with Panel(id="center"):
                yield Input(placeholder="Buscar canciones, artistas o álbumes…", id="search")
                yield Label("RESULTADOS", classes="panel-title")
                yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
            with Vertical(id="right"):
                with Panel(id="queue-table"):
                    yield Label("COLA DE REPRODUCCIÓN", classes="panel-title")
                    yield DataTable(id="queue", cursor_type="row")
                with Panel(id="track-info"):
                    yield Label("INFORMACIÓN DE LA CANCIÓN", classes="panel-title")
                    yield Static(id="track-card")
                    yield Static("Esperando audio…", id="visualizer")
        with Horizontal(id="player"):
            yield Static(id="now-playing")
            yield Static(id="transport")
            yield Static(id="volume")
        yield Footer()

    def on_mount(self) -> None:
        results = self.query_one("#results", DataTable)
        results.add_columns("#", "CANCIÓN", "ARTISTA", "DURACIÓN")
        for index, track in enumerate(self.tracks, start=1):
            results.add_row(str(index), track.title, track.artist, track.duration, key=str(index - 1))

        queue = self.query_one("#queue", DataTable)
        queue.add_columns("#", "CANCIÓN", "DURACIÓN")
        for index, track in enumerate(DEMO_TRACKS[:3], start=1):
            queue.add_row(str(index), track.title, track.duration)

        self.query_one("#nav-list", ListView).index = 0
        results.focus()
        self._refresh_player()
        self.set_interval(0.5, self.poll_playback)
        if self.enable_cava:
            self.stream_cava()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "results":
            return
        self.current_index = int(str(event.row_key.value))
        self.playing = True
        self._refresh_player()
        self._play_current()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if "Historial" in self._list_item_text(event.item):
            self._show_history()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if query:
            self.query_one("#results", DataTable).clear()
            self.query_one("#results", DataTable).loading = True
            self.search_youtube(query)

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_toggle_play(self) -> None:
        if self.player.active:
            new_state = self.player.toggle_pause()
            if new_state is not None:
                self.playing = new_state
        else:
            self.playing = self._play_current()
        self._refresh_player()

    def action_next_track(self) -> None:
        self.current_index = (self.current_index + 1) % len(self.tracks)
        self.playing = True
        self._refresh_player()
        self._play_current()

    def action_previous_track(self) -> None:
        self.current_index = (self.current_index - 1) % len(self.tracks)
        self.playing = True
        self._refresh_player()
        self._play_current()

    def action_add_queue(self) -> None:
        track = self.tracks[self.current_index]
        queue = self.query_one("#queue", DataTable)
        queue.add_row(str(queue.row_count + 1), track.title, track.duration)
        self.notify(f"Añadida a la cola: {track.title}")

    def action_toggle_mute(self) -> None:
        self.muted = not self.muted
        self.player.set_mute(self.muted)
        self._refresh_player()

    def _refresh_player(self) -> None:
        track = self.tracks[self.current_index]
        state = "REPRODUCIENDO" if self.playing else "PAUSADO"
        icon = "Ⅱ" if self.playing else "▶"
        volume = "SILENCIO" if self.muted else "70%"
        duration = self.duration_seconds or self._parse_duration(track.duration)
        position = min(self.position_seconds, duration) if duration else self.position_seconds
        ratio = position / duration if duration > 0 else 0
        filled = min(20, max(0, round(ratio * 20)))
        progress = f"[#00aeef]{'━' * filled}[/#00aeef][#636b92]{'─' * (20 - filled)}[/#636b92]"

        self.query_one("#now-playing", Static).update(
            f"[bold]{track.title}[/bold]\n[dim]{track.artist}[/dim]\n"
            f"{self._format_time(position)} {progress} {self._format_time(duration)}"
        )
        self.query_one("#transport", Static).update(
            f"[#58c7e8][ {state} ][/#58c7e8]\n\n|◀   {icon}   ▶|"
        )
        self.query_one("#volume", Static).update(f"Volumen  🔊  ━━━━━━  {volume}")
        self.query_one("#track-card", Static).update(
            f"[bold #00aeef]{track.title}[/bold #00aeef]\n"
            f"{track.artist}\n\n"
            f"[dim]Álbum:[/dim] {track.album}\n"
            f"[dim]Duración:[/dim] {track.duration}\n"
            "[dim]Fuente:[/dim] YouTube"
        )

    @work(exclusive=True, thread=True)
    def search_youtube(self, query: str) -> None:
        try:
            results = self.search_service.search(query)
        except Exception as error:
            self.call_from_thread(self._show_search_error, str(error))
            return
        self.call_from_thread(self._show_search_results, results)

    def _show_search_results(self, results: list[SearchResult]) -> None:
        table = self.query_one("#results", DataTable)
        table.loading = False
        table.clear()
        if not results:
            self.notify("No se encontraron canciones.", severity="warning")
            return

        self.tracks = [
            Track(result.title, result.artist, result.duration, "YouTube", result.url)
            for result in results
        ]
        self.current_index = 0
        for index, track in enumerate(self.tracks, start=1):
            table.add_row(str(index), track.title, track.artist, track.duration, key=str(index - 1))
        table.move_cursor(row=0)
        table.focus()
        self._refresh_player()
        self.notify(f"{len(results)} canciones encontradas")

    def _show_search_error(self, message: str) -> None:
        table = self.query_one("#results", DataTable)
        table.loading = False
        self.notify(f"Error de YouTube: {message}", severity="error", timeout=8)
        self.query_one("#search", Input).focus()

    def _play_current(self) -> bool:
        track = self.tracks[self.current_index]
        if not track.url:
            self.notify("Busca una canción real antes de reproducir.", severity="warning")
            self.playing = False
            return False
        self.position_seconds = 0.0
        self.duration_seconds = self._parse_duration(track.duration)
        self.player.play(track.url)
        self.playing = True
        self.history.add(
            {
                "title": track.title,
                "artist": track.artist,
                "duration": track.duration,
                "album": track.album,
                "url": track.url,
            }
        )
        return True

    def _show_history(self) -> None:
        entries = self.history.load()
        table = self.query_one("#results", DataTable)
        table.clear()
        if not entries:
            self.notify("Todavía no hay canciones reproducidas.", severity="warning")
            table.focus()
            return

        self.tracks = [
            Track(
                str(entry.get("title") or "Sin título"),
                str(entry.get("artist") or "Desconocido"),
                str(entry.get("duration") or "0:00"),
                str(entry.get("album") or "Historial"),
                str(entry.get("url") or ""),
            )
            for entry in entries
        ]
        self.current_index = 0
        for index, track in enumerate(self.tracks, start=1):
            table.add_row(str(index), track.title, track.artist, track.duration, key=str(index - 1))
        table.move_cursor(row=0)
        table.focus()
        self._refresh_player()
        self.notify(f"{len(entries)} canciones en historial")

    @staticmethod
    def _list_item_text(item: ListItem) -> str:
        try:
            return str(item.query_one(Label).render())
        except NoMatches:
            return ""

    @work(thread=True, group="playback-status", exclusive=True)
    def poll_playback(self) -> None:
        if not self.player.active:
            if self.playing:
                self.call_from_thread(self._advance_after_track_finished)
            return
        position = self.player.get_property("time-pos")
        duration = self.player.get_property("duration")
        paused = self.player.get_property("pause")
        if position is None:
            return
        self.call_from_thread(
            self._update_playback_status,
            float(position),
            float(duration or self.duration_seconds),
            bool(paused),
        )

    def _update_playback_status(self, position: float, duration: float, paused: bool) -> None:
        self.position_seconds = position
        if duration > 0:
            self.duration_seconds = duration
        self.playing = not paused
        self._refresh_player()

    def _advance_after_track_finished(self) -> None:
        if not self.playing:
            return

        next_index = self.current_index + 1
        if next_index >= len(self.tracks):
            self.playing = False
            self.position_seconds = self.duration_seconds
            self._refresh_player()
            self.notify("Fin de la lista")
            return

        self.current_index = next_index
        self.position_seconds = 0.0
        self.playing = self._play_current()
        self._refresh_player()

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, int(seconds))
        minutes, remainder = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{remainder:02d}" if hours else f"{minutes}:{remainder:02d}"

    @staticmethod
    def _parse_duration(duration: str) -> float:
        try:
            parts = [int(part) for part in duration.split(":")]
        except ValueError:
            return 0.0
        if len(parts) == 2:
            return float(parts[0] * 60 + parts[1])
        if len(parts) == 3:
            return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
        return 0.0

    @work(thread=True, group="cava", exclusive=True)
    def stream_cava(self) -> None:
        process = self.cava.start()
        if process.stdout is None:
            return
        for line in process.stdout:
            try:
                values = [int(value) for value in line.strip().split(";") if value]
            except ValueError:
                continue
            if values:
                self.call_from_thread(self._update_visualizer, values)

    def _update_visualizer(self, values: list[int]) -> None:
        height = 5
        rows = []
        for level in range(height, 0, -1):
            rows.append(" ".join("█" if value * height >= level * 8 else " " for value in values))
        self.query_one("#visualizer", Static).update("\n".join(rows))

    def on_unmount(self) -> None:
        self.cava.stop()
        self.player.stop()


def main() -> None:
    NinjaMusicApp().run()


if __name__ == "__main__":
    main()
