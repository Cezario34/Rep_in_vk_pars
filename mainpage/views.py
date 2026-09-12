# core/views.py
import json
import logging
import secrets
import base64
import hashlib
import requests
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from .forms import CampaignForm
from django.views.decorators.http import require_GET, require_POST
from .utils import load_groups_from_excel
from .vkposter.client import VkPoster, build_post_text
log = logging.getLogger(__name__)
from sendonce.logic import has_attempt, consume_attempt
from django.http import FileResponse, HttpResponse
from io import BytesIO
import pandas as pd
from django.utils.timezone import now
from sendonce.logic import consume_attempt, has_attempt
from mailing.jobs import start_mailing_job, get_job
from mailing.post_text import build_post_text
from pathlib import Path
from sendonce.models import MailingLog


# === настройки вашего приложения VK ID ===
VK_APP_ID = getattr(settings, "VK_APP_ID", 54138257)  # подставьте свой
VK_REDIRECT_URL = getattr(settings, "VK_REDIRECT_URL", "https://ladaorfeeva.ru/vkstart/vk-token/")
# Эндпоинт обмена кода на токены. Для VK ID как правило oauth2/token:
VK_TOKEN_URLS = [
    "https://id.vk.ru/oauth2/auth",
    "https://id.vk.com/oauth2/auth",
]
@login_required
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

@login_required
def _gen_code_verifier() -> str:
    # 43–128 символов base64url без '='
    raw = secrets.token_urlsafe(64).encode("utf-8")
    # token_urlsafe уже base64url, но подрезаем '=' на всякий
    return _b64url(raw)[:86]

@login_required
def _code_challenge_s256(verifier: str) -> str:
    d = hashlib.sha256(verifier.encode("utf-8")).digest()
    return _b64url(d)

@login_required
def vk_login_page(request):
    """
    Рендерим страницу с кнопкой "Войти через VK ID".
    JS на странице дергает /vk-store-pkce/ чтобы положить verifier/state в сессию,
    считает challenge и инициализирует VKID SDK (Redirect mode).
    """
    return render(request, "mainpage/vk_login.html", {
        "VK_APP_ID": VK_APP_ID,
        "VK_REDIRECT_URL": VK_REDIRECT_URL,
    })

@login_required
@csrf_exempt
def vk_store_pkce(request):
    """
    Принимаем из браузера verifier/state и кладем в серверную сессию,
    чтобы потом использовать при обмене кода на токен (без CORS/куки третьей стороны).
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")
    try:
        payload = json.loads(request.body.decode("utf-8"))
        code_verifier = payload["code_verifier"]
        state = payload["state"]
    except Exception:
        return HttpResponseBadRequest("Bad JSON")

    if not (43 <= len(code_verifier) <= 128):
        return HttpResponseBadRequest("Invalid verifier length")

    request.session["vk_pkce"] = {"code_verifier": code_verifier, "state": state}
    request.session.modified = True
    return JsonResponse({"ok": True})

@login_required
def vk_token_view(request):
    code = request.GET.get("code")
    device_id = request.GET.get("device_id")
    pkce = request.session.get("vk_pkce") or {}
    code_verifier = pkce.get("code_verifier")

    if not code or not device_id:
        return render(request, "mainpage/vk_token.html", {"access_token": None, "error": "Нет code/device_id", "diag": {"query": dict(request.GET.items())}})

    if not code_verifier:
        return render(request, "mainpage/vk_token.html", {"access_token": None, "error": "В сессии нет code_verifier", "diag": {"query": dict(request.GET.items()), "session_has_pkce": False}})

    form = {
        "grant_type": "authorization_code",
        "client_id": str(VK_APP_ID),
        "redirect_uri": VK_REDIRECT_URL,
        "code": code,
        "code_verifier": code_verifier,
        "device_id": device_id,
    }
    url = "https://id.vk.ru/oauth2/auth"  # корректный эндпоинт VK ID
    headers = {"Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}

    resp = requests.post(url, data=form, headers=headers, timeout=20)
    txt = resp.text
    ok = False
    tk = {}
    try:
        tk = resp.json()
        ok = resp.ok and "access_token" in tk
    except Exception:
        pass

    if not ok:
        return render(request, "mainpage/vk_token.html", {
            "access_token": None,
            "error": f"VK вернул ошибку: HTTP {resp.status_code}",
            "diag": {
                "body": tk or txt,
                "query": dict(request.GET.items()),
                "session_has_pkce": "vk_pkce" in request.session,
                "used_url": url,
            },
        })

    # успех
    request.session.pop("vk_pkce", None)

    request.session["access_token"] = tk["access_token"]
    ctx = {
        "access_token": tk["access_token"],
        "error": None,
        "diag": {"token_response_keys": list(tk.keys())},
    }

    if has_attempt(request.user):
        ctx["form"] = CampaignForm()
    else:
        ctx["error"] = "У вас нет доступных попыток. Обратитесь к администратору."

    return render(request, "mainpage/vk_token.html", ctx)

EXCEL_MAP = {
    "day1": "День1.xlsx",
    "day2": "День2.xlsx",
    "day3": "День 3.xlsx",
}



@require_POST  # NEW
@login_required
def vk_compose_view(request):
    form = CampaignForm(request.POST)
    token = request.session.get("access_token") or request.POST.get("token")
    if not form.is_valid():
        return render(request, "mainpage/vk_token.html", {"form": form, "error": None})

    if not token:
        return render(request, "mainpage/vk_token.html", {
            "form": form,
            "error": "Нет VK-токена. Войдите через VK ID или вставьте токен.",
        })

    if not consume_attempt(request.user):
        return render(request, "mainpage/vk_token.html", {
            "form": None,
            "error": "Попытки исчерпаны. Обратитесь к администратору.",
        })

    cd = form.cleaned_data
    preview = build_post_text(
        author_name=cd["author_name"],
        book_title=cd["book_title"],
        age_rating=cd.get("age_rating") or cd.get("genre", ""),
        annotation=cd["annotation"],
        book_links=cd["vk_short_url"],
        )

    if request.POST.get("action") != "send":
        return render(
            request, "mainpage/vk_token.html", {
                "form": form,
                "error": None,
                "preview": preview,
                "access_token": token,
                }
            )

    log = MailingLog.objects.create(
        user=request.user,
        book_title=cd["book_title"],
        author_name=cd["author_name"],
        day=cd["send_day"],
        status="running",
        message="Запущена",
        )
    job_id = start_mailing_job(
        author_name=cd["author_name"],
        book_title=cd["book_title"],
        age_rating=cd.get("age_rating") or cd.get("genre", ""),
        annotation=cd["annotation"],
        book_links=cd["vk_short_url"],
        token=token,
        day=cd["send_day"],

        attachment=(cd.get("cover_url") or "").strip() or None,
        groups_dir="group_target",
    )
    return redirect("send_progress", job_id=job_id)


@login_required
def vk_report_download(request):
    results = request.session.get("vk_last_results")
    payload = request.session.get("vk_last_payload")
    if not results:
        return HttpResponse("Нет данных для отчёта. Сначала запустите рассылку.", status=404)

    df = pd.DataFrame(results)


    # собираем Excel в память
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Результаты")
        if payload:
            pd.DataFrame([payload]).to_excel(writer, index=False, sheet_name="Кампания")
    buf.seek(0)

    filename = f"vk_report_{now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return FileResponse(
        buf,
        as_attachment=True,
        filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@login_required
def send_progress(request, job_id):
    if not get_job(job_id):
        return HttpResponse("Задача не найдена", status=404)
    return render(request, "mainpage/progress.html", {"job_id": job_id})


@login_required
def send_status(request, job_id):
    job = get_job(job_id)
    if not job:
        return JsonResponse({"ok": 0, "err": 0, "processed": 0, "total": 0, "done": True, "failed": True, "message": "Нет задачи", "current": ""})
    return JsonResponse(job)


@login_required
def send_report(request, job_id):
    job = get_job(job_id)
    if not job or not job.get("report_name"):
        return HttpResponse("Отчёт ещё не готов", status=404)
    path = Path("group_target") / job["report_name"]
    if not path.exists():
        return HttpResponse("Файл не найден", status=404)
    return FileResponse(path.open("rb"), as_attachment=True, filename=job["report_name"])


@login_required
def vk_dev_token(request):
    if not settings.DEBUG:
        return HttpResponse("Not found", status=404)

    if request.method != "POST":
        return render(request, "mainpage/vk_dev_token.html")

    raw = (request.POST.get("token") or "").strip()
    if "access_token=" in raw:
        raw = raw.split("access_token=", 1)[1]
    raw = raw.split("&")[0].strip()
    if not raw:
        return render(request, "mainpage/vk_dev_token.html", {
            "error": "Вставьте токен",
        })

    request.session["access_token"] = raw
    ctx = {"access_token": raw, "error": None, "diag": {"debug_token": True}}
    if has_attempt(request.user):
        ctx["form"] = CampaignForm()
    else:
        ctx["error"] = "У вас нет доступных попыток. Обратитесь к администратору."
    return render(request, "mainpage/vk_token.html", ctx)