from django.urls import path
from . import views


urlpatterns = [
    path("vk-login/", views.vk_login_page, name="vk_login"),
    path("vk-token/", views.vk_token_view, name="vk_token"),
    path("vk-store-pkce/", views.vk_store_pkce, name="vk_store_pkce"),
    path("vk-compose/", views.vk_compose_view, name="vk_compose"),
    path("vk-report.xlsx", views.vk_report_download, name="vk_report_download"),
    path("vk-compose/", views.vk_compose_view, name="vk_compose"),
    path("progress/<str:job_id>/", views.send_progress, name="send_progress"),
    path("status/<str:job_id>/", views.send_status, name="send_status"),
    path("report/<str:job_id>/", views.send_report, name="send_report"),
    # ← новый
    # AJAX для сохранения verifier в сессию
]

