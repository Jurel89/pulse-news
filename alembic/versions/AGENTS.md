<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# versions

## Purpose
Individual Alembic revision scripts. The app runs `alembic upgrade head` on startup, so every schema change that has merged to `main` is represented here and must be idempotent enough to apply cleanly to a fresh database.

## Key Files
| File | Description |
|------|-------------|
| `1703f317ccfa_initial_schema.py` | Initial schema — users, newsletters, recipients, runs, events, email templates, providers, api keys, audit events |
| `bb2893350268_add_email_templates_providers_and_api_.py` | Introduced email templates, providers, and api keys tables |
| `1c2b6170f8d3_add_resend_api_key_to_newsletters.py` | Per-newsletter Resend API key pin |
| `add_from_email_to_api_keys.py` | Sender email stored on api keys |
| `3b4c5d6e7f80_add_draft_revisions_and_run_links.py` | (Superseded) draft/revision schema — subsequently dropped |
| `4c5d6e7f8091_add_generation_and_delivery_profiles.py` | (Superseded) generation/delivery profiles — subsequently dropped |
| `5d6e7f8091a2_…` / `6e7f8091a2b3_…` / `7f8091a2b3c4_…` / `8a9b0c1d2e3f_…` | (Superseded) draft-revision add-on columns |
| `9b0c1d2e3f4a_add_operation_modes_to_system_settings.py` | (Superseded) simulated operation mode columns |
| `ab13d7e4f9c2_simplify_newsletter_schema.py` | Drops draft/revision/profile tables and simulated-mode columns |
| `c14d9e5f6a7b_rename_draft_columns_to_subject_preheader_.py` | Renames `draft_subject` / `draft_preheader` / `draft_body_text` → `subject` / `preheader` / `body_text` |

## For AI Agents

### Working In This Directory
- Filenames are generated; do not rename existing revisions after they have merged to `main`.
- A new migration must declare a correct `down_revision` pointing at the current head (run `alembic heads` to check).
- Write idempotent DDL: guard `ADD COLUMN` with introspection and make `DROP` statements safe for fresh installs.
- The "(Superseded)" migrations above are part of the chain and must continue to apply cleanly on a fresh DB; do not delete them.

### Testing Requirements
- `backend/tests/test_database_migrations.py` builds the full chain against a fresh SQLite DB as part of every CI run.

## Dependencies

### Internal
- `backend/app/models.py` — the metadata target for autogenerate.

### External
- `alembic`, `sqlalchemy`
