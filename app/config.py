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

    model_config = {"env_file": ".env", "env_prefix": "S1_"}


settings = Settings()
