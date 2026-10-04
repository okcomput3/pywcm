# Complete recorded test inventory

149 passed; 0 failed. Final full-suite results from this conversation.

## test_config.py

- **PASS** — `test_add_new_option`
- **PASS** — `test_add_new_section`
- **PASS** — `test_comments_preserved_after_multiple_edits`
- **PASS** — `test_duplicate_rule_repair_keeps_rules_comments_and_other_sections`
- **PASS** — `test_empty_section_survives_unrelated_index_rebuild`
- **PASS** — `test_enable_disable_plugin`
- **PASS** — `test_get_option`
- **PASS** — `test_read_and_preserve`
- **PASS** — `test_remove_option`
- **PASS** — `test_reuse_section_after_removing_last_rule`
- **PASS** — `test_rule_spacing_after_add_remove_and_existing_gap`
- **PASS** — `test_save_repairs_existing_duplicate_rule_sections`
- **PASS** — `test_set_existing_option`

## test_metadata.py

- **PASS** — `test_animation_type`
- **PASS** — `test_basic_parse`
- **PASS** — `test_extra_animations_merge`
- **PASS** — `test_groups_and_subgroups`
- **PASS** — `test_import_wcm`
- **PASS** — `test_option_types`

## test_outputs.py

- **PASS** — `test_detect_unavailable`
- **PASS** — `test_list_configured_outputs`
- **PASS** — `test_parse_basic`
- **PASS** — `test_parse_disabled_output`
- **PASS** — `test_parse_transform_mapping`
- **PASS** — `test_remove_section`
- **PASS** — `test_section_name`
- **PASS** — `test_validate_mode`

## test_presets.py

- **PASS** — `test_delete_master_preset`
- **PASS** — `test_delete_plugin_preset`
- **PASS** — `test_get_all_options`
- **PASS** — `test_master_preset_single_line_changes`
- **PASS** — `test_multiple_master_presets`
- **PASS** — `test_plugin_preset_preserves_enabled`
- **PASS** — `test_sanitize_name`
- **PASS** — `test_save_and_load_master_preset`
- **PASS** — `test_save_and_load_plugin_preset`

## test_pages.py

- **PASS** — `test_empty_prefix_rules_use_rule_editor`
- **PASS** — `test_hotplug_keeps_disconnected_config`
- **PASS** — `test_hotplug_preserves_confirmation_and_coalesces_events`
- **PASS** — `test_rules_keep_arbitrary_names_and_avoid_collisions`

## test_metadata_discovery.py

- **PASS** — `test_duplicate_installs_preserve_priority_and_distinct_plugins`

## test_i18n.py

- **PASS** — `test_all_shipped_msgstrs_keep_format_fields`
- **PASS** — `test_compile_mo_roundtrip`
- **PASS** — `test_metadata_domain`
- **PASS** — `test_mode_helpers`
- **PASS** — `test_parse_po_basic`
- **PASS** — `test_shipped_catalogs_compile_and_resolve`

## test_issue1.py

- **PASS** — `test_command_heading_width_and_full_text`
- **PASS** — `test_criteria_help_preserves_description_and_free_text`
- **PASS** — `test_rules_have_one_editor_and_preserve_every_name`
- **PASS** — `test_wiki_routes_and_empty_pages`

## test_regressions.py

- **PASS** — `test_config_delete_all_duplicate_keys`
- **PASS** — `test_config_external_merge`
- **PASS** — `test_config_multiline_toggle_and_crlf_preservation`
- **PASS** — `test_config_randomized_2000_operations`
- **PASS** — `test_config_remove_duplicate_output_sections`
- **PASS** — `test_config_unterminated_header`
- **PASS** — `test_display_invalid_refresh_matrix`
- **PASS** — `test_display_zero_dimensions`
- **PASS** — `test_gui_binding_type_edit_real_signals_known_bug`
- **PASS** — `test_gui_binding_without_command_visible`
- **PASS** — `test_gui_close_flushes_last_edit`
- **PASS** — `test_gui_debounce_latest_value`
- **PASS** — `test_gui_display_open_no_writes`
- **PASS** — `test_gui_invalid_position_does_not_break_page`
- **PASS** — `test_gui_new_command_preserves_existing_binding`
- **PASS** — `test_gui_open_options_no_writes`
- **PASS** — `test_gui_pending_display_refresh_and_close_rollback`
- **PASS** — `test_gui_pending_edit_after_preset`
- **PASS** — `test_gui_release_switch_edit_delete`
- **PASS** — `test_gui_reset_boolean_and_double`
- **PASS** — `test_gui_reset_zero_real_signals_known_bug`
- **PASS** — `test_gui_small_double_precision`
- **PASS** — `test_gui_unlisted_saved_choice_visible`
- **PASS** — `test_preset_legacy_shell_metadata_ignored`
- **PASS** — `test_preset_master_verbatim_crlf`
- **PASS** — `test_preset_unicode_roundtrip`
- **PASS** — `test_preset_wfshell_no_core_pollution`

## test_followup.py

- **PASS** — `test_atomic_save_preserves_symlink_and_permissions`
- **PASS** — `test_auto_choice_has_display_rollback`
- **PASS** — `test_clear_resolution_commits_auto_on_enter`
- **PASS** — `test_enable_output_without_resolution_uses_auto`
- **PASS** — `test_failed_master_preset_keeps_pending_edit`
- **PASS** — `test_master_preset_reconnects_live_panel`
- **PASS** — `test_partial_write_preserves_file_and_retry`
- **PASS** — `test_replace_failure_preserves_file`

## test_preset_safety.py

- **PASS** — `test_master_pair_success_keeps_exact_bytes_and_symlinks`
- **PASS** — `test_master_stage_failure_preserves_both_save_and_load_destinations`
- **PASS** — `test_plugin_failed_load_preserves_pending_edits_and_memory`
- **PASS** — `test_plugin_merge_keeps_extra_rows`
- **PASS** — `test_rollback_failure_retains_recovery_copy`
- **PASS** — `test_sanitized_name_collision_preserves_original`
- **PASS** — `test_saved_plugin_selected_after_sanitization`
- **PASS** — `test_second_file_failure_rolls_back_first_for_save_and_load`

## test_final_safety.py

- **PASS** — `test_companion_cleanup_preserves_symlink_targets`
- **PASS** — `test_delete_handlers_report_errors_and_preserve_selection`
- **PASS** — `test_rotation_rollback_preserves_new_enable_baseline`
- **PASS** — `test_symlink_deletion_rollback_restores_link`

## test_interaction_safety.py

- **PASS** — `test_failed_pending_edit_is_retryable`
- **PASS** — `test_last_moment_inplace_write_retained_for_recovery`
- **PASS** — `test_master_delete_failure_restores_both_files`
- **PASS** — `test_plugin_operations_merge_external_changes`
- **PASS** — `test_staging_race_preserves_file_and_retry_merges`

## test_release_safety.py

- **PASS** — `test_close_blocks_on_either_config_failure_then_retries`
- **PASS** — `test_confirmation_timeout_failure_remains_retryable`
- **PASS** — `test_confirmation_window_close_reverts_and_retries`
- **PASS** — `test_display_rollback_repeated_failure_preserves_ui_and_retry`
- **PASS** — `test_failed_revert_blocks_close_and_reload`
- **PASS** — `test_failed_rollback_retry_preserves_external_edits`
- **PASS** — `test_keep_after_failed_revert_preserves_selected_mode`
- **PASS** — `test_multiple_output_rollback_retries_remaining_output`
- **PASS** — `test_portable_save_copy_failure_preserves_original_and_retries`
- **PASS** — `test_portable_save_detects_copy_race`
- **PASS** — `test_portable_save_preserves_mode_and_symlink`
- **PASS** — `test_preset_staging_and_commit_failure_matrix`
- **PASS** — `test_timeout_retries_automatically_after_failure`

## test_transition_safety.py

- **PASS** — `test_cleanup_failure_keeps_committed_mode_and_confirmation`
- **PASS** — `test_failed_disable_keeps_pending_mode_revert`
- **PASS** — `test_failed_initial_display_changes_never_leak_into_later_save`
- **PASS** — `test_failed_mode_change_can_be_retried_and_reverted`
- **PASS** — `test_keep_after_failed_second_edit_has_consistent_baseline`
- **PASS** — `test_keep_ignores_invalid_or_incomplete_mode_input`
- **PASS** — `test_master_load_rebuilds_display_with_new_config_and_baseline`
- **PASS** — `test_plugin_committed_warning_keeps_preset_and_cancels_old_typing`
- **PASS** — `test_plugin_committed_warning_refreshes_page_before_reporting`
- **PASS** — `test_post_commit_verification_error_identifies_saved_state`
- **PASS** — `test_repeated_timeout_errors_stay_inline_and_eventually_recover`

## test_output_actions.py

- **PASS** — `test_failed_output_add_does_not_leak_into_later_save`
- **PASS** — `test_failed_output_remove_does_not_leak_into_later_save`
- **PASS** — `test_output_add_cleanup_warning_preserves_added_output`
- **PASS** — `test_output_name_cannot_create_unreadable_section`
- **PASS** — `test_removal_cancels_only_its_own_active_confirmation`
- **PASS** — `test_remove_failure_keeps_rollback_and_success_preserves_other_output`
- **PASS** — `test_removed_output_is_not_restored_by_pending_confirmation`

## test_master_cleanup.py

- **PASS** — `test_cleanup_failure_does_not_mask_original_preset_failure`
- **PASS** — `test_master_cleanup_error_identifies_committed_pair`
- **PASS** — `test_master_delete_warning_refreshes_removed_selection`
- **PASS** — `test_master_load_cleanup_warning_refreshes_and_cancels_old_typing`
- **PASS** — `test_master_save_warning_refreshes_saved_selection`
- **PASS** — `test_preset_name_roundtrip_matrix`

## test_repeated_workflows.py

- **PASS** — `test_keep_automatic_then_numeric_revert`
- **PASS** — `test_repeated_master_switches_with_display_and_pending_typing`
- **PASS** — `test_repeated_plugin_switches_preserve_unrelated_settings`
- **PASS** — `test_repeated_scale_edits_survive_mode_revert`

## test_final_workflows.py

- **PASS** — `test_failed_save_master_does_not_replace_existing_snapshot`
- **PASS** — `test_invalid_refresh_and_blank_resolution_do_not_break_toggle`
- **PASS** — `test_invalid_resolution_cannot_show_disabled_output_as_enabled`
- **PASS** — `test_repeated_toggles_and_failed_enable_preserve_saved_mode`
- **PASS** — `test_save_master_flushes_both_configs_and_preserves_display_state`
