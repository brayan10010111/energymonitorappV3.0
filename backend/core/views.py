"""Vistas del proyecto Django `core`.

Este proyecto sirve un frontend SPA (React/Vite) desde `index.html`.
Las rutas que no comienzan por `/api/` se redirigen a `FrontendAppView`.
"""

from django.views.generic import TemplateView

class FrontendAppView(TemplateView):
    """Sirve `index.html` para soportar routing del SPA en el cliente."""
    template_name = "index.html"


