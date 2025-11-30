# app/application/pdf.py
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import TEMPLATES_DIR, BASE_DIR


def _env() -> Environment:
    """
    Crea el entorno Jinja2 apuntando al directorio de plantillas HTML.
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2.html"]),
    )


def render_template_to_html(template_name: str, context: Dict[str, Any]) -> str:
    """
    Renderiza una plantilla Jinja2 a HTML en memoria.
    """
    tpl = _env().get_template(template_name)
    return tpl.render(**context)


def _wkhtmltopdf(html: str, out_path: Path) -> Path:
    """
    Genera PDF usando wkhtmltopdf.

    Lanza RuntimeError con un mensaje claro si:
    - El binario no está instalado o no está en PATH.
    - El comando devuelve un código de salida distinto de 0.
    """
    if not shutil.which("wkhtmltopdf"):
        raise RuntimeError(
            "wkhtmltopdf no está instalado o no se encuentra en el PATH. "
            "Instálalo o define PDF_ENGINE=weasyprint en tu .env."
        )

    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "report.html"
        html_path.write_text(html, encoding="utf-8")

        cmd = ["wkhtmltopdf", "--quiet", str(html_path), str(out_path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError as e:
            raise RuntimeError(
                "No se pudo ejecutar wkhtmltopdf. Verifica que esté instalado y disponible en PATH."
            ) from e

        if proc.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf falló: {proc.stderr or proc.stdout}")

    return out_path


def _weasyprint(html: str, out_path: Path) -> Path:
    """
    Genera PDF usando WeasyPrint. Requiere weasyprint + Cairo/Pango.
    """
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "WeasyPrint no está instalado o faltan dependencias (Cairo/Pango). "
            "Instálalo o cambia PDF_ENGINE a 'wkhtmltopdf'."
        ) from e

    HTML(string=html, base_url=str(BASE_DIR)).write_pdf(str(out_path))
    return out_path


def _detect_engine(explicit: Optional[str] = None) -> str:
    """
    Determina el motor por defecto de forma robusta:

    1. Si se pasa `explicit` -> se usa tal cual.
    2. Si hay PDF_ENGINE en el entorno -> se usa su valor.
    3. Si existe wkhtmltopdf en PATH -> 'wkhtmltopdf'.
    4. Si se puede importar weasyprint -> 'weasyprint'.
    5. Fallback: 'wkhtmltopdf' (y luego dará un error descriptivo si falta).
    """
    if explicit:
        return explicit.lower()

    env_engine = os.getenv("PDF_ENGINE")
    if env_engine:
        return env_engine.lower()

    if shutil.which("wkhtmltopdf"):
        return "wkhtmltopdf"

    try:
        # Comprobación ligera de disponibilidad de WeasyPrint
        from weasyprint import HTML  # noqa: F401
        return "weasyprint"
    except Exception:
        return "wkhtmltopdf"


def build_pdf_from_template(
    template_name: str,
    out_path: Path,
    context: Dict[str, Any],
    engine: Optional[str] = None,
) -> Path:
    """
    Genera un PDF a partir de una plantilla Jinja2 (HTML) usando el motor indicado.

    Parámetros
    ----------
    template_name:
        Nombre de la plantilla dentro de TEMPLATES_DIR (por ejemplo 'report.j2.html').
    out_path:
        Ruta completa donde se guardará el PDF.
    context:
        Diccionario con las variables a inyectar en la plantilla.
    engine:
        'wkhtmltopdf' o 'weasyprint'. Si es None, se auto-detecta con _detect_engine().
    """
    engine = _detect_engine(engine)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = render_template_to_html(template_name, context)

    if engine == "weasyprint":
        return _weasyprint(html, out_path)
    if engine == "wkhtmltopdf":
        return _wkhtmltopdf(html, out_path)

    raise ValueError(f"Engine PDF desconocido: {engine}")


def build_pdf_from_html_file(
    html_path: Path,
    out_path: Path,
    engine: Optional[str] = None,
) -> Path:
    """
    Variante de conveniencia: recibe una ruta a un HTML ya renderizado en disco
    y lo convierte a PDF usando el mismo sistema de motores.

    (Ahora mismo no la usas en `pipeline.py`, pero queda disponible si algún día
    quieres convertir directamente `reporte_integrado.html` a PDF.)
    """
    html = Path(html_path).read_text(encoding="utf-8")
    engine = _detect_engine(engine)

    if engine == "weasyprint":
        return _weasyprint(html, out_path)
    if engine == "wkhtmltopdf":
        return _wkhtmltopdf(html, out_path)

    raise ValueError(f"Engine PDF desconocido: {engine}")
