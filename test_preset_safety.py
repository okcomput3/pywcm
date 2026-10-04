"""Preset failure recovery and UI naming regressions; temporary files only."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from config_backend import WayfireConfigFile, PresetManager
from metadata import Option, OptionType, Plugin, PluginType
from wcm import Gtk, WCM, OptionWidget


def fixture(root):
    cfg = WayfireConfigFile(str(root / 'wayfire.ini'))
    cfg.set_option('core', 'plugins', 'command move')
    cfg.set_option('command', 'command_a', 'echo original')
    cfg.save()
    shell = root / 'wf-shell.ini'
    shell.write_text('[panel]\nposition = top\n')
    manager = PresetManager(str(root / 'presets'))
    manager.save_master_preset_file('saved', cfg.path, str(shell))
    cfg.set_option('command', 'command_a', 'echo live')
    cfg.save()
    shell.write_text('[panel]\nposition = bottom\n')
    return cfg, shell, manager


def test_master_stage_failure_preserves_both_save_and_load_destinations():
    for saving in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg, shell, manager = fixture(root)
            destinations = [Path(manager._master_path('saved')), Path(manager._master_wfshell_path('saved'))] if saving else [Path(cfg.path), shell]
            before = [p.read_bytes() for p in destinations]
            operation = manager.save_master_preset_file if saving else manager.load_master_preset_file
            with patch('config_backend.os.fsync', side_effect=OSError(28, 'simulated disk full')):
                try: operation('saved', cfg.path, str(shell))
                except OSError: pass
                else: raise AssertionError('expected staging failure')
            assert [p.read_bytes() for p in destinations] == before
            assert not list(root.rglob('.wcm-preset-*'))


def test_second_file_failure_rolls_back_first_for_save_and_load():
    for saving in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg, shell, manager = fixture(root)
            destinations = [Path(manager._master_path('saved')), Path(manager._master_wfshell_path('saved'))] if saving else [Path(cfg.path), shell]
            before = [p.read_bytes() for p in destinations]
            replace = os.replace
            def fail_second(src, dst):
                if str(dst) == str(destinations[1]):
                    raise PermissionError('simulated second-file failure')
                return replace(src, dst)
            operation = manager.save_master_preset_file if saving else manager.load_master_preset_file
            with patch('config_backend.os.replace', side_effect=fail_second):
                try: operation('saved', cfg.path, str(shell))
                except PermissionError: pass
                else: raise AssertionError('expected second-file failure')
            assert [p.read_bytes() for p in destinations] == before
            assert not list(root.rglob('.wcm-preset-*'))


def test_rollback_failure_retains_recovery_copy():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg, shell, manager = fixture(root)
        before = Path(cfg.path).read_bytes()
        replace = os.replace
        calls = []
        def fail_after_first(src, dst):
            calls.append(dst)
            if len(calls) > 1: raise PermissionError('simulated persistent failure')
            return replace(src, dst)
        with patch('config_backend.os.replace', side_effect=fail_after_first):
            try: manager.load_master_preset_file('saved', cfg.path, str(shell))
            except OSError as error: assert 'Recovery files' in str(error)
            else: raise AssertionError('expected failure')
        backups = list(root.rglob('.wcm-preset-*'))
        assert len(backups) == 1
        assert backups[0].read_bytes() == before


def test_master_pair_success_keeps_exact_bytes_and_symlinks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg, shell, manager = fixture(root)
        target = root / 'real.ini'
        os.replace(cfg.path, target)
        Path(cfg.path).symlink_to(target)
        expected = Path(manager._master_path('saved')).read_bytes()
        manager.load_master_preset_file('saved', cfg.path, str(shell))
        assert Path(cfg.path).is_symlink()
        assert target.read_bytes() == expected
        assert shell.read_bytes() == Path(manager._master_wfshell_path('saved')).read_bytes()


def test_plugin_failed_load_preserves_pending_edits_and_memory():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg, shell, manager = fixture(Path(tmp))
        manager.save_plugin_preset('saved', 'command', cfg)
        cfg.set_option('command', 'command_a', 'echo before')
        cfg.save()
        editor = OptionWidget(Option(name='command_a', type=OptionType.STRING, default_value=''), cfg, Plugin(name='command'))
        editor.ed.set_text('echo pending')
        before = Path(cfg.path).read_bytes()
        with patch('config_backend.os.replace', side_effect=OSError('simulated write failure')):
            try: manager.load_plugin_preset('saved', 'command', cfg)
            except OSError: pass
            else: raise AssertionError('expected failure')
        assert Path(cfg.path).read_bytes() == before
        assert cfg.get_option('command', 'command_a') == 'echo before'
        assert editor in cfg._pending_edits
        cfg.set_option('core', 'vwidth', '5')
        cfg.save()
        assert WayfireConfigFile(cfg.path).get_option('command', 'command_a') == 'echo before'
        cfg.flush_pending_edits()
        assert WayfireConfigFile(cfg.path).get_option('command', 'command_a') == 'echo pending'


def test_sanitized_name_collision_preserves_original():
    with tempfile.TemporaryDirectory() as tmp:
        cfg, shell, manager = fixture(Path(tmp))
        for plugin in (None, 'command'):
            save = (lambda name: manager.save_master_preset_file(name, cfg.path, str(shell))) if plugin is None else (lambda name: manager.save_plugin_preset(name, plugin, cfg))
            save('work/laptop')
            path = Path(manager._master_path('work_laptop') if plugin is None else manager._plugin_path(plugin, 'work_laptop'))
            before = path.read_bytes()
            cfg.set_option('command', 'command_a', 'echo changed')
            cfg.save()
            try: save('work?laptop')
            except FileExistsError: pass
            else: raise AssertionError('collision not rejected')
            assert path.read_bytes() == before
            save('work_laptop')  # Explicit existing name still supports overwrite.
            assert path.exists()


def test_saved_plugin_selected_after_sanitization():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg, shell, manager = fixture(Path(tmp))
        manager.save_plugin_preset('aaa', 'command', cfg)
        combo = Gtk.ComboBoxText()
        window = SimpleNamespace(current_plugin=Plugin(name='command', type=PluginType.WAYFIRE), preset_mgr=manager, _plugin_combo=combo, _cfg_for=lambda plugin: cfg)
        window._refresh_plugin_presets = lambda: WCM._refresh_plugin_presets(window)
        window._prompt_name = lambda title, callback: callback('zzz/work')
        WCM._on_plugin_save(window, None)
        assert combo.get_active_text() == 'zzz_work'
        assert manager.list_plugin_presets('command') == ['aaa', 'zzz_work']


def test_plugin_merge_keeps_extra_rows():
    with tempfile.TemporaryDirectory() as tmp:
        cfg, shell, manager = fixture(Path(tmp))
        manager.save_plugin_preset('small', 'command', cfg)
        cfg.set_option('command', 'command_extra', 'echo extra')
        cfg.save()
        manager.load_plugin_preset('small', 'command', cfg)
        assert cfg.get_option('command', 'command_extra') == 'echo extra'


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in list(globals().items()) if name.startswith('test_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
