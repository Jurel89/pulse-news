import type { NewsletterSummary } from "./newsletter-types";

type NewsletterListPageProps = {
  items: NewsletterSummary[];
  loading?: boolean;
  error?: string | null;
  onDismissError?: () => void;
  onCreate: () => void;
  onEdit: (newsletter: NewsletterSummary) => void;
  onPreview: (newsletter: NewsletterSummary) => void;
  onArchive: (newsletterId: number) => Promise<void>;
  onPause: (newsletterId: number) => Promise<void>;
  onSchedulePause: (newsletterId: number) => Promise<void>;
  onScheduleResume: (newsletterId: number) => Promise<void>;
  onDelete: (newsletterId: number) => Promise<void>;
};

export function NewsletterListPage({
  items,
  loading,
  error,
  onDismissError,
  onCreate,
  onEdit,
  onPreview,
  onArchive,
  onPause,
  onSchedulePause,
  onScheduleResume,
  onDelete
}: NewsletterListPageProps) {
  return (
    <section className="data-grid-section">
      <header className="section-header">
        <div>
          <p className="eyebrow">Newsletters</p>
          <h2 className="section-title">Manage your newsletters</h2>
        </div>
        <button className="primary-button" onClick={onCreate} type="button">
          New Newsletter
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
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Provider</th>
                <th>Schedule</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 3 }, (_, index) => (
                <tr key={index} className="loading-row">
                  <td><div className="loading-skeleton-bar" style={{ width: '150px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '80px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '120px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '100px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '200px' }} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : items.length === 0 ? (
        <article className="empty-state">
          <h3>No newsletters yet</h3>
          <p>
            Create your first newsletter. Define content, configure recipients, set a schedule,
            and send — all from one place.
          </p>
        </article>
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Provider / Model</th>
                <th>Template</th>
                <th>Audience</th>
                <th>Schedule</th>
                <th className="actions-column">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((newsletter) => (
                <tr key={newsletter.id} className="data-row">
                  <td className="name-cell">
                    <div className="cell-primary">{newsletter.name}</div>
                    <div className="cell-secondary">{newsletter.slug}</div>
                  </td>
                  <td>
                    <span className={`status-badge status-${newsletter.status}`}>
                      {newsletter.status}
                    </span>
                  </td>
                  <td className="provider-cell">
                    <div className="cell-primary">{newsletter.provider_name}</div>
                    <div className="cell-secondary">{newsletter.model_name}</div>
                  </td>
                  <td>{newsletter.template_key}</td>
                  <td>{newsletter.audience_name}</td>
                  <td>
                    {newsletter.schedule_cron ? (
                      <span className={newsletter.schedule_enabled ? 'schedule-active' : 'schedule-paused'}>
                        {newsletter.schedule_enabled ? 'Active' : 'Paused'}
                        <span className="schedule-cron">{newsletter.schedule_cron}</span>
                      </span>
                    ) : (
                      <span className="schedule-none">Manual</span>
                    )}
                  </td>
                  <td className="actions-cell">
                    <div className="row-actions">
                      <button 
                        className="action-button" 
                        onClick={() => onPreview(newsletter)} 
                        type="button"
                        title="Preview"
                      >
                        Preview
                      </button>
                      <button 
                        className="action-button" 
                        onClick={() => onEdit(newsletter)} 
                        type="button"
                        title="Edit"
                      >
                        Edit
                      </button>
                      <button 
                        className="action-button" 
                        onClick={() => void onPause(newsletter.id)} 
                        type="button"
                        title="Pause"
                      >
                        Pause
                      </button>
                      {newsletter.schedule_cron ? (
                        newsletter.schedule_enabled ? (
                          <button
                            className="action-button"
                            onClick={() => void onSchedulePause(newsletter.id)}
                            type="button"
                            title="Pause Schedule"
                          >
                            Pause Schedule
                          </button>
                        ) : (
                          <button
                            className="action-button"
                            onClick={() => void onScheduleResume(newsletter.id)}
                            type="button"
                            title="Resume Schedule"
                          >
                            Resume
                          </button>
                        )
                      ) : null}
                      <button 
                        className="action-button secondary" 
                        onClick={() => void onArchive(newsletter.id)} 
                        type="button"
                        title="Archive"
                      >
                        Archive
                      </button>
                      <button 
                        className="action-button danger" 
                        onClick={() => void onDelete(newsletter.id)} 
                        type="button"
                        title="Delete"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
