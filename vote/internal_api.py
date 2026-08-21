import secrets

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.sessions.models import Session
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


def bearer_token_is_valid(request):
    expected_token = settings.INTERNAL_API_TOKEN
    authorization = request.headers.get('Authorization', '')
    scheme, separator, provided_token = authorization.partition(' ')

    if not expected_token or scheme != 'Bearer' or not separator or not provided_token:
        return False

    return secrets.compare_digest(
        provided_token.encode('utf-8'),
        expected_token.encode('utf-8'),
    )


@require_GET
def active_users(request):
    if not bearer_token_is_valid(request):
        return JsonResponse({'detail': 'Unauthorized'}, status=401)

    active_user_ids = set()
    active_sessions = Session.objects.filter(expire_date__gt=timezone.now())

    for session in active_sessions.iterator():
        user_id = session.get_decoded().get(SESSION_KEY)
        if user_id is not None:
            active_user_ids.add(user_id)

    user_count = get_user_model().objects.filter(
        pk__in=active_user_ids,
        is_active=True,
    ).count()

    return JsonResponse({'active_users': user_count})
