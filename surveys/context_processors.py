from django.conf import settings

from .sheets import google_oauth_configured


def branding(request):
    return {
        'site_name': getattr(settings, 'SITE_NAME', 'Lumen'),
        'site_tagline': getattr(
            settings,
            'SITE_TAGLINE',
            'Sign in with Google. Build a form. Answers land in your Sheet.',
        ),
        'google_oauth_configured': google_oauth_configured(),
    }
