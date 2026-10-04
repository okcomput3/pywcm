"""
Wayfire Config File Backend

Reads and writes wayfire.ini preserving comments and blank lines.
Only modifies the specific line for a changed option, never rewrites
the entire file. This is the key improvement over wf-config's approach.
"""

import os
import errno
import sys
import re
import stat
import tempfile
import copy

from i18n import _
import shutil
import subprocess
from collections import OrderedDict


class SaveCommittedError(OSError):
    """The new file is installed, but verification or cleanup failed."""


def _replace_preset_files(changes):
    """Stage all files first; roll back earlier replacements on a later error.

    Values are bytes, or None to remove a stale companion. Recovery copies
    remain on disk if rollback itself fails; never discard the last good copy.
    """
    staged, backups, committed = {}, {}, []
    retained = set()
    completed = False

    def stage(destination, data):
        fd, path = tempfile.mkstemp(prefix='.wcm-preset-', dir=os.path.dirname(destination))
        try:
            with os.fdopen(fd, 'wb') as stream:
                if os.path.exists(destination):
                    os.fchmod(stream.fileno(), stat.S_IMODE(os.stat(destination).st_mode))
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return path
        except BaseException:
            os.unlink(path)
            raise

    try:
        for path, data in changes.items():
            # Replacements follow a config symlink; deletion removes only
            # the named directory entry, never the file it points to.
            destination = (os.path.join(os.path.realpath(os.path.dirname(path) or '.'),
                                        os.path.basename(path))
                           if data is None else os.path.realpath(path))
            if destination in backups:
                raise ValueError('Preset destinations must be different files')
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            if data is None and os.path.islink(destination):
                fd, backup = tempfile.mkstemp(prefix='.wcm-preset-', dir=os.path.dirname(destination))
                os.close(fd)
                os.unlink(backup)
                os.symlink(os.readlink(destination), backup)
                backups[destination] = backup
            elif os.path.exists(destination):
                with open(destination, 'rb') as stream:
                    backups[destination] = stage(destination, stream.read())
            else:
                backups[destination] = None
            staged[destination] = stage(destination, data) if data is not None else None
        try:
            for destination, source in staged.items():
                if source is not None:
                    os.replace(source, destination)
                elif os.path.lexists(destination):
                    os.unlink(destination)
                committed.append(destination)
            completed = True
        except BaseException as error:
            recovery_errors = []
            for destination in reversed(committed):
                backup = backups[destination]
                try:
                    if backup is not None:
                        os.replace(backup, destination)
                    elif os.path.exists(destination):
                        os.unlink(destination)
                except OSError as recovery_error:
                    if backup is not None:
                        retained.add(backup)
                    recovery_errors.append(f'{destination}: {recovery_error}; backup: {backup}')
            if recovery_errors:
                raise OSError('Preset rollback failed. Recovery files: ' + '; '.join(recovery_errors)) from error
            raise
    finally:
        cleanup_errors = []
        for path in list(staged.values()) + list(backups.values()):
            if path and path not in retained and os.path.lexists(path):
                try:
                    os.unlink(path)
                except OSError as error:
                    cleanup_errors.append(f'{path}: {error}')
        if cleanup_errors and completed:
            raise SaveCommittedError('Preset operation completed; cleanup failed. Recovery files: '
                                     + '; '.join(cleanup_errors))
        if cleanup_errors and not completed:
            original_error = sys.exc_info()[1]
            if original_error is not None and hasattr(original_error, 'add_note'):
                original_error.add_note('Temporary recovery files retained: ' + '; '.join(cleanup_errors))


class ConfigEntry:
    """Represents a single line in the config file."""
    __slots__ = ('kind', 'text', 'section', 'key', 'value', 'original_value')

    # kind: 'comment', 'blank', 'section', 'option'
    def __init__(self, kind, text, section=None, key=None, value=None):
        self.kind = kind
        self.text = text
        self.section = section
        self.key = key
        self.value = value
        self.original_value = value

    def to_line(self):
        if self.kind == 'option' and self.value != self.original_value:
            # Keep indentation and spacing on edited single-line options too.
            prefix = re.match(r'([^=]*=[ \t]*)', self.text)
            ending = '\r\n' if self.text.endswith('\r\n') else '\n'
            return f"{prefix.group(1) if prefix else self.key + ' = '}{self.value}{ending}"
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
        self._operations = []
        self._disk_text = None
        self._pending_edits = set()
        self._save_listeners = []   # callables invoked after each save()
        if path and os.path.isfile(path):
            self._load(path)

    def add_save_listener(self, fn):
        """Register a callback invoked (with self) after every save()."""
        if fn not in self._save_listeners:
            self._save_listeners.append(fn)

    def _load(self, path):
        self.entries.clear()
        self._section_map.clear()
        current_section = None

        with open(path, 'r', newline='') as f:
            self._disk_text = f.read()
        self._operations.clear()
        lines = iter(self._disk_text.splitlines(keepends=True))
        for line in lines:
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
                raw = line
                while value.rstrip().endswith('\\'):
                    following = next(lines, None)
                    if following is None:
                        break
                    raw += following
                    value = value.rstrip()[:-1].rstrip() + ' ' + following.strip()
                line = raw
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
        self._operations.append(('set_option', section, key, value))

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
        """Remove every definition of an option so older duplicates cannot return."""
        self._operations.append(('remove_option', section, key))
        self.entries = [entry for entry in self.entries
                        if not (entry.kind == 'option' and entry.section == section
                                and entry.key == key)]
        self._rebuild_index()

    def remove_section(self, section):
        """Remove an entire ``[section]`` and the lines that belong to it.

        Deletes the section header plus everything up to the next section
        header. Trailing blank/comment lines (which usually introduce the
        *next* section) are preserved, so removing one output doesn't eat
        the comment documenting the one after it.
        """
        self._operations.append(('remove_section', section))
        # Remove all occurrences, from the end so earlier indices stay valid.
        starts = [i for i, e in enumerate(self.entries)
                  if e.kind == 'section' and e.section == section]
        for start in reversed(starts):
            end = start + 1
            while end < len(self.entries) and self.entries[end].kind != 'section':
                end += 1
            while end - 1 > start and self.entries[end - 1].kind in ('blank', 'comment'):
                end -= 1
            del self.entries[start:end]
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
                    return last_idx
                if e.kind != 'blank':
                    last_idx = i + 1
        return last_idx

    def _rebuild_index(self):
        """Rebuild the section->key->index map after insertions/deletions."""
        self._section_map.clear()
        for i, e in enumerate(self.entries):
            if e.kind == 'section':
                # Empty sections still exist after their last option is removed
                # or an unrelated edit rebuilds the index.
                self._section_map.setdefault(e.section, {})
            elif e.kind == 'option' and e.section:
                if e.section not in self._section_map:
                    self._section_map[e.section] = {}
                self._section_map[e.section][e.key] = i

    def _consolidate_rule_sections(self):
        """Repair duplicate window-rules headers left by older WCM versions.

        Move their contents into the first block, preserving comments and
        the last value of repeated keys (matching the reader's behavior).
        Other sections and already-valid rule sections are left untouched.
        """
        starts = [i for i, entry in enumerate(self.entries)
                  if entry.kind == 'section' and entry.section == 'window-rules']
        if len(starts) < 2:
            return
        ranges = []
        body = []
        for start in starts:
            end = start + 1
            while end < len(self.entries) and self.entries[end].kind != 'section':
                end += 1
            ranges.append((start, end))
            block = list(self.entries[start + 1:end])
            while block and block[0].kind == 'blank':
                block.pop(0)
            while block and block[-1].kind == 'blank':
                block.pop()
            body.extend(block)
        last = {entry.key: i for i, entry in enumerate(body)
                if entry.kind == 'option'}
        body = [entry for i, entry in enumerate(body)
                if entry.kind != 'option' or last[entry.key] == i]
        repaired = []
        cursor = 0
        for number, (start, end) in enumerate(ranges):
            repaired.extend(self.entries[cursor:start])
            if number == 0:
                repaired.append(self.entries[start])
                repaired.extend(body)
                repaired.append(ConfigEntry('blank', '\n'))
            cursor = end
        repaired.extend(self.entries[cursor:])
        self.entries = repaired
        self._rebuild_index()

    def save(self, path=None):
        """Write the config back to disk, preserving all formatting."""
        path = path or self.path
        if not path:
            raise ValueError("No path specified for saving")

        # Replay only local edits onto the newest disk contents. An unrelated
        # external edit must not be overwritten by our stale in-memory copy.
        disk = None
        if os.path.isfile(path):
            with open(path, 'r', newline='') as f:
                disk = f.read()
        if self.path and os.path.abspath(path) == os.path.abspath(self.path) and disk != self._disk_text:
            operations = list(self._operations)
            if disk is not None:
                self._load(path)
            else:
                self.entries.clear()
                self._section_map.clear()
                self._operations.clear()
            for method, *args in operations:
                getattr(self, method)(*args)
        self._consolidate_rule_sections()
        # Repair spacing left by older versions when inserting into an empty
        # rules section. Keep separators after rules and all comments intact.
        gaps = set()
        for i, entry in enumerate(self.entries):
            if entry.kind != 'section' or entry.section != 'window-rules':
                continue
            end = i + 1
            while end < len(self.entries) and self.entries[end].kind == 'blank':
                end += 1
            if end < len(self.entries) and self.entries[end].kind == 'option':
                gaps.update(range(i + 1, end))
        if gaps:
            self.entries = [entry for i, entry in enumerate(self.entries)
                            if i not in gaps]
            self._rebuild_index()
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        lines = [entry.to_line() for entry in self.entries]
        # A header or comment at EOF need not originally have a newline.
        text = ''.join(line if i == len(lines) - 1 or line.endswith(('\n', '\r'))
                       else line + '\n' for i, line in enumerate(lines))
        # Write beside the destination and replace it only after a complete,
        # flushed write. Resolve symlinks so user-managed config links survive.
        destination = os.path.realpath(path)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.wcm-', dir=os.path.dirname(destination))
        recovery = None
        committed = False
        try:
            with os.fdopen(fd, 'w', newline='') as f:
                if os.path.exists(destination):
                    os.fchmod(f.fileno(), stat.S_IMODE(os.stat(destination).st_mode))
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            # Check again after staging: another editor may have saved while
            # we were writing. Keep the local operations available for retry.
            latest = None
            if os.path.exists(destination):
                with open(destination, 'r', newline='') as stream:
                    latest = stream.read()
            if latest != disk:
                raise OSError('Config changed during save. Retry to merge the latest changes.')
            if os.path.exists(destination):
                recovery_fd, recovery = tempfile.mkstemp(prefix='.wcm-recovery-', dir=os.path.dirname(destination))
                os.close(recovery_fd)
                os.unlink(recovery)
                try:
                    os.link(destination, recovery)
                except OSError as error:
                    if error.errno not in (errno.EPERM, errno.EACCES, errno.ENOSYS,
                                           errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK):
                        raise
                    # Some writable filesystems cannot create hard links.
                    # Keep a snapshot there, and recheck before replacement.
                    shutil.copy2(destination, recovery)
                    with open(recovery, 'r', newline='') as stream:
                        snapshot = stream.read()
                    with open(destination, 'r', newline='') as stream:
                        current = stream.read()
                    if snapshot != disk or current != disk:
                        raise OSError('Config changed during save. Retry to merge the latest changes.')
            os.replace(temporary, destination)
            committed = True
            self._disk_text = text
            self._operations.clear()
            if recovery is not None:
                try:
                    with open(recovery, 'r', newline='') as stream:
                        replaced_text = stream.read()
                except OSError as error:
                    saved_recovery, recovery = recovery, None
                    raise SaveCommittedError('Config saved; recovery verification failed. Recovery file: '
                                             + saved_recovery) from error
                if replaced_text != disk:
                    saved_recovery = recovery
                    recovery = None  # Preserve the competing writer's bytes.
                    raise SaveCommittedError('Concurrent config edit detected. External changes retained in ' + saved_recovery)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
            if recovery is not None and os.path.exists(recovery):
                try:
                    os.unlink(recovery)
                except OSError as error:
                    if committed:
                        raise SaveCommittedError('Config saved; recovery cleanup failed. Recovery file: '
                                                 + recovery) from error
                    raise
        self._disk_text = text
        self._operations.clear()

        for fn in self._save_listeners:
            try:
                fn(self)
            except Exception:
                pass

    def cancel_pending_edits(self, section=None):
        for widget in list(self._pending_edits):
            if section is None or widget.plugin.name == section:
                widget.cancel_pending_edit()

    def flush_pending_edits(self):
        for widget in list(self._pending_edits):
            widget.flush_pending_edit()

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
        start = len(self._operations)
        if name not in plugins:
            plugins.append(name)
            self.set_enabled_plugins(plugins)
        self._operations[start:] = [('enable_plugin', name)]

    def disable_plugin(self, name):
        """Remove a plugin from the enabled list."""
        plugins = self.get_enabled_plugins()
        start = len(self._operations)
        plugins = [p for p in plugins if p != name]
        self.set_enabled_plugins(plugins)
        self._operations[start:] = [('disable_plugin', name)]

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

    def _master_wfshell_path(self, name):
        """Companion path holding the verbatim wf-shell.ini snapshot.

        Stored under a 'wfshell' subdirectory so it is never picked up by
        list_master_presets() (which only scans the top level for *.ini).
        """
        d = os.path.join(self.preset_dir, 'wfshell')
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{name}.ini")

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

    def _save_name(self, name, plugin_name=None):
        safe = self._sanitize(name)
        if not safe:
            raise ValueError("Preset name cannot be empty")
        path = self._master_path(safe) if plugin_name is None else self._plugin_path(plugin_name, safe)
        if safe != name.strip() and os.path.exists(path):
            raise FileExistsError(
                f"'{name}' becomes '{safe}', which already exists. "
                f"Choose another name, or enter '{safe}' explicitly to overwrite it.")
        return safe

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
        name = self._save_name(name)
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
        ws = self._master_wfshell_path(name)
        _replace_preset_files({p: None for p in (path, ws) if os.path.lexists(p)})

    # ------------------------------------------------------------------
    # Master presets — verbatim whole-file snapshot
    # ------------------------------------------------------------------
    #
    # These copy the config file(s) byte-for-byte instead of rewriting
    # them option-by-option. Copying the whole file preserves backslash
    # line-continuations (e.g. the multi-line `plugins = \ ...` list in a
    # stock wayfire.ini) and any formatting the line parser would drop,
    # so switching presets can never accidentally blank out the plugin
    # list. The single-line-change contract still governs ordinary option
    # edits; only full-config preset switching uses this whole-file path.

    def save_master_preset_file(self, name, config_path, wfshell_path=None):
        """Snapshot the live config file(s) verbatim as a master preset.

        Args:
            name:         preset name (used as filename stem)
            config_path:  path to the live wayfire.ini
            wfshell_path: path to the live wf-shell.ini (optional)
        """
        name = self._save_name(name)
        dst = self._master_path(name)
        if config_path and os.path.isfile(config_path):
            with open(config_path, 'rb') as stream:
                data = stream.read()
        else:
            data = b''
        changes = {dst: data}
        ws_dst = self._master_wfshell_path(name)
        if wfshell_path and os.path.isfile(wfshell_path):
            with open(wfshell_path, 'rb') as stream:
                changes[ws_dst] = stream.read()
        elif os.path.lexists(ws_dst):
            changes[ws_dst] = None
        _replace_preset_files(changes)

    def load_master_preset_file(self, name, config_path, wfshell_path=None):
        """Restore a master preset by copying the whole file(s) back verbatim.

        Overwrites the live config file(s) with the stored snapshot. The
        caller is responsible for reloading any in-memory config objects
        afterwards.
        """
        src = self._master_path(name)
        if not os.path.isfile(src):
            raise FileNotFoundError(f"Master preset '{name}' not found")

        with open(src, 'rb') as stream:
            changes = {config_path: stream.read()}
        if wfshell_path:
            ws_src = self._master_wfshell_path(name)
            if os.path.isfile(ws_src):
                with open(ws_src, 'rb') as stream:
                    changes[wfshell_path] = stream.read()
        _replace_preset_files(changes)

    # ------------------------------------------------------------------
    # Plugin presets — single-section snapshot
    # ------------------------------------------------------------------

    def list_plugin_presets(self, plugin_name):
        """Return sorted list of preset names for a given plugin."""
        d = os.path.join(self.preset_dir, 'plugins', plugin_name)
        if not os.path.isdir(d):
            return []
        return sorted(f[:-4] for f in os.listdir(d) if f.endswith('.ini'))

    def save_plugin_preset(self, name, plugin_name, config, manage_enabled=None):
        """
        Save the current options for *one* plugin section as a preset.
        """
        name = self._save_name(name, plugin_name)
        preset = WayfireConfigFile()
        opts = config.get_section_options(plugin_name)
        for key, value in opts.items():
            preset.set_option(plugin_name, key, value)

        # Also store whether the plugin was enabled (in [core] plugins)
        if manage_enabled is None:
            manage_enabled = 'core' in config.get_sections()
        if manage_enabled:
            enabled = config.get_enabled_plugins()
            preset.set_option('_preset_meta', 'enabled',
                              'true' if plugin_name in enabled else 'false')

        preset.save(self._plugin_path(plugin_name, name))

    def load_plugin_preset(self, name, plugin_name, config, manage_enabled=True):
        """
        Apply a plugin preset — only touches that plugin's section.
        """
        path = self._plugin_path(plugin_name, name)
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"Plugin preset '{name}' for '{plugin_name}' not found")
        preset = WayfireConfigFile(path)
        opts = preset.get_section_options(plugin_name)
        original = copy.deepcopy((config.entries, config._section_map,
                                  config._operations, config._disk_text))
        try:
            for key, value in opts.items():
                config.set_option(plugin_name, key, value)
            was_enabled = preset.get_option('_preset_meta', 'enabled')
            if manage_enabled and was_enabled is not None:
                if was_enabled == 'true':
                    config.enable_plugin(plugin_name)
                else:
                    config.disable_plugin(plugin_name)
            config.save()
        except SaveCommittedError:
            # The preset is already installed. Retain its in-memory state and
            # cancel obsolete typing even though cleanup needs attention.
            config.cancel_pending_edits(plugin_name)
            raise
        except BaseException:
            (config.entries, config._section_map,
             config._operations, config._disk_text) = original
            raise
        config.cancel_pending_edits(plugin_name)

    def delete_plugin_preset(self, name, plugin_name):
        path = self._plugin_path(plugin_name, name)
        if os.path.isfile(path):
            os.unlink(path)

class OutputManager:
    """Detect connected monitors and read/write their wayfire.ini config.

    Output configuration lives in ``[output:<name>]`` sections::

        mode      = <w>x<h>@<refresh_mHz>   (or 'off' / 'default' / 'mirror <out>')
        position  = <x>,<y>
        scale     = <float>
        transform = normal|90|180|270|flipped|90_flipped|180_flipped|270_flipped

    Detection shells out to ``wlr-randr`` and parses its text output. This
    class is toolkit-agnostic and returns plain dicts, so any frontend can
    render it (mirroring the backend/frontend split used elsewhere).
    """

    #: transform values as written in wayfire.ini
    TRANSFORMS = ['normal', '90', '180', '270',
                  'flipped', '90_flipped', '180_flipped', '270_flipped']

    # wlr-randr prints rotated flips as 'flipped-90'; wayfire.ini wants
    # '90_flipped'. Translate so a detected value matches the config vocabulary.
    _WLR_TO_WF = {
        'normal': 'normal', '90': '90', '180': '180', '270': '270',
        'flipped': 'flipped',
        'flipped-90': '90_flipped',
        'flipped-180': '180_flipped',
        'flipped-270': '270_flipped',
    }

    _MODE_RE = re.compile(r'(\d+)\s*x\s*(\d+)\s*px(?:\s*,\s*([\d.]+)\s*Hz)?(.*)')

    @staticmethod
    def section_name(output_name):
        return f"output:{output_name}"

    @staticmethod
    def validate_mode(res, refresh_mhz, enabled, modes):
        """Check a chosen resolution/refresh before it's written to the config.

        Returns ``(level, message)`` where level is ``'ok'``, ``'warn'`` or
        ``'error'``. An ``'error'`` means the value is malformed or
        unsupported and must NOT be written, so wayfire is never handed a
        bad mode (which can blank an output). A ``'warn'`` is allowed but
        flagged to the user.

        Args:
            res:         resolution string like '1920x1080' ('' means auto)
            refresh_mhz: refresh in millihertz; 0 = unspecified,
                         negative = the user typed something unparseable
            enabled:     whether the output is on (disabled is always valid)
            modes:       advertised modes for this output (may be empty/None,
                         in which case only the format is checked)
        """
        if not enabled:
            return ('ok', '')
        res = (res or '').strip()
        if res == '':
            return ('ok', '')  # empty -> 'default' (auto-detect), always safe
        if not re.fullmatch(r'\d+x\d+', res) or any(int(v) <= 0 for v in res.split('x')):
            return ('error',
                    _('Invalid resolution — use WIDTHxHEIGHT, '
                      'e.g. 1920x1080.'))
        if refresh_mhz is not None and refresh_mhz < 0:
            return ('error',
                    _('Invalid refresh rate — enter a number of Hz, '
                      'e.g. 60.'))
        if modes:
            adv = {}
            for m in modes:
                adv.setdefault(f"{m['width']}x{m['height']}", []).append(
                    m['refresh'])
            if res not in adv:
                return ('error',
                        _('{res} is not a mode this monitor reports; it may '
                          'fail to apply. Pick a listed resolution.'
                          ).format(res=res))
            if refresh_mhz and refresh_mhz > 0 and not any(
                    abs(refresh_mhz - r) <= 500 for r in adv[res]):
                return ('warn',
                        _("That refresh rate isn't advertised for this "
                          "resolution; it may be ignored."))
        return ('ok', '')

    @staticmethod
    def list_configured_outputs(config):
        """Return names of outputs that already have an ``[output:<name>]`` section."""
        names = []
        for sec in config.get_sections():
            if sec.startswith('output:'):
                n = sec.split(':', 1)[1]
                if n and n not in names:
                    names.append(n)
        return names

    def detect(self):
        """Return a list of detected outputs, or ``[]`` if unavailable.

        Each entry is a dict::

            {
                'name': str, 'description': str, 'enabled': bool,
                'modes': [ {'width', 'height', 'refresh'(mHz),
                            'current', 'preferred'}, ... ],
                'current_mode': (w, h, refresh_mHz) | None,
                'position': (x, y) | None,
                'transform': str,   # wayfire vocabulary
                'scale': float,
            }

        Returns ``[]`` when wlr-randr is missing or no Wayland session is
        available, so the frontend can fall back to manual entry.
        """
        try:
            r = subprocess.run(['wlr-randr'], capture_output=True,
                               text=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return []
        if r.returncode != 0 or not r.stdout.strip():
            return []
        return self._parse(r.stdout)

    def _parse(self, text):
        outputs = []
        cur = None
        for raw in text.splitlines():
            if not raw.strip():
                continue
            if not raw.startswith((' ', '\t')):
                # Output header line:  <name> "<description>"
                name = raw.split()[0]
                desc = ''
                if '"' in raw:
                    try:
                        desc = raw.split('"', 1)[1].rsplit('"', 1)[0]
                    except IndexError:
                        desc = ''
                cur = {'name': name, 'description': desc, 'enabled': False,
                       'modes': [], 'current_mode': None, 'position': None,
                       'transform': 'normal', 'scale': 1.0}
                outputs.append(cur)
                continue
            if cur is None:
                continue
            line = raw.strip()
            low = line.lower()
            if low.startswith('enabled:'):
                cur['enabled'] = 'yes' in low
            elif low.startswith('position:'):
                try:
                    x, y = line.split(':', 1)[1].strip().split(',')
                    cur['position'] = (int(x), int(y))
                except (ValueError, IndexError):
                    pass
            elif low.startswith('transform:'):
                t = line.split(':', 1)[1].strip()
                cur['transform'] = self._WLR_TO_WF.get(t, t)
            elif low.startswith('scale:'):
                try:
                    cur['scale'] = float(line.split(':', 1)[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'px' in low:
                m = self._MODE_RE.match(line)
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    refresh = (int(round(float(m.group(3)) * 1000))
                               if m.group(3) else 0)
                    flags = m.group(4) or ''
                    is_cur = 'current' in flags
                    cur['modes'].append({
                        'width': w, 'height': h, 'refresh': refresh,
                        'current': is_cur, 'preferred': 'preferred' in flags,
                    })
                    if is_cur:
                        cur['current_mode'] = (w, h, refresh)
        return outputs
