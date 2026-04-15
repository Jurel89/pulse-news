<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# templates

## Purpose
Email templates that wrap AI-generated body text into a full HTML email. Ships with two built-in templates (`signal`, `ledger`); operators may add more.

## Key Files
| File | Description |
|------|-------------|
| `EmailTemplatesPage.tsx` | Template list + `EmailTemplateEditor` for create/edit |
| `template-types.ts` | `EmailTemplateSummary`, `EmailTemplateDetail`, `EmailTemplateInput` |

## For AI Agents

### Working In This Directory
- Templates receive render variables `{ subject, preheader, body_text, recipient_email, unsubscribe_url, newsletter_name, newsletter_description }`. Keep that contract stable if you extend templates; the backend renderer in `backend/app/email_templates.py` is the source of truth.
- The "Set Default" action flips `is_default` on the chosen template (and clears it elsewhere) via `api.emailTemplates.setDefault(id)`.

## Dependencies

### Internal
- `../../lib/api.ts`
