import type { NewsletterSummary } from "./newsletter-types";
import { ActionDropdown, type ActionItem } from "../../components/ui/ActionDropdown";

type NewsletterListPageProps = {
  items: NewsletterSummary[];
  loading?: boolean;
  busy?: boolean;
  error?: string | null;
  notice?: string | null;
  onDismissError?: () => void;
  onCreate: () => void;
  onEdit: (newsletter: NewsletterSummary) => void;
  onRun: (newsletterId: number) => Promise<void>;
  onArchive: (newsletterId: number) => Promise<void>;
  onPause: (newsletterId: number) => Promise<void>;
  onResume: (newsletterId: number) => Promise<void>;
  onSchedulePause: (newsletterId: number) => Promise<void>;
  onScheduleResume: (newsletterId: number) => Promise<void>;
  onDelete: (newsletterId: number) => Promise<void>;
};

export function NewsletterListPage({
  items,
  loading,
  busy,
  error,
  notice,
  onDismissError,
  onCreate,
  onEdit,
  onRun,
  onArchive,
  onPause,
  onResume,
  onSchedulePause,
  onScheduleResume,
  onDelete
}: NewsletterListPageProps) {
  function getNewsletterActions(newsletter: NewsletterSummary): ActionItem[] {
    const actions: ActionItem[] = [
      {
        label: "Run Now",
        onClick: () => void onRun(newsletter.id),
        variant: "primary",
        disabled: busy,
        hidden: newsletter.status !== "active",
        icon: (
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M5 3.5v9l7-4.5-7-4.5z" fill="currentColor"/>
          </svg>
        )
      },
      {
        label: "Edit",
        onClick: () => onEdit(newsletter),
        disabled: busy,
        icon: (
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M11.5 2.5l2 2M2 14l3-1 8.5-8.5-2-2L3 11 2 14z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        )
      },
      {
        label: "Pause",
        onClick: () => void onPause(newsletter.id),
        disabled: busy,
        icon: (
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="4" y="3" width="3" height="10" rx="1" fill="currentColor"/>
            <rect x="9" y="3" width="3" height="10" rx="1" fill="currentColor"/>
          </svg>
        ),
        hidden: newsletter.status === "archived" || newsletter.status === "paused"
      },
      {
        label: "Resume",
        onClick: () => void onResume(newsletter.id),
        disabled: busy,
        icon: (
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M5 3.5v9l7-4.5-7-4.5z" fill="currentColor"/>
          </svg>
        ),
        hidden: newsletter.status !== "paused"
      }
    ];

    if (newsletter.schedule_cron && newsletter.status === "active") {
      if (newsletter.schedule_enabled) {
        actions.push({
          label: "Pause Schedule",
          onClick: () => void onSchedulePause(newsletter.id),
          disabled: busy,
          icon: (
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 4v4l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          )
        });
      } else {
        actions.push({
          label: "Resume Schedule",
          onClick: () => void onScheduleResume(newsletter.id),
          disabled: busy,
          icon: (
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M6 5l5 3-5 3V5z" fill="currentColor"/>
            </svg>
          ),
          variant: "primary"
        });
      }
    }

    actions.push(
      {
        label: "Archive",
        onClick: () => void onArchive(newsletter.id),
        disabled: busy,
        icon: (
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 5h12M4 5v8a1 1 0 001 1h6a1 1 0 001-1V5M6 2h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        ),
        hidden: newsletter.status === "archived"
      },
      {
        label: "Delete",
        onClick: () => void onDelete(newsletter.id),
        variant: "danger",
        disabled: busy,
        icon: (
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 4h12M12 4v9a1 1 0 01-1 1H5a1 1 0 01-1-1V4M6 2h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        )
      }
    );

    return actions;
  }

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

      {notice ? <p className="form-notice">{notice}</p> : null}

      {loading ? (
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
              {["newsletter-loading-1", "newsletter-loading-2", "newsletter-loading-3"].map((loadingKey) => (
                <tr key={loadingKey} className="loading-row">
                  <td><div className="loading-skeleton-bar" style={{ width: '150px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '80px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '120px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '100px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '110px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '100px' }} /></td>
                  <td><div className="loading-skeleton-bar" style={{ width: '60px' }} /></td>
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
                  <td data-label="Status">
                    <span className={`status-badge status-${newsletter.status}`}>
                      {newsletter.status}
                    </span>
                  </td>
                  <td className="provider-cell" data-label="Provider">
                    <div className="cell-primary">{newsletter.provider_name}</div>
                    <div className="cell-secondary">{newsletter.model_name}</div>
                  </td>
                  <td data-label="Template">{newsletter.template_key}</td>
                  <td data-label="Audience">{newsletter.audience_name}</td>
                  <td data-label="Schedule">
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
                    <ActionDropdown actions={getNewsletterActions(newsletter)} />
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
