import { useEffect, useMemo, useState } from "react";

import {
  emptyNewsletterInput,
  type NewsletterDetail,
  type NewsletterInput,
  toNewsletterInput
} from "./newsletter-types";
import { api } from "../../lib/api";
import type { FormOptions } from "../../lib/api";

type NewsletterEditorPageProps = {
  busy: boolean;
  initialNewsletter: NewsletterDetail | null;
  onCancel: () => void;
  onRun: (newsletterId: number) => Promise<void>;
  onSave: (payload: NewsletterInput, newsletterId?: number) => Promise<void>;
};

type NewsletterEditorForm = NewsletterInput & {
  from_email: string;
};

type NewsletterEditorFieldAliases = Partial<{
  from_email: string | null;
}>;

type SelectOption = {
  value: string;
  label: string;
};

type ProviderSelectOption = {
  value: number;
  label: string;
  providerName: string;
};

const fieldHelpText: Record<string, string> = {
  name: "Public name of the newsletter",
  description: "Short summary used in listings and as context for the AI",
  prompt: "Instructions for the AI. It will generate the subject, preheader, and body automatically.",
  audience_name: "Used for audience segmentation in analytics",
  delivery_topic: "Topic name for webhook filtering and delivery tracking",
  provider_name: "AI provider for content generation",
  api_key_id: "Optional pinned credential for this newsletter's generation requests",
  resend_api_key_id: "Resend API key used for email delivery. Make sure the key has a Sender Email configured in Settings > API Keys.",
  from_email: "Sender email address. If not set, falls back to the Resend API key sender or the environment default.",
  model_name: "Specific AI model to use for generating content",
  template_key: "Email template design that determines the visual layout",
  timezone: "Timezone for interpreting the schedule cron expression",
  schedule_enabled: "Enable automatic recurring sends based on the cron schedule. Requires a valid cron expression.",
  schedule_cron: "Cron expression for recurring sends (e.g. 0 9 * * 1 for Mondays at 9am)",
  notes: "Internal notes, runbooks, or editorial context.",
  recipient_import_text: "Paste one email per line or separate addresses with commas or semicolons."
};

function FieldLabel({ label, helpText }: { label: string; helpText?: string }) {
  if (!helpText) {
    return <span>{label}</span>;
  }

  return (
    <span className="field-label-with-help">
      {label}
      <HelpText text={helpText} />
    </span>
  );
}

function getProviderOptions(formOptions: FormOptions | null): ProviderSelectOption[] {
  return (formOptions?.providers ?? []).map((provider) => ({
    value: provider.id,
    label: provider.name,
    providerName: provider.provider_type
  }));
}

function getAvailableModels(providerId: number | null, formOptions: FormOptions | null): string[] {
  if (providerId === null) return [];
  return formOptions?.models[String(providerId)] ?? [];
}

function getAvailableTemplates(formOptions: FormOptions | null) {
  return formOptions?.templates ?? [];
}

function getAvailableApiKeys(providerName: string, formOptions: FormOptions | null) {
  const keys = (formOptions?.api_keys ?? []).filter(
    (apiKey) => apiKey.provider_type === providerName
  );
  if (providerName === "openai_chatgpt") {
    return keys.filter((k) => k.auth_type === "oauth");
  }
  return keys;
}

function getAvailableResendApiKeys(formOptions: FormOptions | null) {
  return (formOptions?.api_keys ?? []).filter(
    (apiKey) => apiKey.provider_type === "resend"
  );
}

function getTimezoneOptions(formOptions: FormOptions | null): SelectOption[] {
  const timezones = formOptions?.timezones ?? [];
  return timezones.map((timezone) => ({
    value: timezone,
    label: timezone.replace(/_/g, " ")
  }));
}

function toEditorForm(detail: NewsletterDetail | null): NewsletterEditorForm {
  const base = (detail ? toNewsletterInput(detail) : emptyNewsletterInput) as NewsletterInput &
    NewsletterEditorFieldAliases;

  return {
    name: base.name,
    description: base.description,
    prompt: base.prompt,
    from_email: base.from_email ?? "",
    provider_id: base.provider_id,
    provider_name: base.provider_name,
    api_key_id: base.api_key_id,
    resend_api_key_id: base.resend_api_key_id,
    model_name: base.model_name,
    template_key: base.template_key,
    audience_name: base.audience_name,
    delivery_topic: base.delivery_topic,
    timezone: base.timezone,
    schedule_cron: base.schedule_cron,
    schedule_enabled: base.schedule_enabled,
    status: base.status,
    notes: base.notes,
    recipient_import_text: base.recipient_import_text
  };
}

function toSubmitPayload(form: NewsletterEditorForm): NewsletterInput {
  return {
    ...form
  } as NewsletterInput;
}

export function NewsletterEditorPage({
  busy,
  initialNewsletter,
  onCancel,
  onRun,
  onSave
}: NewsletterEditorPageProps) {
  const [form, setForm] = useState<NewsletterEditorForm>(toEditorForm(initialNewsletter));
  const [savedForm, setSavedForm] = useState<NewsletterEditorForm | null>(
    initialNewsletter ? toEditorForm(initialNewsletter) : null
  );
  const [formOptions, setFormOptions] = useState<FormOptions | null>(null);
  const [formOptionsError, setFormOptionsError] = useState<string | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);

  const title = useMemo(
    () => (initialNewsletter ? `Edit ${initialNewsletter.name}` : "Create newsletter"),
    [initialNewsletter]
  );

  const isDirty = useMemo(() => {
    if (!savedForm) return false;
    return JSON.stringify(form) !== JSON.stringify(savedForm);
  }, [form, savedForm]);

  useEffect(() => {
    const nextForm = toEditorForm(initialNewsletter);
    setForm(nextForm);
    setSavedForm(initialNewsletter ? nextForm : null);
  }, [initialNewsletter]);

  useEffect(() => {
    async function loadOptions() {
      setLoadingOptions(true);
      setFormOptionsError(null);
      try {
        const options = await api.formOptions();
        setFormOptions(options);
      } catch {
        setFormOptions(null);
        setFormOptionsError("Unable to load form options. Try refreshing the page.");
      } finally {
        setLoadingOptions(false);
      }
    }
    void loadOptions();
  }, []);

  const providerOptions = useMemo(() => getProviderOptions(formOptions), [formOptions]);

  const selectedProviderValue = useMemo(() => {
    const selectedProvider = providerOptions.find((provider) => provider.value === form.provider_id)
      ?? providerOptions.find((provider) => provider.providerName === form.provider_name);

    return selectedProvider ? String(selectedProvider.value) : "";
  }, [form.provider_id, form.provider_name, providerOptions]);

  const availableModels = useMemo(
    () => getAvailableModels(form.provider_id, formOptions),
    [form.provider_id, formOptions]
  );

  const availableTemplates = useMemo(() => getAvailableTemplates(formOptions), [formOptions]);

  const availableApiKeys = useMemo(
    () => getAvailableApiKeys(form.provider_name, formOptions),
    [form.provider_name, formOptions]
  );

  const availableResendApiKeys = useMemo(
    () => getAvailableResendApiKeys(formOptions),
    [formOptions]
  );

  const timezoneOptions = useMemo(() => getTimezoneOptions(formOptions), [formOptions]);
  const providerSelectDisabled = loadingOptions || providerOptions.length === 0;
  const modelSelectDisabled = loadingOptions || form.provider_id === null || availableModels.length === 0;
  const templateSelectDisabled = loadingOptions || availableTemplates.length === 0;
  const timezoneSelectDisabled = loadingOptions || timezoneOptions.length === 0;

  const missingApiKeyOption = useMemo(() => {
    if (form.api_key_id == null) return null;
    if (availableApiKeys.some((k) => k.id === form.api_key_id)) return null;
    return { id: form.api_key_id, label: `Key #${form.api_key_id} (not available or inactive)` };
  }, [form.api_key_id, availableApiKeys]);

  const missingResendKeyOption = useMemo(() => {
    if (form.resend_api_key_id == null) return null;
    if (availableResendApiKeys.some((k) => k.id === form.resend_api_key_id)) return null;
    return { id: form.resend_api_key_id, label: `Key #${form.resend_api_key_id} (not available or inactive)` };
  }, [form.resend_api_key_id, availableResendApiKeys]);

  function updateProvider(providerValue: string) {
    setForm((current) => {
      if (!providerValue) {
        return {
          ...current,
          provider_id: null,
          provider_name: "",
          model_name: "",
          api_key_id: null
        };
      }

      const providerId = Number(providerValue);
      const selectedProvider = providerOptions.find((provider) => provider.value === providerId);
      if (!selectedProvider) {
        return current;
      }

      const next = {
        ...current,
        provider_id: selectedProvider.value,
        provider_name: selectedProvider.providerName
      };

      const models = getAvailableModels(selectedProvider.value, formOptions);
      if (!models.includes(next.model_name)) {
        next.model_name = "";
      }

      const apiKeys = getAvailableApiKeys(selectedProvider.providerName, formOptions);
      if (next.api_key_id !== null && !apiKeys.some((apiKey) => apiKey.id === next.api_key_id)) {
        next.api_key_id = null;
      }

      return next;
    });
  }

  function updateField<K extends keyof NewsletterEditorForm>(key: K, value: NewsletterEditorForm[K]) {
    setForm((current) => {
      return { ...current, [key]: value };
    });
  }

  async function handleSubmit() {
    await onSave(toSubmitPayload(form), initialNewsletter?.id);
  }

  return (
    <section className="editor-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">Newsletter editor</p>
          <h2 className="section-title">{title}</h2>
        </div>
        <div>
          {initialNewsletter && initialNewsletter.status === "active" ? (
            <button
              className="secondary-button"
              disabled={busy || isDirty}
              onClick={() => void onRun(initialNewsletter!.id)}
              title={isDirty ? "Save changes before running" : undefined}
              type="button"
            >
              {busy ? "Working..." : "Run Now"}
            </button>
          ) : null}
          <button className="secondary-button" onClick={onCancel} type="button">
            Back to list
          </button>
        </div>
      </header>

      <form className="editor-form newsletter-editor">
        {loadingOptions ? <p className="form-notice">Loading form options...</p> : null}
        {formOptionsError ? <p className="form-notice">{formOptionsError}</p> : null}

        <div className="form-section">
          <h3 className="form-section-title">Basic Information</h3>

          <label>
            <FieldLabel label="Name" helpText={fieldHelpText.name} />
            <input onChange={(event) => updateField("name", event.target.value)} required value={form.name} />
          </label>

          <label>
            <FieldLabel label="Description" helpText={fieldHelpText.description} />
            <textarea
              onChange={(event) => updateField("description", event.target.value)}
              rows={2}
              value={form.description}
            />
          </label>

          <label>
            <FieldLabel label="Status" helpText={fieldHelpText.status} />
            <select onChange={(event) => updateField("status", event.target.value)} value={form.status}>
              <option value="">Select status</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="archived">Archived</option>
            </select>
          </label>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Prompt</h3>

          <label>
            <FieldLabel label="Prompt" helpText={fieldHelpText.prompt} />
            <textarea
              onChange={(event) => updateField("prompt", event.target.value)}
              rows={6}
              value={form.prompt}
            />
          </label>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Configuration</h3>

          <div className="form-grid">
            <label>
              <FieldLabel label="Provider" helpText={fieldHelpText.provider_name} />
              <select
                onChange={(event) => updateProvider(event.target.value)}
                value={selectedProviderValue}
                disabled={providerSelectDisabled}
              >
                {loadingOptions ? <option value="">Loading providers...</option> : null}
                {!loadingOptions && providerOptions.length === 0 ? (
                  <option value="">No enabled providers available</option>
                ) : null}
                {!loadingOptions && providerOptions.length > 0 ? (
                  <option value="">Select provider</option>
                ) : null}
                {providerOptions.map((option) => (
                  <option key={option.value} value={String(option.value)}>{option.label}</option>
                ))}
              </select>
            </label>

            <label>
              <FieldLabel label="Model" helpText={fieldHelpText.model_name} />
              <select
                onChange={(event) => updateField("model_name", event.target.value)}
                value={form.model_name}
                disabled={modelSelectDisabled}
              >
                {loadingOptions ? <option value="">Loading models...</option> : null}
                {!loadingOptions && availableModels.length === 0 ? (
                  <option value="">No models available</option>
                ) : null}
                {!loadingOptions && availableModels.length > 0 ? (
                  <option value="">Select model</option>
                ) : null}
                {availableModels.map(model => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="form-grid">
            <label>
              <FieldLabel label={form.provider_name === "openai_chatgpt" ? "OAuth Connection" : "AI API Key"} helpText={fieldHelpText.api_key_id} />
              <select
                onChange={(event) => updateField("api_key_id", event.target.value ? Number(event.target.value) : null)}
                value={form.api_key_id === null ? "" : String(form.api_key_id)}
              >
                <option value="">
                  {availableApiKeys.length > 0
                    ? "No pinned credential selected (fail closed)"
                    : form.provider_name === "openai_chatgpt"
                      ? "No OAuth connection available — connect in Settings > API Keys"
                      : "No matching API keys available"}
                </option>
                {missingApiKeyOption ? (
                  <option disabled value={String(missingApiKeyOption.id)}>
                    {missingApiKeyOption.label}
                  </option>
                ) : null}
                {availableApiKeys.map((apiKey) => (
                  <option key={apiKey.id} value={String(apiKey.id)}>
                    {`${apiKey.name} (${apiKey.masked_key})`}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <FieldLabel label="Resend API Key" helpText={fieldHelpText.resend_api_key_id} />
              <select
                onChange={(event) => updateField("resend_api_key_id", event.target.value ? Number(event.target.value) : null)}
                value={form.resend_api_key_id === null ? "" : String(form.resend_api_key_id)}
              >
                <option value="">
                  {availableResendApiKeys.length > 0
                    ? "No pinned Resend key selected (fail closed)"
                    : "No active Resend API keys — add one in Settings > API Keys"}
                </option>
                {missingResendKeyOption ? (
                  <option disabled value={String(missingResendKeyOption.id)}>
                    {missingResendKeyOption.label}
                  </option>
                ) : null}
                {availableResendApiKeys.map((apiKey) => (
                  <option key={apiKey.id} value={String(apiKey.id)}>
                    {apiKey.from_email
                      ? `${apiKey.name} — ${apiKey.from_email}`
                      : `${apiKey.name} — no sender email configured`}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="form-grid">
            <label>
              <FieldLabel label="From Email" helpText={fieldHelpText.from_email} />
              <input
                onChange={(event) => updateField("from_email", event.target.value)}
                placeholder="newsletter@example.com"
                value={form.from_email}
              />
            </label>

            <label>
              <FieldLabel label="Template" helpText={fieldHelpText.template_key} />
              <select
                onChange={(event) => updateField("template_key", event.target.value)}
                value={form.template_key}
                disabled={templateSelectDisabled}
              >
                {loadingOptions ? <option value="">Loading templates...</option> : null}
                {!loadingOptions && availableTemplates.length === 0 ? (
                  <option value="">No templates available</option>
                ) : null}
                {!loadingOptions && availableTemplates.length > 0 ? (
                  <option value="">Select template</option>
                ) : null}
                {availableTemplates.map((template) => (
                  <option key={template.key} value={template.key}>{template.name}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="form-grid">
            <label>
              <FieldLabel label="Audience" helpText={fieldHelpText.audience_name} />
              <input
                onChange={(event) => updateField("audience_name", event.target.value)}
                value={form.audience_name}
              />
            </label>
          </div>

          <div className="form-grid">
            <label>
              <FieldLabel label="Delivery Topic" helpText={fieldHelpText.delivery_topic} />
              <input
                onChange={(event) => updateField("delivery_topic", event.target.value)}
                value={form.delivery_topic}
              />
            </label>
          </div>

          <div className="form-grid">
            <label>
              <FieldLabel label="Timezone" helpText={fieldHelpText.timezone} />
              <select
                onChange={(event) => updateField("timezone", event.target.value)}
                value={form.timezone}
                disabled={timezoneSelectDisabled}
              >
                {loadingOptions ? <option value="">Loading timezones...</option> : null}
                {!loadingOptions && timezoneOptions.length === 0 ? (
                  <option value="">No timezones available</option>
                ) : null}
                {!loadingOptions && timezoneOptions.length > 0 ? (
                  <option value="">Select timezone</option>
                ) : null}
                {timezoneOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </label>

            <label>
              <FieldLabel label="Notes" helpText={fieldHelpText.notes} />
              <input onChange={(event) => updateField("notes", event.target.value)} value={form.notes} />
            </label>
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Scheduling</h3>

          <div className="form-grid">
            <label>
              <FieldLabel label="Schedule Cron" helpText={fieldHelpText.schedule_cron} />
              <input
                onChange={(event) => updateField("schedule_cron", event.target.value)}
                value={form.schedule_cron}
              />
            </label>

            <label className="checkbox-row schedule-enabled-row">
              <input
                checked={form.schedule_enabled}
                onChange={(event) => updateField("schedule_enabled", event.target.checked)}
                type="checkbox"
              />
              <span>Enable recurring schedule</span>
            </label>
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Recipients</h3>

          <label>
            <FieldLabel label="Recipients" helpText={fieldHelpText.recipient_import_text} />
            <textarea
              onChange={(event) => updateField("recipient_import_text", event.target.value)}
              rows={5}
              value={form.recipient_import_text}
            />
          </label>
        </div>

        <div className="form-actions">
          <button className="primary-button" disabled={busy} onClick={() => void handleSubmit()} type="button">
            {busy ? "Saving..." : initialNewsletter ? "Save Newsletter" : "Create Newsletter"}
          </button>
        </div>
      </form>
    </section>
  );
}

function HelpText({ text }: { text: string }) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span className="help-text-wrapper">
      <button
        className="help-text-icon"
        type="button"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        aria-label="Show help"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
          <title>Help</title>
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </button>
      {showTooltip ? (
        <span className="help-text-tooltip">
          {text}
        </span>
      ) : null}
    </span>
  );
}
