# Ninja Music

Reproductor de música para terminal, diseñado para CachyOS, Hyprland y Kitty.

La interfaz tomará como referencia visual y funcional a `btop`. La
especificación se encuentra en [INTERFAZ.md](INTERFAZ.md).

## Objetivo inicial

Crear una interfaz TUI propia que permita:

- buscar música de YouTube;
- reproducir solamente el audio mediante `mpv`;
- controlar reproducción, pausa y volumen;
- administrar una cola de canciones;
- guardar historial de canciones reproducidas;
- integrarse visualmente con el tema de la terminal.

## Herramientas disponibles

- `yt-dlp`: extracción de audio desde YouTube;
- `mpv`: reproducción y control mediante IPC;
- `ytfzf`: referencia para búsquedas y flujo de selección;
- `fzf`: selección interactiva desde la terminal.

## Ubicación

El proyecto está dentro de:

```text
/home/jhasmany/Proyectos/Linux/L.J.-Ninja-Music
```

## Dependencias

Dependencias del sistema usadas por el reproductor:

```bash
sudo pacman -S --needed python-textual mpv yt-dlp cava kitty
```

Estado verificado el 2026-07-24:

- `mpv`: instalado.
- `yt-dlp`: instalado.
- `cava`: instalado.
- `kitty`: instalado.
- `textual`: instalado para Python, versión `8.2.8`.

Para ejecutar pruebas automatizadas también se necesita:

```bash
sudo pacman -S --needed python-pytest
```

## Ejecutar el prototipo

Desde cualquier terminal:

```bash
cd /home/jhasmany/Proyectos/Linux/L.J.-Ninja-Music
PYTHONPATH=src python -m ninja_music
```

Desde esta carpeta también sirve:

```bash
PYTHONPATH=src python -m ninja_music
```

La aplicación inicia mostrando **Favoritos**. Si todavía no tienes favoritos,
la tabla central aparece vacía. Pulsa `/`, escribe una búsqueda y presiona
`Enter` para consultar YouTube. Selecciona una canción con las flechas y
presiona `Enter` para reproducirla, o `f` para guardarla en Favoritos.

Cuando una canción real termina, Ninja Music avanza automáticamente a la
siguiente canción de la lista actual. Si termina la última canción, la
reproducción se detiene.

La búsqueda utiliza `yt-dlp`; el audio se reproduce mediante `mpv` y su socket
IPC. Las conexiones a YouTube se fuerzan por IPv4 para evitar bloqueos de red.

El panel **Información de la canción** incluye un analizador de espectro real
alimentado por CAVA. El perfil integrado captura la salida de PipeWire y genera
24 barras animadas en color `#00AEEF`.

## Controles básicos

- `/`: buscar música.
- `Enter`: seleccionar o reproducir.
- Flechas: moverse por la lista.
- `n`: pasar manualmente a la siguiente canción.
- `b`: volver a la canción anterior.
- `c`: abrir **Mis listas** para crear una lista.
- `l`: guardar la canción seleccionada en una lista.
- `f`: marcar o quitar la canción seleccionada de **Favoritos**.
- `x`: eliminar una canción cuando estás dentro de una lista.
- `u`: subir una canción dentro de una lista.
- `j`: bajar una canción dentro de una lista.

## Historial

Cada canción real reproducida se guarda automáticamente en:

```text
~/.local/state/ninja-music/history.db
```

El historial usa SQLite mediante el módulo estándar `sqlite3` de Python,
conserva las canciones más recientes y evita duplicar la misma canción si se
vuelve a reproducir. En la interfaz, entra a **Historial** desde la navegación
lateral para cargar las canciones reproducidas en la tabla central y volver a
reproducir una de ellas con `Enter`.

## Favoritos

Para marcar una canción como favorita, busca una canción real, selecciónala en
la tabla y presiona `f`. Si presionas `f` de nuevo sobre la misma canción, se
quita de favoritos.

Para ver tus favoritos, entra a **Favoritos** desde la navegación lateral. Las
canciones favoritas se cargan en la tabla central y se pueden reproducir con
`Enter`.

## Mis listas

Las listas se guardan en la misma base de datos SQLite:

```text
~/.local/state/ninja-music/history.db
```

Para crear una lista, entra a **Mis listas** desde la navegación lateral o
presiona `c`. Arriba de la tabla aparecerá el campo **NUEVA LISTA**; escribe el
nombre ahí y presiona `Enter`.

Para guardar una canción en una lista, busca una canción real, selecciónala en
la tabla y presiona `l`. Si tienes una sola lista, se guardará ahí
automáticamente. Si tienes dos o más listas, la tabla cambiará a **ELIGE LISTA**:
muévete con las flechas y presiona `Enter` sobre la lista donde quieres guardar
la canción.

Para ver una lista, entra a **Mis listas**, selecciona una lista con las flechas
y presiona `Enter`. Las canciones guardadas se cargan en la tabla central y se
pueden reproducir con `Enter`.

Cuando estás viendo las canciones de una lista, selecciona una canción con las
flechas y usa `x` para eliminarla, `u` para subirla o `j` para bajarla.

## Pruebas

Las pruebas se ejecutan desde esta carpeta con:

```bash
PYTHONPATH=src python -m unittest discover -s tests -q
```

También se puede usar `pytest` si está instalado:

```bash
python -m pytest -q
```

## Nombre provisional

```text
ninja-music
```
