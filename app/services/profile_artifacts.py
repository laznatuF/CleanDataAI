# app/services/profile_artifacts.py
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List

import pandas as pd
from weasyprint import HTML as WeasyHTML, CSS as WeasyCSS  # ⬅️ IMPORTANTE: añadimos CSS


@dataclass
class _TableData:
    headers: List[str]
    rows: List[List[str]]


class _ProfileTableParser(HTMLParser):
    """
    Parser muy simple que extrae la PRIMERA tabla del HTML
    (la del perfilado de datos) y devuelve headers + filas
    tal como se ven en la página.
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_thead = False
        self.in_tbody = False
        self.in_tr = False
        self.in_cell = False

        self.headers: List[str] = []
        self.rows: List[List[str]] = []

        self._buffer: List[str] = []
        self._current_row: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "thead":
            self.in_thead = True
        elif self.in_table and tag == "tbody":
            self.in_tbody = True
        elif self.in_table and tag == "tr":
            self.in_tr = True
            self._current_row = []
        elif self.in_tr and tag in ("th", "td"):
            self.in_cell = True
            self._buffer = []

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.in_tr and self.in_cell:
            text = " ".join(x.strip() for x in self._buffer if x.strip())
            self._current_row.append(text)
            self.in_cell = False
        elif tag == "tr" and self.in_tr:
            if self.in_thead:
                self.headers = self._current_row
            elif self.in_tbody:
                if any(self._current_row):
                    self.rows.append(self._current_row)
            self.in_tr = False
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "table":
            self.in_table = False

    def handle_data(self, data):
        if self.in_cell:
            self._buffer.append(data)


def _parse_profile_table(html_text: str) -> _TableData:
    parser = _ProfileTableParser()
    parser.feed(html_text)
    return _TableData(headers=parser.headers, rows=parser.rows)


def build_profile_csv_from_html(html_path: Path, csv_path: Path) -> Path:
    """
    Lee la tabla del perfilado desde el HTML y la guarda como CSV.
    Lo que queda en el CSV es exactamente lo que se ve en pantalla.
    """
    html_text = html_path.read_text(encoding="utf-8")
    table = _parse_profile_table(html_text)
    if not table.headers or not table.rows:
        raise ValueError("No se pudo extraer la tabla de perfilado desde el HTML.")

    df = pd.DataFrame(table.rows, columns=table.headers)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    return csv_path


def build_profile_pdf_from_html(html_path: Path, pdf_path: Path) -> Path:
    """
    Convierte el mismo HTML de perfilado en un PDF usando WeasyPrint.
    El PDF se genera en horizontal (A4 landscape) para que la tabla se vea mejor.
    """
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # CSS para forzar orientación horizontal
    landscape_css = WeasyCSS(
        string="""
        @page {
            size: A4 landscape;
            margin: 1.5cm;
        }
        """
    )

    WeasyHTML(filename=str(html_path)).write_pdf(
        str(pdf_path),
        stylesheets=[landscape_css],
    )
    return pdf_path
