import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import type { NewsletterSummary } from "../newsletters/newsletter-types";

type RunSummary = {
  id: number;
  newsletter_id: number;
  trigger_mode: string;
  run_status: string;
  provider_name: string;
  model_name: string;
  template_key: string;
  recipient_count: number;
  snapshot_subject: string;
  snapshot_preheader: string | null;
  snapshot_body_text: string;
  snapshot_recipient_emails: string;
  delivery_outcomes: string;
  result_mode: string | null;
  result_message: string | null;
  created_at: string;
  updated_at: string;
};

type RunDetail = {
  run: RunSummary;
  newsletter_snapshot: NewsletterSummary | null;
  recipient_emails: string[];
  recipient_outcomes: Array<{
    email: string;
    status: string;
    provider_id: string | null;
    detail: string;
  }>;
  events: Array<{
    id: number;
    event_type: string;
    event_status: string;
    message: string;
    provider_id: string | null;
    created_at: string;
  }>;
};

type RunDashboardPageProps = {
  newsletters: NewsletterSummary[];
};

export function RunDashboardPage({ newsletters }: RunDashboardPageProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [newsletterId, setNewsletterId] = useState("");
  const [runStatus, setRunStatus] = useState("");
  const [triggerMode, setTriggerMode] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadRuns();
  }, [newsletterId, runStatus, triggerMode, dateFrom, dateTo]);

  async function loadRuns() {
    setLoading(true);
    setError(null);
    try {
      const payload = await api.listRuns({
        newsletter_id: newsletterId || undefined,
        run_status: runStatus || undefined,
        trigger_mode: triggerMode || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined
      });
      setRuns(payload.items);
      if (payload.items.length > 0) {
        const detail = await api.getRunDetail(payload.items[0].id);
        setSelectedRun(detail);
      } else {
        setSelectedRun(null);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load runs.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectRun(runId: number) {
    try {
      const detail = await api.getRunDetail(runId);
      setSelectedRun(detail);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load run detail.");
    }
  }

  async function handleReconcile(runId: number) {
    try {
      await api.reconcileRun(runId);
      const detail = await api.getRunDetail(runId);
      setSelectedRun(detail);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reconcile run.");
    }
  }

  return (
    <section className="preview-shell">
      <header className="section-header">
        <div>
          <p className="eyebrow">Operations</p>
          <h2 className="section-title">Run dashboard</h2>
        </div>
      </header>

      {error ? (
        <div className="error-banner">
          <span>{error}</span>
          <button className="error-banner-dismiss" onClick={() => setError(null)} type="button">
            Dismiss
          </button>
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
      ) : (
        <>
      <div className="editor-form">
        <div className="form-grid">
          <label>
            <span>Newsletter</span>
            <select onChange={(event) => setNewsletterId(event.target.value)} value={newsletterId}>
              <option value="">All newsletters</option>
              {newsletters.map((newsletter) => (
                <option key={newsletter.id} value={String(newsletter.id)}>
                  {newsletter.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Status</span>
            <select onChange={(event) => setRunStatus(event.target.value)} value={runStatus}>
              <option value="">Any status</option>
              <option value="generated">Generated</option>
              <option value="fallback">Fallback</option>
              <option value="sent">Sent</option>
              <option value="partial">Partial</option>
            </select>
          </label>
        </div>

        <div className="form-grid">
          <label>
            <span>Trigger mode</span>
            <select onChange={(event) => setTriggerMode(event.target.value)} value={triggerMode}>
              <option value="">Any trigger</option>
              <option value="manual-generate">Manual generate</option>
              <option value="manual-send">Manual send</option>
              <option value="scheduled-send">Scheduled send</option>
            </select>
          </label>

          <label>
            <span>Date from</span>
            <input onChange={(event) => setDateFrom(event.target.value)} type="date" value={dateFrom} />
          </label>
        </div>

        <label>
          <span>Date to</span>
          <input onChange={(event) => setDateTo(event.target.value)} type="date" value={dateTo} />
        </label>
      </div>

      <div className="newsletter-list">
        {runs.map((run) => (
          <article className="newsletter-card" key={run.id} onClick={() => void handleSelectRun(run.id)}>
            <div className="newsletter-card-header">
              <div>
                <h3>{run.snapshot_subject}</h3>
                <p>
                  {run.trigger_mode} • {run.run_status}
                </p>
              </div>
              <span className="status-chip">{run.result_mode ?? "run"}</span>
            </div>
          </article>
        ))}
      </div>

      {selectedRun ? (
        <article className="preview-frame">
          <h3>{selectedRun.run.snapshot_subject}</h3>
          <p>{selectedRun.run.result_message ?? "No result message recorded."}</p>
          <p>{selectedRun.run.snapshot_body_text}</p>
          <p>Recipients: {selectedRun.recipient_emails.join(", ") || "None"}</p>
          <button className="secondary-button" onClick={() => void handleReconcile(selectedRun.run.id)} type="button">
            Reconcile Delivery
          </button>
          <div className="newsletter-list">
            {selectedRun.recipient_outcomes.map((outcome) => (
              <article className="newsletter-card" key={outcome.email}>
                <strong>{outcome.email}</strong>
                <p>{outcome.status}</p>
                <p className="newsletter-description">{outcome.detail}</p>
              </article>
            ))}
          </div>
          <div className="newsletter-list">
            {selectedRun.events.map((event) => (
              <article className="newsletter-card" key={event.id}>
                <strong>{event.event_type}</strong>
                <p>{event.event_status}</p>
                <p className="newsletter-description">{event.message}</p>
              </article>
            ))}
          </div>
        </article>
      ) : null}
      </>
      )}
    </section>
  );
}
