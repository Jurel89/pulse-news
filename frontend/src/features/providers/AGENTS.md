<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-15 | Updated: 2026-04-15 -->

# providers

## Purpose
AI provider configuration. A provider is a named binding of a provider type (`openai`, `anthropic`, `gemini`, `google`, `openrouter`, `zai`, `kimi`) to a default model, plus an enable/disable flag. The backend refuses to create a provider that has no active API key of the matching provider type.

## Key Files
| File | Description |
|------|-------------|
| `ProvidersPage.tsx` | Provider table with per-row `ActionDropdown` — Edit / Enable / Disable / Delete. `ProviderEditor` is exported from the same file and used by `App.tsx` for create/edit |
| `provider-types.ts` | `ProviderSummary`, `ProviderDetail`, `ProviderInput` |

## For AI Agents

### Working In This Directory
- The Enable / Disable action is a `PUT /providers/{id}` with the existing fields + `is_enabled: !current`. It is not a dedicated endpoint.
- Model discovery is a separate backend endpoint (`GET /providers/presets/{provider_type}/models`) and is called lazily by the editor — don't eager-load model lists on mount.

## Dependencies

### Internal
- `../../lib/api.ts`
- `../../components/ui/ActionDropdown.tsx`
