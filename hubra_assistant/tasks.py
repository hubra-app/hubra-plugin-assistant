"""Celery task: delete drafts past the club's keep_days, and orphans."""

from __future__ import annotations

from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app


@celery_app.task(name="hubra_assistant.tasks.purge")
@per_tenant_job("assistant")
def purge() -> int:
    from hubra.core.extensions import db

    from . import services

    done = services.purge(services.config())
    db.session.commit()
    return done
