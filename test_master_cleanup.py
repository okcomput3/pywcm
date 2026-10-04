"""Master preset cleanup errors must not conceal completed replacement."""
import os
from pathlib import Path
from unittest.mock import patch, Mock
from test_followup import fixture
from config_backend import WayfireConfigFile, SaveCommittedError
from metadata import Option, OptionType, Plugin
from wcm import Gtk, WCM, OptionWidget


def cleanup_failure():
    unlink = os.unlink
    def fail(path, *args, **kwargs):
        if '.wcm-preset-' in str(path) and os.path.exists(path):
            raise PermissionError('backup cleanup denied')
        return unlink(path, *args, **kwargs)
    return patch('config_backend.os.unlink', side_effect=fail)


def test_master_load_cleanup_warning_refreshes_and_cancels_old_typing(tmp_path):
    Gtk.init()
    window = fixture(tmp_path)
    window.config.set_option('demo', 'text', 'preset'); window.config.save()
    window.preset_mgr.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
    window.config.set_option('demo', 'text', 'old'); window.config.save()
    old = window.config
    editor = OptionWidget(Option(name='text', type=OptionType.STRING, default_value=''), old, Plugin(name='demo'))
    editor.ed.set_text('obsolete typing')
    try:
        with cleanup_failure(), patch('wcm._operation_error') as warning, patch('wcm._preset_error') as failure:
            WCM._on_master_load(window, None)
            warning.assert_called_once()
            failure.assert_not_called()
        assert window.config is not old
        assert not old._pending_edits
        old.flush_pending_edits()
        assert window.config.get_option('demo', 'text') == 'preset'
        assert WayfireConfigFile(old.path).get_option('demo', 'text') == 'preset'
    finally:
        old.cancel_pending_edits()


def test_master_cleanup_error_identifies_committed_pair(tmp_path):
    window = fixture(tmp_path)
    manager = window.preset_mgr
    manager.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
    window.config.set_option('demo', 'text', 'new'); window.config.save()
    window.wf_shell_config.set_option('panel', 'position', 'bottom'); window.wf_shell_config.save()
    with cleanup_failure():
        try: manager.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
        except SaveCommittedError as error:
            assert 'Recovery files:' in str(error)
        else: raise AssertionError('expected committed cleanup warning')
    assert WayfireConfigFile(manager._master_path('chosen')).get_option('demo', 'text') == 'new'
    assert WayfireConfigFile(manager._master_wfshell_path('chosen')).get_option('panel', 'position') == 'bottom'


def test_preset_name_roundtrip_matrix(tmp_path):
    window = fixture(tmp_path)
    manager = window.preset_mgr
    for name in ('normal', 'two words', '测试', '.hidden', '..', 'path/name', 'a?b'):
        manager.save_master_preset_file(name, window.config.path, window.wf_shell_config.path)
        safe = manager._sanitize(name)
        assert safe in manager.list_master_presets()
        manager.load_master_preset_file(safe, window.config.path, window.wf_shell_config.path)
        assert WayfireConfigFile(window.config.path).get_enabled_plugins() == ['move']


def test_master_save_warning_refreshes_saved_selection(tmp_path):
    window = fixture(tmp_path)
    manager = window.preset_mgr
    manager.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
    window.config.set_option('demo', 'text', 'new'); window.config.save()
    window._refresh_master_presets = Mock()
    model = Mock()
    model.get_iter_first.return_value = object()
    model.get_value.return_value = 'chosen'
    window._master_combo.get_model.return_value = model
    window._prompt_name = lambda title, callback: callback('chosen')
    with cleanup_failure(), patch('wcm._operation_error') as warning, patch('wcm._preset_error') as error:
        WCM._on_master_save(window, None)
        warning.assert_called_once(); error.assert_not_called()
    window._refresh_master_presets.assert_called_once()
    window._master_combo.set_active.assert_called_once_with(0)
    assert WayfireConfigFile(manager._master_path('chosen')).get_option('demo', 'text') == 'new'


def test_master_delete_warning_refreshes_removed_selection(tmp_path):
    window = fixture(tmp_path)
    manager = window.preset_mgr
    manager.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
    window._refresh_master_presets = Mock()
    with cleanup_failure(), patch('wcm._operation_error') as warning, patch('wcm._preset_error') as error:
        WCM._on_master_delete(window, None)
        warning.assert_called_once(); error.assert_not_called()
    window._refresh_master_presets.assert_called_once()
    assert not Path(manager._master_path('chosen')).exists()
    assert not Path(manager._master_wfshell_path('chosen')).exists()


def test_cleanup_failure_does_not_mask_original_preset_failure(tmp_path):
    window = fixture(tmp_path)
    manager = window.preset_mgr
    manager.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
    before = Path(manager._master_path('chosen')).read_bytes()
    with cleanup_failure(), patch('config_backend.os.replace', side_effect=OSError('primary replacement failure')):
        try: manager.save_master_preset_file('chosen', window.config.path, window.wf_shell_config.path)
        except OSError as error:
            assert not isinstance(error, SaveCommittedError)
            assert 'primary replacement failure' in str(error)
            assert 'Temporary recovery files retained:' in error.__notes__[0]
        else: raise AssertionError('expected replacement error')
    assert Path(manager._master_path('chosen')).read_bytes() == before
