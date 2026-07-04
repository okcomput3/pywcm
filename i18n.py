"""
i18n support for WCM (Python/GTK4).

Mirrors the C++ WCM's translation scheme:

  * UI strings use the ``wcm`` gettext domain
    (upstream: ``bindtextdomain("wcm", WAYFIRE_LOCALEDIR)``).
  * Plugin metadata strings (display names, tooltips, option names,
    descriptions) use the per-plugin ``wf-plugin-<name>`` domains that
    Wayfire itself installs, via ``dgettext`` — exactly as upstream does
    in metadata parsing (see wcm.hpp: ``"wf-plugin-" + plugin->name``).

Locale directories are searched in this order:

  1. ``$WCM_LOCALEDIR`` (explicit override)
  2. ``<script dir>/locale``          — running from a source checkout
  3. ``$XDG_DATA_HOME/locale``
  4. ``/usr/local/share/locale``
  5. ``/usr/share/locale``

For a source checkout we ship plain ``.po`` files.  If a matching
``.mo`` is missing or older than its ``.po``, it is compiled on the fly
with a small pure-Python compiler into ``$XDG_CACHE_HOME/wcm/locale``,
so translations work even without the gettext command-line tools.

The selected language follows the usual environment variables
(``LANGUAGE``, ``LC_ALL``, ``LC_MESSAGES``, ``LANG``); ``WCM_LANG`` can
be set to force a language just for WCM (handy for testing).
"""

import os
import re
import sys
import struct
import gettext as _gettext
import locale as _locale

DOMAIN = "wcm"

_translation = _gettext.NullTranslations()
_metadata_cache = {}
_locale_dirs = []


# --------------------------------------------------------------------------
# Pure-Python .po -> .mo compilation (subset sufficient for our catalogs:
# msgid/msgstr with multi-line strings; msgctxt and plurals are parsed and
# skipped gracefully).
# --------------------------------------------------------------------------

_po_line = re.compile(r'^(msgid|msgid_plural|msgstr(?:\[\d+\])?|msgctxt)\s+"(.*)"\s*$')
_po_cont = re.compile(r'^"(.*)"\s*$')


def _po_unescape(s):
    return (
        s.replace(r"\\", "\x00")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace(r"\r", "\r")
        .replace(r"\"", '"')
        .replace("\x00", "\\")
    )


def parse_po(path):
    """Parse a .po file into {msgid: msgstr}, skipping fuzzy entries."""
    entries = {}
    cur = {}
    key = None
    fuzzy = False

    def flush():
        nonlocal cur, fuzzy
        msgid = cur.get("msgid")
        msgstr = cur.get("msgstr", "")
        if msgid is not None and msgstr and not (fuzzy and msgid != ""):
            # Header (msgid "") is kept even when fuzzy so charset is known.
            if msgid == "" or not fuzzy:
                entries[msgid] = msgstr
        cur = {}
        fuzzy = False

    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if line.startswith("#"):
                    if line.startswith("#,") and "fuzzy" in line:
                        fuzzy = True
                    key = None
                    continue
                if not line.strip():
                    flush()
                    key = None
                    continue
                m = _po_line.match(line)
                if m:
                    k, v = m.group(1), _po_unescape(m.group(2))
                    if k == "msgid" and "msgid" in cur:
                        flush()
                    key = "msgstr" if k.startswith("msgstr") else k
                    cur[key] = cur.get(key, "") + v if key in cur else v
                    continue
                m = _po_cont.match(line)
                if m and key:
                    cur[key] = cur.get(key, "") + _po_unescape(m.group(1))
        flush()
    except OSError:
        return {}
    # Drop msgctxt-only oddities and empty translations
    return {k: v for k, v in entries.items() if v}


def compile_mo(entries, mo_path):
    """Write a minimal little-endian .mo file from {msgid: msgstr}."""
    items = sorted(entries.items())
    ids = b""
    strs = b""
    offsets = []
    for msgid, msgstr in items:
        bid = msgid.encode("utf-8")
        bstr = msgstr.encode("utf-8")
        offsets.append((len(ids), len(bid), len(strs), len(bstr)))
        ids += bid + b"\x00"
        strs += bstr + b"\x00"
    n = len(items)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    output = struct.pack(
        "Iiiiiii",
        0x950412DE,  # magic
        0,           # version
        n,           # number of entries
        7 * 4,       # offset of key table
        7 * 4 + n * 8,  # offset of value table
        0, 0,        # hash table (unused)
    )
    output += struct.pack(f"{2*n}i", *koffsets)
    output += struct.pack(f"{2*n}i", *voffsets)
    output += ids + strs
    os.makedirs(os.path.dirname(mo_path), exist_ok=True)
    tmp = mo_path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(output)
    os.replace(tmp, mo_path)


def _cache_localedir():
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(cache, "wcm", "locale")


def _compile_source_translations(src_localedir):
    """Compile locale/<lang>/LC_MESSAGES/wcm.po files (source checkout)
    into the user cache when the .mo is missing or stale.  Returns the
    cache locale dir if anything is available there."""
    compiled_dir = _cache_localedir()
    found = False
    try:
        langs = os.listdir(src_localedir)
    except OSError:
        return None
    for lang in langs:
        po = os.path.join(src_localedir, lang, "LC_MESSAGES", DOMAIN + ".po")
        if not os.path.isfile(po):
            continue
        mo = os.path.join(compiled_dir, lang, "LC_MESSAGES", DOMAIN + ".mo")
        try:
            stale = (not os.path.isfile(mo)
                     or os.path.getmtime(mo) < os.path.getmtime(po))
            if stale:
                entries = parse_po(po)
                if entries:
                    compile_mo(entries, mo)
            found = found or os.path.isfile(mo)
        except Exception as e:
            print(f"WCM: failed to compile translation {po}: {e}",
                  file=sys.stderr)
    return compiled_dir if found else None


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

def _candidate_localedirs():
    dirs = []
    env = os.environ.get("WCM_LOCALEDIR")
    if env:
        dirs.append(env)
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "locale")
    if os.path.isdir(src):
        # Source checkout: .mo files may need compiling from the .po files.
        compiled = _compile_source_translations(src)
        if compiled:
            dirs.append(compiled)
        dirs.append(src)  # in case .mo files were committed/installed there
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    dirs.append(os.path.join(xdg, "locale"))
    dirs.append("/usr/local/share/locale")
    dirs.append("/usr/share/locale")
    return dirs


def _languages():
    forced = os.environ.get("WCM_LANG")
    if forced:
        return [forced]
    return None  # let gettext use LANGUAGE/LC_ALL/LC_MESSAGES/LANG


def init():
    """Initialise locale + the 'wcm' textdomain.  Safe to call twice."""
    global _translation, _locale_dirs
    try:
        _locale.setlocale(_locale.LC_ALL, "")
    except _locale.Error:
        pass

    _locale_dirs = _candidate_localedirs()
    langs = _languages()
    for d in _locale_dirs:
        try:
            _translation = _gettext.translation(
                DOMAIN, localedir=d, languages=langs, fallback=False)
            break
        except OSError:
            continue
    else:
        _translation = _gettext.NullTranslations()

    # Also bind for C libraries (GTK builtin strings etc. use their own
    # domains; this mainly helps anything reading the process textdomain).
    for d in _locale_dirs:
        if os.path.isdir(d):
            try:
                _locale.bindtextdomain(DOMAIN, d)  # type: ignore[attr-defined]
                _locale.textdomain(DOMAIN)         # type: ignore[attr-defined]
            except (AttributeError, OSError):
                pass
            break
    return _translation


def _(message):
    """Translate a UI string in the 'wcm' domain."""
    if not message:
        return message
    return _translation.gettext(message)


def ngettext(singular, plural, n):
    return _translation.ngettext(singular, plural, n)


def gettext_metadata(plugin_name, message):
    """Translate a plugin metadata string, mirroring the C++ WCM:
    dgettext("wf-plugin-<plugin>", message).  Falls back to the original
    string when no catalog is installed for that plugin."""
    if not message or not plugin_name:
        return message
    domain = "wf-plugin-" + plugin_name
    tr = _metadata_cache.get(domain)
    if tr is None:
        langs = _languages()
        tr = _gettext.NullTranslations()
        for d in _locale_dirs or _candidate_localedirs():
            try:
                tr = _gettext.translation(
                    domain, localedir=d, languages=langs, fallback=False)
                break
            except OSError:
                continue
        _metadata_cache[domain] = tr
    return tr.gettext(message)


# Initialise on import so `from i18n import _` just works.
init()
