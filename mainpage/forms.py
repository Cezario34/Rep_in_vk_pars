from django import forms
from django.core.validators import URLValidator

STATUS_CHOICES = [
    ("new", "Новинка"),
    ("progress", "В процессе"),
    ("done", "Завершена"),
]

DAY_CHOICES = [
    ("day1", "День 1"),
    ("day2", "День 2"),
    ("day3", "День 3"),
    ("day4", "Тестовый"),
    ("СЛР", "СЛР"),
]

class CampaignForm(forms.Form):
    cover_url = forms.URLField(
        label="Ссылка на обложку",
        required=True,
        widget=forms.URLInput(attrs={"placeholder": "https://...jpg", "class": "input"})
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
    send_day = forms.ChoiceField(
        label="Выбор дня для отправки",
        choices=DAY_CHOICES,
        widget=forms.RadioSelect
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
