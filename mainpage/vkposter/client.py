from __future__ import annotations
import re
import time
import logging
from typing import Iterable, Optional, Tuple, Dict, Any
import pandas as pd
import vk_api
import re
from urllib.parse import unquote


logger = logging.getLogger(__name__)

def build_post_text(author_name: str, title: str, genre: str, annotation: str, short_link: str) -> str:
    """
    Конструктор текста поста — теперь это чистая функция (удобно тестировать и переиспользовать).
    """
    return (
        f"{author_name}\n"
        f"{title}\n\n"
        f"{genre}\n\n"
        f"{annotation}\n\n"
        f"{short_link}"
    )


class VkPoster:
    """
    Инкапсулирует всё: VK API-сессию, подписку на группы, постинг, обработку капчи,
    аккуратные результаты и контроль задержек между постами.
    """

    def __init__(
        self,
        token: str,
        pause_seconds: float = 7.0,
        attachment: Optional[str] = None,
        logger_: Optional[logging.Logger] = None,
    ):
        self.token = token
        self.pause_seconds = pause_seconds
        self.attachment = attachment
        self.logger = logger_ or logger

        self.session = vk_api.VkApi(token=self.token)
        self.vk = self.session.get_api()
        self.upload = vk_api.VkUpload(self.vk)

    # ---------- низкоуровневые вспомогательные ----------

    def resolve_group_id(self, url_or_screen: str) -> int:
        """
        Принимает полную ссылку vk.com/... или screen_name (club123, public456, mygroup)
        Возвращает owner_id группы (ОТРИЦАТЕЛЬНЫЙ int).
        Бросает ValueError, если не получилось распознать.
        """
        s = str(url_or_screen).strip()
        m = re.search(r"vk\.com/(?:club|public)?([^?/]+)", s)
        screen = m.group(1) if m else s

        if screen.startswith(("club", "public")):
            screen = screen.lstrip("club").lstrip("public")

        if screen.isdigit():
            return -int(screen)

        resolved = self.vk.utils.resolveScreenName(screen_name=screen)
        if not resolved or resolved.get("type") != "group":
            raise ValueError(f"Группа не найдена/неверное имя: {url_or_screen}")
        return -int(resolved["object_id"])

    def ensure_membership(self, group_id: int) -> str:
        """
        Проверка и попытка вступить в группу. Возвращает строковый статус.
        """
        try:
            resp = self.vk.groups.isMember(group_id=abs(group_id))
            is_member = resp.get("member") if isinstance(resp, dict) else int(resp)
            if is_member:
                return "🔁 Уже подписаны"
            try:
                self.vk.groups.join(group_id=abs(group_id))
                time.sleep(3)
                return "✅ Подписались"
            except vk_api.exceptions.ApiError as e:
                self.logger.info("Join error: %s", e)
                return f"❌ Не удалось подписаться: {e}"
        except Exception as e:
            return f"❌ Ошибка при проверке подписки: {e}"

    def get_photo_link(self):
        PHOTO_RE = re.compile(r'photo-?\d+_\d+')
        if not self.attachment:
            return None

        s = self.attachment.strip()

        # 1) сначала по-быстрому (вдруг строка уже 'photo-...' или простая ссылка)
        m = PHOTO_RE.search(s)
        if m:
            return m.group(0)

        # 2) декодируем %2F и прочее, пробуем снова (иногда закодировано дважды)
        s = unquote(s)
        m = PHOTO_RE.search(s)
        if m:
            return m.group(0)

        s = unquote(s)
        m = PHOTO_RE.search(s)
        return m.group(0) if m else None

    def post_to_group(self, group_url: str, message: str, ensure_join: bool = True) -> Tuple[str, str]:
        """
        Делает пост в одну группу.
        Возвращает (post_status, subscription_status).
        """
        subscription_status = "❌ Группа не обработана"
        try:
            group_id = self.resolve_group_id(group_url)
            subscription_status = self.ensure_membership(group_id) if ensure_join else "—"
            attachment = self.get_photo_link()
            try:
                resp = self.vk.wall.post(
                    owner_id=group_id,
                    message=message,
                    attachments=attachment,
                    from_group=0,
                    signed=1,
                )
                time.sleep(self.pause_seconds)
                return (f"✅ Пост ID: {resp['post_id']}", subscription_status)

            except vk_api.exceptions.ApiError as e:
                self.logger.info("API error: %s", e)
                return (f"❌ Пост не отправлен! ошибка: {e}", subscription_status)

        except Exception as e:
            self.logger.info("Resolve/post error: %s", e)
            return (f"❌ Ошибка: {e}", subscription_status)

    def post_many(self, group_urls: Iterable[str], message: str, ensure_join: bool = True) -> list[Dict[str, Any]]:

        results = []
        for url in group_urls:
            status, subs = self.post_to_group(str(url), message, ensure_join=ensure_join)
            results.append({"url": str(url), "status": status, "subscription": subs})
        return results

    # ---------- вспомогательные сценарии с pandas (необязательно) ----------

    def post_from_dataframe(
        self,
        df,
        link_col: str = "Ссылка",
        message: str = "",
        ensure_join: bool = True,
    ):
        """
        Добавляет/перезаписывает колонки df[['status','subscription']] на основе link_col.
        Возвращает тот же df для удобства чейнинга.
        """
        results = df[link_col].apply(lambda u: self.post_to_group(u, message, ensure_join=ensure_join))
        df[["status", "subscription"]] = pd.DataFrame(results.tolist(), index=df.index)
        return df

