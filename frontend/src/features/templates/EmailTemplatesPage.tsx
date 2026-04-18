import { useState, useMemo, useEffect, type BaseSyntheticEvent } from "react";
import type { EmailTemplateSummary, EmailTemplateDetail, EmailTemplateInput, TemplatePreset } from "./template-types";
import { emptyEmailTemplateInput, toEmailTemplateInput } from "./template-types";
import { api } from "../../lib/api";
import { ActionDropdown, type ActionItem } from "../../components/ui/ActionDropdown";

type EmailTemplatesPageProps = {
  templates: EmailTemplateSummary[];
  loading?: boolean;
  error?: string | null;
  onDismissError?: () => void;
  onCreate: () => void;
  onEdit: (template: EmailTemplateSummary) => void;
  onDelete: (templateId: number) => Promise<void>;
  onSetDefault: (templateId: number) => Promise<void>;
  onRefresh: () => void;
};

export function EmailTemplatesPage(props: EmailTemplatesPageProps) {
  const {
    templates,
    loading,
    error,
    onDismissError,
    onCreate,
    onEdit,
    onDelete,
    onSetDefault
  } = props;
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [settingDefaultId, setSettingDefaultId] = useState<number | null>(null);

  void props.onRefresh;

  async function handleDelete(templateId: number) {
    setDeletingId(templateId);
    try {
      await onDelete(templateId);
    } finally {
      setDeletingId(null);
    }
  }

  async function handleSetDefault(templateId: number) {
    setSettingDefaultId(templateId);
    try {
      await onSetDefault(templateId);
    } finally {
      setSettingDefaultId(null);
    }
  }

  function getTemplateActions(template: EmailTemplateSummary): ActionItem[] {
    const actions: ActionItem[] = [
      {
        label: "Edit",
        onClick: () => onEdit(template),
        icon: (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M11.5 2.5l2 2M2 14l3-1 8.5-8.5-2-2L3 11 2 14z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )
      }
    ];

    if (!template.is_default) {
      actions.push({
        label: "Set Default",
        onClick: () => void handleSetDefault(template.id),
        disabled: settingDefaultId === template.id,
        variant: "primary",
        icon: (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )
      });
    }

    if (!template.is_system) {
      actions.push({
        label: "Delete",
        onClick: () => void handleDelete(template.id),
        disabled: deletingId === template.id,
        variant: "danger",
        icon: (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 4h12M12 4v9a1 1 0 01-1 1H5a1 1 0 01-1-1V4M6 2h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        )
      });
    }

    return actions;
  }

  return (
    <section className="data-grid-section">
      <header className="section-header">
        <div>
          <p className="eyebrow">Email Templates</p>
          <h2 className="section-title">Design reusable email layouts</h2>
        </div>
        <button className="primary-button" onClick={onCreate} type="button">
          New Template
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
        <div className="data-table-container">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Key</th>
                  <th>Default</th>
                  <th>Updated</th>
                  <th className="actions-column">Actions</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 3 }, (_, index) => (
                  <tr key={index} className="loading-row">
                    <td><div className="loading-skeleton-bar" style={{ width: '150px' }} /></td>
                    <td><div className="loading-skeleton-bar" style={{ width: '120px' }} /></td>
                    <td><div className="loading-skeleton-bar" style={{ width: '80px' }} /></td>
                    <td><div className="loading-skeleton-bar" style={{ width: '100px' }} /></td>
                    <td><div className="loading-skeleton-bar" style={{ width: '60px' }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : templates.length === 0 ? (
        <article className="empty-state">
          <h3>No templates yet</h3>
          <p>
            Create your first email template. Design reusable HTML layouts for your newsletters
            with customizable variables and consistent branding.
          </p>
        </article>
      ) : (
        <div className="data-table-container">
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Key</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th className="actions-column">Actions</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => (
                  <tr key={template.id} className="data-row">
                    <td className="name-cell">
                      <div className="cell-primary">{template.name}</div>
                      <div className="cell-secondary">{template.description || "No description"}</div>
                    </td>
                    <td data-label="Key">
                      <code>{template.key}</code>
                    </td>
                    <td data-label="Status">
                      <div className="template-badges">
                        {template.is_default ? (
                          <span className="status-badge status-active">Default</span>
                        ) : null}
                        {template.is_system ? (
                          <span className="status-badge">System</span>
                        ) : null}
                      </div>
                    </td>
                    <td className="cell-secondary" data-label="Updated">
                      {new Date(template.updated_at).toLocaleDateString()}
                    </td>
                    <td className="actions-cell">
                      <ActionDropdown actions={getTemplateActions(template)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

type EmailTemplateEditorProps = {
  initialTemplate: EmailTemplateDetail | null;
  onCancel: () => void;
  onSave: (payload: EmailTemplateInput, templateId?: number) => Promise<void>;
};

export function EmailTemplateEditor({
  initialTemplate,
  onCancel,
  onSave
}: EmailTemplateEditorProps) {
  const [form, setForm] = useState<EmailTemplateInput>(
    initialTemplate ? toEmailTemplateInput(initialTemplate) : emptyEmailTemplateInput
  );
  const [busy, setBusy] = useState(false);
  const [presets, setPresets] = useState<TemplatePreset[]>([]);
  const [selectedPresetKey, setSelectedPresetKey] = useState<string | null>(null);

  const title = useMemo(
    () => (initialTemplate ? `Edit ${initialTemplate.name}` : "Create email template"),
    [initialTemplate]
  );

  useEffect(() => {
    let isActive = true;

    async function loadPresets() {
      try {
        const nextPresets = await api.emailTemplates.listPresets();
        if (!isActive) return;
        setPresets(nextPresets);
      } catch {
        setPresets([]);
      }
    }

    void loadPresets();

    return () => {
      isActive = false;
    };
  }, []);

  function updateField<K extends keyof EmailTemplateInput>(key: K, value: EmailTemplateInput[K]) {
    setForm((current) => ({
      ...current,
      [key]: value
    }));
  }

  function applyPreset(presetKey: string) {
    const preset = presets.find((p) => p.key === presetKey);
    if (!preset) return;

    setSelectedPresetKey(presetKey);
    setForm((current) => ({
      ...current,
      name: current.name || preset.name,
      key: current.key || preset.key,
      html_template: preset.html_template
    }));
  }

  async function handleSubmit(event: BaseSyntheticEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await onSave(form, initialTemplate?.id);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="editor-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">Email template editor</p>
          <h2 className="section-title">{title}</h2>
        </div>
        <button className="secondary-button" onClick={onCancel} type="button">
          Back to list
        </button>
      </header>

      {!initialTemplate && presets.length > 0 && (
        <div className="template-presets-section">
          <h3>Choose a preset</h3>
          <div className="template-presets-grid">
            {presets.map((preset) => (
              <div
                key={preset.key}
                className={`template-preset-card ${selectedPresetKey === preset.key ? 'selected' : ''}`}
                onClick={() => applyPreset(preset.key)}
              >
                <h4>{preset.name}</h4>
                <p>{preset.description}</p>
              </div>
            ))}
          </div>
          <hr className="form-divider" />
        </div>
      )}

      <form className="editor-form" onSubmit={handleSubmit}>
        <label>
          <span>Name</span>
          <input
            onChange={(event) => updateField("name", event.target.value)}
            required
            value={form.name}
          />
        </label>

        <label>
          <span>Key</span>
          <input
            onChange={(event) => updateField("key", event.target.value)}
            required
            pattern="^[a-z0-9][a-z0-9_-]*$"
            title="Must start with letter/number, contain only lowercase letters, numbers, hyphens, or underscores"
            value={form.key}
          />
        </label>

        <label>
          <span>Description</span>
          <textarea
            onChange={(event) => updateField("description", event.target.value)}
            rows={2}
            value={form.description}
          />
        </label>

        <label>
          <span>HTML Template</span>
          <textarea
            onChange={(event) => updateField("html_template", event.target.value)}
            required
            rows={20}
            value={form.html_template}
            placeholder={'<!DOCTYPE html>\n<html>\n<head>\n  <meta charset="UTF-8">\n  <title>{{subject}}</title>\n</head>\n<body>\n  <h1>{{headline}}</h1>\n  <div>{{body_html}}</div>\n</body>\n</html>'}
          />
        </label>

        <p className="template-variables-hint">
          Available variables: subject, preheader, headline, newsletter_name, body_html, content
        </p>

        <label className="checkbox-row">
          <input
            checked={form.is_default}
            onChange={(event) => updateField("is_default", event.target.checked)}
            type="checkbox"
          />
          <span>Set as default template</span>
        </label>

        <button className="primary-button" disabled={busy} type="submit">
          {busy ? "Saving..." : initialTemplate ? "Save Template" : "Create Template"}
        </button>
      </form>
    </section>
  );
}