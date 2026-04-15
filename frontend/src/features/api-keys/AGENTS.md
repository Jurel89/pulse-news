<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# api-keys

## Purpose
Stored credentials for AI providers (OpenAI, Anthropic, Gemini, OpenRouter, Google, zai, Kimi) and for Resend (email delivery). Secrets are symmetrically encrypted at rest by `backend/app/crypto.py`; only a `****xxxx` mask is returned from the backend on reads.

## Key Files
| File | Description |
|------|-------------|
| `ApiKeysPage.tsx` | Card grid with `Edit` / `Activate`/`Deactivate` / `Delete` buttons per key. `ApiKeyEditor` is exported from the same file |
| `api-key-types.ts` | `ApiKeySummary`, `ApiKeyDetail`, `ApiKeyInput` |

## For AI Agents

### Working In This Directory
- Only Resend keys expose the `from_email` field. The editor should hide it for other provider types.
- Deactivating the last active key for a provider type is blocked by the backend when enabled providers of that type exist. Surface the error message; don't silently succeed.
- E2E tests scope to a specific card via `article.newsletter-card:has-text(<name>)` — keep the `newsletter-card` class on each card, and make sure the `<h3>{name}</h3>` in the header stays as plain text.

## Dependencies

### Internal
- `../../lib/api.ts`
