# Latency feature inventory (current behaviour)

Recorded **before** any latency-optimization behaviour change. Re-verify after every landed step. A faster answer that drops a row here is a failed change.

Date: 2026-09-03. Source: repository as of this commit, not a live matrix.

## Planning

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| AI primary call | `PLANNER_MODE=ai`, non-empty question, selected list | One structured `PlannedTurn`. Success binds selected file. | `test_ai_default_path_plans_with_fake_provider` |
| Schema-validation retry | First parse is `ValidationError` or `PlannerContractError` | Second attempt with schema-retry preamble. Two failures → `planner_invalid_output`. | `test_primary_retries_validation_error_only`, `test_malformed_primary_twice` |
| Event-loop deadline | Each provider call | `asyncio.timeout` / `wait_for` of `timeout_for(model)` (60s for the direct model). Queueing on the semaphore is **outside** the deadline. | `test_a_host_that_stops_sending_hits_the_deadline_instead_of_hanging`, `test_a_timeout_is_transient_so_the_planner_can_spend_its_second_attempt` |
| Transient-failure retry | `TransientReasoningError` (timeout, network, 429/502/503) | Second attempt **repeats the original user prompt** (not the schema preamble). Second failure → `planner_unavailable`. Other `Exception` → unavailable with **no** retry. | `test_a_timed_out_planner_call_is_asked_again_before_giving_up`, `test_a_host_that_stays_down_is_reported_unavailable_not_retried_forever`, `test_no_retry_on_provider_failure` |
| Self-review (today) | `_review_eligible`: any query, any `VerifyPreviousAction`, or non-navigation modify; `planner_self_review=True` | Serial review after bind/validate/build/predicate. `complete` keeps plan; `corrected` revalidates once; `needs_clarification` clarifies **unless the question names the selected list**, in which case it is overruled and the validated plan is kept (`review_status=clarification_overruled`); invalid/unavailable review **keeps** the validated plan. | `test_data_request_reviews_even_with_zero_filters`, `test_review_correction_not_reviewed_again`, `test_malformed_review_has_no_retry` |
| Unknown-field / bad-operator salvage | `PlanValidationError` code `unknown_field` or `operator` after bind | **Blocking** one review with the validation error in the prompt. Corrected plan re-enters `_validate_and_route`. | `test_unknown_field_review_can_correct`, `test_an_operator_the_field_forbids_is_worth_a_second_look` |
| `dataset_not_selected` | Respond intent `dataset_not_selected` **and** the question/response names another authorized source | Status `dataset_not_selected`, optional `suggested_file_id`. Ungrounded use is a contract error and retries. Unauthorized source is not named in the answer. | `test_authorized_other_list_suggestion`, `test_unauthorized_list_is_not_disclosed`, `test_dataset_not_selected_requires_named_other_source`, `test_ungrounded_dataset_not_selected_retries` |
| Clarification turns | Clarify action, dropped_requirement, unknown field after salvage fails, low confidence (see below) | `status=clarification`; no QueryPlan executed. | `test_strict_validation_no_orphan_promotion`, `test_response_contract_rejects_suppressed_query` |
| Confidence threshold | `planner_min_confidence=0.75`. AI path calls `validate_turn_plan(..., strict=True)` **before** review | If `confidence < 0.75` **and** the turn is executable, strict mode **replaces the whole turn with a canned clarification** (`unresolved=["low_confidence"]`). Review never sees that plan. Comment in `turn_validator.py` says the opposite of the `strict and executable` branch. | `test_strict_low_confidence_executable_becomes_clarification` |
| `PLANNER_MODE=legacy` | Default in pytest via `conftest`; env `legacy` | 15-gate tree; no AI planner. App default is `ai`. | `test_legacy_rollback_still_plans`, `test_application_default_is_ai`, `test_golden_question_executes_without_a_compiler_call` |

| Review clarification overrule | Review returns `needs_clarification`, the question names the selected list and no other authorized list, **and** names no field this list lacks | Verdict dropped, validated plan executes, `review_status=clarification_overruled`. Mirrors `_assert_grounded_dataset_not_selected` on the primary path. | `test_review_may_not_ask_which_list_when_the_question_named_it`, `test_review_still_clarifies_when_the_question_names_no_list`, `test_a_question_naming_the_selected_list_is_recognized_as_such` |
| Validation-failure wording | Any `PlanValidationError` reaching the clarification path | `_safe_clarification` maps a known code to written wording; anything else gets a generic sentence. The exception text stays on `detail` only. | `test_a_plan_that_fails_validation_never_shows_its_reason_verbatim` |
| Dataset phrase matching | Any check of "does this text name this list" | Word runs with plurals folded, not substrings: "additional death names" names Additional Deaths; "master" no longer matches inside "postmaster". | `test_a_list_is_named_by_words_not_by_substring`, `test_word_matching_does_not_fire_inside_a_longer_word`, `test_plural_folding_is_not_applied_to_short_or_double_s_words` |
| Unaccounted conditions | Plan filters on a condition no stated requirement claims | Reported to the review in a section present only when non-empty; **nothing is deleted on this signal**. Reviewer keeps or drops it against the question. | `test_conditions_the_plan_never_claimed_are_reported_not_removed`, `test_the_review_prompt_is_unchanged_when_every_condition_is_accounted_for`, `test_the_review_is_told_which_conditions_were_never_claimed` |
| Named-but-absent field | Question names a multi-word field another authorized list records and this one does not | Named to the review, which refuses rather than answering from a field whose name overlaps. Single broad words never count. | `test_a_broad_alias_cannot_swallow_a_more_specific_request`, `test_a_single_broad_word_is_not_treated_as_naming_a_field`, `test_a_field_both_lists_share_is_never_reported_absent`, `test_the_review_prompt_names_the_missing_field_only_when_there_is_one` |

## Turn schema

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| `modify_previous` | Follow-up edits | Applies changes to the active query on the **selected** list only. Stale frames for another file are dropped. | `test_a_follow_up_keeps_its_turn_when_it_states_the_filter_it_carries`, `test_source_actions_drops_stale_active_frame`, AI conversation-memory tests |
| `verify_previous` **flag** on a query | `QueryAction.verify_previous=True` | Preserved through bind. | `test_planned_turn_preserves_query_semantics` |
| `verify_previous` **action** | `type=verify_previous` | Review-eligible. Trusted code re-runs the previous result. | `test_verify_previous_action_is_review_eligible` |
| Navigation-only modify | `page` or `restore_frame` and no other edits | `_review_eligible` is **False** — review skipped. | `test_navigation_only_modify_skips_review`, `test_list_pagination` |
| Drop query requirements without a query | Query-kind requirements with no query action to target | Those requirements are dropped before index checks. | `test_conversational_plan_drops_query_requirements`, `test_a_follow_up_keeps_its_turn_when_it_states_the_filter_it_carries` |
| Drop blank `general_conversation` beside real work | Empty respond + at least one query/modify/verify | Flourish dropped; remaining `action_index` values are **renumbered**. Only-blank small talk still fails. Non-empty flourish is kept. | `test_a_blank_conversational_flourish_does_not_take_the_query_with_it`, `test_requirement_indexes_follow_the_action_that_moved`, `test_small_talk_that_is_the_whole_turn_still_has_to_say_something`, `test_a_flourish_that_actually_says_something_is_kept` |

## Security

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| `bind_scope` | After parse | Stamps `datasets=[selected_file_id]`. Model `datasets` field is forbidden. | `test_bind_scope_never_reads_model_file_ids`, `test_planned_turn_rejects_datasets_field` |
| `validate_turn_plan` | After bind, `strict=True` in AI | Fields, operators, orphans, injection, confidence. | `test_strict_validation_no_orphan_promotion`, `test_plan_validator.py` |
| `check_requirement_parity` | After validate if `planner_requirement_check` | Missing stated requirement → `dropped_requirement`. | `test_requirement_parity_one_to_one`, `test_three_condition_parity_reaches_plan` |
| Predicate contract | After QueryPlan build | Sibling predicates AND for contradictions. | `test_predicate_and_or_contract`, `test_sibling_predicates_are_anded_for_contradictions` |
| QueryPlan validation | After expansion | Op contracts, scope, budgets. | `test_plan_validator.py`, `test_plan_schema.py` |
| Gateway authorization | Every `assistant_api.*` call | Principal + allowed_file_ids + `can_use_private_files`. | `test_privilege_boundary.py`, `test_private_dataset_does_not_leak` |
| `evidence_allowed` | Evidence / GET_EVIDENCE | Only allowed fields are packed. `needs_evidence` with none allowed → `sensitivity`. | `test_evidence_disallowed_fields_are_not_packed` |
| `raw_fetch_allowed` | Raw cell fetch | Only granted keys. | `test_raw_fetch_gate.py` |
| Empty registry in production | `load_catalog` finds no fields and `app_env=production` | `RuntimeError`. Dev falls back to `static_catalog()`. | `test_empty_registry_fails_closed_in_production` |

`scope.fingerprint()` includes `principal_id`, file ids, `can_use_private_files`, and history.

## Answering

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| Deterministic format | `final_response=deterministic` | `format_deterministic_answer`; no synthesis call. | eval suite, matrix, chat regressions |
| `llm_synthesis` | Narrative / explanation | `answer_structured` then one late `answer_delta`. Citations from the evidence packet. | `test_cause_summary_is_synthesized_and_evidence_backed`, `test_synthesis_sse_includes_citations` |
| Evidence packet | Synthesis or quote/search | Built from executed rows; unauthorized prefixes stripped. | `test_eval_unauthorized_source_rate_is_zero_even_when_model_poisons_ids` |
| Whole-list answers | `WHOLE_LIST_ANSWER=true` and under max rows | `planner_type=whole_list`. Off by default. | `test_whole_list_answer.py` |
| Name correction, 1 edit unambiguous | Unique candidate distance 1 | Answer rewritten; prefix states the correction. | `test_one_person_one_edit_away_is_a_typo`, `test_a_correction_is_stated_never_silent` |
| Name correction, 2–3 edits or ties | Distance 2–3 or several distance-1 | Clarify “Did you mean …”. | `test_two_edits_away_is_asked_about_not_assumed`, `test_several_people_equally_close_are_asked_about` |
| Exact match anywhere | Any candidate distance 0 | Correction suppressed. | `test_a_name_the_list_records_is_never_corrected`, `test_an_exact_match_silences_the_near_ones` |

## Conversation

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| Persist conversation | `get_or_create` then `_persist` | `assistant.conversations`, `messages`, state. | `test_conversation_list_and_get`, `test_conversations_are_isolated_by_principal` |
| `selected_file_id` pin | First selected list | Cannot rebind. | `test_pin_conflict_before_planner`, `test_conversation_cannot_be_rebound_to_another_list` |
| Frames / result sets / paging | List + next/previous | Active frame updated. | `test_list_pagination.py` |
| Recent-turn context | Subsequent turns | Memory text + active query. | `test_conversation_memory_ai.py` |

## Voice

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| Phrase-streamed TTS | Voice synthesis | `stream_answer` → phrase buffer. | `test_tts.py` |
| Interruption | Barge-in | Cancels TTS; `interrupted=True`. | `test_voice_state_machine_happy_path_and_interrupt` |
| `interrupted` on messages | Persist after interrupt | Column on `assistant.messages`. | Persist path in `postgres.py` |
| `delivered_text` | Spoken phrases actually sent | Session accumulates text. DB column `delivered_text_boundary` exists. | `tts/session.py` (no DB-write test) |
| Whisper session | First audio | Lazy `POST /v1/session`. | `test_whisper_service.py` |
| Preemptive generation | — | **Disabled.** | `test_preemptive_generation_is_disabled` |

## Ops

| Item | Trigger | Current return | Tests |
|---|---|---|---|
| Audit `query_completed` | Completed query | Auditor record. | `test_audit_records_query_without_evidence` |
| Audit access-denied | Restricted file | Audited. | `test_access_denied_is_audited` |
| Query traces | After execute, before retrieval-completed | `save_query_run`; failures swallowed. | Observability / gateway |
| Rate limiting | Auth / query / livekit / tts | Per-client limits. | `test_expensive_routes_are_rate_limited_per_client` |
| SSE heartbeats | Stream query > 1s | `: keep-alive`; cancel on disconnect. | `test_query_api.py` |
| Model picker | `QueryRequest.model` | Allowlisted name selects the **answer** provider (`_reasoner_for` → `_turn_reasoner`). Planning/review stay on the service default. Off-list → default. Voice reuse clears the pick after the turn. | `test_ui_model_selects_the_synthesis_provider`, `test_ui_model_does_not_select_the_planner`, `test_a_model_outside_the_allowlist_never_reaches_the_provider` |
| `timeout_for` | Direct vs reasoning | 60s vs 150s. | `test_a_direct_model_keeps_the_short_budget`, `test_a_reasoning_model_gets_longer` |

## Implication for later steps

On the AI path, **every plan that reaches review already has `confidence >= 0.75`**, because strict validation turned lower-confidence executable plans into clarifications. A conditional-review gate of `confidence < 0.75` would never fire for surviving single-action queries.

## Re-verification log

| After step | Inventory still holds? | Deltas |
|---|---|---|
| (initial + characterization tests) | yes | Five characterization tests: `test_strict_low_confidence_executable_becomes_clarification`, `test_verify_previous_action_is_review_eligible`, `test_navigation_only_modify_skips_review`, `test_evidence_disallowed_fields_are_not_packed`, `test_empty_registry_fails_closed_in_production`. Also `test_matrix_aborts_on_connection_loss`, `test_ui_model_does_not_select_the_planner`. |
| Phase 0 baseline + instrumentation | yes | `TurnResult.latency` added (observability only). Matrix aborts on connection loss. |
| Model guardrail + frontend | yes | UI `model` no longer selects the planner. Conversation list refresh no longer blocks `busy`. Review remains `always`. |
| Review-defect fix | yes | UI `model` again selects synthesis (`_turn_reasoner`). Dead `sync_audit_writes` / `stream_text_synthesis` removed. `planner_review_mode` is `off`\|`always` only. |
