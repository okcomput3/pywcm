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
i18n.py             — gettext setup + pure-Python .po→.mo compiler
locale/             — translations (wcm.pot + per-language .po files)
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

## Display / Output Configuration

A built-in **DISPLAY** page (in the sidebar) configures monitors without
editing the config by hand. For each output you can set the resolution,
refresh rate, scale, position and rotation, or turn the output on/off.
Changes are written to the `[output:<name>]` sections of `wayfire.ini`
(`mode`, `position`, `scale`, `transform`; disabling an output writes
`mode = off`).

Connected monitors and their available modes are detected with
[`wlr-randr`](https://github.com/emersion/wlr-randr) when it's installed
and a Wayfire session is running. If detection isn't available, outputs
already present in the config are still shown, and new ones can be added
by name and configured manually.

Each output has a remove button that deletes its `[output:<name>]`
section (after confirmation). Removing a still-connected monitor just
clears its saved settings — it reappears as an unconfigured output.

The display **WCM is currently running on** is protected: it can't be
switched off or removed, since that would blank the screen you're looking
at and force you back to editing the `.ini` by hand. It stays fully
editable otherwise (resolution, refresh, scale, position, rotation), and
every other output can be edited, disabled, removed, or added freely. To
manage the protected one, move the WCM window to a different display and
hit "Detect Outputs" — protection follows the window. (If the window's
display can't be determined, the first output that's on is protected as a
fallback.)

To avoid breaking the session, a chosen resolution or refresh rate is
**validated before it is written**: malformed values, or resolutions a
monitor doesn't report, are flagged and never saved, so Wayfire is never
handed a mode that could blank an output.

Unlike `wdisplays` (which adjusts outputs at runtime via the
output-management protocol but never persists them), the DISPLAY page
saves directly to the config, so the settings survive a restart.

## Translations / Multi-language

WCM is translated with **gettext**, using the same scheme as the C++ WCM:

- **UI strings** use the `wcm` domain. Shipped languages: **Spanish
  (es_ES)**, **Romanian (ro)** and **Simplified Chinese (zh_CN)** — the
  same set as upstream. Strings shared with the C++ WCM were ported
  verbatim from its catalogs; strings new to this edition are
  machine-assisted translations (review welcome).
- **Plugin metadata** (plugin names, option names, descriptions from the
  XML files) is translated through the per-plugin `wf-plugin-<name>`
  domains that Wayfire itself installs — identical to the C++ WCM's
  `dgettext("wf-plugin-" + name, …)`. So if your distro ships translated
  Wayfire plugin catalogs, plugin pages localize automatically.

The language follows your session locale (`LANGUAGE`, `LC_ALL`,
`LC_MESSAGES`, `LANG`). To try a specific language just for WCM:

```bash
WCM_LANG=es_ES python3 wcm.py
WCM_LANG=zh_CN python3 wcm.py
```

No build step is needed when running from a checkout: `.po` files under
`locale/` are compiled to `.mo` on the fly (into `~/.cache/wcm/locale`)
by a small pure-Python compiler, so the gettext command-line tools are
not required at runtime. Installed copies use the standard
`<prefix>/share/locale/<lang>/LC_MESSAGES/wcm.mo`; `setup.py` compiles
and installs these for you. `WCM_LOCALEDIR` overrides the search path.

### Adding a language

```bash
mkdir -p locale/de/LC_MESSAGES
cp locale/wcm.pot locale/de/LC_MESSAGES/wcm.po
# translate the msgstr entries, then just run wcm.py
```

After changing translatable strings in the source, run
`./update-translations.sh` (needs `gettext` installed) to refresh
`locale/wcm.pot` and merge it into every `.po`.

## Requirements

- Python 3.8+
- GTK4 (`gir1.2-gtk-4.0` / `gtk4`)
- PyGObject (`python3-gi`)
- lxml
- `wlr-randr` (optional) — enables monitor auto-detection on the DISPLAY page

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

# Print version
python3 wcm.py --version

# Force a UI language for this run
WCM_LANG=ro python3 wcm.py
```

## Icon Resolution

Icons are found the same way as the C++ WCM:

1. `$XDG_DATA_HOME/wayfire/icons/`
2. `WAYFIRE_ICONDIR` (from `pkg-config --variable=icondir wayfire`)
3. `WCM_ICONDIR` (derived from installed `wcm`/`wayfire` binary prefix)

Works with any install prefix (`/usr`, `/usr/local`, `/opt/wayfire`, etc).

## License

MIT — same as the original WCM.

## Regression checks

Run `python3 test_regressions.py` in a session with GTK4 available. The suite
uses temporary configurations, exercises real GTK controls, and includes 2,000
seeded config operations. It does not change your Wayfire or monitor settings.
The existing `test_*.py` files can also be run together with pytest.

The command editor supports Regular, Repeat, Always, and Release bindings,
including existing bindings whose command entry is missing. Config saves retain
untouched formatting and merge local edits into externally updated files;
Plugin enable/disable actions are replayed on the latest list so independent
plugin toggles merge. Explicit replacement of the same option still uses the
local value.
Pending text edits are flushed on normal window close and cancelled when a
plugin preset replaces them. Display refresh waits for pending confirmation;
closing WCM reverts unconfirmed display changes.

The Spanish, Romanian and Simplified Chinese catalogs include upstream WCM
translations and additional Python UI controls. Untranslated messages fall
back to English. Group/subgroup `hidden` attributes are not interpreted by
upstream WCM; only option-level hiding is supported here as well.

Config writes use a temporary file and replace the destination only after the
write succeeds, preserving config symlinks and file permissions. Select
**Automatic** in the display resolution menu to restore the default mode;
clearing the field and pressing Enter or leaving the field does the same.

Master preset save/load stages all destination files before replacing them.
If a later replacement fails, earlier replacements are rolled back. If recovery
itself fails, the error identifies retained recovery copies. This handles
reported I/O failures; it is not a cross-file guarantee against sudden power loss.
Plugin preset loads keep pending edits and the previous in-memory config on
failure. Plugin presets merge stored options; extra commands and settings stay.
Names that normalize to an existing preset are rejected unless the existing
normalized name is entered explicitly. Preset errors are shown in the app.

Config saves recheck the destination after staging and refuse a detected
concurrent change so the operation can be retried. A hard-linked recovery copy
protects the reproduced last-moment in-place write race; when detected, the
error identifies the retained external contents. This is not a universal lock
against arbitrary external editors (particularly concurrent atomic replacement).
Where hard links are unavailable, saves use a copied recovery snapshot and an
additional pre-replacement check; this fallback cannot capture an in-place edit
made after that check. Save errors keep the main window open and pending edits
available for retry. Failed display reverts retain their original baseline and
retry callback; an open confirmation dialog retries on its countdown and can
still be reverted manually, including through the window manager's close action.
Failed text flushes remain pending for retry. Master-preset deletion uses the
same staged backup/rollback mechanism as preset replacement.
