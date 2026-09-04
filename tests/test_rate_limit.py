"""Tests del rate limiter propio (main.RateLimitMiddleware)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app, RateLimitMiddleware

client = TestClient(app)


@pytest.fixture(autouse=True)
def _limpiar_ventanas():
    """Aislar tests: limpiar contadores por IP antes de cada test."""
    # La instancia del middleware vive dentro de app.middleware_stack ya construido
    node = app.middleware_stack
    while node is not None:
        if isinstance(node, RateLimitMiddleware):
            node._ventanas.clear()
            break
        node = getattr(node, "app", None)
    yield


class TestRateLimiter:
    def test_health_exento_de_rate_limit(self):
        """El health check de Render no debe recibir nunca 429."""
        codigos = [client.get("/api/v1/health").status_code for _ in range(70)]
        assert all(c == 200 for c in codigos), f"/health recibio 429: {set(codigos)}"

    def test_rate_limit_dispara_429(self):
        """Exceder el limite (60/min default) debe retornar 429 con Retry-After."""
        codigos = [client.get("/api/v1/stock?limit=1").status_code for _ in range(70)]
        n_429 = codigos.count(429)
        assert n_429 > 0, "rate limit no se activo (0x429 en 70 requests)"
        # La primera parte del burst debe pasar (60 permitidos)
        assert codigos[:60].count(200) == 60, "los primeros 60 deberian ser 200"

        r = client.get("/api/v1/stock?limit=1")
        assert r.status_code == 429
        assert "Retry-After" in r.headers

    def test_parsear_limite(self):
        """Conversor de 'N/periodo' a (cantidad, segundos)."""
        assert RateLimitMiddleware._parsear_limite("60/minute") == (60, 60)
        assert RateLimitMiddleware._parsear_limite("10/second") == (10, 1)
        assert RateLimitMiddleware._parsear_limite("100/hour") == (100, 3600)
        # default a minuto si el periodo es desconocido
        assert RateLimitMiddleware._parsear_limite("5/weird") == (5, 60)
