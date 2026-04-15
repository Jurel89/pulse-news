import { Fragment, useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type { AuditEvent, OperationalEvent } from "./audit-types";

type ActiveLogTab = "audit" | "operational";

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatLabel(value: string): string {
  return value.replace(/[._-]/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getStatusBadgeClass(value: string): string {
  const normalizedValue = value.toLowerCase();

  if (
    normalizedValue.includes("create")
    || normalizedValue.includes("send")
    || normalizedValue.includes("generate")
    || normalizedValue.includes("set")
    || normalizedValue.includes("resume")
    || normalizedValue.includes("login")
    || normalizedValue.includes("deliver")
    || normalizedValue.includes("success")
    || normalizedValue === "ok"
  ) {
    return "status-badge status-active";
  }

  if (
    normalizedValue.includes("delete")
    || normalizedValue.includes("archive")
    || normalizedValue.includes("pause")
    || normalizedValue.includes("fail")
    || normalizedValue.includes("error")
    || normalizedValue.includes("bounce")
    || normalizedValue.includes("partial")
  ) {
    return "status-badge status-paused";
  }

  return "status-badge";
}

function formatAuditEntity(event: AuditEvent): string {
  return `${formatLabel(event.entity_type)} · ${event.entity_id}`;
}

function formatPayload(payloadJson: string | null): string {
  if (!payloadJson) {
    return "No payload recorded.";
  }

  try {
    return JSON.stringify(JSON.parse(payloadJson), null, 2);
  } catch {
    return payloadJson;
  }
}

function isToday(value: string): boolean {
  const currentDate = new Date();
  const eventDate = new Date(value);

  return currentDate.toDateString() === eventDate.toDateString();
}

function isOperationalFailure(status: string): boolean {
  const normalizedStatus = status.toLowerCase();
  return (
    normalizedStatus.includes("fail")
    || normalizedStatus.includes("error")
    || normalizedStatus.includes("bounce")
    || normalizedStatus.includes("partial")
  );
}

export function AuditLogsPage() {
  const [activeTab, setActiveTab] = useState<ActiveLogTab>("audit");

  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [selectedAuditEvent, setSelectedAuditEvent] = useState<AuditEvent | null>(null);
  const [auditSearch, setAuditSearch] = useState("");
  const [auditAction, setAuditAction] = useState("");
  const [auditDateFrom, setAuditDateFrom] = useState("");
  const [auditDateTo, setAuditDateTo] = useState("");
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  const [operationalEvents, setOperationalEvents] = useState<OperationalEvent[]>([]);
  const [selectedOperationalEvent, setSelectedOperationalEvent] = useState<OperationalEvent | null>(null);
  const [operationalSearch, setOperationalSearch] = useState("");
  const [operationalType, setOperationalType] = useState("");
  const [operationalStatus, setOperationalStatus] = useState("");
  const [operationalDateFrom, setOperationalDateFrom] = useState("");
  const [operationalDateTo, setOperationalDateTo] = useState("");
  const [operationalLoading, setOperationalLoading] = useState(false);
  const [operationalError, setOperationalError] = useState<string | null>(null);

  const loadAuditEvents = useCallback(async () => {
    setAuditLoading(true);
    setAuditError(null);

    try {
      const payload = await api.listAuditEvents({
        action: auditAction || undefined,
        search: auditSearch.trim() || undefined,
        date_from: auditDateFrom || undefined,
        date_to: auditDateTo || undefined
      });

      setAuditEvents(payload.items);
      setSelectedAuditEvent((current) => payload.items.find((event) => event.id === current?.id) ?? null);
    } catch (requestError) {
      setAuditError(requestError instanceof Error ? requestError.message : "Unable to load audit events.");
    } finally {
      setAuditLoading(false);
    }
  }, [auditAction, auditDateFrom, auditDateTo, auditSearch]);

  const loadOperationalEvents = useCallback(async () => {
    setOperationalLoading(true);
    setOperationalError(null);

    try {
      const payload = await api.listOperationalEvents({
        event_type: operationalType || undefined,
        status: operationalStatus || undefined,
        search: operationalSearch.trim() || undefined,
        date_from: operationalDateFrom || undefined,
        date_to: operationalDateTo || undefined
      });

      setOperationalEvents(payload.items);
      setSelectedOperationalEvent((current) => payload.items.find((event) => event.id === current?.id) ?? null);
    } catch (requestError) {
      setOperationalError(requestError instanceof Error ? requestError.message : "Unable to load operational events.");
    } finally {
      setOperationalLoading(false);
    }
  }, [operationalDateFrom, operationalDateTo, operationalSearch, operationalStatus, operationalType]);

  useEffect(() => {
    void loadAuditEvents();
  }, [loadAuditEvents]);

  useEffect(() => {
    void loadOperationalEvents();
  }, [loadOperationalEvents]);

  const availableActions = useMemo(
    () => Array.from(new Set(auditEvents.map((event) => event.action))).sort(),
    [auditEvents]
  );

  const availableOperationalTypes = useMemo(
    () => Array.from(new Set(operationalEvents.map((event) => event.event_type))).sort(),
    [operationalEvents]
  );

  const availableOperationalStatuses = useMemo(
    () => Array.from(new Set(operationalEvents.map((event) => event.status))).sort(),
    [operationalEvents]
  );

  const auditStats = useMemo(() => ({
    totalEvents: auditEvents.length,
    todayEvents: auditEvents.filter((event) => isToday(event.created_at)).length,
    uniqueActions: new Set(auditEvents.map((event) => event.action)).size,
    uniqueActors: new Set(auditEvents.map((event) => event.actor_email ?? "system")).size
  }), [auditEvents]);

  const operationalStats = useMemo(() => ({
    totalEvents: operationalEvents.length,
    todayEvents: operationalEvents.filter((event) => isToday(event.created_at)).length,
    runEntries: operationalEvents.filter((event) => event.source === "run").length,
    failureEvents: operationalEvents.filter((event) => isOperationalFailure(event.status)).length
  }), [operationalEvents]);

  const activeError = activeTab === "audit" ? auditError : operationalError;

  function dismissActiveError() {
    if (activeTab === "audit") {
      setAuditError(null);
      return;
    }
    setOperationalError(null);
  }

  return (
    <section className="data-grid-section">
      <header className="section-header">
        <div>
          <p className="eyebrow">Operations</p>
          <h2 className="section-title">Logs</h2>
        </div>
      </header>

      <div className="nav-pills" aria-label="Log views" role="tablist">
        <button
          aria-selected={activeTab === "audit"}
          className={activeTab === "audit" ? "nav-pill active" : "nav-pill"}
          onClick={() => setActiveTab("audit")}
          role="tab"
          type="button"
        >
          Audit Trail
        </button>
        <button
          aria-selected={activeTab === "operational"}
          className={activeTab === "operational" ? "nav-pill active" : "nav-pill"}
          onClick={() => setActiveTab("operational")}
          role="tab"
          type="button"
        >
          Operational Log
        </button>
      </div>

      {activeError ? (
        <div className="error-banner">
          <span>{activeError}</span>
          <button className="error-banner-dismiss" onClick={dismissActiveError} type="button">
            Dismiss
          </button>
        </div>
      ) : null}

      {activeTab === "audit" ? (
        <>
          <div className="info-card-grid">
            <article className="info-card">
              <span className="status-label">Visible Events</span>
              <strong>{auditStats.totalEvents.toLocaleString()}</strong>
            </article>
            <article className="info-card">
              <span className="status-label">Today</span>
              <strong>{auditStats.todayEvents.toLocaleString()}</strong>
            </article>
            <article className="info-card">
              <span className="status-label">Action Types</span>
              <strong>{auditStats.uniqueActions.toLocaleString()}</strong>
            </article>
            <article className="info-card">
              <span className="status-label">Actors</span>
              <strong>{auditStats.uniqueActors.toLocaleString()}</strong>
            </article>
          </div>

          <div className="editor-form">
            <div className="form-grid">
              <label>
                <span>Search</span>
                <input
                  onChange={(event) => setAuditSearch(event.target.value)}
                  placeholder="Search actor, action, entity, or summary"
                  type="search"
                  value={auditSearch}
                />
              </label>

              <label>
                <span>Action type</span>
                <select onChange={(event) => setAuditAction(event.target.value)} value={auditAction}>
                  <option value="">All actions</option>
                  {availableActions.map((actionOption) => (
                    <option key={actionOption} value={actionOption}>
                      {formatLabel(actionOption)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Date from</span>
                <input onChange={(event) => setAuditDateFrom(event.target.value)} type="date" value={auditDateFrom} />
              </label>

              <label>
                <span>Date to</span>
                <input onChange={(event) => setAuditDateTo(event.target.value)} type="date" value={auditDateTo} />
              </label>
            </div>
          </div>

          {auditLoading ? (
            <div className="newsletter-list">
              {Array.from({ length: 3 }, (_, index) => index + 1).map((skeletonId) => (
                <article className="loading-skeleton" key={skeletonId}>
                  <div className="loading-skeleton-bar" />
                  <div className="loading-skeleton-bar" />
                  <div className="loading-skeleton-bar" />
                </article>
              ))}
            </div>
          ) : auditEvents.length === 0 ? (
            <article className="empty-state">
              <h3>No audit events found</h3>
              <p>Try broadening the filters or trigger a newsletter action to generate new audit data.</p>
            </article>
          ) : (
            <div className="data-table-container">
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Entity</th>
                      <th>Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditEvents.map((event) => (
                      <Fragment key={event.id}>
                        <tr
                          className={`data-row ${selectedAuditEvent?.id === event.id ? "expanded" : ""}`}
                          onClick={() => setSelectedAuditEvent((current) => current?.id === event.id ? null : event)}
                          style={{ cursor: "pointer" }}
                        >
                          <td className="cell-secondary" data-label="Timestamp">
                            {formatDateTime(event.created_at)}
                          </td>
                          <td data-label="Action">
                            <span className={getStatusBadgeClass(event.action)}>{formatLabel(event.action)}</span>
                          </td>
                          <td className="name-cell" data-label="Actor">
                            <div className="cell-primary">{event.actor_email ?? "System"}</div>
                            <div className="cell-secondary">Event #{event.id}</div>
                          </td>
                          <td data-label="Entity">
                            <div className="cell-primary">{formatLabel(event.entity_type)}</div>
                            <div className="cell-secondary">{event.entity_id}</div>
                          </td>
                          <td className="name-cell" data-label="Summary">
                            <div className="cell-primary">{event.summary}</div>
                          </td>
                        </tr>
                        {selectedAuditEvent?.id === event.id ? (
                          <tr className="detail-row">
                            <td className="detail-cell" colSpan={5}>
                              <article className="inline-detail-panel">
                                <div className="section-header">
                                  <div>
                                    <h3>{event.summary}</h3>
                                    <span className={getStatusBadgeClass(event.action)}>
                                      {formatLabel(event.action)}
                                    </span>
                                  </div>
                                  <button
                                    aria-label="Close audit event details"
                                    className="secondary-button"
                                    onClick={() => setSelectedAuditEvent(null)}
                                    type="button"
                                  >
                                    Close
                                  </button>
                                </div>

                                <p className="cell-secondary">{formatAuditEntity(event)}</p>

                                <hr className="form-divider" />

                                <div className="newsletter-meta">
                                  <div>
                                    <dt>Timestamp</dt>
                                    <dd>{formatDateTime(event.created_at)}</dd>
                                  </div>
                                  <div>
                                    <dt>Actor</dt>
                                    <dd>{event.actor_email ?? "System"}</dd>
                                  </div>
                                  <div>
                                    <dt>Entity</dt>
                                    <dd>{formatAuditEntity(event)}</dd>
                                  </div>
                                  <div>
                                    <dt>Event ID</dt>
                                    <dd>{event.id}</dd>
                                  </div>
                                </div>

                                <hr className="form-divider" />

                                <div>
                                  <h4>Payload</h4>
                                  <div className="plain-preview">
                                    <pre>{formatPayload(event.payload_json)}</pre>
                                  </div>
                                </div>
                              </article>
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
        </>
      ) : (
        <>
          <div className="info-card-grid">
            <article className="info-card">
              <span className="status-label">Visible Events</span>
              <strong>{operationalStats.totalEvents.toLocaleString()}</strong>
            </article>
            <article className="info-card">
              <span className="status-label">Today</span>
              <strong>{operationalStats.todayEvents.toLocaleString()}</strong>
            </article>
            <article className="info-card">
              <span className="status-label">Run Entries</span>
              <strong>{operationalStats.runEntries.toLocaleString()}</strong>
            </article>
            <article className="info-card">
              <span className="status-label">Failures / Errors</span>
              <strong>{operationalStats.failureEvents.toLocaleString()}</strong>
            </article>
          </div>

          <div className="editor-form">
            <div className="form-grid">
              <label>
                <span>Search</span>
                <input
                  onChange={(event) => setOperationalSearch(event.target.value)}
                  placeholder="Search status, type, newsletter, run, or message"
                  type="search"
                  value={operationalSearch}
                />
              </label>

              <label>
                <span>Event type</span>
                <select onChange={(event) => setOperationalType(event.target.value)} value={operationalType}>
                  <option value="">All event types</option>
                  {availableOperationalTypes.map((typeOption) => (
                    <option key={typeOption} value={typeOption}>
                      {formatLabel(typeOption)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Status</span>
                <select onChange={(event) => setOperationalStatus(event.target.value)} value={operationalStatus}>
                  <option value="">All statuses</option>
                  {availableOperationalStatuses.map((statusOption) => (
                    <option key={statusOption} value={statusOption}>
                      {formatLabel(statusOption)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Date from</span>
                <input
                  onChange={(event) => setOperationalDateFrom(event.target.value)}
                  type="date"
                  value={operationalDateFrom}
                />
              </label>

              <label>
                <span>Date to</span>
                <input
                  onChange={(event) => setOperationalDateTo(event.target.value)}
                  type="date"
                  value={operationalDateTo}
                />
              </label>
            </div>
          </div>

          {operationalLoading ? (
            <div className="newsletter-list">
              {Array.from({ length: 3 }, (_, index) => index + 1).map((skeletonId) => (
                <article className="loading-skeleton" key={skeletonId}>
                  <div className="loading-skeleton-bar" />
                  <div className="loading-skeleton-bar" />
                  <div className="loading-skeleton-bar" />
                </article>
              ))}
            </div>
          ) : operationalEvents.length === 0 ? (
            <article className="empty-state">
              <h3>No operational events found</h3>
              <p>Run a newsletter to capture delivery and generation activity here.</p>
            </article>
          ) : (
            <div className="data-table-container">
              <div className="data-table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Event Type</th>
                      <th>Status</th>
                      <th>Related Entity</th>
                      <th>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {operationalEvents.map((event) => (
                      <Fragment key={event.id}>
                        <tr
                          className={`data-row ${selectedOperationalEvent?.id === event.id ? "expanded" : ""}`}
                          onClick={() => setSelectedOperationalEvent((current) => current?.id === event.id ? null : event)}
                          style={{ cursor: "pointer" }}
                        >
                          <td className="cell-secondary" data-label="Timestamp">
                            {formatDateTime(event.created_at)}
                          </td>
                          <td data-label="Event Type">
                            <span className={getStatusBadgeClass(event.event_type)}>{formatLabel(event.event_type)}</span>
                          </td>
                          <td data-label="Status">
                            <span className={getStatusBadgeClass(event.status)}>{formatLabel(event.status)}</span>
                          </td>
                          <td className="name-cell" data-label="Related Entity">
                            <div className="cell-primary">
                              {event.newsletter_name ?? event.newsletter_slug ?? `Newsletter #${event.newsletter_id}`}
                            </div>
                            <div className="cell-secondary">Run #{event.run_id} · {formatLabel(event.source)}</div>
                          </td>
                          <td className="name-cell" data-label="Message">
                            <div className="cell-primary">{event.message}</div>
                            <div className="cell-secondary">
                              {event.provider_id
                                ? `Provider ID: ${event.provider_id}`
                                : event.trigger_mode
                                  ? formatLabel(event.trigger_mode)
                                  : "Operational event"}
                            </div>
                          </td>
                        </tr>
                        {selectedOperationalEvent?.id === event.id ? (
                          <tr className="detail-row">
                            <td className="detail-cell" colSpan={5}>
                              <article className="inline-detail-panel">
                                <div className="section-header">
                                  <div>
                                    <h3>{event.message}</h3>
                                    <span className={getStatusBadgeClass(event.status)}>
                                      {formatLabel(event.status)}
                                    </span>
                                  </div>
                                  <button
                                    aria-label="Close operational event details"
                                    className="secondary-button"
                                    onClick={() => setSelectedOperationalEvent(null)}
                                    type="button"
                                  >
                                    Close
                                  </button>
                                </div>

                                <p className="cell-secondary">{event.related_entity}</p>

                                <hr className="form-divider" />

                                <div className="newsletter-meta">
                                  <div>
                                    <dt>Timestamp</dt>
                                    <dd>{formatDateTime(event.created_at)}</dd>
                                  </div>
                                  <div>
                                    <dt>Event type</dt>
                                    <dd>{formatLabel(event.event_type)}</dd>
                                  </div>
                                  <div>
                                    <dt>Status</dt>
                                    <dd>{formatLabel(event.status)}</dd>
                                  </div>
                                  <div>
                                    <dt>Source</dt>
                                    <dd>{formatLabel(event.source)}</dd>
                                  </div>
                                  <div>
                                    <dt>Newsletter</dt>
                                    <dd>
                                      {event.newsletter_name ?? event.newsletter_slug ?? `Newsletter #${event.newsletter_id}`}
                                    </dd>
                                  </div>
                                  <div>
                                    <dt>Run</dt>
                                    <dd>{event.run_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Trigger mode</dt>
                                    <dd>{event.trigger_mode ? formatLabel(event.trigger_mode) : "Not recorded"}</dd>
                                  </div>
                                  <div>
                                    <dt>Recipient count</dt>
                                    <dd>{event.recipient_count ?? "Not recorded"}</dd>
                                  </div>
                                  <div>
                                    <dt>Provider ID</dt>
                                    <dd>{event.provider_id ?? "Not recorded"}</dd>
                                  </div>
                                  <div>
                                    <dt>Source ID</dt>
                                    <dd>{event.source_id}</dd>
                                  </div>
                                </div>

                                <hr className="form-divider" />

                                <div>
                                  <h4>Message</h4>
                                  <div className="plain-preview">
                                    <pre>{event.message}</pre>
                                  </div>
                                </div>
                              </article>
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
        </>
      )}
    </section>
  );
}
