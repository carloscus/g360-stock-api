from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    source1_url: str = (
        "http://appweb.cipsa.com.pe:8054/AlmacenStock/DownLoadFiles"
        '?value={"linea":"","porLinea":"tbLinea","grupo":"","porGrupo":"tbGrupo","tipo":"","porTipo":"tbTipo","familia":"","porFamilia":"tbFamilia","parametroX2":"","parametroX1":"0"}'
    )
    source2_url: str = (
        "http://appweb.cipsa.com.pe:8054/AlmacenStock/DownLoadFiles"
        '?value={"linea":"","porLinea":"tbLinea","grupo":"","porGrupo":"tbGrupo","tipo":"","porTipo":"tbTipo","familia":"","porFamilia":"tbFamilia","parametroX2":"1","parametroX1":"0"}'
    )
    api_key: str = ""
    cache_ttl_segundos: int = 900
    cache_ruta: str = "data/stock_cache.json"
    cache_ruta2: str = "data/stock_cache_sucursales.json"
    puerto: int = 8000
    # Catalogo maestro
    catalogo_ruta: str = "data/catalog_cache.json"
    catalogo_ttl_segundos: int = 21600  # 6 horas
    # Fuente remota del catalogo (para auto-cargar cuando el disco es efimero, ej: Render free)
    catalogo_raw_url: str = (
        "https://raw.githubusercontent.com/carloscus/g360-master-data/main/output/catalogo_productos.json"
    )
    # CORS - origenes permitidos (separados por coma, "*" para todos)
    cors_origins: str = "*"
    # Rate limiting
    rate_limit: str = "60/minute"
    # Request timeout en segundos
    request_timeout: int = 30
    # Maximo tamano de XLS descargado en bytes (5MB)
    xls_max_bytes: int = 5_242_880
    # Circuit breaker: maximos fallos consecutivos antes de abrir circuito
    circuit_breaker_max_fallos: int = 3
    # Circuit breaker: segundos para intentar de nuevo despues de abrir
    circuit_breaker_reset_seg: int = 300

    model_config = {"env_file": ".env", "env_prefix": "S1_"}


settings = Settings()
