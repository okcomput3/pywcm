#!/usr/bin/env python3
"""Tests for the WCM config backend — validates line-preserving behavior."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
from config_backend import WayfireConfigFile

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


def test_read_and_preserve():
    """Config read preserves all lines exactly."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.save(path + '.out')

        with open(path + '.out') as f:
            result = f.read()

        assert result == SAMPLE_CONFIG, \
            f"Round-trip failed!\n---EXPECTED---\n{SAMPLE_CONFIG}\n---GOT---\n{result}"
        print("PASS: read_and_preserve")
    finally:
        os.unlink(path)
        if os.path.exists(path + '.out'):
            os.unlink(path + '.out')


def test_get_option():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        assert cfg.get_option('core', 'vwidth') == '3'
        assert cfg.get_option('move', 'activate') == '<super> BTN_LEFT'
        assert cfg.get_option('decoration', 'title_height') == '30'
        assert cfg.get_option('core', 'nonexistent') is None
        assert cfg.get_option('nonexistent', 'foo') is None
        print("PASS: get_option")
    finally:
        os.unlink(path)


def test_set_existing_option():
    """Setting an existing option only changes that one line."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'vwidth', '5')
        cfg.save(path)

        with open(path) as f:
            lines = f.readlines()

        # Comments must be preserved
        assert lines[0] == '# Wayfire config file\n'
        assert lines[1] == '# This is a comment\n'
        assert lines[2] == '\n'

        # The changed line
        found = False
        for line in lines:
            if line.strip() == 'vwidth = 5':
                found = True
            # Old value must not be present
            assert 'vwidth = 3' not in line or 'vheight' in line
        assert found, "Changed option not found"

        # Other options unchanged
        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('core', 'vheight') == '3'
        assert cfg2.get_option('core', 'plugins') == 'move resize alpha'
        assert cfg2.get_option('move', 'activate') == '<super> BTN_LEFT'

        # Comment about core plugins still present
        assert any('# Core plugins' in l for l in lines)

        print("PASS: set_existing_option (single-line change, comments preserved)")
    finally:
        os.unlink(path)


def test_add_new_option():
    """Adding a new option to existing section appends it."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'close_top_view', '<super> KEY_Q')
        cfg.save(path)

        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('core', 'close_top_view') == '<super> KEY_Q'
        # Existing options still there
        assert cfg2.get_option('core', 'vwidth') == '3'
        print("PASS: add_new_option")
    finally:
        os.unlink(path)


def test_add_new_section():
    """Adding option to nonexistent section creates it."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('wobbly', 'spring_k', '8.0')
        cfg.save(path)

        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('wobbly', 'spring_k') == '8.0'
        # Old sections still fine
        assert cfg2.get_option('core', 'vwidth') == '3'
        print("PASS: add_new_section")
    finally:
        os.unlink(path)


def test_remove_option():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.remove_option('decoration', 'title_height')
        cfg.save(path)

        cfg2 = WayfireConfigFile(path)
        assert cfg2.get_option('decoration', 'title_height') is None
        assert cfg2.get_option('decoration', 'active_color') is not None
        print("PASS: remove_option")
    finally:
        os.unlink(path)


def test_enable_disable_plugin():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        assert cfg.get_enabled_plugins() == ['move', 'resize', 'alpha']

        cfg.enable_plugin('wobbly')
        assert 'wobbly' in cfg.get_enabled_plugins()

        cfg.disable_plugin('resize')
        assert 'resize' not in cfg.get_enabled_plugins()
        assert 'move' in cfg.get_enabled_plugins()

        cfg.save(path)
        cfg2 = WayfireConfigFile(path)
        plugins = cfg2.get_enabled_plugins()
        assert 'wobbly' in plugins
        assert 'resize' not in plugins
        print("PASS: enable_disable_plugin")
    finally:
        os.unlink(path)


def test_comments_preserved_after_multiple_edits():
    """Multiple edits should still keep all comments."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(SAMPLE_CONFIG)
        path = f.name

    try:
        cfg = WayfireConfigFile(path)
        cfg.set_option('core', 'vwidth', '4')
        cfg.set_option('move', 'activate', '<alt> BTN_LEFT')
        cfg.set_option('decoration', 'title_height', '25')
        cfg.save(path)

        with open(path) as f:
            content = f.read()

        assert '# Wayfire config file' in content
        assert '# This is a comment' in content
        assert '# Core plugins' in content
        assert '# Move plugin options' in content
        print("PASS: comments_preserved_after_multiple_edits")
    finally:
        os.unlink(path)


if __name__ == '__main__':
    test_read_and_preserve()
    test_get_option()
    test_set_existing_option()
    test_add_new_option()
    test_add_new_section()
    test_remove_option()
    test_enable_disable_plugin()
    test_comments_preserved_after_multiple_edits()
    print("\nAll tests passed!")
