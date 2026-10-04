# PyWCM bug-fix report

Final recorded validation: **149 tests passed, 0 failed**, across 19 test modules. Syntax checks passed for **24 Python files**. This report consolidates related defects and later corrections to fixes made during this conversation; it does not count each failed probe as a separate bug.

## Fixes completed

| Area | Bugs fixed |
|---|---|
| Plugin discovery and original issue | Duplicate plugin cards from overlapping installations; discovery priority; clipped command headings; duplicate/missing rule editors and arbitrary rule names; incorrect wiki routing/empty pages; missing criteria help while preserving free-text entry. |
| Config parsing and editing | Multiline plugin lists; preservation of CRLF, comments and spacing; missing newline after a final header; duplicate keys/sections surviving deletion; empty/reused rule sections and unwanted rule spacing; stale saves overwriting unrelated external edits; conflicting plugin-list updates now merge individual enable/disable operations. |
| Option and command controls | Incorrect zero/boolean/double reset values; insufficient decimal precision; invisible custom choices; command-name collisions; orphan bindings not shown; stale callbacks after binding-type changes; missing release-binding handling; malformed refresh/position values and zero-size modes. |
| Save safety | Partial-write/replacement failures; symlink and permission preservation; edits during staging; recovery of detected last-moment in-place writes; inability to save without hard-link support; lost retry state after failed text flushes; lost final keystrokes on close; closing despite save failure; treating errors after replacement as if nothing had saved. |
| Presets | Old typing overwriting loaded presets; failed loads discarding typing or in-memory state; wf-shell presets adding unwanted core/plugin state; stale live-panel listeners; incomplete two-file save/load/delete rollback; lost recovery backups; symlink cleanup affecting targets; sanitized-name collisions and selection; unreported delete failures; stale display controls/baselines after master load; already-saved plugin loads restoring old memory and retaining obsolete typing after recovery errors. |
| Display modes and confirmation | Enabling without a mode; clearing resolution/Automatic behavior; incorrect restoration of absent, mirrored or exact mode values; lost rollback on reload, hotplug or close; rotation rollback using an old enable baseline; failed rollback losing its callback/dialog; window-manager close bypassing Revert; repeated retry errors stacking dialogs; failed initial edits leaking into later saves; failed disable bypassing rollback; post-save errors leaving applied modes without confirmation; Keep recording failed, invalid or incomplete resolution/refresh input; controls retaining failed values. |
| Output add/remove | Failed additions and removals leaking into later saves; unreadable sections from malformed output names; mishandling recovery errors after successful changes; pending rollback recreating a removed output; removal now cancels only that output’s confirmation after success. |
| Translations | Restored missing Spanish, Romanian and Simplified Chinese catalogs and extended common interface strings; verified compilation, lookup and format placeholders. Untranslated strings still fall back to English. |

Latest deeper check also fixed master preset save/load/delete treating completed transactions as failures when backup cleanup failed, and cleanup errors masking the original transaction failure. Master loads now refresh saved state and cancel obsolete typing even when cleanup needs attention.

Latest normal-use testing fixed Automatic mode losing its dropdown selection on Keep/Revert. Additional checks passed for 20 master-preset switches with pending typing and display rollback, 50 plugin-preset switches, and 20 scale/edit/revert cycles.

Latest boundary checks fixed invalid or incomplete mode text making an output appear enabled while its saved mode remained off. Disable/enable now preserves a usable saved mode. Master snapshot tests also verified both pending text flushes and preservation of an existing snapshot after a failed save.

Latest verification found no new bugs. The full suite passed again, including an added repeated numeric/Automatic toggle test with injected enable failures and retries.

## Test coverage and results

The full suite covers config round trips, metadata/discovery, commands and rules, translations, master/plugin presets, real GTK signals and timers, display rollback, concurrent edits, symlinks, permissions, and injected write/staging/cleanup failures. It includes **2,000 seeded config operations** within one regression test, multi-output recovery, preset fault matrices, and unsupported-hard-link cases.

| Test module | Passed |
|---|---:|
| `test_config.py` | 13 |
| `test_metadata.py` | 6 |
| `test_outputs.py` | 8 |
| `test_presets.py` | 9 |
| `test_pages.py` | 4 |
| `test_metadata_discovery.py` | 1 |
| `test_i18n.py` | 6 |
| `test_issue1.py` | 4 |
| `test_regressions.py` | 27 |
| `test_followup.py` | 8 |
| `test_preset_safety.py` | 8 |
| `test_final_safety.py` | 4 |
| `test_interaction_safety.py` | 5 |
| `test_release_safety.py` | 13 |
| `test_transition_safety.py` | 11 |
| `test_output_actions.py` | 7 |
| `test_master_cleanup.py` | 6 |
| `test_repeated_workflows.py` | 4 |
| `test_final_workflows.py` | 5 |

The [complete test inventory](BUG_FIX_TEST_INVENTORY.md) lists every test and its recorded result. [Machine-readable results](BUG_FIX_TEST_RESULTS.json) preserve the final run. Earlier targeted audit failures were reproduced, fixed and covered by regressions; historical reports describe the state at the time, not outstanding bugs. Test totals from repeated runs are not added together.

## Limits and preservation

Tests used temporary configurations; no real user configurations or physical display modes were changed. No user files or features were removed. Plugin presets retain extra settings by design.

Physical monitor/compositor behavior remains untested. Uncoordinated simultaneous external writers, especially atomic replacements, still have documented limits; copied recovery snapshots cannot capture edits after their final check. Multi-file preset operations recover from reported I/O errors but do not guarantee atomicity across power loss. Passing tests do not prove the absence of every possible bug.
