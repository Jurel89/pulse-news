import { useState, useMemo, FormEvent } from "react";
import type { EmailTemplateSummary, EmailTemplateDetail, EmailTemplateInput } from "./template-types";
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

export function EmailTemplatesPage({
  templates,
  loading,
  error,
  onDismissError,
  onCreate,
  onEdit,
  onDelete,
  onSetDefault,
  onRefresh
}: EmailTemplatesPageProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [settingDefaultId, setSettingDefaultId] = useState<number | null>(null);

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
    <section className="newsletters-grid">
      <header className="section-header">
        <div>
          <p className="eyebrow">Email Templates</p>
          <h2 className="section-title">Design reusable email layouts.</h2>
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
        <div className="newsletter-list">
          {Array.from({ length: 3 }, (_, index) => (
            <article className="loading-skeleton" key={index}>
              <div className="loading-skeleton-bar" />
              <div className="loading-skeleton-bar" />
              <div className="loading-skeleton-bar" />
            </article>
          ))}
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
        <div className="newsletter-list">
          {templates.map((template) => (
            <article className="newsletter-card" key={template.id}>
              <div className="newsletter-card-header">
                <div>
                  <h3>{template.name}</h3>
                  <p>{template.key}</p>
                </div>
                <div className="template-badges">
                  {template.is_default ? (
                    <span className="status-chip status-active">Default</span>
                  ) : null}
                  {template.is_system ? (
                    <span className="status-chip">System</span>
                  ) : null}
                </div>
              </div>

              <dl className="newsletter-meta">
                <div>
                  <dt>Key</dt>
                  <dd>{template.key}</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{new Date(template.updated_at).toLocaleDateString()}</dd>
                </div>
              </dl>

              <p className="newsletter-description">
                {template.description || "No description yet."}
              </p>

              <div className="card-actions">
                <button className="secondary-button" onClick={() => onEdit(template)} type="button">
                  Edit
                </button>
                {!template.is_default ? (
                  <button
                    className="secondary-button"
                    onClick={() => void handleSetDefault(template.id)}
                    disabled={settingDefaultId === template.id}
                    type="button"
                  >
                    {settingDefaultId === template.id ? "Setting..." : "Set Default"}
                  </button>
                ) : null}
                {!template.is_system ? (
                  <button
                    className="danger-button"
                    onClick={() => void handleDelete(template.id)}
                    disabled={deletingId === template.id}
                    type="button"
                  >
                    {deletingId === template.id ? "Deleting..." : "Delete"}
                  </button>
                ) : null}
              </div>
            </article>
          ))}
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

  const title = useMemo(
    () => (initialTemplate ? `Edit ${initialTemplate.name}` : "Create email template"),
    [initialTemplate]
  );

  function updateField<K extends keyof EmailTemplateInput>(key: K, value: EmailTemplateInput[K]) {
    setForm((current) => ({
      ...current,
      [key]: value
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
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
              placeholder={'<!DOCTYPE html>\n<html>\n<head>\n  <meta charset="UTF-8">\n  <title>{{subject}}</title>\n</head>\n<body>\n  <h1>{{headline}}</h1>\n  <div>{{content}}</div>\n</body>\n</html>'}
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

        {initialTemplate ? (
          <div className="template-preview-panel">
            <div className="template-preview-header">
              <h3>Preview</h3>
              <button
                className="secondary-button"
                onClick={handlePreview}
                disabled={previewLoading}
                type="button"
              >
                {previewLoading ? "Loading..." : "Refresh Preview"}
              </button>
            </div>
            {previewHtml ? (
              <div
                className="template-preview-frame"
                dangerouslySetInnerHTML={{ __html: previewHtml }}
              />
            ) : (
              <div className="template-preview-placeholder">
                <p>Click "Refresh Preview" to see how this template will render.</p>
                <p className="template-variables-hint">
                  Available variables: subject, preheader, headline, newsletter_name, body_html, content
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
