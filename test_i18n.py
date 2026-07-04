"""Tests for the i18n layer and the display mode-string helpers."""

import os
import re
import glob
import gettext as gt

import i18n


# ---------------------------------------------------------------------------
# .po parsing / .mo compilation
# ---------------------------------------------------------------------------

def test_parse_po_basic(tmp_path):
    po = tmp_path / "t.po"
    po.write_text(
        'msgid ""\n'
        'msgstr "Content-Type: text/plain; charset=UTF-8\\n"\n'
        '\n'
        'msgid "Save"\n'
        'msgstr "Guardar"\n'
        '\n'
        'msgid ""\n'
        '"Multi "\n'
        '"line"\n'
        'msgstr "Multilínea"\n'
        '\n'
        '#, fuzzy\n'
        'msgid "Fuzzy"\n'
        'msgstr "Borroso"\n',
        encoding="utf-8",
    )
    entries = i18n.parse_po(str(po))
    assert entries["Save"] == "Guardar"
    assert entries["Multi line"] == "Multilínea"
    assert "Fuzzy" not in entries  # fuzzy entries are skipped
    print("PASS: parse_po")


def test_compile_mo_roundtrip(tmp_path):
    entries = {
        "": "Content-Type: text/plain; charset=UTF-8\n",
        "Save": "Guardar",
        "Remove output \u201c{name}\u201d?": "¿Eliminar «{name}»?",
    }
    mo = tmp_path / "es" / "LC_MESSAGES" / "wcm.mo"
    i18n.compile_mo(entries, str(mo))
    tr = gt.translation("wcm", localedir=str(tmp_path), languages=["es"])
    assert tr.gettext("Save") == "Guardar"
    assert tr.gettext("unknown msgid") == "unknown msgid"
    print("PASS: compile_mo roundtrip via stdlib gettext")


def test_shipped_catalogs_compile_and_resolve(tmp_path, monkeypatch):
    here = os.path.dirname(os.path.abspath(i18n.__file__))
    pos = glob.glob(os.path.join(here, "locale", "*", "LC_MESSAGES", "wcm.po"))
    assert pos, "no shipped .po files found"
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    for lang, probe, expect in (
        ("es_ES", "Save", "Guardar"),
        ("ro", "Save", "Salvează"),
        ("zh_CN", "Save", "保存"),
    ):
        monkeypatch.setenv("WCM_LANG", lang)
        i18n._metadata_cache.clear()
        tr = i18n.init()
        assert tr.gettext(probe) == expect, (lang, tr.gettext(probe))
    # unknown language falls back to English
    monkeypatch.setenv("WCM_LANG", "tlh")
    assert i18n.init().gettext("Save") == "Save"
    monkeypatch.delenv("WCM_LANG")
    i18n.init()
    print("PASS: shipped catalogs resolve for es_ES / ro / zh_CN")


def test_all_shipped_msgstrs_keep_format_fields():
    """Every {placeholder} in a msgid must survive into its msgstr,
    otherwise .format() at runtime silently drops information."""
    here = os.path.dirname(os.path.abspath(i18n.__file__))
    for po in glob.glob(os.path.join(here, "locale", "*", "LC_MESSAGES", "wcm.po")):
        entries = i18n.parse_po(po)
        for msgid, msgstr in entries.items():
            fields = set(re.findall(r"\{(\w+)\}", msgid))
            for f in fields:
                assert ("{%s}" % f) in msgstr, (po, msgid, f)
    print("PASS: format placeholders preserved in all catalogs")


def test_metadata_domain(tmp_path, monkeypatch):
    """Plugin metadata strings translate via wf-plugin-<name>, like C++ WCM."""
    mo = tmp_path / "es_ES" / "LC_MESSAGES" / "wf-plugin-move.mo"
    i18n.compile_mo(
        {"": "Content-Type: text/plain; charset=UTF-8\n", "Move": "Mover"},
        str(mo))
    monkeypatch.setenv("WCM_LOCALEDIR", str(tmp_path))
    monkeypatch.setenv("WCM_LANG", "es_ES")
    i18n._metadata_cache.clear()
    i18n.init()
    assert i18n.gettext_metadata("move", "Move") == "Mover"
    assert i18n.gettext_metadata("scale", "Scale") == "Scale"  # no catalog
    monkeypatch.delenv("WCM_LOCALEDIR")
    monkeypatch.delenv("WCM_LANG")
    i18n._metadata_cache.clear()
    i18n.init()
    print("PASS: per-plugin metadata domains")


# ---------------------------------------------------------------------------
# Display mode-string helpers (module-level functions in wcm.py; exercised
# without GTK by executing just their source block)
# ---------------------------------------------------------------------------

def _load_helpers():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "wcm.py"), encoding="utf-8").read()
    start = src.index("def _parse_refresh")
    end = src.index("class _DisplayConfirmDialog")
    ns = {"re": re, "_": lambda s: s}
    exec(src[start:end], ns)
    return ns


def test_mode_helpers():
    ns = _load_helpers()
    pm, bm = ns["_parse_mode"], ns["_build_mode"]
    pr, fr, mh = ns["_parse_refresh"], ns["_fmt_refresh"], ns["_mode_human"]

    assert pm("1920x1080@60000") == ("1920x1080", 60000, False)  # mHz (wayfire)
    assert pm("1920x1080@60") == ("1920x1080", 60000, False)     # Hz tolerated
    assert pm("1920x1080@59.97") == ("1920x1080", 59970, False)
    assert pm("1920x1080") == ("1920x1080", 0, False)
    assert pm("off") == ("", 0, True)
    assert pm("default") == ("", 0, False)
    assert pm("mirror eDP-1") == ("", 0, False)
    assert pm(None) == ("", 0, False)
    assert pm("garbage") == ("", 0, False)

    assert fr(60000) == "60.000 Hz"
    assert fr(0) == "" and fr(None) == ""
    assert pr("60.000 Hz") == 60000       # round-trips _fmt_refresh
    assert pr("59.97") == 59970
    assert pr("") == 0
    assert pr("junk") < 0                 # flagged invalid, never written

    assert bm("1920x1080", 60000) == "1920x1080@60000"
    assert bm("1920x1080", 0) == "1920x1080"

    assert mh("1920x1080", "60.000 Hz") == "1920x1080 @ 60.000 Hz"
    assert mh("", "") == "auto"
    print("PASS: mode helpers")


if __name__ == "__main__":
    import tempfile
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
