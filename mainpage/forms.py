from django import forms
from django.core.validators import URLValidator
from urllib.parse import unquote
import re

STATUS_CHOICES = [
    ("new", "Новинка"),
    ("progress", "В процессе"),
    ("done", "Завершена"),
]


USER_DAYS = [
    (1, "День 1"),
    (2, "День 2"),
    (10, "СЛР"),
]

DAY_CHOICES = [
    (0, "Тестовый"),
    (1, "День 1"),
    (2, "День 2"),
    (3, "День 3"),
    (4, "День 4"),
    (5, "День 5"),
    (10, "СЛР"),
    (50, "СЛР 2"),
]

PHOTO_RE = re.compile(r"(photo-?\d+_\d+)")


def extract_vk_photo(value: str) -> str:
    text = unquote((value or "").strip())
    if text.startswith("photo"):
        match = PHOTO_RE.search(text)
        if match:
            return match.group(1)
        raise ValueError("Не похоже на вложение photo-123_456")
    match = PHOTO_RE.search(text)
    if not match:
        raise ValueError("В ссылке нет photo-123_456")
    return match.group(1)


class CampaignForm(forms.Form):

    cover_url = forms.CharField(
        label="Обложка VK",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "ссылка на фото или photo-123_456",
                }
            ),
        )


    author_name = forms.CharField(
        label="Имя автора",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Имя автора", "class": "input"})
    )
    book_title = forms.CharField(
        label="Название книги",
        max_length=160,
        widget=forms.TextInput(attrs={"placeholder": "Название книги", "class": "input"})
    )
    genre = forms.CharField(
        label="Жанр",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Фэнтези / Детектив / ...", "class": "input"})
    )
    status = forms.ChoiceField(
        label="Статус",
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "input"})
    )
    annotation = forms.CharField(
        label="Аннотация",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Коротко о книге...", "class": "input"}),
        max_length=3000
    )
    send_day = forms.TypedChoiceField(
        label="Выбор дня для отправки",
        choices=DAY_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        )
    vk_short_url = forms.CharField(
        label="Короткая ссылка ВК",
        required=True,
        widget=forms.URLInput(attrs={"placeholder": "https://vk.cc/...", "class": "input"})
    )

    def clean_vk_short_url(self):
        url = self.cleaned_data["vk_short_url"]
        # Можно сузить до vk.cc:
        if not url.startswith(("https://vk.cc/", "http://vk.cc/")):
            raise forms.ValidationError("Ожидается короткая ссылка формата https://vk.cc/…")
        return url

    def clean_cover_url(self):
        raw = self.cleaned_data.get("cover_url") or ""
        if not raw.strip():
            return ""
        try:
            return extract_vk_photo(raw)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and (user.is_staff or user.is_superuser):
            self.fields["send_day"].choices = DAY_CHOICES
        else:
            self.fields["send_day"].choices = USER_DAYS

    def clean_send_day(self):
        day = self.cleaned_data["send_day"]
        allowed = {int(value) for value, _ in self.fields["send_day"].choices}
        if int(day) not in allowed:
            raise forms.ValidationError("Этот день вам недоступен.")
        return day
