"""Display save failures and preset/confirmation transitions."""
from pathlib import Path
from unittest.mock import Mock, patch

from config_backend import WayfireConfigFile, OutputManager
from test_followup import fixture
from test_release_safety import display
from wcm import Gtk, GLib, WCM, DisplayPage, _DisplayConfirmDialog


def test_plugin_committed_warning_keeps_preset_and_cancels_old_typing(tmp_path):
    import os
    from config_backend import SaveCommittedError
    from metadata import Option, OptionType, Plugin
    from wcm import OptionWidget
    Gtk.init()
    window = fixture(tmp_path)
    cfg = window.config
    cfg.set_option('demo', 'text', 'preset'); cfg.save()
    window.preset_mgr.save_plugin_preset('saved', 'demo', cfg)
    cfg.set_option('demo', 'text', 'old'); cfg.save()
    widget = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), cfg, Plugin(name='demo'))
    other = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), cfg, Plugin(name='other'))
    widget.ed.set_text('obsolete typing'); other.ed.set_text('keep typing')
    unlink = os.unlink
    def fail(path, *args, **kwargs):
        if '.wcm-recovery-' in str(path) and os.path.exists(path) and os.stat(path).st_size:
            raise PermissionError('cleanup denied')
        return unlink(path, *args, **kwargs)
    try:
        with patch('config_backend.os.unlink', side_effect=fail):
            try:
                window.preset_mgr.load_plugin_preset('saved', 'demo', cfg)
            except SaveCommittedError:
                pass
            else:
                raise AssertionError('expected cleanup warning')
        assert cfg.get_option('demo', 'text') == 'preset'
        assert widget not in cfg._pending_edits and other in cfg._pending_edits
        cfg.flush_pending_edits()
        saved = WayfireConfigFile(cfg.path)
        assert saved.get_option('demo', 'text') == 'preset'
        assert saved.get_option('other', 'text') == 'keep typing'
    finally:
        cfg.cancel_pending_edits()


def test_plugin_committed_warning_refreshes_page_before_reporting(tmp_path):
    from types import SimpleNamespace
    from config_backend import SaveCommittedError
    from metadata import Plugin
    window = fixture(tmp_path)
    window.current_plugin = Plugin(name='demo')
    window._plugin_combo = Mock()
    window._plugin_combo.get_active_text.return_value = 'saved'
    window._cfg_for = lambda plugin: window.config
    window.ec = Mock(); window._on_pe = Mock(); window.open_page = Mock()
    window.preset_mgr = Mock()
    window.preset_mgr.load_plugin_preset.side_effect = SaveCommittedError('saved; cleanup failed')
    with patch('wcm._operation_error') as report, patch('wcm._preset_error') as failure:
        WCM._on_plugin_load(window, None)
        window.open_page.assert_called_once_with(window.current_plugin)
        report.assert_called_once()
        failure.assert_not_called()


def test_keep_ignores_invalid_or_incomplete_mode_input(tmp_path):
    import time
    Gtk.init()
    for field, text in (('resolution', 'not-a-mode'), ('refresh', 'bad-refresh'), ('resolution', '')):
        cfg = fixture(tmp_path).config
        page, cards, resolutions = display(cfg)
        refresh = cards[0].get_child().get_first_child().get_next_sibling().get_next_sibling().get_last_child()
        try:
            deadline = time.monotonic() + 2
            while page._active_confirm is None and time.monotonic() < deadline:
                GLib.MainContext.default().iteration(False); time.sleep(.005)
            assert page._active_confirm is not None
            (resolutions[0] if field == 'resolution' else refresh).get_child().set_text(text)
            page._active_confirm._finish('keep')
            assert resolutions[0].get_child().get_text() == '1280x720'
            assert refresh.get_child().get_text() == ''
            resolutions[0].get_child().set_text('1600x900')
            DisplayPage.revert_pending_changes(page)
            assert resolutions[0].get_child().get_text() == '1280x720'
            assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1280x720'
        finally:
            DisplayPage.revert_pending_changes(page)


def test_failed_disable_keeps_pending_mode_revert(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    switch = cards[0].get_child().get_first_child().get_first_child().get_next_sibling().get_next_sibling()
    with patch('config_backend.os.replace', side_effect=OSError('denied')):
        switch.set_active(False)
    assert switch.get_active()
    DisplayPage.revert_pending_changes(page)
    assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1920x1080'


def test_post_commit_verification_error_identifies_saved_state(tmp_path):
    import builtins
    from config_backend import SaveCommittedError
    cfg = fixture(tmp_path).config
    cfg.set_option('core', 'vwidth', '9')
    original_open = builtins.open
    def fail(path, *args, **kwargs):
        if '.wcm-recovery-' in str(path):
            raise OSError('verification read denied')
        return original_open(path, *args, **kwargs)
    with patch('builtins.open', side_effect=fail):
        try:
            cfg.save()
        except SaveCommittedError as error:
            assert 'Recovery file:' in str(error)
        else:
            raise AssertionError('expected committed warning')
    assert not cfg._operations
    assert WayfireConfigFile(cfg.path).get_option('core', 'vwidth') == '9'
    assert list(tmp_path.glob('.wcm-recovery-*'))


def test_cleanup_failure_keeps_committed_mode_and_confirmation(tmp_path):
    import os
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    DisplayPage.revert_pending_changes(page)
    unlink = os.unlink
    def fail(path, *args, **kwargs):
        if '.wcm-recovery-' in str(path) and os.path.exists(path) and os.stat(path).st_size:
            raise PermissionError('cleanup denied')
        return unlink(path, *args, **kwargs)
    with patch('config_backend.os.unlink', side_effect=fail):
        resolutions[0].get_child().set_text('1600x900')
    assert cfg.get_option('output:DP-1', 'mode') == '1600x900'
    assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1600x900'
    assert not cfg._operations and page._pending_reverts
    DisplayPage.revert_pending_changes(page)
    assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1920x1080'


def test_keep_after_failed_second_edit_has_consistent_baseline(tmp_path):
    import time
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    try:
        deadline = time.monotonic() + 2
        while page._active_confirm is None and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False); time.sleep(.005)
        assert page._active_confirm is not None
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            resolutions[0].get_child().set_text('1600x900')
        page._active_confirm._finish('keep')
        resolutions[0].get_child().set_text('1920x1080')
        DisplayPage.revert_pending_changes(page)
        assert resolutions[0].get_child().get_text() == '1280x720'
        assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1280x720'
        # A failed edit after rollback must use that restored baseline too.
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            resolutions[0].get_child().set_text('1600x900')
        assert resolutions[0].get_child().get_text() == '1280x720'
    finally:
        DisplayPage.revert_pending_changes(page)


def test_failed_initial_display_changes_never_leak_into_later_save(tmp_path):
    Gtk.init()
    window = fixture(tmp_path)
    cfg = window.config
    page, cards, resolutions = display(cfg)
    page.revert_pending_changes = lambda: DisplayPage.revert_pending_changes(page)
    page.revert_pending_changes()
    box = cards[0].get_child()
    rows = []
    child = box.get_first_child()
    while child:
        rows.append(child)
        child = child.get_next_sibling()
    rotation = rows[5].get_last_child()
    for change in (lambda: resolutions[0].get_child().set_text('1600x900'),
                   lambda: rotation.set_active(1)):
        original = Path(cfg.path).read_bytes()
        with patch('config_backend.os.replace', side_effect=OSError('denied')):
            change()
        assert Path(cfg.path).read_bytes() == original
        assert not page._pending_reverts
        cfg.set_option('core', 'vwidth', '5'); cfg.save()
        saved = WayfireConfigFile(cfg.path)
        assert saved.get_option('output:DP-1', 'mode') == '1920x1080'
        assert saved.get_option('output:DP-1', 'transform') is None


def test_failed_mode_change_can_be_retried_and_reverted(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    DisplayPage.revert_pending_changes(page)
    with patch('config_backend.os.replace', side_effect=OSError('denied')):
        resolutions[0].get_child().set_text('1600x900')
    resolutions[0].get_child().set_text('1280x720')
    assert page._pending_reverts
    assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1280x720'
    DisplayPage.revert_pending_changes(page)
    assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1920x1080'


def test_master_load_rebuilds_display_with_new_config_and_baseline(tmp_path):
    Gtk.init()
    window = fixture(tmp_path)
    cfg = window.config
    cfg.set_option('output:DP-1', 'mode', '1600x900'); cfg.save()
    window.preset_mgr.save_master_preset_file('chosen', cfg.path, window.wf_shell_config.path)
    cfg.set_option('output:DP-1', 'mode', '1920x1080'); cfg.save()
    detected = [dict(name='DP-1', enabled=True, modes=[])]
    with patch.object(OutputManager, 'detect', return_value=detected):
        page = DisplayPage(window)
        window.display_page = page
        with patch('wcm._preset_error') as errors:
            WCM._on_master_load(window, None)
            errors.assert_not_called()
        card = page._root.get_first_child()
        resolution = card.get_child().get_first_child().get_next_sibling().get_last_child()
        assert resolution.get_child().get_text() == '1600x900'
        resolution.get_child().set_text('1280x720')
        page.revert_pending_changes()
        assert window.config.get_option('output:DP-1', 'mode') == '1600x900'
        assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1600x900'


def test_repeated_timeout_errors_stay_inline_and_eventually_recover(tmp_path):
    Gtk.init()
    import time
    callback = Mock(side_effect=[OSError('first denial'), OSError('second denial'), None])
    done = Mock()
    dialog = _DisplayConfirmDialog(None, seconds=1, detail_lines=[], on_keep=Mock(),
                                   on_revert=callback, on_finished=done)
    before = set(Gtk.Window.get_toplevels())
    try:
        deadline = time.monotonic() + 6
        while not dialog._done and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(.01)
            assert not [w for w in Gtk.Window.get_toplevels()
                        if w not in before and isinstance(w, Gtk.MessageDialog)]
        assert dialog._done and callback.call_count == 3
        assert 'second denial' in dialog._error_lbl.get_text()
        done.assert_called_once()
    finally:
        dialog.close_silent()
