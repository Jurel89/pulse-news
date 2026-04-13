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
  onOpenRuns?: (runId: number) => void;
};

export function NewsletterPreviewPage({ newsletter, onBack, onOpenRuns }: NewsletterPreviewPageProps) {
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
  const [revisionDraft, setRevisionDraft] = useState({ subject: "", preheader: "", body_text: "" });
  const approvedRevision = revisions.find((revision) => revision.id === approvedRevisionId) ?? null;
  const selectedRevision = revisions.find((revision) => revision.id === selectedRevisionId) ?? null;

  const loadRevisionState = useCallback(async () => {
    const nextRevisions = await api.listNewsletterRevisions(newsletter.id);
    setRevisions(nextRevisions.items);
    const approved = nextRevisions.items.find((revision) => revision.state === "approved") ?? null;
    setApprovedRevisionId(approved?.id ?? null);
    const nextDraftHeadRevisionId = nextRevisions.items[0]?.id ?? null;
    setDraftHeadRevisionId(nextDraftHeadRevisionId);
    const nextSelectedRevisionId = approved?.id ?? nextDraftHeadRevisionId;
    setSelectedRevisionId((current) => current ?? nextSelectedRevisionId);

    if (nextSelectedRevisionId) {
      const nextPreview = await api.previewNewsletterRevision(newsletter.id, nextSelectedRevisionId);
      setPreview(nextPreview);
      const selectedRevision = nextRevisions.items.find((revision) => revision.id === nextSelectedRevisionId);
      if (selectedRevision) {
        setRevisionDraft({
          subject: selectedRevision.subject,
          preheader: selectedRevision.preheader ?? "",
          body_text: selectedRevision.body_text,
        });
      }
    }
  }, [newsletter.id]);

  async function handleSelectRevision(revisionId: number) {
    setBusy(true);
    setError(null);
    try {
      const nextPreview = await api.previewNewsletterRevision(newsletter.id, revisionId);
      setSelectedRevisionId(revisionId);
      setPreview(nextPreview);
      const selectedRevision = revisions.find((revision) => revision.id === revisionId);
      if (selectedRevision) {
        setRevisionDraft({
          subject: selectedRevision.subject,
          preheader: selectedRevision.preheader ?? "",
          body_text: selectedRevision.body_text,
        });
      }
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
      if (!targetRevisionId) {
        throw new Error("No revision selected for test send.");
      }
      const result = await api.testSendNewsletterRevision(newsletter.id, targetRevisionId, testAddress);
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

  async function handleSaveRevision() {
    if (!selectedRevisionId) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.updateNewsletterRevision(newsletter.id, selectedRevisionId, revisionDraft);
      await loadRevisionState();
      await handleSelectRevision(selectedRevisionId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to update revision.");
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
      if (selectedRevisionId && selectedRevisionId !== approvedRevisionId) {
        throw new Error("Only the approved revision can be sent. Approve this revision first.");
      }
      const targetRevisionId = selectedRevisionId ?? approvedRevisionId;
      const idempotencyKey = crypto.randomUUID();
      if (!targetRevisionId) {
        throw new Error("No approved revision selected for send.");
      }
      const result = await api.sendNewsletterRevision(newsletter.id, targetRevisionId, idempotencyKey);
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
                    <p className="newsletter-description">Created by: {revision.created_by_email ?? "System"}</p>
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
                      {revision.generation_run_id && onOpenRuns ? (
                        <button
                          className="secondary-button"
                          disabled={busy}
                          onClick={() => onOpenRuns(revision.generation_run_id!)}
                          type="button"
                        >
                          Open run #{revision.generation_run_id}
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>

          {selectedRevision && approvedRevision && selectedRevision.id !== approvedRevision.id ? (
            <div className="status-panel">
              <div className="section-header">
                <div>
                  <p className="eyebrow">Compare revisions</p>
                  <h3 className="section-title">Candidate vs approved</h3>
                </div>
              </div>
              <div className="form-grid">
                <article className="newsletter-card">
                  <strong>Approved revision #{approvedRevision.version_number}</strong>
                  <p className="newsletter-description">{approvedRevision.subject}</p>
                  <p className="newsletter-description">Created by: {approvedRevision.created_by_email ?? "System"}</p>
                  <p className="newsletter-description">{approvedRevision.preheader || "No preheader"}</p>
                  <p className="newsletter-description">Run #{approvedRevision.generation_run_id ?? "—"}</p>
                </article>
                <article className="newsletter-card">
                  <strong>Candidate revision #{selectedRevision.version_number}</strong>
                  <p className="newsletter-description">{selectedRevision.subject}</p>
                  <p className="newsletter-description">Created by: {selectedRevision.created_by_email ?? "System"}</p>
                  <p className="newsletter-description">{selectedRevision.preheader || "No preheader"}</p>
                  <p className="newsletter-description">Run #{selectedRevision.generation_run_id ?? "—"}</p>
                </article>
              </div>
            </div>
          ) : null}

          {selectedRevisionId && selectedRevisionId !== approvedRevisionId ? (
            <div className="status-panel">
              <div className="section-header">
                <div>
                  <p className="eyebrow">Edit revision</p>
                  <h3 className="section-title">Candidate revision editor</h3>
                </div>
              </div>
              <div className="editor-form">
                <label>
                  <span className="status-label">Subject</span>
                  <input
                    value={revisionDraft.subject}
                    onChange={(event) => setRevisionDraft((current) => ({ ...current, subject: event.target.value }))}
                  />
                </label>
                <label>
                  <span className="status-label">Preheader</span>
                  <input
                    value={revisionDraft.preheader}
                    onChange={(event) => setRevisionDraft((current) => ({ ...current, preheader: event.target.value }))}
                  />
                </label>
                <label>
                  <span className="status-label">Body</span>
                  <textarea
                    rows={8}
                    value={revisionDraft.body_text}
                    onChange={(event) => setRevisionDraft((current) => ({ ...current, body_text: event.target.value }))}
                  />
                </label>
                <button className="primary-button" disabled={busy} onClick={() => void handleSaveRevision()} type="button">
                  {busy ? "Saving..." : "Save revision changes"}
                </button>
              </div>
            </div>
          ) : null}

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
               {busy ? "Working..." : selectedRevisionId && selectedRevisionId !== approvedRevisionId ? "Approve revision to send" : "Send Approved Draft"}
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
