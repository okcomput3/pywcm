"""Boundary sequences between display edits and preset snapshots."""
from unittest.mock import Mock, patch
from config_backend import WayfireConfigFile
from test_followup import fixture
from test_release_safety import display
from wcm import Gtk, DisplayPage, WCM


def test_invalid_resolution_cannot_show_disabled_output_as_enabled(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    switch = cards[0].get_child().get_first_child().get_first_child().get_next_sibling().get_next_sibling()
    try:
        DisplayPage.revert_pending_changes(page)
        resolutions[0].get_child().set_text('invalid-mode')
        switch.set_active(False)
        assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == 'off'
        switch.set_active(True)
        saved = WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode')
        assert switch.get_active() == (saved != 'off')
        assert saved == '1920x1080'
        assert resolutions[0].get_child().get_text() == '1920x1080'
    finally:
        DisplayPage.revert_pending_changes(page)


def test_save_master_flushes_both_configs_and_preserves_display_state(tmp_path):
    from metadata import Option, OptionType, Plugin
    from wcm import OptionWidget
    Gtk.init()
    window = fixture(tmp_path)
    page, cards, resolutions = display(window.config)
    DisplayPage.revert_pending_changes(page)
    window.display_page = page
    editors = []
    for cfg in (window.config, window.wf_shell_config):
        editor = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), cfg, Plugin(name='demo'))
        editor.ed.set_text('last keystroke'); editors.append(editor)
    window._refresh_master_presets = Mock()
    window._master_combo.get_model.return_value.get_iter_first.return_value = None
    window._prompt_name = lambda title, callback: callback('snapshot')
    try:
        with patch('wcm._preset_error') as error:
            WCM._on_master_save(window, None)
            error.assert_not_called()
        manager = window.preset_mgr
        for path in (manager._master_path('snapshot'), manager._master_wfshell_path('snapshot')):
            assert WayfireConfigFile(path).get_option('demo', 'text') == 'last keystroke'
        assert WayfireConfigFile(manager._master_path('snapshot')).get_option('output:DP-1', 'mode') == '1920x1080'
    finally:
        window.config.cancel_pending_edits(); window.wf_shell_config.cancel_pending_edits()


def test_invalid_refresh_and_blank_resolution_do_not_break_toggle(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    header = cards[0].get_child().get_first_child()
    switch = header.get_first_child().get_next_sibling().get_next_sibling()
    refresh = header.get_next_sibling().get_next_sibling().get_last_child()
    try:
        DisplayPage.revert_pending_changes(page)
        for entry, value in ((refresh.get_child(), 'bad-refresh'), (resolutions[0].get_child(), '')):
            entry.set_text(value)
            switch.set_active(False)
            switch.set_active(True)
            assert switch.get_active()
            assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == '1920x1080'
            assert resolutions[0].get_child().get_text() == '1920x1080'
    finally:
        DisplayPage.revert_pending_changes(page)


def test_failed_save_master_does_not_replace_existing_snapshot(tmp_path):
    window = fixture(tmp_path)
    manager = window.preset_mgr
    manager.save_master_preset_file('snapshot', window.config.path, window.wf_shell_config.path)
    from pathlib import Path
    before = Path(manager._master_path('snapshot')).read_bytes()
    window.config.set_option('core', 'vwidth', '9'); window.config.save()
    window._prompt_name = lambda title, callback: callback('snapshot')
    window._refresh_master_presets = Mock()
    with patch('config_backend.os.replace', side_effect=OSError('denied')), patch('wcm._preset_error') as error:
        WCM._on_master_save(window, None)
        error.assert_called_once()
    assert Path(manager._master_path('snapshot')).read_bytes() == before
    window._refresh_master_presets.assert_not_called()


def test_repeated_toggles_and_failed_enable_preserve_saved_mode(tmp_path):
    Gtk.init()
    cfg = fixture(tmp_path).config
    page, cards, resolutions = display(cfg)
    header = cards[0].get_child().get_first_child()
    switch = header.get_first_child().get_next_sibling().get_next_sibling()
    try:
        DisplayPage.revert_pending_changes(page)
        for automatic in (False, True):
            if automatic:
                resolutions[0].set_active_id('default')
                # Commit the new baseline through an off/on transition.
            expected = 'default' if automatic else '1920x1080'
            for _ in range(5):
                switch.set_active(False)
                assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == 'off'
                with patch('config_backend.os.replace', side_effect=OSError('enable denied')):
                    switch.set_active(True)
                assert not switch.get_active()
                assert not resolutions[0].get_sensitive()
                assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == 'off'
                switch.set_active(True)
                assert switch.get_active() and resolutions[0].get_sensitive()
                assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == expected
            DisplayPage.revert_pending_changes(page)
            assert WayfireConfigFile(cfg.path).get_option('output:DP-1', 'mode') == expected
    finally:
        DisplayPage.revert_pending_changes(page)
