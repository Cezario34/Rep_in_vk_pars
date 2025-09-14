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

