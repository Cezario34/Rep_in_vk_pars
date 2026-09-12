from __future__ import annotations
import pandas as pd

import threading
import uuid
from pathlib import Path

from .groups import load_group_urls
from .poster import VkMailing
from .service import prepare_post
from .logging_setup import setup_logging
logger = setup_logging("mailing")

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _update(job_id: str, **fields) -> None:
    with _lock:
        _jobs[job_id].update(fields)

def _write_log(log_id, **fields):
    if not log_id:
        return
    try:
        from django.db import close_old_connections
        from django.utils.timezone import now
        from sendonce.models import MailingLog

        close_old_connections()
        if "finished_at" not in fields and fields.get("status") in {"done", "failed"}:
            fields["finished_at"] = now()
        MailingLog.objects.filter(pk=log_id).update(**fields)
    except Exception:
        logger.exception("Не удалось обновить журнал")


def start_mailing_job(
    author_name: str,
    book_title: str,
    age_rating: str,
    annotation: str,
    book_links: str | list[str],
    token: str,
    day: int,
    attachment: str | None,
    groups_dir: str | Path = "group_target",
    log_id=None,
) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "ok": 0,
            "err": 0,
            "total": 0,
            "processed": 0,
            "done": False,
            "failed": False,
            "current": "",
            "message": "Рассылка запускается",
            "report_name": "",
        }

    thread = threading.Thread(
        target=_run_job,
        kwargs={
            "job_id": job_id,
            "author_name": author_name,
            "book_title": book_title,
            "age_rating": age_rating,
            "annotation": annotation,
            "book_links": book_links,
            "token": token,
            "day": day,
            "attachment": attachment,
            "groups_dir": groups_dir,
            "log_id": log_id,
        },
        daemon=True,
    )
    thread.start()
    return job_id


def _run_job(
    job_id: str,
    author_name: str,
    book_title: str,
    age_rating: str,
    annotation: str,
    book_links: str | list[str],
    token: str,
    day: int,
    attachment: str | None,
    groups_dir: str | Path,
    log_id=None,
) -> None:
    try:
        text = prepare_post(
            author_name=author_name,
            book_title=book_title,
            age_rating=age_rating,
            annotation=annotation,
            book_links=book_links,
        )
        frame = load_group_urls(day, groups_dir)
        urls = list(frame["url"])
        _update(job_id, total=len(urls), message="Не прерывайте, идёт рассылка")
        _write_log(log_id, total=len(urls), message="Идёт рассылка")

        poster = VkMailing(token=token, post_text=text, attachment=attachment)
        ok = err = 0
        rows = []
        error_lines = []
        for index, url in enumerate(urls, start=1):
            _update(job_id, current=str(url), processed=index - 1)
            row = poster.process_group(url)
            rows.append(row)
            if str(row["status"]).startswith("Пост ID"):
                ok += 1
            else:
                err += 1
                error_lines.append(f"{url} — {row['status']}")
            _update(job_id, ok=ok, err=err, processed=index, current=str(url))

        report_dir = Path(groups_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_name = f"результат_{job_id}.xlsx"
        report_path = report_dir / report_name
        pd.DataFrame(rows).to_excel(report_path, index=False)

        _update(
            job_id,
            done=True,
            message="Рассылка завершена",
            current="",
            report_name=report_name,
        )
        _write_log(
            log_id,
            total=len(urls),
            ok=ok,
            err=err,
            status="done",
            message="Завершена",
            report_name=report_name,
            errors="\n".join(error_lines),
        )
    except Exception as exc:
        _update(job_id, done=True, failed=True, message=f"Остановка: {exc}")
        _write_log(log_id, status="failed", message=str(exc)[:300])