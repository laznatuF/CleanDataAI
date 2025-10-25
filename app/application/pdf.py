# app/application/pdf.py
from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import TEMPLATES_DIR, BASE_DIR

def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2.html"]),
    )

def render_template_to_html(template_name: str, context: Dict[str, Any]) -> str:
    tpl = _env().get_template(template_name)
    return tpl.render(**context)

def _wkhtmltopdf(html: str, out_path: Path) -> Path:
    # Escribe HTML temporal y llama al binario
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "report.html"
        html_path.write_text(html, encoding="utf-8")
        cmd = ["wkhtmltopdf", "--quiet", str(html_path), str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf falló: {proc.stderr or proc.stdout}")
    return out_path

def _weasyprint(html: str, out_path: Path) -> Path:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:
        raise RuntimeError("WeasyPrint no está instalado o faltan dependencias (Cairo/Pango).") from e
    HTML(string=html, base_url=str(BASE_DIR)).write_pdf(str(out_path))
    return out_path

def build_pdf_from_template(
    template_name: str,
    out_path: Path,
    context: Dict[str, Any],
    engine: Optional[str] = None,
) -> Path:
    """
    Genera un PDF a partir de una plantilla Jinja2 (HTML) usando el motor indicado.
    engine: 'wkhtmltopdf' (default) o 'weasyprint'. También se lee PDF_ENGINE de env.
    """
    engine = engine or os.getenv("PDF_ENGINE", "wkhtmltopdf").lower()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html = render_template_to_html(template_name, context)

    if engine == "weasyprint":
        return _weasyprint(html, out_path)
    elif engine == "wkhtmltopdf":
        return _wkhtmltopdf(html, out_path)
    else:
        raise ValueError(f"Engine PDF desconocido: {engine}")
