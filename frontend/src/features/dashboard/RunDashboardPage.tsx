import { useEffect, useState } from "react";

import { api } from "../../lib/api";
import type { NewsletterSummary } from "../newsletters/newsletter-types";
import { ActionDropdown, type ActionItem } from "../../components/ui/ActionDropdown";

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

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case "sent":
      return "status-badge status-active";
    case "partial":
      return "status-badge status-paused";
    case "generated":
      return "status-badge status-draft";
    case "fallback":
      return "status-badge";
    default:
      return "status-badge";
  }
}

function formatTriggerMode(mode: string): string {
  return mode.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

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

  function getRunActions(run: RunSummary): ActionItem[] {
    return [
      {
        label: "View Details",
        onClick: () => void handleSelectRun(run.id),
        icon: (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M8 3C4 3 1 8 1 8s3 5 7 5 7-5 7-5-3-5-7-5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/>
          </svg>
        )
      },
      {
        label: "Reconcile Delivery",
        onClick: () => void handleReconcile(run.id),
        variant: "primary",
        icon: (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 8h12M8 2v12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        )
      }
    ];
  }

  const stats = {
    totalRuns: runs.length,
    sentRuns: runs.filter((r) => r.run_status === "sent").length,
    partialRuns: runs.filter((r) => r.run_status === "partial").length,
    totalRecipients: runs.reduce((sum, r) => sum + r.recipient_count, 0)
  };

  return (
    <section className="data-grid-section">
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

      <div className="info-card-grid">
        <article className="info-card">
          <span className="status-label">Total Runs</span>
          <strong>{stats.totalRuns}</strong>
        </article>
        <article className="info-card">
          <span className="status-label">Sent</span>
          <strong>{stats.sentRuns}</strong>
        </article>
        <article className="info-card">
          <span className="status-label">Partial</span>
          <strong>{stats.partialRuns}</strong>
        </article>
        <article className="info-card">
          <span className="status-label">Total Recipients</span>
          <strong>{stats.totalRecipients.toLocaleString()}</strong>
        </article>
      </div>

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

          <label>
            <span>Date to</span>
            <input onChange={(event) => setDateTo(event.target.value)} type="date" value={dateTo} />
          </label>
        </div>
      </div>

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
      ) : runs.length === 0 ? (
        <article className="empty-state">
          <h3>No runs yet</h3>
          <p>
            No newsletter runs match your current filters. Try adjusting the filters or create
            a new newsletter run.
          </p>
        </article>
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Status</th>
                <th>Trigger</th>
                <th>Recipients</th>
                <th>Date</th>
                <th className="actions-column">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  className="data-row"
                  onClick={() => void handleSelectRun(run.id)}
                  style={{ cursor: "pointer" }}
                >
                  <td className="name-cell" data-label="Subject">
                    <div className="cell-primary">{run.snapshot_subject}</div>
                    <div className="cell-secondary">{run.provider_name} / {run.model_name}</div>
                  </td>
                  <td data-label="Status">
                    <span className={getStatusBadgeClass(run.run_status)}>
                      {run.run_status}
                    </span>
                  </td>
                  <td data-label="Trigger">{formatTriggerMode(run.trigger_mode)}</td>
                  <td data-label="Recipients">{run.recipient_count.toLocaleString()}</td>
                  <td className="cell-secondary" data-label="Date">
                    {formatDate(run.created_at)}
                  </td>
                  <td className="actions-cell" onClick={(e) => e.stopPropagation()}>
                    <ActionDropdown actions={getRunActions(run)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedRun ? (
        <article className="editor-form">
          <div className="section-header">
            <h3>{selectedRun.run.snapshot_subject}</h3>
            <span className={getStatusBadgeClass(selectedRun.run.run_status)}>
              {selectedRun.run.run_status}
            </span>
          </div>

          <p className="cell-secondary">
            {selectedRun.run.result_message ?? "No result message recorded."}
          </p>

          <hr className="form-divider" />

          <div className="newsletter-meta">
            <div>
              <dt>Provider</dt>
              <dd>{selectedRun.run.provider_name}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{selectedRun.run.model_name}</dd>
            </div>
            <div>
              <dt>Template</dt>
              <dd>{selectedRun.run.template_key}</dd>
            </div>
            <div>
              <dt>Recipients</dt>
              <dd>{selectedRun.recipient_emails.length}</dd>
            </div>
          </div>

          <hr className="form-divider" />

          <h4>Recipient Outcomes</h4>
          <div className="newsletter-list">
            {selectedRun.recipient_outcomes.length > 0 ? (
              selectedRun.recipient_outcomes.map((outcome) => (
                <article className="newsletter-card" key={outcome.email}>
                  <div className="newsletter-card-header">
                    <div>
                      <strong>{outcome.email}</strong>
                      <p className="cell-secondary">{outcome.detail}</p>
                    </div>
                    <span
                      className={`status-badge ${
                        outcome.status === "delivered"
                          ? "status-active"
                          : outcome.status === "bounced" || outcome.status === "failed"
                            ? "status-paused"
                            : ""
                      }`}
                    >
                      {outcome.status}
                    </span>
                  </div>
                </article>
              ))
            ) : (
              <p className="cell-secondary">No recipient outcomes recorded.</p>
            )}
          </div>

          <hr className="form-divider" />

          <h4>Events</h4>
          <div className="newsletter-list">
            {selectedRun.events.length > 0 ? (
              selectedRun.events.map((event) => (
                <article className="newsletter-card" key={event.id}>
                  <div className="newsletter-card-header">
                    <div>
                      <strong>{event.event_type}</strong>
                      <p className="cell-secondary">{event.message}</p>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span className="status-badge">{event.event_status}</span>
                      <p className="cell-secondary" style={{ marginTop: "var(--sp-1)" }}>
                        {formatDate(event.created_at)}
                      </p>
                    </div>
                  </div>
                </article>
              ))
            ) : (
              <p className="cell-secondary">No events recorded.</p>
            )}
          </div>
        </article>
      ) : null}
    </section>
  );
}