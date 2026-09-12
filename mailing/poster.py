from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable

import pandas as pd
import vk_api
from vk_api.exceptions import ApiError, Captcha

from .groups import load_group_urls
from .logging_setup import setup_logging

logger = setup_logging("mailing")
GROUP_RE = re.compile(r"vk\.com/(?:club|public)?([^?/]+)", re.IGNORECASE)
CaptchaSolver = Callable[[str], str]


def parse_token(raw: str) -> str:
    text = raw.strip()
    if "access_token=" in text:
        text = text.split("access_token=", 1)[1]
    if "token=" in text and "access_token=" not in raw:
        text = text.split("token=", 1)[1]
    return text.split("&")[0].strip()


class VkMailing:
    def __init__(
        self,
        token: str,
        post_text: str,
        attachment: str | None = None,
        pause_seconds: float = 7.0,
        captcha_solver: CaptchaSolver | None = None,
    ):
        self.token = parse_token(token)
        self.post_text = post_text
        self.attachment = attachment
        self.pause_seconds = pause_seconds
        self.captcha_solver = captcha_solver
        session = vk_api.VkApi(token=self.token)
        self.vk = session.get_api()

    def resolve_group_id(self, url: str) -> int:
        match = GROUP_RE.search(str(url))
        if not match:
            raise ValueError("Некорректный формат ссылки на группу")
        screen = match.group(1).strip()
        if screen.startswith("club") and screen[4:].isdigit():
            screen = screen[4:]
        elif screen.startswith("public") and screen[6:].isdigit():
            screen = screen[6:]
        if screen.isdigit():
            return -int(screen)
        resolved = self.vk.utils.resolveScreenName(screen_name=screen)
        if not resolved or resolved.get("type") != "group":
            raise ValueError("Группа не найдена или указано неверное имя")
        return -int(resolved["object_id"])

    def ensure_membership(self, group_id: int) -> str:
        try:
            response = self.vk.groups.isMember(group_id=abs(group_id))
            is_member = response.get("member") if isinstance(response, dict) else int(response)
            if is_member:
                return "Уже подписаны"
            self.vk.groups.join(group_id=abs(group_id))
            time.sleep(1)
            return "Подписались"
        except ApiError as exc:
            return f"Не удалось подписаться: {exc}"
        except Exception as exc:
            return f"Ошибка при проверке подписки: {exc}"

    def _post(self, group_id: int) -> dict:
        try:
            return self.vk.wall.post(
                owner_id=group_id,
                message=self.post_text,
                attachments=self.attachment,
                from_group=0,
                signed=1,
            )
        except Captcha as cap:
            if not self.captcha_solver:
                raise
            key = self.captcha_solver(cap.get_url())
            return cap.try_again(key=key)

    def process_group(self, url: str) -> dict:
        result = {
            "url": str(url),
            "status": "Группа не обработана",
            "subscription": "Группа не обработана",
        }
        try:
            group_id = self.resolve_group_id(url)
            result["subscription"] = self.ensure_membership(group_id)
            resp = self._post(group_id)
            time.sleep(self.pause_seconds)
            result["status"] = f"Пост ID: {resp['post_id']}"
            logger.info("%s | %s | %s", result["status"], url, result["subscription"])
        except Captcha as cap:
            result["status"] = f"Нужна капча: {cap.get_url()}"
            logger.warning("Капча для %s: %s", url, cap.get_url())
        except Exception as exc:
            result["status"] = f"Ошибка: {exc}"
            logger.exception("Сбой для %s", url)
        return result


def run_mailing(
    post_text: str,
    token: str,
    day: int,
    attachment: str | None = None,
    groups_dir: str | Path = "group_target",
    output_path: str | Path = "group_target/группы.xlsx",
    captcha_solver: CaptchaSolver | None = None,
) -> Path:
    frame = load_group_urls(day, groups_dir)
    poster = VkMailing(
        token=token,
        post_text=post_text,
        attachment=attachment,
        captcha_solver=captcha_solver,
    )
    rows = [poster.process_group(url) for url in frame["url"]]
    report = pd.DataFrame(rows)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.to_excel(output, index=False)
    logger.info("Готово, отчёт: %s, строк: %s", output, len(report))
    return output