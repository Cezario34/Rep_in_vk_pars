from django.conf import settings
from django.db import models

class SendAllowance(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                primary_key=True,
                                related_name='Юзер',
                                verbose_name='логин юзера')
    user_name = models.CharField(max_length=255,blank=True, verbose_name='Имя пользователя в вк')
    remaining = models.IntegerField(default=0, verbose_name='Количество доступных попыток')

    class Meta:
        ordering = ('-remaining',)
        verbose_name = 'Пользователи рассылки'
        verbose_name_plural = 'Пользователи рассылки'


    def __str__(self):
        return f"{self.user.username}: remaining={self.remaining}"

class MailingLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    book_title = models.CharField(max_length=200, blank=True)
    author_name = models.CharField(max_length=200, blank=True)
    day = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    ok = models.IntegerField(default=0)
    err = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default="running")  # running / done / failed
    message = models.CharField(max_length=300, blank=True)
    report_name = models.CharField(max_length=200, blank=True)
    errors = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Журнал рассылки"
        verbose_name_plural = "Журнал рассылок"

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} {self.user} {self.book_title} {self.status}"