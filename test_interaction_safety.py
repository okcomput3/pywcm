"""Concurrent changes, retryable edits and transactional preset deletion."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from config_backend import WayfireConfigFile, PresetManager
from wcm import Gtk, OptionWidget
from metadata import Option, OptionType, Plugin


def fixture(root):
    path = root / 'wayfire.ini'
    path.write_text('[core]\nplugins = move\nvwidth = 2\n')
    return WayfireConfigFile(str(path))


def test_plugin_operations_merge_external_changes():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = fixture(Path(tmp))
        other = WayfireConfigFile(cfg.path)
        other.enable_plugin('resize'); other.save()
        cfg.enable_plugin('blur'); cfg.save()
        assert cfg.get_enabled_plugins() == ['move', 'resize', 'blur']
        other = WayfireConfigFile(cfg.path)
        other.enable_plugin('expo'); other.save()
        cfg.disable_plugin('resize'); cfg.save()
        assert cfg.get_enabled_plugins() == ['move', 'blur', 'expo']


def test_staging_race_preserves_file_and_retry_merges():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = fixture(Path(tmp))
        cfg.set_option('core', 'vwidth', '4')
        fsync = os.fsync
        def intervening(fd):
            fsync(fd)
            Path(cfg.path).write_text('[core]\nplugins = move\nvheight = 9\n')
        with patch('config_backend.os.fsync', side_effect=intervening):
            try: cfg.save()
            except OSError as error: assert 'changed during save' in str(error)
            else: raise AssertionError('race not detected')
        assert WayfireConfigFile(cfg.path).get_option('core', 'vheight') == '9'
        cfg.save()
        saved = WayfireConfigFile(cfg.path)
        assert saved.get_option('core', 'vheight') == '9'
        assert saved.get_option('core', 'vwidth') == '4'


def test_last_moment_inplace_write_retained_for_recovery():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = fixture(root)
        cfg.set_option('core', 'vwidth', '4')
        replace = os.replace
        external = '[core]\nplugins = move\nvheight = 9\n'
        def race(src, dst):
            Path(dst).write_text(external)
            replace(src, dst)
        with patch('config_backend.os.replace', side_effect=race):
            try: cfg.save()
            except OSError as error: assert 'External changes retained' in str(error)
            else: raise AssertionError('race not reported')
        copies = list(root.glob('.wcm-recovery-*'))
        assert len(copies) == 1 and copies[0].read_text() == external
        assert WayfireConfigFile(cfg.path).get_option('core', 'vwidth') == '4'


def test_failed_pending_edit_is_retryable():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = fixture(Path(tmp))
        widget = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), cfg, Plugin(name='demo'))
        widget.ed.set_text('pending typing')
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            try: cfg.flush_pending_edits()
            except OSError: pass
            else: raise AssertionError('expected failure')
        assert widget in cfg._pending_edits
        cfg.flush_pending_edits()
        assert WayfireConfigFile(cfg.path).get_option('demo', 'text') == 'pending typing'
        assert not cfg._pending_edits


def test_master_delete_failure_restores_both_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = fixture(root)
        shell = root / 'shell.ini'; shell.write_text('[panel]\nposition = top\n')
        manager = PresetManager(str(root / 'presets'))
        manager.save_master_preset_file('saved', cfg.path, str(shell))
        main = Path(manager._master_path('saved'))
        companion = Path(manager._master_wfshell_path('saved'))
        before = (main.read_bytes(), companion.read_bytes())
        unlink = os.unlink
        def fail(path, *args, **kwargs):
            if str(path) == str(companion): raise PermissionError('denied')
            return unlink(path, *args, **kwargs)
        with patch('config_backend.os.unlink', side_effect=fail):
            try: manager.delete_master_preset('saved')
            except PermissionError: pass
            else: raise AssertionError('expected failure')
        assert (main.read_bytes(), companion.read_bytes()) == before
        manager.delete_master_preset('saved')
        assert not main.exists() and not companion.exists()


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in list(globals().items()) if name.startswith('test_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
