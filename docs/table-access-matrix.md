# Table access matrix

| Object | Status | Runtime |
|---|---|---|
| `file` | allowed source | no direct SELECT; gateway functions only |
| `data_config` | allowed source | no direct SELECT |
| `file_data` | allowed source, selected rows only | no direct SELECT |
| `file_data_normalized` | allowed source, current version only | no direct SELECT |
| `communities` | allowed reference | no direct SELECT |
| `day_schools` | allowed reference | no direct SELECT |
| `indian_hospitals` | allowed reference | no direct SELECT |
| `provinces` | allowed reference | no direct SELECT |
| `file_version` | feature-gated | denied until enabled |
| `file_edit_request_photos` | feature-gated sanitized view | denied until enabled |
| `users` | denied | no access |
| `roles` | denied | no access |
| `otps` | denied | no access |
| `logs` | denied | no access |
| `support_*` | denied | no access |
| `form_*` | denied | no access |
| `file_access` | denied | no access |
| `file_edit_request` | denied | no access |
| `assistant.*` | owned | CRUD on assistant state |
| `assistant.conversations` / `messages` / `conversation_state` | owned | text+voice history |
| `assistant.query_frames` / `result_sets` | owned | follow-up frames; source IDs only, not full rows |
| `assistant.query_runs` / `query_step_runs` | owned | traces; no evidence payloads |
| `assistant.audit_events` | owned | principal, event type, dataset ids |
| `assistant.background_jobs` | owned | `FOR UPDATE SKIP LOCKED` leases |
| `assistant_api.v_current_records` | internal | EXECUTE via functions only |
| `assistant_api.list_datasets` | allowed API | EXECUTE |

Authorization is an `AccessScope` produced by `StandaloneJwtAuthAdapter` now and `WebsiteAuthAdapter` later. The matrix does not change when the website is connected.

Retention (`RESULT_SET_RETENTION_HOURS`, `QUERY_TRACE_RETENTION_DAYS`, `AUDIT_RETENTION_DAYS`) deletes assistant-owned rows only. It must never `DELETE` from `file_data`, `users`, or other application tables.

