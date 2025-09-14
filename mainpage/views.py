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

# === настройки вашего приложения VK ID ===
VK_APP_ID = getattr(settings, "VK_APP_ID", 54138257)  # подставьте свой
VK_REDIRECT_URL = getattr(settings, "VK_REDIRECT_URL", "https://ladaorfeeva.ru/vk-token/")
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
@login_required  # NEW (если нужно требовать логин)
def vk_compose_view(request):  # NEW
    """
    Принимаем заполненную форму.
    Пока просто показываем подтверждение и payload.
    Позже сюда подвяжем реальную отправку в VK.
    """
    form = CampaignForm(request.POST)
    if not form.is_valid():
        # Вернуть пользователя на ту же страницу с ошибками
        return render(request, "mainpage/vk_token.html", {
            "access_token": None,  # токен можно не светить повторно
            "error": None,
            "diag": None,
            "form": form,  # покажем ошибки валидации
        }, status=400)
    token = request.session.get('access_token')
    # if not token:
    #     return render(request, "mainpage/vk_token.html", {
    #         "access_token": None, "error": "Нет токена в сессии. Пройдите вход через VK ID ещё раз.", "form": form
    #     }, status=401)
    if not consume_attempt(request.user):                      # NEW
        return render(request, "mainpage/vk_token.html", {
            "access_token": None,
            "error": "Попытки исчерпаны. Обратитесь к администратору.",
            "form": None,  # форму не показываем
        }, status=403)

    cd = form.cleaned_data
    message = build_post_text(
        author_name=cd["author_name"],
        title=cd["book_title"],
        genre=cd["genre"],
        annotation=cd["annotation"],
        short_link=cd["vk_short_url"],
    )

    day_key = cd["send_day"]
    try:
        group_urls = load_groups_from_excel(day_key)
    except Exception as e:
        return render(request, "mainpage/vk_token.html", {
            "access_token": None, "error": f"Не удалось получить список групп: {e}", "form": form
        }, status=400)

    if not group_urls:
        return render(request, "mainpage/vk_token.html", {
            "access_token": None, "error": "В файле нет ссылок на группы.", "form": form
        }, status=400)

    poster = VkPoster(token=token, pause_seconds=7.0, attachment=None)
    results = poster.post_many(group_urls, message, ensure_join=True)
    for r in results:
        ok_post = str(r.get("status", "")).startswith("✅")
        ok_sub = str(r.get("subscription", "")).startswith(("✅", "🔁", "—"))
        r["ok"] = ok_post and ok_sub

    request.session["vk_last_results"] = results
    request.session["vk_last_payload"] = cd
    return render(request, "mainpage/vk_compose_done.html", {
        "ok": True,
        "payload": cd,
        "results": results,
        "groups_count": len(group_urls),
    })

from django.http import FileResponse, HttpResponse
from io import BytesIO
import pandas as pd
from django.utils.timezone import now

@login_required
def vk_report_download(request):
    results = request.session.get("vk_last_results")
    payload = request.session.get("vk_last_payload")
    if not results:
        return HttpResponse("Нет данных для отчёта. Сначала запустите рассылку.", status=404)

    df = pd.DataFrame(results)

    # если по какой-то причине 'ok' нет — вычислим на лету
    if "ok" not in df.columns:
        ok_post = df["status"].astype(str).str.startswith("✅")
        ok_sub  = df["subscription"].astype(str).str.startswith(("✅","🔁","—"))
        df["ok"] = ok_post & ok_sub

    df = df[df["ok"] == True].drop(columns=["ok"], errors="ignore")

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