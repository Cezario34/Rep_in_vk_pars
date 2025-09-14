from django.db import transaction
from django.db.models import F
from .models import SendAllowance

def has_attempt(user) -> bool:
    """Есть ли у юзера хотя бы 1 попытка."""
    return SendAllowance.objects.filter(user=user, remaining__gt=0).exists()

def consume_attempt(user) -> bool:
    """
    Атомарно списывает 1 попытку.
    Возвращает True, если получилось (была попытка), иначе False.
    """
    with transaction.atomic():
        row = (SendAllowance.objects
               .select_for_update()
               .filter(user=user)
               .first())
        if not row or row.remaining <= 0:
            return False
        row.remaining = F("remaining") - 1
        row.save(update_fields=["remaining"])
        # refresh (чтобы F() отразился, если дальше нужно вернуть число)
        row.refresh_from_db(fields=["remaining"])
        return True
