import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import { api } from "../../lib/api";
import type { NewsletterRunSummary as RunSummary, NewsletterRunDetailView, RunDetailResponse } from "../../lib/api";
import type { NewsletterSummary } from "../newsletters/newsletter-types";
import { ActionDropdown, type ActionItem } from "../../components/ui/ActionDropdown";

type RunDetail = RunDetailResponse;

type ContentTab = "html" | "plain" | "prompt";

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
  const [contentTab, setContentTab] = useState<ContentTab>("html");
  const [newsletterId, setNewsletterId] = useState("");
  const [runType, setRunType] = useState("");
  const [runStatus, setRunStatus] = useState("");
  const [triggerMode, setTriggerMode] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoOpenedRunIdRef = useRef<number | null>(null);

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

  const openRun = useCallback(async (runId: number) => {
    setExpandedRunId(runId);

    if (!runDetails.has(runId)) {
      try {
        const detail = await api.getRunDetail(runId);
        setRunDetails((prev) => new Map(prev).set(runId, detail));
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Unable to load run detail.");
      }
    }
  }, [runDetails]);

  const handleToggleRun = useCallback(async (runId: number) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }

    await openRun(runId);
  }, [expandedRunId, openRun]);

  useEffect(() => {
    if (initialRunId == null) {
      autoOpenedRunIdRef.current = null;
      return;
    }

    if (autoOpenedRunIdRef.current === initialRunId || expandedRunId === initialRunId) {
      return;
    }

    const matchingRun = runs.find((run) => run.id === initialRunId);
    if (matchingRun) {
      autoOpenedRunIdRef.current = initialRunId;
      void openRun(initialRunId);
    }
  }, [expandedRunId, initialRunId, openRun, runs]);

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
      }
    ];
  }

  const stats = {
    totalRuns: runs.length,
    deliveryRuns: runs.filter((r) => r.run_type === "delivery").length,
    generationRuns: runs.filter((r) => r.run_type === "generation").length,
    totalRecipients: runs.reduce((sum, r) => sum + r.recipient_count, 0)
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
            <option value="delivery">Delivery</option>
            <option value="generation">Generation</option>
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
            <option value="pending">Pending</option>
            <option value="generating">Generating</option>
            <option value="generated">Generated</option>
            <option value="sending">Sending</option>
            <option value="sent">Sent</option>
            <option value="partial">Partial</option>
            <option value="failed">Failed</option>
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
            <option value="manual-run">Manual run</option>
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
                  <th>Type</th>
                  <th>Newsletter</th>
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
                      <td data-label="Type">{formatRunType(run.run_type)}</td>
                      <td className="name-cell" data-label="Newsletter">
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
                          <td colSpan={10} className="detail-cell">
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

                              <h5>Sent Content</h5>
                              <RunContentTabs detail={expandedDetail} activeTab={contentTab} onChangeTab={setContentTab} />

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
                                            outcome.status === "sent" || outcome.status === "delivered"
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

type RunContentTabsProps = {
  detail: RunDetail;
  activeTab: ContentTab;
  onChangeTab: (tab: ContentTab) => void;
};

function RunContentTabs({ detail, activeTab, onChangeTab }: RunContentTabsProps) {
  const run = detail.run as NewsletterRunDetailView;
  const renderedHtml = run.rendered_html;
  const renderedPlain = run.rendered_plain_text ?? run.snapshot_body_text;
  const promptSnapshot = run.snapshot_prompt ?? "";
  const renderedSubject = run.rendered_subject ?? run.snapshot_subject;
  const renderedPreheader = run.rendered_preheader ?? run.snapshot_preheader ?? "";

  return (
    <div className="run-content-panel">
      <div className="newsletter-meta">
        <div>
          <dt>Subject</dt>
          <dd>{renderedSubject || "—"}</dd>
        </div>
        <div>
          <dt>Preheader</dt>
          <dd>{renderedPreheader || "—"}</dd>
        </div>
      </div>

      <div className="nav-pills" role="tablist" aria-label="Sent content views" style={{ marginTop: "var(--sp-2)" }}>
        <button
          aria-selected={activeTab === "html"}
          className={activeTab === "html" ? "nav-pill active" : "nav-pill"}
          onClick={() => onChangeTab("html")}
          role="tab"
          type="button"
        >
          HTML
        </button>
        <button
          aria-selected={activeTab === "plain"}
          className={activeTab === "plain" ? "nav-pill active" : "nav-pill"}
          onClick={() => onChangeTab("plain")}
          role="tab"
          type="button"
        >
          Plain Text
        </button>
        <button
          aria-selected={activeTab === "prompt"}
          className={activeTab === "prompt" ? "nav-pill active" : "nav-pill"}
          onClick={() => onChangeTab("prompt")}
          role="tab"
          type="button"
        >
          Prompt Snapshot
        </button>
      </div>

      <div style={{ marginTop: "var(--sp-2)" }}>
        {activeTab === "html" ? (
          renderedHtml ? (
            (() => {
              // Strip meta-refresh tags before passing to the iframe — belt-and-braces
              // defence against top-level navigation in browsers that allow meta-refresh
              // even with sandbox="" (e.g. some Chromium versions before the csp attribute
              // was honoured universally).
              const safeHtml = renderedHtml ? renderedHtml.replace(/<meta[^>]*http-equiv\s*=\s*["']?refresh["']?[^>]*>/gi, "") : renderedHtml;
              // csp enforces a Content-Security-Policy inside the srcdoc document
              // (Chrome 61+, Firefox 70+). default-src 'none' blocks meta-refresh
              // initiated navigations and any network fetch the sandboxed doc might
              // attempt. Style/image/font sources are kept for cosmetic rendering.
              // The csp attribute is not yet in React's type definitions, so we pass
              // it via a spread cast to avoid a TS2322 error while keeping runtime
              // behaviour identical.
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const cspAttr = { csp: "default-src 'none'; style-src 'unsafe-inline' 'self'; img-src data: https:; font-src data: https:;" } as any;
              return (
                <iframe
                  title="Rendered HTML"
                  // Sandbox without allow-scripts/allow-same-origin — the stored
                  // HTML is operator/AI content that we never want to execute.
                  sandbox=""
                  srcDoc={safeHtml}
                  style={{ width: "100%", minHeight: 480, border: "1px solid var(--border-subtle)", borderRadius: "6px", background: "#fff" }}
                  {...cspAttr}
                />
              );
            })()
          ) : (
            <p className="cell-secondary">
              No rendered HTML was captured for this run. Older runs created before the run-content capture
              landed will not have this field.
            </p>
          )
        ) : null}
        {activeTab === "plain" ? (
          <div className="plain-preview">
            <pre>{renderedPlain || "No plain-text output recorded."}</pre>
          </div>
        ) : null}
        {activeTab === "prompt" ? (
          <div className="plain-preview">
            <p className="cell-secondary">
              Prompts are stored in plaintext. Avoid embedding API keys, passwords, or other secrets
              in the prompt — anyone with operator access can read this snapshot.
            </p>
            <pre>{promptSnapshot || "No prompt snapshot recorded for this run."}</pre>
          </div>
        ) : null}
      </div>
    </div>
  );
}
