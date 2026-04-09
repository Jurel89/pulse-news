import { useEffect, useState } from "react";

import { api, type NewsletterPreview, type NewsletterTestSendResult } from "../../lib/api";
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

  useEffect(() => {
    async function loadPreview() {
      try {
        const nextPreview = await api.previewNewsletter(newsletter.id);
        setPreview(nextPreview);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load preview.");
      }
    }

    void loadPreview();
  }, [newsletter.id]);

  async function handleTestSend() {
    setBusy(true);
    setError(null);
    setTestSendResult(null);
    try {
      const result = await api.testSendNewsletter(newsletter.id, testAddress);
      setTestSendResult(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to send test email.");
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
          </div>

          {testSendResult ? (
            <p className="form-notice">
              {testSendResult.message} ({testSendResult.mode})
            </p>
          ) : null}

          {activeTab === "html" ? (
            <article className="preview-frame" dangerouslySetInnerHTML={{ __html: preview.html }} />
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
