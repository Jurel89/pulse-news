import { useState, useMemo, useEffect, type BaseSyntheticEvent } from "react";
import type { EmailTemplateSummary, EmailTemplateDetail, EmailTemplateInput, TemplatePreset } from "./template-types";
import { emptyEmailTemplateInput, toEmailTemplateInput } from "./template-types";
import { api } from "../../lib/api";

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
                  <td><div className="loading-skeleton-bar" style={{ width: '150px' }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
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
                  <td>
                    <code>{template.key}</code>
                  </td>
                  <td>
                    <div className="template-badges">
                      {template.is_default ? (
                        <span className="status-badge status-active">Default</span>
                      ) : null}
                      {template.is_system ? (
                        <span className="status-badge">System</span>
                      ) : null}
                    </div>
                  </td>
                  <td className="cell-secondary">
                    {new Date(template.updated_at).toLocaleDateString()}
                  </td>
                  <td className="actions-cell">
                    <div className="row-actions">
                      <button 
                        className="action-button" 
                        onClick={() => onEdit(template)} 
                        type="button"
                      >
                        Edit
                      </button>
                      {!template.is_default ? (
                        <button
                          className="action-button"
                          onClick={() => void handleSetDefault(template.id)}
                          disabled={settingDefaultId === template.id}
                          type="button"
                        >
                          {settingDefaultId === template.id ? "..." : "Set Default"}
                        </button>
                      ) : null}
                      {!template.is_system ? (
                        <button
                          className="action-button danger"
                          onClick={() => void handleDelete(template.id)}
                          disabled={deletingId === template.id}
                          type="button"
                        >
                          {deletingId === template.id ? "..." : "Delete"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [presets, setPresets] = useState<TemplatePreset[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [selectedPresetKey, setSelectedPresetKey] = useState<string | null>(null);

  const title = useMemo(
    () => (initialTemplate ? `Edit ${initialTemplate.name}` : "Create email template"),
    [initialTemplate]
  );

  useEffect(() => {
    let isActive = true;

    async function loadPresets() {
      setPresetsLoading(true);
      try {
        const nextPresets = await api.emailTemplates.listPresets();
        if (!isActive) return;
        setPresets(nextPresets);
      } catch {
        setPresets([]);
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

  useEffect(() => {
    if (initialTemplate) {
      handlePreview();
    }
  }, [initialTemplate?.id]);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (form.html_template) {
        handleLivePreview();
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [form.html_template]);

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

  async function handlePreview() {
    if (!initialTemplate) return;
    setPreviewLoading(true);
    try {
      const result = await api.emailTemplates.preview(initialTemplate.id);
      setPreviewHtml(result.html);
    } catch {
      setPreviewHtml("<p style='color: red;'>Failed to load preview</p>");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleLivePreview() {
    if (!form.html_template) {
      setPreviewHtml(null);
      return;
    }
    
    setPreviewLoading(true);
    try {
      const result = await api.emailTemplates.previewLive(form.html_template);
      setPreviewHtml(result.html);
    } catch {
      setPreviewHtml("<p style='color: red;'>Failed to render preview. Check your HTML.</p>");
    } finally {
      setPreviewLoading(false);
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

      <div className="template-editor-layout">
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

        <div className="live-preview-panel">
          <div className="live-preview-header">
            <h3>Live Preview</h3>
            {previewLoading && <span>Rendering...</span>}
          </div>
          {previewHtml ? (
            <iframe
              className="live-preview-frame"
              srcDoc={previewHtml}
              sandbox=""
              title="Template Preview"
            />
          ) : (
            <div className="live-preview-placeholder">
              <p>Start typing HTML to see a live preview</p>
              <p className="template-variables-hint">
                Available variables: subject, preheader, headline, newsletter_name, body_html, content
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
