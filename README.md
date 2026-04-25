# WCM — Wayfire Config Manager (Python/GTK4)

A Python rewrite of [WCM](https://github.com/WayfireWM/wcm) (Wayfire Config Manager),
faithfully reproducing the same layout and functionality using GTK4.

## Design Goals

Per the upstream developer's requirements:

1. **Configure everything** without manually editing the config file by hand.
2. **Single-line config changes** — only the relevant line is modified on each
   option change. Comments, blank lines, and file structure are fully preserved.
3. **Compound option support** — first-class handling of dynamic-list/compound
   options like `autostart` and `command` bindings.

## Architecture

```
wcm.py              — GTK4 frontend (main window, pages, all option widgets)
config_backend.py   — Line-preserving INI reader/writer (the backend)
metadata.py         — XML metadata parser for plugin/option discovery
```

The backend and frontend are cleanly separated — the backend code is
toolkit-agnostic and could be used with a different frontend (PyGTK3, Qt, etc).

## Supported Option Types

| Type         | Widget                          |
|--------------|---------------------------------|
| `int`        | SpinButton or ComboBox (if labeled) |
| `double`     | SpinButton                      |
| `bool`       | CheckButton                     |
| `string`     | Entry or ComboBox (if labeled)  |
| `key`        | Entry + grab button             |
| `button`     | Entry + grab button             |
| `activator`  | Entry + grab button             |
| `gesture`    | Entry                           |
| `color`      | ColorButton (with alpha)        |
| `animation`  | SpinButton (ms) + ComboBox (easing) |
| `dynamic-list` | Compound option list editor   |

## Requirements

- Python 3.8+
- GTK4 (`gir1.2-gtk-4.0` / `gtk4`)
- PyGObject (`python3-gi`)
- lxml

### Debian/Ubuntu
```bash
sudo apt install python3-gi gir1.2-gtk-4.0 python3-lxml
```

### Arch
```bash
sudo pacman -S python-gobject gtk4 python-lxml
```

### Fedora
```bash
sudo dnf install python3-gobject gtk4 python3-lxml
```

## Usage

```bash
python3 wcm.py

# With a specific config file
python3 wcm.py -c ~/.config/wayfire/wayfire.ini

# Open a specific plugin at launch
python3 wcm.py -p move
```

## Icon Resolution

Icons are found the same way as the C++ WCM:

1. `$XDG_DATA_HOME/wayfire/icons/`
2. `WAYFIRE_ICONDIR` (from `pkg-config --variable=icondir wayfire`)
3. `WCM_ICONDIR` (derived from installed `wcm`/`wayfire` binary prefix)

Works with any install prefix (`/usr`, `/usr/local`, `/opt/wayfire`, etc).

## License

MIT — same as the original WCM.
