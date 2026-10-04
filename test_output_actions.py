"""Output creation failure and retry coverage."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_followup import fixture
from config_backend import WayfireConfigFile
from wcm import Gtk, DisplayPage


def test_removed_output_is_not_restored_by_pending_confirmation(tmp_path):
    from test_release_safety import display
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    page.app = SimpleNamespace(config=cfg)
    page.reload = Mock()
    dialog = Mock()
    dialog.choose_finish.return_value = 1
    try:
        with patch('wcm.Gtk.AlertDialog', return_value=dialog):
            DisplayPage._confirm_remove(page, 'DP-1')
        dialog.choose.call_args.args[2](dialog, None)
        assert 'output:DP-1' not in WayfireConfigFile(cfg.path).get_sections()
        DisplayPage.revert_pending_changes(page)
        assert 'output:DP-1' not in WayfireConfigFile(cfg.path).get_sections()
    finally:
        DisplayPage.revert_pending_changes(page)


def test_removal_cancels_only_its_own_active_confirmation(tmp_path):
    import time
    from test_release_safety import display
    from wcm import GLib
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg, ('DP-1', 'DP-2'))
    page.app = None
    page.reload = Mock()
    try:
        # Finish both debounces; the second output owns the visible prompt.
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False); time.sleep(.005)
        assert page._active_confirm.owner == 'output:DP-2'
        page.app = SimpleNamespace(config=cfg)
        dialog = Mock(); dialog.choose_finish.return_value = 1
        with patch('wcm.Gtk.AlertDialog', return_value=dialog):
            DisplayPage._confirm_remove(page, 'DP-2')
        dialog.choose.call_args.args[2](dialog, None)
        assert page._active_confirm is None
        assert not page._pending_reverts and not page._confirm_sources
        assert 'output:DP-2' not in WayfireConfigFile(cfg.path).get_sections()
        assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1920x1080'
    finally:
        DisplayPage.revert_pending_changes(page)


def test_failed_output_add_does_not_leak_into_later_save(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page = SimpleNamespace(app=None, reload=Mock())
    row = DisplayPage._build_add_row(page, cfg)
    entry = row.get_first_child().get_next_sibling()
    entry.set_text('DP-9')
    with patch('config_backend.os.replace', side_effect=OSError('denied')), patch('wcm._operation_error') as report:
        row.get_last_child().emit('clicked')
        assert report.called
    cfg.set_option('core', 'vwidth', '6'); cfg.save()
    assert 'output:DP-9' not in WayfireConfigFile(cfg.path).get_sections()
    row.get_last_child().emit('clicked')
    assert WayfireConfigFile(cfg.path).get_option('output:DP-9', 'mode') == 'default'


def test_remove_failure_keeps_rollback_and_success_preserves_other_output(tmp_path):
    from test_release_safety import display
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg, ('DP-1', 'DP-2'))
    page.app = SimpleNamespace(config=cfg); page.reload = Mock()
    dialog = Mock(); dialog.choose_finish.return_value = 1
    try:
        with patch('wcm.Gtk.AlertDialog', return_value=dialog):
            DisplayPage._confirm_remove(page, 'DP-1')
        callback = dialog.choose.call_args.args[2]
        with patch('config_backend.os.replace', side_effect=OSError('denied')), patch('wcm._operation_error'):
            callback(dialog, None)
        assert set(page._pending_reverts) == {'output:DP-1', 'output:DP-2'}
        callback(dialog, None)
        assert set(page._pending_reverts) == {'output:DP-2'}
        DisplayPage.revert_pending_changes(page)
        saved = WayfireConfigFile(cfg.path)
        assert 'output:DP-1' not in saved.get_sections()
        assert saved.get_option('output:DP-2', 'mode') == '1920x1080'
    finally:
        DisplayPage.revert_pending_changes(page)


def test_output_name_cannot_create_unreadable_section(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page = SimpleNamespace(app=None, reload=Mock())
    row = DisplayPage._build_add_row(page, cfg)
    entry = row.get_first_child().get_next_sibling()
    before = open(cfg.path).read()
    entry.set_text('DP-9]')
    with patch('wcm._operation_error') as report:
        row.get_last_child().emit('clicked')
        assert report.called
    assert open(cfg.path).read() == before


def test_output_add_cleanup_warning_preserves_added_output(tmp_path):
    import os
    Gtk.init()
    cfg = fixture(tmp_path).config
    page = SimpleNamespace(app=None, reload=Mock())
    row = DisplayPage._build_add_row(page, cfg)
    row.get_first_child().get_next_sibling().set_text('DP-9')
    unlink = os.unlink
    def fail(path, *args, **kwargs):
        if '.wcm-recovery-' in str(path) and os.path.exists(path) and os.stat(path).st_size:
            raise PermissionError('cleanup denied')
        return unlink(path, *args, **kwargs)
    with patch('config_backend.os.unlink', side_effect=fail), patch('wcm._operation_error') as report:
        row.get_last_child().emit('clicked')
        report.assert_called_once()
    page.reload.assert_called_once()
    assert cfg.get_option('output:DP-9', 'mode') == 'default'
    assert WayfireConfigFile(cfg.path).get_option('output:DP-9', 'mode') == 'default'


def test_failed_output_remove_does_not_leak_into_later_save(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    cfg.set_option('output:DP-9', 'mode', 'default'); cfg.save()
    page = SimpleNamespace(app=SimpleNamespace(config=cfg), reload=Mock())
    dialog = Mock()
    dialog.choose_finish.return_value = 1
    with patch('wcm.Gtk.AlertDialog', return_value=dialog):
        DisplayPage._confirm_remove(page, 'DP-9')
    callback = dialog.choose.call_args.args[2]
    with patch('config_backend.os.replace', side_effect=OSError('denied')), patch('wcm._operation_error') as report:
        callback(dialog, None)
        report.assert_called_once()
    cfg.set_option('core', 'vwidth', '6'); cfg.save()
    assert WayfireConfigFile(cfg.path).get_option('output:DP-9', 'mode') == 'default'
