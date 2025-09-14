from django.apps import AppConfig

app_name = 'sendonce'

class SendonceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sendonce'
    verbose_name = 'Пользователи рассылки'