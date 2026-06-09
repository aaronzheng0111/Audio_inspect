"""WSGI entry point for the audio_visual_web project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "audio_visual_web.settings")

application = get_wsgi_application()
