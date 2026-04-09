import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  emptyNewsletterInput,
  type Newsletter,
  type NewsletterInput,
  toNewsletterInput
} from "./newsletter-types";

type NewsletterEditorPageProps = {
  busy: boolean;
  initialNewsletter: Newsletter | null;
  onCancel: () => void;
  onGenerate?: (newsletterId: number) => Promise<void>;
  onSave: (payload: NewsletterInput, newsletterId?: number) => Promise<void>;
};

export function NewsletterEditorPage({
  busy,
  initialNewsletter,
  onCancel,
  onGenerate,
  onSave
}: NewsletterEditorPageProps) {
  const [form, setForm] = useState<NewsletterInput>(
    initialNewsletter ? toNewsletterInput(initialNewsletter) : emptyNewsletterInput,
  );
  const title = useMemo(
    () => (initialNewsletter ? `Edit ${initialNewsletter.name}` : "Create newsletter"),
    [initialNewsletter],
  );

  useEffect(() => {
    setForm(initialNewsletter ? toNewsletterInput(initialNewsletter) : emptyNewsletterInput);
  }, [initialNewsletter]);

  function updateField<K extends keyof NewsletterInput>(key: K, value: NewsletterInput[K]) {
    setForm((current) => ({
      ...current,
      [key]: value
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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

      <form className="editor-form" onSubmit={handleSubmit}>
        <label>
          <span>Name</span>
          <input onChange={(event) => updateField("name", event.target.value)} required value={form.name} />
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
          <span>Prompt</span>
          <textarea
            onChange={(event) => updateField("prompt", event.target.value)}
            rows={4}
            value={form.prompt}
          />
        </label>

        <div className="form-grid">
          <label>
            <span>Draft subject</span>
            <input
              onChange={(event) => updateField("draft_subject", event.target.value)}
              value={form.draft_subject}
            />
          </label>

          <label>
            <span>Draft preheader</span>
            <input
              onChange={(event) => updateField("draft_preheader", event.target.value)}
              value={form.draft_preheader}
            />
          </label>
        </div>

        <label>
          <span>Draft body</span>
          <textarea
            onChange={(event) => updateField("draft_body_text", event.target.value)}
            rows={8}
            value={form.draft_body_text}
          />
        </label>

        <div className="form-grid">
          <label>
            <span>Provider</span>
            <input
              onChange={(event) => updateField("provider_name", event.target.value)}
              value={form.provider_name}
            />
          </label>

          <label>
            <span>Model</span>
            <input
              onChange={(event) => updateField("model_name", event.target.value)}
              value={form.model_name}
            />
          </label>
        </div>

        <div className="form-grid">
          <label>
            <span>Template key</span>
            <input
              onChange={(event) => updateField("template_key", event.target.value)}
              value={form.template_key}
            />
          </label>

          <label>
            <span>Audience label</span>
            <input
              onChange={(event) => updateField("audience_name", event.target.value)}
              value={form.audience_name}
            />
          </label>
        </div>

        <label>
          <span>Delivery topic</span>
          <input
            onChange={(event) => updateField("delivery_topic", event.target.value)}
            value={form.delivery_topic}
          />
        </label>

        <div className="form-grid">
          <label>
            <span>Timezone</span>
            <input onChange={(event) => updateField("timezone", event.target.value)} value={form.timezone} />
          </label>

          <label>
            <span>Schedule cron</span>
            <input
              onChange={(event) => updateField("schedule_cron", event.target.value)}
              placeholder="0 7 * * 1-5"
              value={form.schedule_cron}
            />
          </label>
        </div>

        <label className="checkbox-row">
          <input
            checked={form.schedule_enabled}
            onChange={(event) => updateField("schedule_enabled", event.target.checked)}
            type="checkbox"
          />
          <span>Enable recurring schedule</span>
        </label>

        <div className="form-grid">
          <label>
            <span>Status</span>
            <select onChange={(event) => updateField("status", event.target.value)} value={form.status}>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="archived">Archived</option>
            </select>
          </label>

          <label>
            <span>Notes</span>
            <input onChange={(event) => updateField("notes", event.target.value)} value={form.notes} />
          </label>
        </div>

        <label>
          <span>Recipients</span>
          <textarea
            onChange={(event) => updateField("recipient_import_text", event.target.value)}
            placeholder={"ceo@example.com\nops@example.com\nteam@example.com"}
            rows={5}
            value={form.recipient_import_text}
          />
        </label>

        <button className="primary-button" disabled={busy} type="submit">
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
      </form>
    </section>
  );
}
