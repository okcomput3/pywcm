#!/usr/bin/env python3
"""Tests for OutputManager (display/output detection + config helpers)."""

import os
import tempfile

from config_backend import OutputManager, WayfireConfigFile

SAMPLE = """\
eDP-1 "BOE 0x095F (eDP-1)"
  Make: BOE
  Physical size: 290x190 mm
  Enabled: yes
  Modes:
    1920x1080 px, 60.008888 Hz (preferred, current)
    1280x720 px, 60.000000 Hz
  Position: 0,0
  Transform: normal
  Scale: 1.000000
HDMI-A-1 "Samsung S24D300 (HDMI-A-1)"
  Enabled: yes
  Modes:
    2560x1440 px, 144.000000 Hz (current)
    1920x1080 px, 60.000000 Hz (preferred)
  Position: 1920,0
  Transform: flipped-90
  Scale: 1.500000
DP-2 "Dell (DP-2)"
  Enabled: no
  Modes:
    1920x1080 px, 60.000000 Hz (preferred)
"""


def test_parse_basic():
    outs = OutputManager()._parse(SAMPLE)
    assert [o["name"] for o in outs] == ["eDP-1", "HDMI-A-1", "DP-2"]
    edp = outs[0]
    assert edp["enabled"] is True
    assert edp["current_mode"] == (1920, 1080, 60009)   # Hz -> mHz
    assert edp["position"] == (0, 0)
    assert edp["transform"] == "normal"
    assert edp["scale"] == 1.0
    assert len(edp["modes"]) == 2
    print("PASS: parse_basic")


def test_parse_transform_mapping():
    outs = OutputManager()._parse(SAMPLE)
    # wlr-randr 'flipped-90' must map to wayfire's '90_flipped'
    assert outs[1]["transform"] == "90_flipped"
    assert outs[1]["scale"] == 1.5
    assert outs[1]["current_mode"] == (2560, 1440, 144000)
    print("PASS: parse_transform_mapping")


def test_parse_disabled_output():
    outs = OutputManager()._parse(SAMPLE)
    dp2 = outs[2]
    assert dp2["enabled"] is False
    assert dp2["current_mode"] is None
    assert dp2["position"] is None          # no Position line when disabled
    assert len(dp2["modes"]) == 1
    print("PASS: parse_disabled_output")


def test_section_name():
    assert OutputManager.section_name("HDMI-A-1") == "output:HDMI-A-1"
    print("PASS: section_name")


def test_list_configured_outputs():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "wayfire.ini")
        open(p, "w").write(
            "[core]\nplugins = move\n\n"
            "[output:eDP-1]\nmode = 1920x1080@60000\n\n"
            "[output:HDMI-A-1]\nmode = off\n\n"
            "[move]\nactivate = <super> BTN_LEFT\n"
        )
        cfg = WayfireConfigFile(p)
        assert OutputManager.list_configured_outputs(cfg) == ["eDP-1", "HDMI-A-1"]
    print("PASS: list_configured_outputs")


def test_detect_unavailable():
    # In an environment without wlr-randr / wayland, detect() must not raise.
    assert isinstance(OutputManager().detect(), list)
    print("PASS: detect_unavailable")


MODES = [
    {"width": 1920, "height": 1080, "refresh": 60000},
    {"width": 1920, "height": 1080, "refresh": 144000},
    {"width": 1280, "height": 720, "refresh": 60000},
]


def test_validate_mode():
    vm = OutputManager.validate_mode
    # disabled output is always fine
    assert vm("garbage", 0, False, MODES)[0] == "ok"
    # empty resolution -> auto/default, fine
    assert vm("", 0, True, MODES)[0] == "ok"
    # malformed resolution -> error (must not be written)
    assert vm("19201080", 0, True, MODES)[0] == "error"
    assert vm("1920x", 0, True, MODES)[0] == "error"
    # unparseable refresh (signalled as -1) -> error
    assert vm("1920x1080", -1, True, MODES)[0] == "error"
    # well-formed + advertised -> ok
    assert vm("1920x1080", 60000, True, MODES)[0] == "ok"
    # advertised resolution but unlisted refresh -> warn (allowed, flagged)
    assert vm("1920x1080", 75000, True, MODES)[0] == "warn"
    # resolution the monitor doesn't advertise -> error (blocks a bad mode)
    assert vm("3840x2160", 60000, True, MODES)[0] == "error"
    # with no known modes, only format is checked: well-formed passes
    assert vm("3840x2160", 60000, True, [])[0] == "ok"
    assert vm("nope", 0, True, [])[0] == "error"
    print("PASS: validate_mode")


def test_remove_section():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "wayfire.ini")
        open(p, "w").write(
            "[core]\nplugins = move\n\n"
            "[output:eDP-1]\nmode = 1920x1080@60000\nscale = 1.0\n\n"
            "# external monitor\n[output:HDMI-A-1]\nmode = off\n\n"
            "[move]\nactivate = <super> BTN_LEFT\n"
        )
        cfg = WayfireConfigFile(p)
        cfg.remove_section("output:eDP-1")
        cfg.save()
        cfg2 = WayfireConfigFile(p)
        assert "output:eDP-1" not in cfg2.get_sections()
        # other sections survive
        assert "core" in cfg2.get_sections()
        assert "output:HDMI-A-1" in cfg2.get_sections()
        assert "move" in cfg2.get_sections()
        # the comment introducing the *next* section is preserved
        text = open(p).read()
        assert "# external monitor" in text
        assert cfg2.get_option("move", "activate") == "<super> BTN_LEFT"
    print("PASS: remove_section")


if __name__ == "__main__":
    test_parse_basic()
    test_parse_transform_mapping()
    test_parse_disabled_output()
    test_section_name()
    test_list_configured_outputs()
    test_detect_unavailable()
    test_validate_mode()
    test_remove_section()
    print("\nAll output tests passed!")
