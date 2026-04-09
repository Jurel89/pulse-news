from __future__ import annotations

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import get_settings
from app.database import get_session_maker
from app.models import Newsletter

_scheduler: BackgroundScheduler | None = None


def newsletter_job_id(newsletter_id: int) -> str:
    return f"newsletter-send-{newsletter_id}"


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=settings.database_url)},
            timezone="UTC",
        )
    return _scheduler


def run_scheduled_newsletter(newsletter_id: int) -> None:  # pragma: no cover
    from app.api.newsletters import execute_newsletter_send

    session = get_session_maker()()
    try:
        newsletter = session.scalar(select(Newsletter).where(Newsletter.id == newsletter_id))
        if newsletter is None:
            return
        if not newsletter.schedule_enabled or not newsletter.schedule_cron:
            return
        execute_newsletter_send(session, newsletter, trigger_mode="scheduled-send")
    finally:
        session.close()


def sync_newsletter_schedule(newsletter: Newsletter) -> None:
    scheduler = get_scheduler()
    job_id = newsletter_job_id(newsletter.id)
    existing_job = scheduler.get_job(job_id)

    if newsletter.schedule_enabled and newsletter.schedule_cron:
        trigger = CronTrigger.from_crontab(
            newsletter.schedule_cron,
            timezone=newsletter.timezone or "UTC",
        )
        scheduler.add_job(
            run_scheduled_newsletter,
            trigger=trigger,
            id=job_id,
            args=[newsletter.id],
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=300,
        )
        return

    if existing_job is not None:
        scheduler.remove_job(job_id)


def reconcile_scheduler_jobs() -> None:
    scheduler = get_scheduler()
    session = get_session_maker()()
    try:
        newsletters = session.scalars(select(Newsletter)).all()
        desired_job_ids = set()
        for newsletter in newsletters:
            if newsletter.schedule_enabled and newsletter.schedule_cron:
                desired_job_ids.add(newsletter_job_id(newsletter.id))
            sync_newsletter_schedule(newsletter)

        for job in scheduler.get_jobs():
            if job.id.startswith("newsletter-send-") and job.id not in desired_job_ids:
                scheduler.remove_job(job.id)
    finally:
        session.close()


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
    reconcile_scheduler_jobs()


def shutdown_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
