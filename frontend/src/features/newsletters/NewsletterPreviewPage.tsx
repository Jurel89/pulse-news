import { useCallback, useEffect, useState } from "react";

import {
  api,
  type DraftRevisionSummary,
  type NewsletterPreview,
  type NewsletterSendResult,
  type NewsletterTestSendResult
} from "../../lib/api";
import type { Newsletter } from "./newsletter-types";

type NewsletterPreviewPageProps = {
  newsletter: Newsletter;
  onBack: () => void;
};

export function NewsletterPreviewPage({ newsletter, onBack }: NewsletterPreviewPageProps) {
  const [preview, setPreview] = useState<NewsletterPreview | null>(null);
  const [activeTab, setActiveTab] = useState<"html" | "text">("html");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testAddress, setTestAddress] = useState("qa@example.com");
  const [testSendResult, setTestSendResult] = useState<NewsletterTestSendResult | null>(null);
  const [manualSendResult, setManualSendResult] = useState<NewsletterSendResult | null>(null);
  const [revisions, setRevisions] = useState<DraftRevisionSummary[]>([]);
  const [approvedRevisionId, setApprovedRevisionId] = useState<number | null>(newsletter.approved_revision_id);
  const [draftHeadRevisionId, setDraftHeadRevisionId] = useState<number | null>(newsletter.draft_head_revision_id);
  const [selectedRevisionId, setSelectedRevisionId] = useState<number | null>(newsletter.approved_revision_id ?? newsletter.draft_head_revision_id);

  const loadRevisionState = useCallback(async () => {
    const nextRevisions = await api.listNewsletterRevisions(newsletter.id);
    setRevisions(nextRevisions.items);
    const approved = nextRevisions.items.find((revision) => revision.state === "approved") ?? null;
    setApprovedRevisionId(approved?.id ?? null);
    const nextDraftHeadRevisionId = nextRevisions.items[0]?.id ?? null;
    setDraftHeadRevisionId(nextDraftHeadRevisionId);
    const nextSelectedRevisionId = approved?.id ?? nextDraftHeadRevisionId;
    setSelectedRevisionId((current) => current ?? nextSelectedRevisionId);

    const nextPreview = nextSelectedRevisionId
      ? await api.previewNewsletterRevision(newsletter.id, nextSelectedRevisionId)
      : await api.previewNewsletter(newsletter.id);
    setPreview(nextPreview);
  }, [newsletter.id]);

  async function handleSelectRevision(revisionId: number) {
    setBusy(true);
    setError(null);
    try {
      const nextPreview = await api.previewNewsletterRevision(newsletter.id, revisionId);
      setSelectedRevisionId(revisionId);
      setPreview(nextPreview);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to preview revision.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    async function loadPreview() {
      try {
        await loadRevisionState();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load preview.");
      }
    }

    void loadPreview();
  }, [loadRevisionState]);

  async function handleTestSend() {
    setBusy(true);
    setError(null);
    setTestSendResult(null);
    setManualSendResult(null);
    try {
      const targetRevisionId = selectedRevisionId ?? draftHeadRevisionId;
      const result = targetRevisionId
        ? await api.testSendNewsletterRevision(newsletter.id, targetRevisionId, testAddress)
        : await api.testSendNewsletter(newsletter.id, testAddress);
      setTestSendResult(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to send test email.");
    } finally {
      setBusy(false);
    }
  }

  async function handleApproveRevision(revisionId: number) {
    setBusy(true);
    setError(null);
    try {
      await api.approveNewsletterRevision(newsletter.id, revisionId);
      await loadRevisionState();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to approve revision.");
    } finally {
      setBusy(false);
    }
  }

  async function handleManualSend() {
    setBusy(true);
    setError(null);
    setTestSendResult(null);
    setManualSendResult(null);
    try {
      const targetRevisionId = selectedRevisionId ?? approvedRevisionId;
      const result = targetRevisionId
        ? await api.sendNewsletterRevision(newsletter.id, targetRevisionId)
        : await api.sendNewsletter(newsletter.id);
      setManualSendResult(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to send newsletter.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="preview-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">Preview</p>
          <h2 className="section-title">{newsletter.name}</h2>
          <p className="cell-secondary">
            Approved revision #{approvedRevisionId ?? "—"} · Draft revision #{draftHeadRevisionId ?? "—"}
          </p>
        </div>
        <button className="secondary-button" onClick={onBack} type="button">
          Back to newsletters
        </button>
      </header>

      {error ? <p className="form-error">{error}</p> : null}

      {preview ? (
        <>
          <div className="status-panel">
            <div className="status-grid">
              <div>
                <span className="status-label">Template</span>
                <strong>{preview.template_key}</strong>
              </div>
              <div>
                <span className="status-label">Subject</span>
                <strong>{preview.subject}</strong>
              </div>
              <div>
                <span className="status-label">Preheader</span>
                <strong>{preview.preheader || "No preheader"}</strong>
              </div>
            </div>
          </div>

          <div className="status-panel">
            <div className="section-header">
              <div>
                <p className="eyebrow">Revisions</p>
                <h3 className="section-title">Approved and candidate drafts</h3>
              </div>
            </div>
            <div className="newsletter-list">
              {revisions.map((revision) => {
                const isApproved = revision.id === approvedRevisionId;
                const isDraftHead = revision.id === draftHeadRevisionId;
                return (
                  <article className="newsletter-card" key={revision.id}>
                    <div className="section-header">
                      <div>
                        <strong>Revision #{revision.version_number}</strong>
                        <p className="newsletter-description">{revision.subject}</p>
                      </div>
                      <span className={`status-badge status-${revision.state}`}>
                        {revision.state}
                      </span>
                    </div>
                    <p className="newsletter-description">
                      Origin: {revision.origin} · {isApproved ? "Approved" : "Not approved"}
                      {isDraftHead ? " · Current draft" : ""}
                      {revision.id === selectedRevisionId ? " · Previewing" : ""}
                    </p>
                    <p className="newsletter-description">{revision.preheader || "No preheader"}</p>
                    <div className="form-actions">
                      <button
                        className="secondary-button"
                        disabled={busy}
                        onClick={() => void handleSelectRevision(revision.id)}
                        type="button"
                      >
                        Preview revision
                      </button>
                      {!isApproved ? (
                        <button
                          className="secondary-button"
                          disabled={busy}
                          onClick={() => void handleApproveRevision(revision.id)}
                          type="button"
                        >
                          Approve revision
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>

          <div className="nav-pills">
            <button
              className={activeTab === "html" ? "nav-pill active" : "nav-pill"}
              onClick={() => setActiveTab("html")}
              type="button"
            >
              HTML Preview
            </button>
            <button
              className={activeTab === "text" ? "nav-pill active" : "nav-pill"}
              onClick={() => setActiveTab("text")}
              type="button"
            >
              Plain Text
            </button>
          </div>

          <div className="test-send-panel">
            <label>
              <span className="status-label">Test address</span>
              <input onChange={(event) => setTestAddress(event.target.value)} value={testAddress} />
            </label>
            <button className="primary-button" disabled={busy} onClick={() => void handleTestSend()} type="button">
              {busy ? "Sending..." : "Send Test Email"}
            </button>
            <button className="secondary-button" disabled={busy} onClick={() => void handleManualSend()} type="button">
               {busy ? "Working..." : "Send Approved Draft"}
            </button>
          </div>

          {testSendResult ? (
            <p className="form-notice">
              {testSendResult.message} ({testSendResult.mode})
            </p>
          ) : null}

          {manualSendResult ? (
            <div className="status-panel">
              <p className="form-notice">
                {manualSendResult.message} ({manualSendResult.mode})
              </p>
              <div className="newsletter-list">
                {manualSendResult.recipient_outcomes.map((outcome) => (
                  <article className="newsletter-card" key={outcome.email}>
                    <strong>{outcome.email}</strong>
                    <p>{outcome.status}</p>
                    <p className="newsletter-description">{outcome.detail}</p>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === "html" ? (
            <iframe
              className="preview-frame"
              srcDoc={preview.html}
              sandbox=""
              title="Newsletter Preview"
              style={{ width: "100%", minHeight: "400px", border: "none", borderRadius: "12px" }}
            />
          ) : (
            <article className="plain-preview">
              <pre>{preview.plain_text}</pre>
            </article>
          )}
        </>
      ) : (
        <p className="lede">Rendering preview...</p>
      )}
    </section>
  );
}
