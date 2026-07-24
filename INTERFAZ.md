# Diseño de la interfaz

## Referencia

La interfaz de Ninja Music tomará como referencia principal a `btop`:

- aplicación de pantalla completa dentro de la terminal;
- paneles delimitados y redimensionables;
- navegación completa mediante teclado;
- colores adaptados al tema de Kitty;
- actualización en tiempo real sin limpiar ni desplazar la terminal;
- barra inferior permanente con los atajos disponibles;
- diseño adaptable cuando cambia el tamaño de la ventana.

No se copiará el código de `btop`. Se reproducirá su filosofía visual mediante
una TUI propia.

## Distribución principal

```text
┌───────────────┬──────────────────────────────┬──────────────────────┐
│ NAVEGACIÓN    │ BÚSQUEDA Y RESULTADOS        │ COLA                 │
│               │                              ├──────────────────────┤
│ Buscar        │ Canción                      │ INFORMACIÓN          │
│ Reproduciendo │ Artista              Duración│ DE LA CANCIÓN        │
│ Cola          │                              │                      │
│ Favoritos     │                              │ Portada y metadatos  │
│ Historial     │                              │ Visualizador         │
│ Mis listas    │                              │                      │
├───────────────┴──────────────────────────────┴──────────────────────┤
│ CANCIÓN ACTUAL · PROGRESO · CONTROLES · VOLUMEN · VISUALIZADOR     │
├────────────────────────────────────────────────────────────────────┤
│ / buscar · Enter reproducir · Espacio pausa · n siguiente · q salir│
└────────────────────────────────────────────────────────────────────┘
```

## Paneles

### Navegación

- Buscar
- Reproduciendo
- Cola
- Favoritos
- Historial
- Mis listas

### Búsqueda y resultados

- campo de búsqueda;
- título, artista y duración;
- selección resaltada;
- indicador de la canción que está sonando;
- soporte futuro para miniaturas en Kitty.

### Cola de reproducción

- orden de las canciones;
- duración individual y total;
- mover o eliminar elementos;
- selección de la siguiente canción.

### Información

- portada;
- canción, artista y álbum;
- duración y formato;
- favorito;
- visualizador de audio.

### Reproductor inferior

- canción actual;
- barra de progreso;
- reproducir o pausar;
- anterior y siguiente;
- reproducción aleatoria y repetición;
- volumen y silencio.

## Atajos iniciales

| Tecla | Acción |
|---|---|
| `/` | Enfocar la búsqueda |
| `↑` / `↓` o `j` / `k` | Navegar |
| `Enter` | Reproducir la selección |
| `a` | Añadir a la cola |
| `Espacio` | Pausar o continuar |
| `n` | Siguiente canción |
| `b` | Canción anterior |
| `f` | Marcar como favorita |
| `d` | Eliminar de la cola |
| `m` | Silenciar |
| `r` | Cambiar repetición |
| `s` | Cambiar modo aleatorio |
| `q` | Salir |

## Colores

La paleta inicial seguirá el tema Noctalia:

- fondo negro y transparente proporcionado por Kitty;
- cian para reproducción y progreso;
- azul cian `#00AEEF` para selección, títulos y acciones;
- blanco para información principal;
- gris azulado para información secundaria;
- bordes finos similares a `btop`.

## Tecnología propuesta

La primera versión se construirá con Python y Textual:

- Textual administra paneles, foco, teclado y actualización reactiva;
- `mpv` se controla mediante su socket IPC;
- `yt-dlp` obtiene los enlaces y metadatos;
- los datos locales se guardarán inicialmente en SQLite.

La interfaz deberá seguir funcionando sin imágenes cuando la terminal no
soporte el protocolo gráfico de Kitty.
