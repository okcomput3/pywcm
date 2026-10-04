"""Follow-up regressions: safe writes, master presets, automatic display mode."""
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from config_backend import WayfireConfigFile, PresetManager
from metadata import Option, OptionType, Plugin
from wcm import Gtk, GLib, WCM, OptionWidget, DisplayPage


def fixture(directory):
    cfg = WayfireConfigFile(str(directory / 'wayfire.ini'))
    cfg.set_option('core', 'plugins', 'move')
    cfg.save()
    shell = WayfireConfigFile(str(directory / 'wf-shell.ini'))
    shell.set_option('panel', 'position', 'top')
    shell.save()
    window = SimpleNamespace(
        config=cfg, wf_shell_config=shell,
        preset_mgr=PresetManager(str(directory / 'presets')),
        _master_combo=Mock(), display_page=None, plugins=[],
        main_page=SimpleNamespace(_pw=[]), current_plugin=None, ini_panel=Mock())
    window._master_combo.get_active_text.return_value = 'chosen'
    return window


def test_partial_write_preserves_file_and_retry():
    with tempfile.TemporaryDirectory() as tmp:
        window = fixture(Path(tmp))
        cfg = window.config
        original = Path(cfg.path).read_bytes()
        listener = Mock()
        cfg.add_save_listener(listener)
        cfg.set_option('core', 'vwidth', '5')
        real_fdopen = os.fdopen

        class PartialWriter:
            def __init__(self, file): self.file = file
            def __enter__(self): return self
            def __exit__(self, *args): self.file.close()
            def fileno(self): return self.file.fileno()
            def write(self, text):
                self.file.write(text[:5])
                self.file.flush()
                raise OSError(28, 'simulated disk full')

        with patch('config_backend.os.fdopen', side_effect=lambda *a, **k: PartialWriter(real_fdopen(*a, **k))):
            try:
                cfg.save()
            except OSError:
                pass
            else:
                raise AssertionError('write error was not raised')
        assert Path(cfg.path).read_bytes() == original
        assert not list(Path(tmp).glob('.wcm-*'))
        listener.assert_not_called()
        cfg.save()
        assert WayfireConfigFile(cfg.path).get_option('core', 'vwidth') == '5'
        listener.assert_called_once()


def test_replace_failure_preserves_file():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = fixture(Path(tmp)).config
        original = Path(cfg.path).read_bytes()
        cfg.set_option('core', 'vwidth', '9')
        with patch('config_backend.os.replace', side_effect=OSError('replace failed')):
            try: cfg.save()
            except OSError: pass
            else: raise AssertionError('replace error was not raised')
        assert Path(cfg.path).read_bytes() == original
        assert not list(Path(tmp).glob('.wcm-*'))


def test_atomic_save_preserves_symlink_and_permissions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        target = root / 'target.ini'
        target.write_text('[core]\nplugins = move\n')
        target.chmod(0o640)
        link = root / 'wayfire.ini'
        link.symlink_to(target)
        cfg = WayfireConfigFile(str(link))
        cfg.set_option('core', 'vwidth', '4')
        cfg.save()
        assert link.is_symlink()
        assert stat.S_IMODE(target.stat().st_mode) == 0o640
        assert WayfireConfigFile(str(target)).get_option('core', 'vwidth') == '4'


def test_master_preset_reconnects_live_panel():
    with tempfile.TemporaryDirectory() as tmp:
        window = fixture(Path(tmp))
        window.preset_mgr.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
        WCM._on_master_load(window, None)
        window.ini_panel.show.assert_called_once_with(window.config)
        for cfg in (window.config, window.wf_shell_config):
            window.ini_panel.reset_mock()
            cfg.set_option('demo', 'value', 'new')
            cfg.save()
            window.ini_panel.show.assert_called_once_with(cfg)


def test_failed_master_preset_keeps_pending_edit():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        window = fixture(Path(tmp))
        editor = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), window.config, Plugin(name='demo'))
        editor.ed.set_text('pending text')
        WCM._on_master_load(window, None)
        assert editor in window.config._pending_edits
        window.config.flush_pending_edits()
        assert WayfireConfigFile(window.config.path).get_option('demo', 'text') == 'pending text'


def make_card(directory, connected=False):
    cfg = WayfireConfigFile(str(directory / 'wayfire.ini'))
    cfg.set_option('output:DP-1', 'mode', 'off')
    cfg.save()
    page = SimpleNamespace(_active_confirm=None, _confirm_sources=set(), _pending_reverts={}, app=None)
    frame = DisplayPage._build_card(page, dict(name='DP-1', enabled=False, modes=[]), cfg, is_connected=connected)
    box = frame.get_child()
    header = box.get_first_child()
    switch = header.get_first_child().get_next_sibling().get_next_sibling()
    resolution = header.get_next_sibling().get_last_child()
    return cfg, page, switch, resolution


def test_enable_output_without_resolution_uses_auto():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg, page, switch, resolution = make_card(Path(tmp))
        switch.set_active(True)
        assert cfg.get_option('output:DP-1', 'mode') == 'default'
        assert resolution.get_active_id() == 'default'


def test_clear_resolution_commits_auto_on_enter():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg, page, switch, resolution = make_card(Path(tmp))
        resolution.get_child().set_text('1920x1080')
        switch.set_active(True)
        resolution.get_child().set_text('')
        # Do not change mode in the middle of editing a resolution.
        assert cfg.get_option('output:DP-1', 'mode') == '1920x1080'
        resolution.get_child().emit('activate')
        assert cfg.get_option('output:DP-1', 'mode') == 'default'
        assert resolution.get_active_id() == 'default'


def test_auto_choice_has_display_rollback():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg, page, switch, resolution = make_card(Path(tmp), connected=True)
        resolution.get_child().set_text('1920x1080')
        switch.set_active(True)
        # Begin a fresh card with the enabled mode as its baseline.
        cfg2 = WayfireConfigFile(cfg.path)
        frame = DisplayPage._build_card(page, dict(name='DP-1', enabled=True, modes=[]), cfg2, is_primary=True)
        resolution = frame.get_child().get_first_child().get_next_sibling().get_last_child()
        resolution.set_active_id('default')
        assert cfg2.get_option('output:DP-1', 'mode') == 'default'
        assert page._confirm_sources
        DisplayPage.revert_pending_changes(page)
        assert cfg2.get_option('output:DP-1', 'mode') == '1920x1080'


if __name__ == '__main__':
    tests = [unittest.FunctionTestCase(value) for name, value in list(globals().items()) if name.startswith('test_')]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(tests))
    raise SystemExit(not result.wasSuccessful())
