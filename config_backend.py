"""
Wayfire Config File Backend

Reads and writes wayfire.ini preserving comments and blank lines.
Only modifies the specific line for a changed option, never rewrites
the entire file. This is the key improvement over wf-config's approach.
"""

import os
import re
from collections import OrderedDict


class ConfigEntry:
    """Represents a single line in the config file."""
    __slots__ = ('kind', 'text', 'section', 'key', 'value')

    # kind: 'comment', 'blank', 'section', 'option'
    def __init__(self, kind, text, section=None, key=None, value=None):
        self.kind = kind
        self.text = text
        self.section = section
        self.key = key
        self.value = value

    def to_line(self):
        if self.kind == 'option':
            return f"{self.key} = {self.value}\n"
        return self.text


class WayfireConfigFile:
    """
    Line-preserving INI config reader/writer for wayfire.

    Design goals (from developer notes):
    1) Only change the relevant line for an option change (usually one line).
    2) Preserve all comments, blank lines, and formatting.
    3) Support reading/writing compound options.
    """

    SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*$')
    OPTION_RE = re.compile(r'^(\s*)([a-zA-Z0-9_][a-zA-Z0-9_\-]*)\s*=\s*(.*?)\s*$')
    COMMENT_RE = re.compile(r'^\s*[#;]')

    def __init__(self, path=None):
        self.path = path
        self.entries = []           # List[ConfigEntry] preserving file order
        self._section_map = {}      # section_name -> {key -> entry_index}
        if path and os.path.isfile(path):
            self._load(path)

    def _load(self, path):
        self.entries.clear()
        self._section_map.clear()
        current_section = None

        with open(path, 'r') as f:
            for line in f:
                # blank line
                if line.strip() == '':
                    self.entries.append(ConfigEntry('blank', line))
                    continue

                # comment
                if self.COMMENT_RE.match(line):
                    self.entries.append(ConfigEntry('comment', line))
                    continue

                # section header
                m = self.SECTION_RE.match(line.strip())
                if m:
                    current_section = m.group(1)
                    if current_section not in self._section_map:
                        self._section_map[current_section] = {}
                    self.entries.append(
                        ConfigEntry('section', line, section=current_section))
                    continue

                # option
                m = self.OPTION_RE.match(line)
                if m and current_section is not None:
                    key = m.group(2)
                    value = m.group(3)
                    idx = len(self.entries)
                    entry = ConfigEntry('option', line,
                                        section=current_section,
                                        key=key, value=value)
                    self.entries.append(entry)
                    if current_section not in self._section_map:
                        self._section_map[current_section] = {}
                    self._section_map[current_section][key] = idx
                    continue

                # unrecognized — keep as-is
                self.entries.append(ConfigEntry('comment', line))

    def get_sections(self):
        """Return list of section names in file order."""
        seen = []
        for e in self.entries:
            if e.kind == 'section' and e.section not in seen:
                seen.append(e.section)
        return seen

    def get_option(self, section, key, default=None):
        """Get an option value. Returns default if not found."""
        sec = self._section_map.get(section, {})
        idx = sec.get(key)
        if idx is not None:
            return self.entries[idx].value
        return default

    def get_section_options(self, section):
        """Return dict of all key=value pairs in a section."""
        result = OrderedDict()
        sec = self._section_map.get(section, {})
        for key, idx in sec.items():
            result[key] = self.entries[idx].value
        return result

    def set_option(self, section, key, value):
        """
        Set a single option value. Only modifies the relevant line.
        Creates the section and/or option if they don't exist.
        """
        value = str(value)

        sec = self._section_map.get(section)
        if sec is not None and key in sec:
            # Modify existing entry in-place — single line change
            idx = sec[key]
            self.entries[idx].value = value
            return

        # Section exists but key doesn't — append option after last entry in section
        if sec is not None:
            insert_idx = self._find_section_end(section)
            entry = ConfigEntry('option', f"{key} = {value}\n",
                                section=section, key=key, value=value)
            self.entries.insert(insert_idx, entry)
            self._rebuild_index()
            return

        # Section doesn't exist — create it at end of file
        if self.entries and self.entries[-1].kind != 'blank':
            self.entries.append(ConfigEntry('blank', '\n'))
        self.entries.append(
            ConfigEntry('section', f"[{section}]\n", section=section))
        entry = ConfigEntry('option', f"{key} = {value}\n",
                            section=section, key=key, value=value)
        self.entries.append(entry)
        self._rebuild_index()

    def remove_option(self, section, key):
        """Remove a single option line from the file."""
        sec = self._section_map.get(section, {})
        idx = sec.get(key)
        if idx is not None:
            del self.entries[idx]
            self._rebuild_index()

    def _find_section_end(self, section):
        """Find the index where new options should be inserted for a section."""
        in_section = False
        last_idx = len(self.entries)
        for i, e in enumerate(self.entries):
            if e.kind == 'section' and e.section == section:
                in_section = True
                last_idx = i + 1
                continue
            if in_section:
                if e.kind == 'section':
                    return i  # next section starts
                last_idx = i + 1
        return last_idx

    def _rebuild_index(self):
        """Rebuild the section->key->index map after insertions/deletions."""
        self._section_map.clear()
        for i, e in enumerate(self.entries):
            if e.kind == 'option' and e.section:
                if e.section not in self._section_map:
                    self._section_map[e.section] = {}
                self._section_map[e.section][e.key] = i

    def save(self, path=None):
        """Write the config back to disk, preserving all formatting."""
        path = path or self.path
        if not path:
            raise ValueError("No path specified for saving")

        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f:
            for entry in self.entries:
                f.write(entry.to_line())

    def get_enabled_plugins(self):
        """Get the list of enabled plugins from [core] plugins."""
        plugins_str = self.get_option('core', 'plugins', '')
        return [p.strip() for p in plugins_str.split() if p.strip()]

    def set_enabled_plugins(self, plugin_list):
        """Set the enabled plugins list in [core] plugins."""
        self.set_option('core', 'plugins', ' '.join(plugin_list))

    def enable_plugin(self, name):
        """Add a plugin to the enabled list if not already present."""
        plugins = self.get_enabled_plugins()
        if name not in plugins:
            plugins.append(name)
            self.set_enabled_plugins(plugins)

    def disable_plugin(self, name):
        """Remove a plugin from the enabled list."""
        plugins = self.get_enabled_plugins()
        plugins = [p for p in plugins if p != name]
        self.set_enabled_plugins(plugins)

    def get_all_options(self):
        """Return dict of {section: {key: value}} for all options."""
        result = OrderedDict()
        for section in self.get_sections():
            opts = self.get_section_options(section)
            if opts:
                result[section] = dict(opts)
        return result


class PresetManager:
    """
    Manages named presets stored as .ini files.

    Presets are stored in a dedicated directory (default:
    ~/.config/wayfire/presets/). Each preset is a standard INI file
    written through WayfireConfigFile — so comments/formatting of
    the *preset file itself* are preserved too.

    When a preset is *loaded*, changes are applied one option at a
    time through the live config's set_option(), so only the relevant
    lines are modified in wayfire.ini. This honours the single-line-
    change contract.
    """

    def __init__(self, preset_dir=None):
        if preset_dir is None:
            config_home = os.environ.get('XDG_CONFIG_HOME', '') or \
                          os.path.join(os.path.expanduser('~'), '.config')
            preset_dir = os.path.join(config_home, 'wayfire', 'presets')
        self.preset_dir = preset_dir
        os.makedirs(self.preset_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Naming helpers
    # ------------------------------------------------------------------

    def _master_path(self, name):
        return os.path.join(self.preset_dir, f"{name}.ini")

    def _plugin_dir(self, plugin_name):
        d = os.path.join(self.preset_dir, 'plugins', plugin_name)
        os.makedirs(d, exist_ok=True)
        return d

    def _plugin_path(self, plugin_name, preset_name):
        return os.path.join(self._plugin_dir(plugin_name),
                            f"{preset_name}.ini")

    @staticmethod
    def _sanitize(name):
        """Sanitize a preset name to a safe filename component."""
        return re.sub(r'[^\w\-. ]', '_', name).strip()

    # ------------------------------------------------------------------
    # Master presets — full config snapshot
    # ------------------------------------------------------------------

    def list_master_presets(self):
        """Return sorted list of master preset names."""
        names = []
        if os.path.isdir(self.preset_dir):
            for f in sorted(os.listdir(self.preset_dir)):
                if f.endswith('.ini'):
                    names.append(f[:-4])
        return names

    def save_master_preset(self, name, config):
        """
        Save the entire current config as a master preset.

        Args:
            name:   preset name (used as filename stem)
            config: the live WayfireConfigFile instance
        """
        name = self._sanitize(name)
        if not name:
            raise ValueError("Preset name cannot be empty")
        preset = WayfireConfigFile()
        for section, opts in config.get_all_options().items():
            for key, value in opts.items():
                preset.set_option(section, key, value)
        preset.save(self._master_path(name))

    def load_master_preset(self, name, config):
        """
        Apply a master preset to the live config.

        Only calls config.set_option() for each stored value, so the
        single-line-change guarantee is preserved.
        """
        path = self._master_path(name)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Master preset '{name}' not found")
        preset = WayfireConfigFile(path)
        for section in preset.get_sections():
            for key, value in preset.get_section_options(section).items():
                config.set_option(section, key, value)
        config.save()

    def delete_master_preset(self, name):
        path = self._master_path(name)
        if os.path.isfile(path):
            os.unlink(path)

    # ------------------------------------------------------------------
    # Plugin presets — single-section snapshot
    # ------------------------------------------------------------------

    def list_plugin_presets(self, plugin_name):
        """Return sorted list of preset names for a given plugin."""
        d = os.path.join(self.preset_dir, 'plugins', plugin_name)
        if not os.path.isdir(d):
            return []
        return sorted(f[:-4] for f in os.listdir(d) if f.endswith('.ini'))

    def save_plugin_preset(self, name, plugin_name, config):
        """
        Save the current options for *one* plugin section as a preset.
        """
        name = self._sanitize(name)
        if not name:
            raise ValueError("Preset name cannot be empty")
        preset = WayfireConfigFile()
        opts = config.get_section_options(plugin_name)
        for key, value in opts.items():
            preset.set_option(plugin_name, key, value)

        # Also store whether the plugin was enabled (in [core] plugins)
        enabled = config.get_enabled_plugins()
        preset.set_option('_preset_meta', 'enabled',
                          'true' if plugin_name in enabled else 'false')

        preset.save(self._plugin_path(plugin_name, name))

    def load_plugin_preset(self, name, plugin_name, config):
        """
        Apply a plugin preset — only touches that plugin's section.
        """
        path = self._plugin_path(plugin_name, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Plugin preset '{name}' for '{plugin_name}' not found")
        preset = WayfireConfigFile(path)
        opts = preset.get_section_options(plugin_name)
        for key, value in opts.items():
            config.set_option(plugin_name, key, value)

        # Restore enabled state if recorded
        was_enabled = preset.get_option('_preset_meta', 'enabled')
        if was_enabled is not None:
            if was_enabled == 'true':
                config.enable_plugin(plugin_name)
            else:
                config.disable_plugin(plugin_name)

        config.save()

    def delete_plugin_preset(self, name, plugin_name):
        path = self._plugin_path(plugin_name, name)
        if os.path.isfile(path):
            os.unlink(path)