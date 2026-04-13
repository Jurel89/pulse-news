import { Fragment, useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import type { NewsletterSummary } from "../newsletters/newsletter-types";
import { ActionDropdown, type ActionItem } from "../../components/ui/ActionDropdown";

type RunSummary = {
  id: number;
  newsletter_id: number;
  revision_id: number | null;
  run_type: string | null;
  snapshot_newsletter_name: string | null;
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
  started_at: string | null;
  completed_at: string | null;
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
  initialRunId?: number | null;
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

function formatRunType(runType: string | null): string {
  if (!runType) {
    return "Unknown";
  }
  return runType.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
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

export function RunDashboardPage({ newsletters, initialRunId = null }: RunDashboardPageProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [runDetails, setRunDetails] = useState<Map<number, RunDetail>>(new Map());
  const [newsletterId, setNewsletterId] = useState("");
  const [runType, setRunType] = useState("");
  const [runStatus, setRunStatus] = useState("");
  const [triggerMode, setTriggerMode] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await api.listRuns({
        newsletter_id: newsletterId || undefined,
        run_type: runType || undefined,
        run_status: runStatus || undefined,
        trigger_mode: triggerMode || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined
      });
      setRuns(payload.items);
      // Clear expansion when filters change
      setExpandedRunId(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load runs.");
    } finally {
      setLoading(false);
    }
  }, [newsletterId, runType, runStatus, triggerMode, dateFrom, dateTo]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  const handleToggleRun = useCallback(async (runId: number) => {
    // If already expanded, collapse it
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }

    // Expand this run
    setExpandedRunId(runId);

    // Load details if not already cached
    if (!runDetails.has(runId)) {
      try {
        const detail = await api.getRunDetail(runId);
        setRunDetails((prev) => new Map(prev).set(runId, detail));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load run detail.");
      }
    }
  }, [expandedRunId, runDetails]);

  useEffect(() => {
    if (initialRunId == null) {
      return;
    }
    const matchingRun = runs.find((run) => run.id === initialRunId);
    if (matchingRun) {
      void handleToggleRun(initialRunId);
    }
  }, [handleToggleRun, initialRunId, runs]);

  async function handleReconcile(runId: number) {
    try {
      await api.reconcileRun(runId);
      const detail = await api.getRunDetail(runId);
      setRunDetails((prev) => new Map(prev).set(runId, detail));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reconcile run.");
    }
  }

  function getRunActions(run: RunSummary): ActionItem[] {
    return [
      {
        label: "View Details",
        onClick: () => void handleToggleRun(run.id),
        icon: (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <title>View details</title>
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
            <title>Reconcile delivery</title>
            <path d="M2 8h12M8 2v12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        )
      }
    ];
  }

  const stats = {
    totalRuns: runs.length,
    deliveryRuns: runs.filter((r) => r.run_type === "delivery").length,
    generationRuns: runs.filter((r) => r.run_type === "generation").length,
    totalRecipients: runs
      .filter((r) => r.run_type !== "generation")
      .reduce((sum, r) => sum + r.recipient_count, 0)
  };

  const expandedDetail = expandedRunId != null ? runDetails.get(expandedRunId) : null;

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
          <span className="status-label">Delivery Runs</span>
          <strong>{stats.deliveryRuns}</strong>
        </article>
        <article className="info-card">
          <span className="status-label">Generation Runs</span>
          <strong>{stats.generationRuns}</strong>
        </article>
        <article className="info-card">
          <span className="status-label">Total Recipients</span>
          <strong>{stats.totalRecipients.toLocaleString()}</strong>
        </article>
      </div>

      <div className="filter-bar">
        <div className="filter-group">
          <label htmlFor="filter-newsletter">Newsletter</label>
          <select
            id="filter-newsletter"
            onChange={(event) => setNewsletterId(event.target.value)}
            value={newsletterId}
          >
            <option value="">All newsletters</option>
            {newsletters.map((newsletter) => (
              <option key={newsletter.id} value={String(newsletter.id)}>
                {newsletter.name}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-type">Run type</label>
          <select
            id="filter-type"
            onChange={(event) => setRunType(event.target.value)}
            value={runType}
          >
            <option value="">Any type</option>
            <option value="generation">Generation</option>
            <option value="test_send">Test Send</option>
            <option value="delivery">Delivery</option>
            <option value="reconciliation">Reconciliation</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-status">Status</label>
          <select
            id="filter-status"
            onChange={(event) => setRunStatus(event.target.value)}
            value={runStatus}
          >
            <option value="">Any status</option>
            <option value="generated">Generated</option>
            <option value="fallback">Fallback</option>
            <option value="sent">Sent</option>
            <option value="partial">Partial</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-trigger">Trigger mode</label>
          <select
            id="filter-trigger"
            onChange={(event) => setTriggerMode(event.target.value)}
            value={triggerMode}
          >
            <option value="">Any trigger</option>
            <option value="manual-generate">Manual generate</option>
            <option value="manual-send">Manual send</option>
            <option value="scheduled-send">Scheduled send</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-date-from">Date from</label>
          <input
            id="filter-date-from"
            onChange={(event) => setDateFrom(event.target.value)}
            type="date"
            value={dateFrom}
          />
        </div>

        <div className="filter-group">
          <label htmlFor="filter-date-to">Date to</label>
          <input
            id="filter-date-to"
            onChange={(event) => setDateTo(event.target.value)}
            type="date"
            value={dateTo}
          />
        </div>
      </div>

      {loading ? (
        <div className="newsletter-list">
          {Array.from({ length: 3 }, (_, index) => index + 1).map((skeletonId) => (
            <article className="loading-skeleton" key={skeletonId}>
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
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Revision</th>
                  <th>Type</th>
                  <th>Job</th>
                  <th>Subject</th>
                  <th>Status</th>
                  <th>Trigger</th>
                  <th>Recipients</th>
                  <th>Started</th>
                  <th>Completed</th>
                  <th className="actions-column">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <Fragment key={run.id}>
                    <tr
                      className={`data-row ${expandedRunId === run.id ? "expanded" : ""}`}
                      onClick={(event) => {
                        const target = event.target as HTMLElement;
                        if (target.closest(".actions-cell")) {
                          return;
                        }
                        void handleToggleRun(run.id);
                      }}
                      style={{ cursor: "pointer" }}
                    >
                      <td className="cell-secondary" data-label="Run ID">
                        #{run.id}
                      </td>
                      <td className="cell-secondary" data-label="Revision">
                        {run.revision_id ? `#${run.revision_id}` : "—"}
                      </td>
                      <td data-label="Type">{formatRunType(run.run_type)}</td>
                      <td className="name-cell" data-label="Job">
                        <div className="cell-primary">{run.snapshot_newsletter_name ?? `Newsletter #${run.newsletter_id}`}</div>
                        <div className="cell-secondary">#{run.newsletter_id}</div>
                      </td>
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
                      <td className="cell-secondary" data-label="Started">
                        {formatDate(run.started_at ?? run.created_at)}
                      </td>
                      <td className="cell-secondary" data-label="Completed">
                        {run.completed_at ? formatDate(run.completed_at) : "—"}
                      </td>
                      <td className="actions-cell">
                        <ActionDropdown actions={getRunActions(run)} />
                      </td>
                    </tr>
                    {expandedRunId === run.id ? (
                      <tr className="detail-row">
                          <td colSpan={11} className="detail-cell">
                          {expandedDetail ? (
                            <div className="run-detail-panel">
                              <div className="run-detail-header">
                                <h4>Run #{run.id} Details</h4>
                                <button
                                  className="secondary-button"
                                  onClick={() => setExpandedRunId(null)}
                                  type="button"
                                >
                                  Close
                                </button>
                              </div>

                              <p className="cell-secondary">
                                {expandedDetail.run.result_message ?? "No result message recorded."}
                              </p>

                              <hr className="form-divider" />

                              <div className="newsletter-meta">
                                <div>
                                  <dt>Provider</dt>
                                  <dd>{expandedDetail.run.provider_name}</dd>
                                </div>
                                <div>
                                  <dt>Model</dt>
                                  <dd>{expandedDetail.run.model_name}</dd>
                                </div>
                                <div>
                                  <dt>Template</dt>
                                  <dd>{expandedDetail.run.template_key}</dd>
                                </div>
                                <div>
                                  <dt>Recipients</dt>
                                  <dd>{expandedDetail.recipient_emails.length}</dd>
                                </div>
                              </div>

                              <hr className="form-divider" />

                              <h5>Recipient Outcomes</h5>
                              <div className="newsletter-list compact">
                                {expandedDetail.recipient_outcomes.length > 0 ? (
                                  expandedDetail.recipient_outcomes.map((outcome) => (
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

                              <h5>Events</h5>
                              <div className="newsletter-list compact">
                                {expandedDetail.events.length > 0 ? (
                                  expandedDetail.events.map((event) => (
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
                            </div>
                          ) : (
                            <div className="run-detail-panel">
                              <p className="cell-secondary">Loading details...</p>
                            </div>
                          )}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
