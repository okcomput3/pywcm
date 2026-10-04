"""Regressions for symlink cleanup, output toggle baselines and delete errors."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from config_backend import WayfireConfigFile, PresetManager, _replace_preset_files
from wcm import Gtk, DisplayPage, WCM


def test_companion_cleanup_preserves_symlink_targets():
    for dangling in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / 'wayfire.ini'
            live.write_text('[core]\nplugins = move\n')
            target = root / 'shell-target.ini'
            if not dangling: target.write_bytes(b'keep this file')
            manager = PresetManager(str(root / 'presets'))
            companion = Path(manager._master_wfshell_path('saved'))
            companion.symlink_to(target)
            manager.save_master_preset_file('saved', str(live))
            assert not os.path.lexists(companion)
            assert target.exists() == (not dangling)
            if not dangling: assert target.read_bytes() == b'keep this file'
            assert not list(root.rglob('.wcm-preset-*'))


def test_symlink_deletion_rollback_restores_link():
    for dangling in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'target'
            if not dangling: target.write_bytes(b'keep target')
            link = root / 'link'
            link.symlink_to('target')
            other = root / 'other'
            other.write_bytes(b'old')
            replace = os.replace
            def fail(src, dst):
                if dst == str(other): raise PermissionError('injected failure')
                return replace(src, dst)
            with patch('config_backend.os.replace', side_effect=fail):
                try: _replace_preset_files({str(link): None, str(other): b'new'})
                except PermissionError: pass
                else: raise AssertionError('expected replacement failure')
            assert link.is_symlink() and os.readlink(link) == 'target'
            assert target.exists() == (not dangling)
            if not dangling: assert target.read_bytes() == b'keep target'
            assert other.read_bytes() == b'old'
            assert not list(root.glob('.wcm-preset-*'))


def test_rotation_rollback_preserves_new_enable_baseline():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = WayfireConfigFile(str(Path(tmp) / 'wayfire.ini'))
        cfg.set_option('output:DP-1', 'mode', 'off')
        cfg.save()
        page = SimpleNamespace(_active_confirm=None, _confirm_sources=set(), _pending_reverts={}, app=None)
        frame = DisplayPage._build_card(page, dict(name='DP-1', enabled=False, modes=[]), cfg, is_connected=True)
        header = frame.get_child().get_first_child()
        switch = header.get_first_child().get_next_sibling().get_next_sibling()
        switch.set_active(True)
        assert cfg.get_option('output:DP-1', 'mode') == 'default'
        rotation_row = header
        for _ in range(5): rotation_row = rotation_row.get_next_sibling()
        rotation = rotation_row.get_last_child()
        for angle in (1, 2):
            rotation.set_active(angle)
            assert page._confirm_sources
            DisplayPage.revert_pending_changes(page)
            assert cfg.get_option('output:DP-1', 'mode') == 'default'
            assert cfg.get_option('output:DP-1', 'transform') is None
            assert switch.get_active()
            assert not page._pending_reverts and not page._confirm_sources
        switch.set_active(False)
        assert cfg.get_option('output:DP-1', 'mode') == 'off'
        switch.set_active(True)
        rotation.set_active(3)
        DisplayPage.revert_pending_changes(page)
        assert cfg.get_option('output:DP-1', 'mode') == 'default'


def test_delete_handlers_report_errors_and_preserve_selection():
    for plugin in (False, True):
        manager = Mock()
        error = PermissionError('injected deletion denial')
        window = SimpleNamespace(preset_mgr=manager, _master_combo=Mock(), _plugin_combo=Mock(),
                                 current_plugin=SimpleNamespace(name='command'),
                                 _refresh_master_presets=Mock(), _refresh_plugin_presets=Mock())
        combo = window._plugin_combo if plugin else window._master_combo
        combo.get_active_text.return_value = 'saved'
        delete = manager.delete_plugin_preset if plugin else manager.delete_master_preset
        delete.side_effect = error
        with patch('wcm._preset_error') as report:
            (WCM._on_plugin_delete if plugin else WCM._on_master_delete)(window, None)
            report.assert_called_once_with(window, error)
        window._refresh_master_presets.assert_not_called()
        window._refresh_plugin_presets.assert_not_called()


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in list(globals().items()) if name.startswith('test_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
