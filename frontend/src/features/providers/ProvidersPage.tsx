import { useEffect, useMemo, useState, type BaseSyntheticEvent } from "react";
import type { ProviderSummary, ProviderDetail, ProviderInput, ProviderPreset } from "./provider-types";
import { emptyProviderInput, toProviderInput } from "./provider-types";
import { api } from "../../lib/api";
import type { ProviderTestResponse } from "../../lib/api";

type ProvidersPageProps = {
  providers: ProviderSummary[];
  loading?: boolean;
  error?: string | null;
  onDismissError?: () => void;
  onCreate: () => void;
  onEdit: (provider: ProviderSummary) => void;
  onDelete: (providerId: number) => Promise<void>;
  onToggleEnabled: (providerId: number, enabled: boolean) => Promise<void>;
};

export function ProvidersPage({
  providers,
  loading,
  error,
  onDismissError,
  onCreate,
  onEdit,
  onDelete,
  onToggleEnabled
}: ProvidersPageProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  async function handleDelete(providerId: number) {
    setDeletingId(providerId);
    try {
      await onDelete(providerId);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleToggle(providerId: number, currentEnabled: boolean) {
    setTogglingId(providerId);
    try {
      await onToggleEnabled(providerId, !currentEnabled);
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <section className="newsletters-grid">
      <header className="section-header">
        <div>
          <p className="eyebrow">AI Providers</p>
          <h2 className="section-title">Configure AI providers for content generation.</h2>
        </div>
        <button className="primary-button" onClick={onCreate} type="button">
          New Provider
        </button>
      </header>

      {error ? (
        <div className="error-banner">
          <span>{error}</span>
          {onDismissError ? (
            <button className="error-banner-dismiss" onClick={onDismissError} type="button">
              Dismiss
            </button>
          ) : null}
        </div>
      ) : null}

      {loading ? (
        <div className="newsletter-list">
          {Array.from({ length: 3 }, (_, index) => (
            <article className="loading-skeleton" key={index}>
              <div className="loading-skeleton-bar" />
              <div className="loading-skeleton-bar" />
              <div className="loading-skeleton-bar" />
            </article>
          ))}
        </div>
      ) : providers.length === 0 ? (
        <article className="empty-state">
          <h3>No providers yet</h3>
          <p>
            Configure your first AI provider. Connect to OpenAI, Anthropic, Gemini, or OpenRouter
            to generate newsletter content with AI.
          </p>
        </article>
      ) : (
        <div className="newsletter-list">
          {providers.map((provider) => (
            <article className="newsletter-card" key={provider.id}>
              <div className="newsletter-card-header">
                <div>
                  <h3>{provider.name}</h3>
                  <p>{provider.provider_type}</p>
                </div>
                <span className={`status-chip ${provider.is_enabled ? "status-active" : "status-paused"}`}>
                  {provider.is_enabled ? "Enabled" : "Disabled"}
                </span>
              </div>

              <dl className="newsletter-meta">
                <div>
                  <dt>Type</dt>
                  <dd>{provider.provider_type}</dd>
                </div>
                <div>
                  <dt>Default Model</dt>
                  <dd>{provider.default_model ?? "None set"}</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{new Date(provider.updated_at).toLocaleDateString()}</dd>
                </div>
              </dl>

              <p className="newsletter-description">
                {provider.description || "No description yet."}
              </p>

              <div className="card-actions">
                <button className="secondary-button" onClick={() => onEdit(provider)} type="button">
                  Edit
                </button>
                <button
                  className="secondary-button"
                  onClick={() => void handleToggle(provider.id, provider.is_enabled)}
                  disabled={togglingId === provider.id}
                  type="button"
                >
                  {togglingId === provider.id
                    ? "Updating..."
                    : provider.is_enabled
                      ? "Disable"
                      : "Enable"}
                </button>
                <button
                  className="danger-button"
                  onClick={() => void handleDelete(provider.id)}
                  disabled={deletingId === provider.id}
                  type="button"
                >
                  {deletingId === provider.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

type ProviderEditorProps = {
  initialProvider: ProviderDetail | null;
  onCancel: () => void;
  onSave: (payload: ProviderInput, providerId?: number) => Promise<void>;
};

export function ProviderEditor({
  initialProvider,
  onCancel,
  onSave
}: ProviderEditorProps) {
  const [form, setForm] = useState<ProviderInput>(
    initialProvider ? toProviderInput(initialProvider) : emptyProviderInput
  );
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<ProviderTestResponse | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [presets, setPresets] = useState<ProviderPreset[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    async function loadPresets() {
      setPresetsLoading(true);
      setPresetsError(null);
      try {
        const nextPresets = await api.providers.listPresets();
        if (!isActive) return;
        setPresets(nextPresets);
      } catch (error) {
        if (!isActive) return;
        setPresetsError(error instanceof Error ? error.message : "Unable to load provider presets.");
      } finally {
        if (isActive) {
          setPresetsLoading(false);
        }
      }
    }

    void loadPresets();

    return () => {
      isActive = false;
    };
  }, []);

  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.key === form.provider_type) ?? null,
    [form.provider_type, presets]
  );

  const availableModels = useMemo(() => {
    const models = selectedPreset?.recommended_models ?? [];
    if (!form.default_model) {
      return models;
    }

    return Array.from(new Set([form.default_model, ...models]));
  }, [form.default_model, selectedPreset]);

  const title = useMemo(
    () => (initialProvider ? `Edit ${initialProvider.name}` : "Create provider"),
    [initialProvider]
  );

  function updateField<K extends keyof ProviderInput>(key: K, value: ProviderInput[K]) {
    setForm((current) => ({
      ...current,
      [key]: value
    }));
  }

  function applyPreset(presetKey: string) {
    const preset = presets.find((entry) => entry.key === presetKey);
    if (!preset) return;

    setForm((current) => ({
      ...current,
      name: preset.name,
      provider_type: preset.key,
      default_model: preset.recommended_models[0] ?? current.default_model,
      configuration: JSON.stringify({ base_url: preset.base_url }, null, 2)
    }));
  }

  async function handleSubmit(event: BaseSyntheticEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await onSave(form, initialProvider?.id);
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    if (!initialProvider) return;
    setTestLoading(true);
    try {
      const result = await api.providers.test(initialProvider.id);
      setTestResult(result);
    } finally {
      setTestLoading(false);
    }
  }

  return (
    <section className="editor-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">Provider editor</p>
          <h2 className="section-title">{title}</h2>
        </div>
        <button className="secondary-button" onClick={onCancel} type="button">
          Back to list
        </button>
      </header>

      <form className="editor-form" onSubmit={handleSubmit}>
        {!initialProvider ? (
          <label>
            <span>Provider Preset</span>
            <select
              onChange={(event) => applyPreset(event.target.value)}
              disabled={presetsLoading}
              value={selectedPreset?.key ?? ""}
            >
              <option value="">Manual entry</option>
              {presets.map((preset) => (
                <option key={preset.key} value={preset.key}>
                  {preset.name}
                </option>
              ))}
            </select>
            {presetsLoading ? <small>Loading backend presets…</small> : null}
            {presetsError ? <small>{presetsError}</small> : null}
            {selectedPreset ? (
              <small>
                Adapter: {selectedPreset.adapter}
                {selectedPreset.base_url ? ` • Base URL: ${selectedPreset.base_url}` : " • Uses provider default base URL"}
              </small>
            ) : (
              <small>Select a preset to auto-fill, or continue with manual entry.</small>
            )}
          </label>
        ) : null}

        <label>
          <span>Name</span>
          <input
            onChange={(event) => updateField("name", event.target.value)}
            required
            value={form.name}
          />
        </label>

        <label>
          <span>Provider Type</span>
          <input
            list="provider-type-options"
            onChange={(event) => updateField("provider_type", event.target.value)}
            required
            value={form.provider_type}
            placeholder="openai"
          />
          <datalist id="provider-type-options">
            {presets.map((preset) => (
              <option key={preset.key} value={preset.key}>
                {preset.name}
              </option>
            ))}
          </datalist>
        </label>

        <label>
          <span>Default Model</span>
          <input
            list="provider-model-options"
            onChange={(event) => updateField("default_model", event.target.value)}
            value={form.default_model}
            placeholder={selectedPreset?.recommended_models[0] ?? "gpt-4o-mini"}
          />
          <datalist id="provider-model-options">
            {availableModels.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </datalist>
        </label>

        <label className="checkbox-row">
          <input
            checked={form.is_enabled}
            onChange={(event) => updateField("is_enabled", event.target.checked)}
            type="checkbox"
          />
          <span>Enabled</span>
        </label>

        <label>
          <span>Description</span>
          <textarea
            onChange={(event) => updateField("description", event.target.value)}
            rows={3}
            value={form.description}
          />
        </label>

        <label>
          <span>Configuration (JSON)</span>
          <textarea
            onChange={(event) => updateField("configuration", event.target.value)}
            rows={5}
            value={form.configuration}
            placeholder='{"temperature": 0.7, "max_tokens": 2000}'
          />
        </label>

        <button className="primary-button" disabled={busy} type="submit">
          {busy ? "Saving..." : initialProvider ? "Save Provider" : "Create Provider"}
        </button>

        {initialProvider ? (
          <>
            <hr className="form-divider" />
            <div className="provider-test-section">
              <h3>Test Connection</h3>
              <button
                className="secondary-button"
                onClick={handleTest}
                disabled={testLoading}
                type="button"
              >
                {testLoading ? "Testing..." : "Test Connection"}
              </button>
              {testResult ? (
                <div className={`test-result test-result-${testResult.status}`}>
                  <strong>{testResult.status === "ok" ? "Success" : "Warning"}</strong>
                  <p>{testResult.message}</p>
                  <dl>
                    <div>
                      <dt>Provider</dt>
                      <dd>{testResult.provider_type}</dd>
                    </div>
                    <div>
                      <dt>Default Model</dt>
                      <dd>{testResult.default_model ?? "None set"}</dd>
                    </div>
                    <div>
                      <dt>API Key Configured</dt>
                      <dd>{testResult.has_active_api_key ? "Yes" : "No"}</dd>
                    </div>
                  </dl>
                </div>
              ) : null}
            </div>
          </>
        ) : null}
      </form>
    </section>
  );
}
