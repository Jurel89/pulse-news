import type { NewsletterSummary } from "./newsletter-types";

type NewsletterListPageProps = {
  items: NewsletterSummary[];
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
    <section className="newsletters-grid">
      <header className="section-header">
        <div>
          <p className="eyebrow">Newsletters</p>
          <h2 className="section-title">Control every newsletter definition from one place.</h2>
        </div>
        <button className="primary-button" onClick={onCreate} type="button">
          New Newsletter
        </button>
      </header>

      {items.length === 0 ? (
        <article className="empty-state">
          <h3>No newsletters yet</h3>
          <p>
            Create your first newsletter. Define content, configure recipients, set a schedule,
            and send — all from one place.
          </p>
        </article>
      ) : (
        <div className="newsletter-list">
          {items.map((newsletter) => (
            <article className="newsletter-card" key={newsletter.id}>
              <div className="newsletter-card-header">
                <div>
                  <h3>{newsletter.name}</h3>
                  <p>{newsletter.slug}</p>
                </div>
                <span className={`status-chip status-${newsletter.status}`}>{newsletter.status}</span>
              </div>

              <dl className="newsletter-meta">
                <div>
                  <dt>Provider</dt>
                  <dd>
                    {newsletter.provider_name} / {newsletter.model_name}
                  </dd>
                </div>
                <div>
                  <dt>Template</dt>
                  <dd>{newsletter.template_key}</dd>
                </div>
                <div>
                  <dt>Audience</dt>
                  <dd>{newsletter.audience_name}</dd>
                </div>
                <div>
                  <dt>Schedule</dt>
                  <dd>{newsletter.schedule_cron ?? "Manual only"}</dd>
                </div>
              </dl>

              <p className="newsletter-description">{newsletter.description || "No description yet."}</p>

              <div className="card-actions">
                <button className="secondary-button" onClick={() => onPreview(newsletter)} type="button">
                  Preview
                </button>
                <button className="secondary-button" onClick={() => onEdit(newsletter)} type="button">
                  Edit
                </button>
                <button className="secondary-button" onClick={() => void onPause(newsletter.id)} type="button">
                  Pause
                </button>
                {newsletter.schedule_cron ? (
                  newsletter.schedule_enabled ? (
                    <button
                      className="secondary-button"
                      onClick={() => void onSchedulePause(newsletter.id)}
                      type="button"
                    >
                      Pause Schedule
                    </button>
                  ) : (
                    <button
                      className="secondary-button"
                      onClick={() => void onScheduleResume(newsletter.id)}
                      type="button"
                    >
                      Resume Schedule
                    </button>
                  )
                ) : null}
                <button className="secondary-button" onClick={() => void onArchive(newsletter.id)} type="button">
                  Archive
                </button>
                <button className="danger-button" onClick={() => void onDelete(newsletter.id)} type="button">
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
