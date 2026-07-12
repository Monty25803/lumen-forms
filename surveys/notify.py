"""Email and sheet-sync helpers."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .sheets import SheetsError, append_response_to_sheet

logger = logging.getLogger(__name__)


def notify_owner_of_response(form, response, request=None):
    owner = form.owner
    if owner is None or not owner.email:
        return False
    if not getattr(settings, 'LUMEN_NOTIFY_OWNER_ON_RESPONSE', True):
        return False

    absolute = ''
    if request is not None:
        absolute = request.build_absolute_uri(
            reverse('form_responses', args=[form.public_id])
        )
    subject = f'New Lumen response: {form.title}'
    body = (
        f'{response.respondent_name} ({response.respondent_email}) submitted '
        f'"{form.title}".\n\n'
        f'View responses: {absolute or reverse("form_responses", args=[form.public_id])}\n'
    )
    try:
        send_mail(
            subject,
            body,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lumen.local'),
            [owner.email],
            fail_silently=True,
        )
        return True
    except Exception:
        logger.exception('Failed sending owner notification for response %s', response.pk)
        return False


def retry_unsynced_responses(form, limit=50):
    """Retry Google Sheet sync for responses that failed earlier."""
    pending = form.responses.filter(synced_to_sheet=False).order_by('submitted_at')[:limit]
    synced = 0
    failed = 0
    for response in pending:
        try:
            if append_response_to_sheet(form, response):
                synced += 1
            else:
                failed += 1
        except SheetsError:
            failed += 1
    return synced, failed
