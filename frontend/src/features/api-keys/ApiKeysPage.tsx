import { useEffect, useMemo, useState } from "react";
import type { ApiKeySummary, ApiKeyDetail, ApiKeyInput } from "./api-key-types";
import { emptyApiKeyInput, toApiKeyInput } from "./api-key-types";
import { getProviderTypeOptionsFromPresets, type ProviderPreset } from "../providers/provider-types";
import { api } from "../../lib/api";
import type { ApiKeyTestResponse } from "../../lib/api";
import { ConnectChatGPTModal } from "./ConnectChatGPTModal";
import { ChatGPTConnectionCard } from "./ChatGPTConnectionCard";

type ApiKeysPageProps = {
  apiKeys: ApiKeySummary[];
  loading?: boolean;
  error?: string | null;
  onDismissError?: () => void;
  onCreate: () => void;
  onEdit: (apiKey: ApiKeySummary) => void;
  onDelete: (apiKeyId: number) => Promise<void>;
  onToggleActive: (apiKeyId: number, active: boolean) => Promise<void>;
  onRefresh: () => void;
};

export function ApiKeysPage({
  apiKeys,
  loading,
  error,
  onDismissError,
  onCreate,
  onEdit,
  onDelete,
  onToggleActive,
  onRefresh
}: ApiKeysPageProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [showChatGPTModal, setShowChatGPTModal] = useState(false);

  const oauthApiKeys = apiKeys.filter((k) => k.auth_type === "oauth");
  const regularApiKeys = apiKeys.filter(
    (k) => k.auth_type !== "oauth" && k.provider_type !== "openai_chatgpt"
  );
  const hasOAuthConnection = oauthApiKeys.length > 0;

  async function handleDelete(apiKeyId: number) {
    setDeletingId(apiKeyId);
    try {
      await onDelete(apiKeyId);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleToggle(apiKeyId: number, currentActive: boolean) {
    setTogglingId(apiKeyId);
    try {
      await onToggleActive(apiKeyId, !currentActive);
    } finally {
      setTogglingId(null);
    }
  }

  function formatLastUsed(date: string | null): string {
    if (!date) return "Never";
    const d = new Date(date);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 30) return `${days} days ago`;
    return d.toLocaleDateString();
  }

  return (
    <section className="newsletters-grid">
      <header className="section-header">
        <div>
          <p className="eyebrow">API Keys</p>
          <h2 className="section-title">Manage credentials for AI providers and Resend.</h2>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="secondary-button"
            onClick={() => setShowChatGPTModal(true)}
            type="button"
          >
            {hasOAuthConnection ? "Reconnect ChatGPT" : "Connect ChatGPT"}
          </button>
          <button className="primary-button" onClick={onCreate} type="button">
            New API Key
          </button>
        </div>
      </header>

      {showChatGPTModal && (
        <ConnectChatGPTModal
          onConnected={() => {
            setShowChatGPTModal(false);
            onRefresh();
          }}
          onCancel={() => setShowChatGPTModal(false)}
        />
      )}

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

      {oauthApiKeys.length > 0 && (
        <div className="newsletter-list" style={{ marginBottom: 16 }}>
          {oauthApiKeys.map((apiKey) => (
            <ChatGPTConnectionCard
              key={apiKey.id}
              apiKey={apiKey}
              onDisconnected={onRefresh}
              onRefreshed={onRefresh}
            />
          ))}
        </div>
      )}

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
      ) : regularApiKeys.length === 0 && oauthApiKeys.length === 0 ? (
        <article className="empty-state">
          <h3>No API keys yet</h3>
          <p>
            Add your first API key. You'll need provider keys for AI generation
            and can optionally store Resend delivery keys here too.
          </p>
        </article>
      ) : regularApiKeys.length > 0 ? (
        <div className="newsletter-list">
          {regularApiKeys.map((apiKey) => (
            <article className="newsletter-card" key={apiKey.id}>
              <div className="newsletter-card-header">
                <div>
                  <h3>{apiKey.name}</h3>
                  <p>{apiKey.masked_key}</p>
                </div>
                <span className={`status-chip ${apiKey.is_active ? "status-active" : "status-paused"}`}>
                  {apiKey.is_active ? "Active" : "Inactive"}
                </span>
              </div>

              <dl className="newsletter-meta">
                <div>
                  <dt>Provider</dt>
                  <dd>{apiKey.provider_type}</dd>
                </div>
                <div>
                  <dt>Last Used</dt>
                  <dd>{formatLastUsed(apiKey.last_used_at)}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{new Date(apiKey.created_at).toLocaleDateString()}</dd>
                </div>
                {apiKey.provider_type === "resend" ? (
                  <div>
                    <dt>Sender Email</dt>
                    <dd>{apiKey.from_email ? apiKey.from_email : (
                      <span style={{ color: "#b45309" }}>Not configured — sending disabled</span>
                    )}</dd>
                  </div>
                ) : null}
              </dl>

              <div className="card-actions">
                <button className="secondary-button" onClick={() => onEdit(apiKey)} type="button">
                  Edit
                </button>
                <button
                  className="secondary-button"
                  onClick={() => void handleToggle(apiKey.id, apiKey.is_active)}
                  disabled={togglingId === apiKey.id}
                  type="button"
                >
                  {togglingId === apiKey.id
                    ? "Updating..."
                    : apiKey.is_active
                      ? "Deactivate"
                      : "Activate"}
                </button>
                <button
                  className="danger-button"
                  onClick={() => void handleDelete(apiKey.id)}
                  disabled={deletingId === apiKey.id}
                  type="button"
                >
                  {deletingId === apiKey.id ? "Deleting..." : "Delete"}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

type ApiKeyEditorProps = {
  initialApiKey: ApiKeyDetail | null;
  onCancel: () => void;
  onSave: (payload: ApiKeyInput, apiKeyId?: number) => Promise<void>;
};

export function ApiKeyEditor({
  initialApiKey,
  onCancel,
  onSave
}: ApiKeyEditorProps) {
  const [form, setForm] = useState<ApiKeyInput>(
    initialApiKey ? toApiKeyInput(initialApiKey) : emptyApiKeyInput
  );
  const [busy, setBusy] = useState(false);
  const [testResult, setTestResult] = useState<ApiKeyTestResponse | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [presets, setPresets] = useState<ProviderPreset[]>([]);

  useEffect(() => {
    let isActive = true;

    async function loadPresets() {
      try {
        const nextPresets = await api.providers.listPresets();
        if (!isActive) return;
        setPresets(nextPresets);
      } catch {
        if (!isActive) return;
        setPresets([]);
      }
    }

    void loadPresets();

    return () => {
      isActive = false;
    };
  }, []);

  const title = useMemo(
    () => (initialApiKey ? `Edit ${initialApiKey.name}` : "Create API key"),
    [initialApiKey]
  );

  const providerOptions = useMemo(
    () => [
      ...getProviderTypeOptionsFromPresets(presets).filter(
        (preset) => preset.value !== "openai_chatgpt"
      ),
      { value: "resend", label: "Resend" }
    ],
    [presets]
  );

  function updateField<K extends keyof ApiKeyInput>(key: K, value: ApiKeyInput[K]) {
    setForm((current) => ({
      ...current,
      [key]: value
    }));
  }

  async function handleSubmit() {
    setBusy(true);
    try {
      await onSave(form, initialApiKey?.id);
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    if (!initialApiKey) return;
    setTestLoading(true);
    try {
      const result = await api.apiKeys.test(initialApiKey.id);
      setTestResult(result);
    } finally {
      setTestLoading(false);
    }
  }

  return (
    <section className="editor-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">API key editor</p>
          <h2 className="section-title">{title}</h2>
        </div>
        <button className="secondary-button" onClick={onCancel} type="button">
          Back to list
        </button>
      </header>

      <form className="editor-form">
        <label>
          <span>Name</span>
          <input
            onChange={(event) => updateField("name", event.target.value)}
            required
            value={form.name}
          />
        </label>

        <label>
          <span>Provider</span>
          <select
            onChange={(event) => updateField("provider_type", event.target.value)}
            required
            value={form.provider_type}
          >
            <option value="">Select a provider...</option>
            {providerOptions.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>{initialApiKey ? "API Key (leave blank to keep unchanged)" : "API Key"}</span>
          <input
            onChange={(event) => updateField("key_value", event.target.value)}
            required={!initialApiKey}
            type="password"
            value={form.key_value ?? ""}
            placeholder={initialApiKey ? "••••••••••••" : "sk-..."}
          />
        </label>

        {form.provider_type === "resend" ? (
          <label>
            <span>Sender Email</span>
            <input
              onChange={(event) => updateField("from_email", event.target.value || null)}
              type="email"
              value={form.from_email ?? ""}
              placeholder="newsletter@yourdomain.com"
            />
            <small style={{ display: "block", marginTop: "4px", fontSize: "13px", color: "#5c6b78" }}>
              The verified sender email address from your Resend account. Required for sending newsletters.
            </small>
          </label>
        ) : null}

        <label className="checkbox-row">
          <input
            checked={form.is_active}
            onChange={(event) => updateField("is_active", event.target.checked)}
            type="checkbox"
          />
          <span>Active</span>
        </label>

        <button className="primary-button" disabled={busy} onClick={() => void handleSubmit()} type="button">
          {busy ? "Saving..." : initialApiKey ? "Save API Key" : "Create API Key"}
        </button>

        {initialApiKey ? (
          <>
            <hr className="form-divider" />
            <div className="provider-test-section">
              <h3>Test API Key</h3>
              <button
                className="secondary-button"
                onClick={handleTest}
                disabled={testLoading}
                type="button"
              >
                {testLoading ? "Testing..." : "Test API Key"}
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
                      <dt>Key</dt>
                      <dd>{testResult.masked_key}</dd>
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
