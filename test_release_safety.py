"""Fault-injection coverage for close, display recovery and portable saves."""
import errno
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from config_backend import WayfireConfigFile
from metadata import Option, OptionType, Plugin
from wcm import Gtk, WCM, OptionWidget, DisplayPage, _DisplayConfirmDialog


def config(root):
    path = root / 'wayfire.ini'
    path.write_text('[core]\nplugins = move\n')
    return WayfireConfigFile(str(path))


def display(cfg, names=('DP-1',)):
    page = SimpleNamespace(_active_confirm=None, _confirm_sources=set(),
                           _pending_reverts={}, app=None)
    cards, resolutions = [], []
    for name in names:
        cfg.set_option('output:' + name, 'mode', '1920x1080')
    cfg.save()
    for name in names:
        card = DisplayPage._build_card(page, dict(name=name, enabled=True, modes=[]),
                                      cfg, is_primary=True, is_connected=True)
        resolution = card.get_child().get_first_child().get_next_sibling().get_last_child()
        resolution.get_child().set_text('1280x720')
        cards.append(card)
        resolutions.append(resolution)
    return page, cards, resolutions


def test_portable_save_preserves_mode_and_symlink():
    for code in (errno.EOPNOTSUPP, errno.EPERM, errno.EACCES, errno.EXDEV, errno.EMLINK, errno.ENOSYS):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config(root)
            Path(cfg.path).chmod(0o640)
            link = root / 'linked.ini'
            link.symlink_to(cfg.path)
            cfg = WayfireConfigFile(str(link))
            cfg.set_option('core', 'vwidth', '5')
            with patch('config_backend.os.link', side_effect=OSError(code, 'unsupported')):
                cfg.save()
            assert link.is_symlink()
            assert link.stat().st_mode & 0o777 == 0o640
            assert WayfireConfigFile(str(link)).get_option('core', 'vwidth') == '5'
            assert not list(root.glob('.wcm-*'))


def test_portable_save_copy_failure_preserves_original_and_retries():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = config(root)
        original = Path(cfg.path).read_bytes()
        cfg.set_option('core', 'vwidth', '5')
        with patch('config_backend.os.link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')):
            with patch('config_backend.shutil.copy2', side_effect=OSError(errno.ENOSPC, 'full')):
                with unittest.TestCase().assertRaises(OSError): cfg.save()
            assert Path(cfg.path).read_bytes() == original
            assert not list(root.glob('.wcm-*'))
            cfg.save()
        assert WayfireConfigFile(cfg.path).get_option('core', 'vwidth') == '5'


def test_portable_save_detects_copy_race():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cfg = config(root)
        cfg.set_option('core', 'vwidth', '5')
        import shutil
        copy = shutil.copy2
        def race(src, dst):
            copy(src, dst)
            Path(src).write_text('[core]\nplugins = move\nvheight = 9\n')
        with patch('config_backend.os.link', side_effect=OSError(errno.EOPNOTSUPP, 'unsupported')):
            with patch('config_backend.shutil.copy2', side_effect=race):
                with unittest.TestCase().assertRaises(OSError): cfg.save()
        cfg.save()
        saved = WayfireConfigFile(cfg.path)
        assert saved.get_option('core', 'vwidth') == '5'
        assert saved.get_option('core', 'vheight') == '9'


def test_close_blocks_on_either_config_failure_then_retries():
    Gtk.init()
    for shell in (False, True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config(root)
            other = WayfireConfigFile(str(root / 'shell.ini'))
            target = other if shell else cfg
            widget = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''),
                                  target, Plugin(name='demo'))
            widget.ed.set_text('keep this edit')
            state = SimpleNamespace(config=cfg, wf_shell_config=other, display_page=None)
            window = Gtk.Window()
            window.connect('close-request', lambda *_: WCM._before_close(state))
            try:
                with patch('config_backend.os.replace', side_effect=PermissionError('denied')), patch('wcm._operation_error') as report:
                    assert window.emit('close-request') is True
                    report.assert_called_once()
                assert widget in target._pending_edits
                assert window.emit('close-request') is False
                assert WayfireConfigFile(target.path).get_option('demo', 'text') == 'keep this edit'
            finally:
                target.cancel_pending_edits()
                window.destroy()


def test_display_rollback_repeated_failure_preserves_ui_and_retry():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = config(Path(tmp))
        page, cards, resolutions = display(cfg)
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            for _ in range(3):
                with unittest.TestCase().assertRaises(OSError): DisplayPage.revert_pending_changes(page)
                assert len(page._pending_reverts) == 1
                assert resolutions[0].get_child().get_text() == '1280x720'
                assert cfg.get_option('output:DP-1', 'mode') == '1280x720'
        DisplayPage.revert_pending_changes(page)
        assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1920x1080'
        assert not page._pending_reverts


def test_failed_rollback_retry_preserves_external_edits():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = config(Path(tmp))
        page, cards, resolutions = display(cfg)
        other = WayfireConfigFile(cfg.path)
        other.set_option('core', 'vheight', '9'); other.save()
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            with unittest.TestCase().assertRaises(OSError): DisplayPage.revert_pending_changes(page)
        DisplayPage.revert_pending_changes(page)
        saved = WayfireConfigFile(cfg.path)
        assert saved.get_option('core', 'vheight') == '9'
        assert saved.get_option('output:DP-1', 'mode') == '1920x1080'


def test_multiple_output_rollback_retries_remaining_output():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = config(Path(tmp))
        page, cards, resolutions = display(cfg, ('DP-1', 'DP-2'))
        replace = os.replace
        count = 0
        def fail_second(src, dst):
            nonlocal count
            count += 1
            if count == 2: raise OSError('denied')
            return replace(src, dst)
        with patch('config_backend.os.replace', side_effect=fail_second):
            with unittest.TestCase().assertRaises(OSError): DisplayPage.revert_pending_changes(page)
        assert set(page._pending_reverts) == {'output:DP-2'}
        DisplayPage.revert_pending_changes(page)
        saved = WayfireConfigFile(cfg.path)
        for name in ('DP-1', 'DP-2'):
            assert saved.get_option('output:' + name, 'mode') == '1920x1080'


def test_confirmation_timeout_failure_remains_retryable():
    Gtk.init()
    callback = Mock(side_effect=[OSError('denied'), None])
    finished = Mock()
    dialog = _DisplayConfirmDialog(None, seconds=15, detail_lines=[], on_keep=Mock(),
                                   on_revert=callback, on_finished=finished)
    try:
        with patch('wcm._operation_error'):
            assert dialog._finish('revert') is False
        assert not dialog._done and dialog._timer_id
        finished.assert_not_called()
        assert dialog._finish('revert') is True
        finished.assert_called_once()
        assert dialog._done and not dialog._timer_id
    finally:
        dialog.close_silent()


def test_failed_revert_blocks_close_and_reload():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = config(Path(tmp))
        page, cards, resolutions = display(cfg)
        page.revert_pending_changes = lambda: DisplayPage.revert_pending_changes(page)
        state = SimpleNamespace(config=cfg, wf_shell_config=WayfireConfigFile(), display_page=page)
        with patch('config_backend.os.replace', side_effect=OSError('denied')), patch('wcm._operation_error'):
            assert WCM._before_close(state) is True
        # This partial page has no root: reload must return before rebuilding.
        DisplayPage.reload(page)
        assert DisplayPage._refresh_outputs(page) is True
        assert WCM._before_close(state) is False


def test_confirmation_window_close_reverts_and_retries():
    Gtk.init()
    callback = Mock(side_effect=[OSError('denied'), None])
    finished = Mock()
    dialog = _DisplayConfirmDialog(None, seconds=15, detail_lines=[], on_keep=Mock(),
                                   on_revert=callback, on_finished=finished)
    try:
        with patch('wcm._operation_error'):
            assert dialog.emit('close-request') is True
        assert not dialog._done
        assert callback.call_count == 1
        assert dialog.emit('close-request') is True
        assert dialog._done
        finished.assert_called_once()
    finally:
        dialog.close_silent()


def test_timeout_retries_automatically_after_failure():
    Gtk.init()
    from wcm import GLib
    callback = Mock(side_effect=[OSError('denied'), None])
    dialog = _DisplayConfirmDialog(None, seconds=1, detail_lines=[], on_keep=Mock(),
                                   on_revert=callback, on_finished=Mock())
    try:
        # Dispatch actual timeout sources, including the replacement created
        # inside the failed timeout, with a bounded event loop.
        import time
        deadline = time.monotonic() + 5
        with patch('wcm._operation_error'):
            while not dialog._done and time.monotonic() < deadline:
                GLib.MainContext.default().iteration(False)
                time.sleep(0.01)
        assert dialog._done and callback.call_count == 2
    finally:
        dialog.close_silent()


def test_keep_after_failed_revert_preserves_selected_mode():
    Gtk.init()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = config(Path(tmp))
        page, cards, resolutions = display(cfg)
        revert = page._pending_reverts['output:DP-1']
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            with unittest.TestCase().assertRaises(OSError): revert()
        # The failure must not leave a rollback operation to be replayed by
        # an unrelated later save after the user decides to keep the mode.
        cfg.set_option('core', 'vheight', '3'); cfg.save()
        assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1280x720'
        DisplayPage.revert_pending_changes(page)


def test_preset_staging_and_commit_failure_matrix():
    from config_backend import _replace_preset_files
    for operation, count in (('fsync', 4), ('replace', 2)):
        for failure in range(1, count + 1):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                a, b = root / 'a.ini', root / 'b.ini'
                a.write_bytes(b'original a'); b.write_bytes(b'original b')
                original = getattr(os, operation)
                calls = 0
                def injected(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == failure: raise OSError('injected failure')
                    return original(*args, **kwargs)
                with patch('config_backend.os.' + operation, side_effect=injected):
                    with unittest.TestCase().assertRaises(OSError):
                        _replace_preset_files({str(a): b'new a', str(b): b'new b'})
                assert (a.read_bytes(), b.read_bytes()) == (b'original a', b'original b')
                assert not list(root.glob('.wcm-preset-*'))


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in list(globals().items()) if name.startswith('test_'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
