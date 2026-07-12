"""Google Sheets helpers for Lumen form responses."""
from __future__ import annotations

import logging
from datetime import timezone

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SHEETS_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
]


class SheetsError(Exception):
    """Raised when Google Sheets operations fail."""


def google_oauth_configured():
    return bool(getattr(settings, 'GOOGLE_OAUTH_CONFIGURED', False))


def _friendly_http_error(exc: HttpError) -> SheetsError:
    status = getattr(exc.resp, 'status', None)
    content = ''
    try:
        content = (exc.content or b'').decode('utf-8', errors='ignore').lower()
    except Exception:
        content = str(exc).lower()

    if status == 403 and ('sheets.googleapis.com' in content or 'service_disabled' in content):
        return SheetsError(
            'Google Sheets API is not enabled for this Google Cloud project. '
            'Enable it, wait a minute, then publish again: '
            'https://console.developers.google.com/apis/api/sheets.googleapis.com/overview'
        )
    if status == 403 and ('drive.googleapis.com' in content or 'drive api' in content):
        return SheetsError(
            'Google Drive API is not enabled for this Google Cloud project. '
            'Enable it, wait a minute, then publish again: '
            'https://console.developers.google.com/apis/api/drive.googleapis.com/overview'
        )
    if status == 401:
        return SheetsError(
            'Google access expired. Sign out, sign in with Google again, then retry.'
        )
    return SheetsError('Could not create or update the Google Sheet. Please try again.')


def get_google_credentials(user):
    """Build Google OAuth credentials from django-allauth social tokens."""
    from allauth.socialaccount.models import SocialToken

    token = (
        SocialToken.objects
        .select_related('account')
        .filter(account__user=user, account__provider='google')
        .first()
    )
    if token is None:
        raise SheetsError('Connect Google to create and update Sheets.')

    credentials = Credentials(
        token=token.token,
        refresh_token=token.token_secret or None,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SHEETS_SCOPES,
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        token.token = credentials.token
        token.save(update_fields=['token'])
    return credentials


def _sheets_service(user):
    return build('sheets', 'v4', credentials=get_google_credentials(user), cache_discovery=False)


def create_spreadsheet_for_form(user, form):
    """Create a Google Sheet owned by the signed-in user and attach it to the form."""
    try:
        service = _sheets_service(user)
        body = {
            'properties': {'title': f'Lumen — {form.title}'},
            'sheets': [{'properties': {'title': 'Responses'}}],
        }
        created = service.spreadsheets().create(
            body=body,
            fields='spreadsheetId,spreadsheetUrl',
        ).execute()
    except HttpError as exc:
        logger.exception('Sheets create failed for form %s', form.pk)
        raise _friendly_http_error(exc) from exc

    form.google_sheet_id = created['spreadsheetId']
    form.google_sheet_url = created.get(
        'spreadsheetUrl',
        f"https://docs.google.com/spreadsheets/d/{created['spreadsheetId']}/edit",
    )
    form.save(update_fields=['google_sheet_id', 'google_sheet_url', 'updated_at'])
    sync_sheet_headers(user, form)
    return form


def sync_sheet_headers(user, form):
    if not form.google_sheet_id:
        return
    try:
        service = _sheets_service(user)
        headers = ['Submitted at', 'Name', 'Email'] + [q.text for q in form.questions.all()]
        service.spreadsheets().values().update(
            spreadsheetId=form.google_sheet_id,
            range='Responses!A1',
            valueInputOption='RAW',
            body={'values': [headers]},
        ).execute()
    except HttpError as exc:
        logger.exception('Sheets header sync failed for form %s', form.pk)
        raise _friendly_http_error(exc) from exc


def answer_display_value(answer):
    if answer.text_answer:
        return answer.text_answer
    return ', '.join(o.text for o in answer.selected_options.all())


def append_response_to_sheet(form, response):
    """Append one response row. Failures are logged; callers may continue."""
    if not form.google_sheet_id or not form.owner_id:
        return False
    try:
        service = _sheets_service(form.owner)
        questions = list(form.questions.all())
        answers = {
            a.question_id: answer_display_value(a)
            for a in response.answers.prefetch_related('selected_options')
        }
        row = [
            response.submitted_at.astimezone(timezone.utc).isoformat(timespec='seconds'),
            response.respondent_name,
            response.respondent_email,
        ] + [answers.get(q.id, '') for q in questions]
        service.spreadsheets().values().append(
            spreadsheetId=form.google_sheet_id,
            range='Responses!A1',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [row]},
        ).execute()
        response.synced_to_sheet = True
        response.save(update_fields=['synced_to_sheet'])
        return True
    except Exception:
        logger.exception('Failed syncing response %s to Google Sheet', response.pk)
        return False


def ensure_form_sheet(user, form):
    if form.google_sheet_id:
        sync_sheet_headers(user, form)
        return form
    return create_spreadsheet_for_form(user, form)
