# Lumen

Sign in with Google, create your own forms, share a link, and collect answers directly into a Google Sheet.

## Features

- Google Sign-in for creators (Sheets + Drive file access)
- In-app builder with starter templates (feedback, RSVP, pulse)
- Multi-field options for choice questions; edit / delete questions
- Share link copy, embed iframe, duplicate / archive / delete forms
- Optional close-at datetime
- Respondent name + email on every submission
- Google Sheets sync with retry for failed rows
- Owner email notification on new responses (console email in dev)
- Responses table, CSV export, and choice charts
- Draft / published / closed / archived lifecycle

## Requirements

- Python 3.10+ (3.12+ recommended)
- Django 6.x
- Google Cloud OAuth client + Sheets API + Drive API

## Setup

```bash
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
py -3 manage.py migrate
py -3 manage.py runserver
```

Open http://127.0.0.1:8000/

### Google Cloud

1. Enable **Google Sheets API** and **Google Drive API**
2. OAuth consent screen → add yourself as a **Test user** while in Testing
3. OAuth client (Web) redirect URI:

```text
http://127.0.0.1:8000/accounts/google/login/callback/
```

4. Put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`

### Retry failed Sheet syncs

From Responses UI, or:

```bash
py -3 manage.py retry_sheet_sync
```

## Production / Postgres

Set at least:

```env
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=long-random-value
DJANGO_ALLOWED_HOSTS=your.domain
```

For Postgres, replace the SQLite `DATABASES` block in `lumen/settings.py` with something like:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['POSTGRES_DB'],
        'USER': os.environ['POSTGRES_USER'],
        'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}
```

Then install `psycopg[binary]`, run `collectstatic`, and serve with gunicorn + HTTPS.

For real email notifications, set SMTP vars (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`) and `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`.
