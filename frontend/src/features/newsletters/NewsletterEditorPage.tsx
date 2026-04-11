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
  onGenerate?: (newsletterId: number) => Promise<void>;
  onSave: (payload: NewsletterInput, newsletterId?: number) => Promise<void>;
};

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
  name: "Operator-facing name used across the UI, runs, and delivery history.",
  description: "Internal summary of the newsletter's purpose, audience, or scope.",
  status: "Lifecycle state that controls whether the newsletter can be scheduled or sent.",
  prompt: "Instructions sent to the AI provider when generating a draft.",
  draft_subject: "Subject line used for previews, test sends, and live sends.",
  draft_preheader: "Preview text shown alongside the subject line in inboxes.",
  draft_body_text: "Body copy that gets rendered into the selected email template.",
  audience_name: "Used for audience segmentation in analytics",
  delivery_topic: "Topic name for webhook filtering and delivery tracking",
  provider_name: "AI provider for content generation (requires matching API key)",
  api_key_id: "Optional active AI API key to pin for this newsletter's generation requests",
  resend_api_key_id: "Optional active Resend API key to pin for this newsletter's delivery requests",
  model_name: "Specific AI model to use for generating content",
  template_key: "Email template design that determines the visual layout",
  timezone: "Timezone for interpreting the schedule cron expression",
  schedule_enabled: "Enable automatic recurring sends based on the cron schedule. Requires a valid cron expression.",
  schedule_cron: "Cron expression for recurring sends (e.g., 0 9 * * 1 for Mondays at 9am)",
  notes: "Internal notes for approvals, runbooks, or editorial context.",
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
  return (formOptions?.api_keys ?? []).filter(
    (apiKey) => apiKey.provider_type === providerName
  );
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

export function NewsletterEditorPage({
  busy,
  initialNewsletter,
  onCancel,
  onGenerate,
  onSave
}: NewsletterEditorPageProps) {
  const [form, setForm] = useState<NewsletterInput>(
    initialNewsletter ? toNewsletterInput(initialNewsletter) : emptyNewsletterInput
  );
  const [formOptions, setFormOptions] = useState<FormOptions | null>(null);
  const [formOptionsError, setFormOptionsError] = useState<string | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);

  const title = useMemo(
    () => (initialNewsletter ? `Edit ${initialNewsletter.name}` : "Create newsletter"),
    [initialNewsletter]
  );

  useEffect(() => {
    setForm(initialNewsletter ? toNewsletterInput(initialNewsletter) : emptyNewsletterInput);
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

  useEffect(() => {
    setForm((current) => {
      const next = { ...current };
      let changed = false;

      const apiKeys = getAvailableApiKeys(next.provider_name, formOptions);
      if (next.api_key_id !== null && !apiKeys.some((apiKey) => apiKey.id === next.api_key_id)) {
        next.api_key_id = null;
        changed = true;
      }

      const resendApiKeys = getAvailableResendApiKeys(formOptions);
      if (
        next.resend_api_key_id !== null
        && !resendApiKeys.some((apiKey) => apiKey.id === next.resend_api_key_id)
      ) {
        next.resend_api_key_id = null;
        changed = true;
      }

      return changed ? next : current;
    });
  }, [form.provider_name, formOptions]);

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

  function updateField<K extends keyof NewsletterInput>(key: K, value: NewsletterInput[K]) {
    setForm((current) => {
      return { ...current, [key]: value };
    });
  }

  async function handleSubmit() {
    await onSave(form, initialNewsletter?.id);
  }

  return (
    <section className="editor-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">Newsletter editor</p>
          <h2 className="section-title">{title}</h2>
        </div>
        <button className="secondary-button" onClick={onCancel} type="button">
          Back to list
        </button>
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
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="archived">Archived</option>
            </select>
          </label>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Content Generation</h3>

          <label>
            <FieldLabel label="Prompt" helpText={fieldHelpText.prompt} />
            <textarea
              onChange={(event) => updateField("prompt", event.target.value)}
              rows={4}
              value={form.prompt}
            />
          </label>

          <div className="form-grid">
            <label>
              <FieldLabel label="Draft Subject" helpText={fieldHelpText.draft_subject} />
              <input
                onChange={(event) => updateField("draft_subject", event.target.value)}
                value={form.draft_subject}
              />
            </label>

            <label>
              <FieldLabel label="Draft Preheader" helpText={fieldHelpText.draft_preheader} />
              <input
                onChange={(event) => updateField("draft_preheader", event.target.value)}
                value={form.draft_preheader}
              />
            </label>
          </div>

          <label>
            <FieldLabel label="Draft Body" helpText={fieldHelpText.draft_body_text} />
            <textarea
              onChange={(event) => updateField("draft_body_text", event.target.value)}
              rows={8}
              value={form.draft_body_text}
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
              <FieldLabel label="AI API Key" helpText={fieldHelpText.api_key_id} />
              <select
                onChange={(event) => updateField("api_key_id", event.target.value ? Number(event.target.value) : null)}
                value={form.api_key_id === null ? "" : String(form.api_key_id)}
              >
                <option value="">
                  {availableApiKeys.length > 0 ? "Use any matching active API key" : "No matching API keys available"}
                </option>
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
                    ? "Use the environment Resend API key"
                    : "No active Resend API keys available"}
                </option>
                {availableResendApiKeys.map((apiKey) => (
                  <option key={apiKey.id} value={String(apiKey.id)}>
                    {`${apiKey.name} (${apiKey.masked_key})`}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="form-grid">
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
          {initialNewsletter ? (
            <button
              className="secondary-button"
              disabled={busy}
              onClick={() => void onGenerate?.(initialNewsletter.id)}
              type="button"
            >
              {busy ? "Working..." : "Generate Draft"}
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}

function HelpText({ text }: { text: string }) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span className="help-text-wrapper">
      <span
        className="help-text-icon"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        role="button"
        tabIndex={0}
        aria-label="Show help"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </span>
      {showTooltip ? (
        <span className="help-text-tooltip">
          {text}
        </span>
      ) : null}
    </span>
  );
}
