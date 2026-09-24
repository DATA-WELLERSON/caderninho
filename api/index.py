# Ponto de entrada da Vercel: ela procura um objeto ASGI chamado `app` aqui.
from app.main import app

__all__ = ["app"]
