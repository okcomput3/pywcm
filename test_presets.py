#!/usr/bin/env python3
"""Tests for the WCM preset system."""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(__file__))
from config_backend import WayfireConfigFile, PresetManager

SAMPLE_CONFIG = """\
# Wayfire config file
# This is a comment

[core]
# Core plugins
plugins = move resize alpha
vwidth = 3
vheight = 3

[move]
# Move plugin options
activate = <super> BTN_LEFT

[decoration]
active_color = 0.36 0.8 0.72 1.0
title_height = 30
"""


def test_save_and_load_master_preset():
    """Master preset saves all options and loads them back."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        # Save a master preset
        pm.save_master_preset("test_preset", cfg)
        assert "test_preset" in pm.list_master_presets()

        # Change the config
        cfg.set_option('core', 'vwidth', '7')
        cfg.set_option('decoration', 'title_height', '50')
        cfg.save()
        assert cfg.get_option('core', 'vwidth') == '7'
        assert cfg.get_option('decoration', 'title_height') == '50'

        # Load the preset — should restore old values
        pm.load_master_preset("test_preset", cfg)
        assert cfg.get_option('core', 'vwidth') == '3'
        assert cfg.get_option('decoration', 'title_height') == '30'

        # Comments should still be preserved
        with open(cfg_path) as fh:
            content = fh.read()
        assert '# Wayfire config file' in content
        assert '# This is a comment' in content
        assert '# Core plugins' in content

        print("PASS: save_and_load_master_preset")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_save_and_load_plugin_preset():
    """Plugin preset saves/loads only one plugin section."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        # Save decoration plugin preset
        pm.save_plugin_preset("my_colors", "decoration", cfg)
        assert "my_colors" in pm.list_plugin_presets("decoration")

        # Change the decoration options
        cfg.set_option('decoration', 'title_height', '99')
        cfg.set_option('decoration', 'active_color', '1.0 0 0 1.0')
        cfg.save()

        # Load preset — should restore decoration only
        pm.load_plugin_preset("my_colors", "decoration", cfg)
        assert cfg.get_option('decoration', 'title_height') == '30'
        assert cfg.get_option('decoration', 'active_color') == '0.36 0.8 0.72 1.0'

        # Other sections untouched
        assert cfg.get_option('core', 'vwidth') == '3'

        print("PASS: save_and_load_plugin_preset")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_delete_master_preset():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        pm.save_master_preset("deleteme", cfg)
        assert "deleteme" in pm.list_master_presets()

        pm.delete_master_preset("deleteme")
        assert "deleteme" not in pm.list_master_presets()

        print("PASS: delete_master_preset")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_delete_plugin_preset():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        pm.save_plugin_preset("temp", "move", cfg)
        assert "temp" in pm.list_plugin_presets("move")

        pm.delete_plugin_preset("temp", "move")
        assert "temp" not in pm.list_plugin_presets("move")

        print("PASS: delete_plugin_preset")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_multiple_master_presets():
    """Multiple presets coexist and can be switched between."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        # Save "preset_A" with defaults
        pm.save_master_preset("preset_A", cfg)

        # Change config and save "preset_B"
        cfg.set_option('core', 'vwidth', '5')
        cfg.set_option('core', 'vheight', '5')
        cfg.save()
        pm.save_master_preset("preset_B", cfg)

        names = pm.list_master_presets()
        assert "preset_A" in names
        assert "preset_B" in names

        # Load preset_A
        pm.load_master_preset("preset_A", cfg)
        assert cfg.get_option('core', 'vwidth') == '3'
        assert cfg.get_option('core', 'vheight') == '3'

        # Load preset_B
        pm.load_master_preset("preset_B", cfg)
        assert cfg.get_option('core', 'vwidth') == '5'
        assert cfg.get_option('core', 'vheight') == '5'

        print("PASS: multiple_master_presets")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_plugin_preset_preserves_enabled():
    """Plugin preset records and restores enabled state."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        # move is in plugins list -> enabled
        assert 'move' in cfg.get_enabled_plugins()

        # Save preset with move enabled
        pm.save_plugin_preset("move_on", "move", cfg)

        # Disable move and save another preset
        cfg.disable_plugin('move')
        cfg.save()
        assert 'move' not in cfg.get_enabled_plugins()
        pm.save_plugin_preset("move_off", "move", cfg)

        # Load move_on — should re-enable
        pm.load_plugin_preset("move_on", "move", cfg)
        assert 'move' in cfg.get_enabled_plugins()

        # Load move_off — should disable
        pm.load_plugin_preset("move_off", "move", cfg)
        assert 'move' not in cfg.get_enabled_plugins()

        print("PASS: plugin_preset_preserves_enabled")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_master_preset_single_line_changes():
    """Loading a master preset preserves comments (single-line changes)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    preset_dir = tempfile.mkdtemp()
    try:
        cfg = WayfireConfigFile(cfg_path)
        pm = PresetManager(preset_dir)

        # Change config
        cfg.set_option('core', 'vwidth', '10')
        cfg.save()

        # Save preset with changed value
        pm.save_master_preset("modified", cfg)

        # Reload original
        cfg2 = WayfireConfigFile(cfg_path)
        pm.load_master_preset("modified", cfg2)

        # Read the file and check comments are intact
        with open(cfg_path) as fh:
            content = fh.read()
        assert '# Wayfire config file' in content
        assert '# This is a comment' in content
        assert '# Core plugins' in content
        assert '# Move plugin options' in content
        assert 'vwidth = 10' in content

        print("PASS: master_preset_single_line_changes")
    finally:
        os.unlink(cfg_path)
        shutil.rmtree(preset_dir)


def test_get_all_options():
    """get_all_options returns complete snapshot."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        cfg_path = f.name

    try:
        cfg = WayfireConfigFile(cfg_path)
        all_opts = cfg.get_all_options()

        assert 'core' in all_opts
        assert 'move' in all_opts
        assert 'decoration' in all_opts
        assert all_opts['core']['vwidth'] == '3'
        assert all_opts['move']['activate'] == '<super> BTN_LEFT'
        assert all_opts['decoration']['title_height'] == '30'

        print("PASS: get_all_options")
    finally:
        os.unlink(cfg_path)


def test_sanitize_name():
    """Preset names with special characters are sanitized."""
    pm = PresetManager(tempfile.mkdtemp())
    assert pm._sanitize("my preset") == "my preset"
    assert pm._sanitize("my/preset") == "my_preset"
    assert pm._sanitize("a\\b") == "a_b"
    assert pm._sanitize("  spaces  ") == "spaces"
    print("PASS: sanitize_name")


if __name__ == '__main__':
    test_get_all_options()
    test_save_and_load_master_preset()
    test_save_and_load_plugin_preset()
    test_delete_master_preset()
    test_delete_plugin_preset()
    test_multiple_master_presets()
    test_plugin_preset_preserves_enabled()
    test_master_preset_single_line_changes()
    test_sanitize_name()
    print("\nAll preset tests passed!")