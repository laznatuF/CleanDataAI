import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Header from "../../components/Header";
import { getStatus, artifactUrl } from "../../libs/api";

type CleanSummary = Record<string, any>;
type TableRows = string[][];

/** Detecta separador probable (',' vs ';') en la primera línea */
function detectDelimiter(line: string): string {
  const commas = (line.match(/,/g) || []).length;
  const semis = (line.match(/;/g) || []).length;
  return semis > commas ? ";" : ",";
}

/** Parser CSV sencillito con soporte de comillas */
function parseCsv(text: string): TableRows {
  const lines = text.split(/\r?\n/);
  if (!lines.length) return [];
  const delim = detectDelimiter(lines[0]);
  const rows: TableRows = [];

  for (const raw of lines) {
    const line = raw.replace(/\r$/, "");
    if (!line && rows.length === 0) continue; // salta líneas vacías iniciales
    let inQuotes = false;
    let cur = "";
    const row: string[] = [];

    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          // comilla escapada ""
          cur += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === delim && !inQuotes) {
        row.push(cur);
        cur = "";
      } else {
        cur += ch;
      }
    }
    if (cur !== "" || line.endsWith(delim)) row.push(cur);
    if (row.length) rows.push(row);
  }

  return rows;
}

function CsvTable({ rows }: { rows: TableRows }) {
  if (!rows.length) {
    return (
      <p className="text-sm text-slate-500">
        No hay datos para mostrar.
      </p>
    );
  }

  const [header, ...body] = rows;

  return (
    <div className="overflow-auto border border-slate-200 rounded-2xl bg-white">
      <table className="min-w-full text-xs md:text-sm border-collapse">
        <thead className="bg-slate-50 sticky top-0 z-10">
          <tr>
            {header.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200 whitespace-nowrap"
              >
                {h || <span className="text-slate-400 italic">col_{i + 1}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, r) => (
            <tr key={r} className={r % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
              {row.map((cell, c) => (
                <td
                  key={c}
                  className="px-3 py-1.5 border-b border-slate-100 whitespace-nowrap text-[11px] md:text-xs text-slate-700"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CleanSummaryView({ summary }: { summary: CleanSummary | null }) {
  if (!summary || Object.keys(summary).length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No se registró detalle de limpieza para este proceso.
      </p>
    );
  }

  const trimmed = summary.trimmed_cols as string[] | undefined;
  const dates = summary.date_cols as string[] | undefined;
  const money = summary.money_cols_extracted as string[] | undefined;
  const curNorm = summary.currency_normalized as string[] | undefined;
  const imputed = summary.imputed as Record<string, number> | undefined;
  const dropped = summary.dropped_duplicates as number | undefined;
  const startFix = summary.structural_fixes_start as string[] | undefined;
  const midFix = summary.structural_fixes_middle as string[] | undefined;
  const hrSwap = summary.hr_columns_swapped as Record<string, any> | undefined;
  const mgrInfo = summary.manager_ids_filled as Record<string, any> | undefined;
  const boolCols = summary.bool_cols as string[] | undefined;
  const zipCols = summary.zip_cols_cleaned as string[] | undefined;
  const droppedCols = summary.dropped_columns as string[] | undefined;
  const outliers = summary.outliers as Record<string, any> | undefined;

  return (
    <div className="space-y-3 text-sm text-slate-700">
      {startFix && startFix.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Reparaciones estructurales (inicio)</h4>
          <ul className="list-disc pl-5 mt-1">
            {startFix.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {midFix && midFix.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Reparaciones estructurales (medio)</h4>
          <ul className="list-disc pl-5 mt-1">
            {midFix.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {hrSwap && (
        <div>
          <h4 className="font-semibold text-slate-900">Swap de columnas HR</h4>
          <p className="mt-1">
            Se detectó un posible intercambio entre{" "}
            <code className="text-xs">{hrSwap.performance_col}</code> y{" "}
            <code className="text-xs">{hrSwap.engagement_col}</code>, y se
            reordenaron para que <code className="text-xs">EngagementSurvey</code>{" "}
            sea numérica y <code className="text-xs">PerformanceScore</code> refleje el texto.
          </p>
        </div>
      )}

      {trimmed && trimmed.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Columnas recortadas (trim de espacios y vacíos)</h4>
          <p className="mt-1 text-slate-700">
            Se limpiaron espacios y valores vacíos en{" "}
            <span className="font-medium">{trimmed.length}</span>{" "}
            columnas, por ejemplo:{" "}
            <span className="font-mono text-xs">
              {trimmed.slice(0, 8).join(", ")}
              {trimmed.length > 8 ? "…" : ""}
            </span>
          </p>
        </div>
      )}

      {mgrInfo && (
        <div>
          <h4 className="font-semibold text-slate-900">Relleno de IDs de manager</h4>
          <p className="mt-1">
            Se completaron{" "}
            <span className="font-semibold">{mgrInfo.rows_filled}</span>{" "}
            valores faltantes en la columna{" "}
            <code className="text-xs">{mgrInfo.column}</code> usando el
            nombre del manager en{" "}
            <code className="text-xs">{mgrInfo.from_name_column}</code>.
          </p>
        </div>
      )}

      {boolCols && boolCols.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Columnas convertidas a booleano</h4>
          <p className="mt-1">
            Se detectaron columnas con valores tipo{" "}
            <code className="text-xs">"sí/no", "true/false"</code> y se
            normalizaron a <code className="text-xs">True/False</code>:
            {" "}
            <span className="font-mono text-xs">
              {boolCols.join(", ")}
            </span>
          </p>
        </div>
      )}

      {dates && dates.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Fechas normalizadas</h4>
          <p className="mt-1">
            Se detectaron y normalizaron estas columnas como fechas (formato{" "}
            <code>YYYY-MM-DD</code>):{" "}
            <span className="font-mono text-xs">{dates.join(", ")}</span>
          </p>
        </div>
      )}

      {money && money.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Columnas de monto detectadas</h4>
          <p className="mt-1">
            Se extrajeron valores numéricos y divisas de:{" "}
            <span className="font-mono text-xs">{money.join(", ")}</span>
          </p>
        </div>
      )}

      {curNorm && curNorm.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Monedas normalizadas a CLP</h4>
          <p className="mt-1">
            Se generaron columnas unificadas en CLP, por ejemplo:{" "}
            <span className="font-mono text-xs">{curNorm.join(", ")}</span>
          </p>
        </div>
      )}

      {zipCols && zipCols.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Normalización de códigos postales</h4>
          <p className="mt-1">
            Se estandarizaron códigos postales en:
            {" "}
            <span className="font-mono text-xs">
              {zipCols.join(", ")}
            </span>
          </p>
        </div>
      )}

      {imputed && Object.keys(imputed).length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Imputación de valores faltantes</h4>
          <ul className="list-disc pl-5 mt-1">
            {Object.entries(imputed).map(([col, cnt]) => (
              <li key={col}>
                Columna{" "}
                <span className="font-mono text-xs">{col}</span>:{" "}
                <span className="font-medium">{cnt}</span>{" "}
                valores completados.
              </li>
            ))}
          </ul>
        </div>
      )}

      {typeof dropped === "number" && (
        <div>
          <h4 className="font-semibold text-slate-900">Filas duplicadas eliminadas</h4>
          <p className="mt-1">
            Se eliminaron{" "}
            <span className="font-semibold">{dropped}</span>{" "}
            filas duplicadas.
          </p>
        </div>
      )}

      {droppedCols && droppedCols.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-900">Columnas eliminadas</h4>
          <p className="mt-1">
            Se eliminaron columnas sin nombre o marcadas como{" "}
            <code className="text-xs">Unnamed</code>:{" "}
            <span className="font-mono text-xs">
              {droppedCols.join(", ")}
            </span>
          </p>
        </div>
      )}

      {outliers && (
        <div>
          <h4 className="font-semibold text-slate-900">Detección de outliers (IsolationForest)</h4>
          <p className="mt-1">
            Se identificaron{" "}
            <span className="font-semibold">
              {typeof outliers.outliers === "number" ? outliers.outliers : 0}
            </span>{" "}
            filas atípicas usando columnas{" "}
            <span className="font-mono text-xs">
              {(outliers.used_columns || []).join(", ")}
            </span>{" "}
            con un parámetro de{" "}
            <code className="text-xs">
              contamination ≈ {outliers.contamination}
            </code>.
          </p>
        </div>
      )}
    </div>
  );
}

export default function CsvPreviewPage() {
  const [search] = useSearchParams();
  const navigate = useNavigate();

  const runId = search.get("id") || "";
  const urlParam = search.get("url") || "";

  const [cleanUrl, setCleanUrl] = useState<string | null>(urlParam || null);
  const [origUrl, setOrigUrl] = useState<string | null>(null);
  const [inputUrl, setInputUrl] = useState<string | null>(null);
  const [summary, setSummary] = useState<CleanSummary | null>(null);

  const [cleanRows, setCleanRows] = useState<TableRows>([]);
  const [origRows, setOrigRows] = useState<TableRows>([]);
  const [tab, setTab] = useState<"simple" | "detail">("simple");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);

        let resolvedClean = cleanUrl;
        let resolvedOrig: string | null = null;
        let resolvedInput: string | null = null;
        let cleanSummary: CleanSummary | null = null;

        if (runId) {
          const status: any = await getStatus(runId);
          const arts = status?.artifacts || {};
          const metrics = status?.metrics || {};

          if (arts["dataset_limpio.csv"]) {
            resolvedClean = artifactUrl(arts["dataset_limpio.csv"]);
          }
          if (arts["dataset_original.csv"]) {
            resolvedOrig = artifactUrl(arts["dataset_original.csv"]);
          }
          if (arts["input_original"]) {
            resolvedInput = artifactUrl(arts["input_original"]);
          }
          cleanSummary = metrics["clean_summary"] || metrics["cleanSummary"] || null;
        }

        if (!resolvedClean) {
          throw new Error("No se encontró el archivo limpio para este proceso.");
        }

        setCleanUrl(resolvedClean);
        setOrigUrl(resolvedOrig);
        setInputUrl(resolvedInput);
        setSummary(cleanSummary);

        // Descargamos y parseamos el CSV limpio
        const cleanResp = await fetch(resolvedClean);
        const cleanText = await cleanResp.text();
        setCleanRows(parseCsv(cleanText));

        // Dataset original (si existe)
        if (resolvedOrig) {
          const origResp = await fetch(resolvedOrig);
          const origText = await origResp.text();
          setOrigRows(parseCsv(origText));
        } else {
          setOrigRows([]);
        }
      } catch (e: any) {
        setError(e?.message || "Error al cargar los datos.");
      } finally {
        setLoading(false);
      }
    }

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, urlParam]);

  const handleBack = () => {
    if (runId) navigate(`/status/${runId}`);
    else navigate(-1);
  };

  return (
    <div className="min-h-screen bg-white text-slate-800">
      <Header />

      <main className="mx-auto w-full max-w-[1400px] px-6 md:px-8 py-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl md:text-2xl font-semibold text-slate-900">
              Archivo limpio (CSV)
            </h1>
            {runId && (
              <p className="text-xs text-slate-500 mt-1">
                Proceso{" "}
                <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded">
                  {runId}
                </span>
              </p>
            )}
          </div>

          <div className="flex gap-3">
            {cleanUrl && (
              <a
                href={cleanUrl}
                download
                className="inline-flex items-center rounded-full border border-[#F28C18] bg-white px-4 py-2 text-xs md:text-sm font-semibold text-[#F28C18] shadow-sm hover:bg-[#FFF3E6]"
              >
                Descargar CSV
              </a>
            )}
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-xs md:text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Volver
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-4 border-b border-slate-200 flex gap-2">
          <button
            type="button"
            onClick={() => setTab("simple")}
            className={
              "px-3 pb-2 text-xs md:text-sm font-medium border-b-2 -mb-px " +
              (tab === "simple"
                ? "border-[#F28C18] text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800")
            }
          >
            Vista rápida
          </button>
          <button
            type="button"
            onClick={() => setTab("detail")}
            className={
              "px-3 pb-2 text-xs md:text-sm font-medium border-b-2 -mb-px " +
              (tab === "detail"
                ? "border-[#F28C18] text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800")
            }
          >
            Detalle de limpieza
          </button>
        </div>

        {loading && (
          <p className="text-sm text-slate-500">Cargando datos…</p>
        )}
        {error && (
          <p className="text-sm text-red-600 mb-4">Error: {error}</p>
        )}

        {!loading && !error && (
          <>
            {tab === "simple" && (
              <section>
                <CsvTable rows={cleanRows} />
              </section>
            )}

            {tab === "detail" && (
              <section className="space-y-8">
                {/* 1. CSV limpio (igual que la vista simple) */}
                <div>
                  <h2 className="text-sm md:text-base font-semibold text-slate-900 mb-2">
                    1. Archivo limpio (listo para análisis)
                  </h2>
                  <CsvTable rows={cleanRows} />
                </div>

                {/* 2. Dataset original (versión CSV antes de la limpieza) */}
                <div>
                  <h2 className="text-sm md:text-base font-semibold text-slate-900 mb-2">
                    2. Datos originales antes de limpiar
                  </h2>
                  {origRows.length > 0 ? (
                    <>
                      <p className="text-xs text-slate-500 mb-2">
                        Esta tabla corresponde a{" "}
                        <code>dataset_original.csv</code>, generado a partir del
                        archivo de entrada antes de aplicar reglas de limpieza.
                      </p>
                      <CsvTable rows={origRows} />
                    </>
                  ) : (
                    <p className="text-sm text-slate-500">
                      No se encontró el dataset original en este proceso.
                    </p>
                  )}

                  {inputUrl && (
                    <p className="mt-2 text-xs text-slate-500">
                      Archivo original en su formato cargado:{" "}
                      <a
                        href={inputUrl}
                        className="text-[#1d7fd6] hover:underline font-medium"
                        target="_blank"
                        rel="noreferrer"
                      >
                        descargar archivo original
                      </a>
                      .
                    </p>
                  )}
                </div>

                {/* 3. Resumen de pasos de limpieza */}
                <div>
                  <h2 className="text-sm md:text-base font-semibold text-slate-900 mb-2">
                    3. Resumen de todo lo que se hizo para limpiar
                  </h2>
                  <CleanSummaryView summary={summary} />
                </div>

                {/* 4. Detalle completo (JSON técnico) */}
                <div>
                  <h2 className="text-sm md:text-base font-semibold text-slate-900 mb-2">
                    4. Detalle completo (JSON técnico)
                  </h2>
                  {summary && Object.keys(summary).length > 0 ? (
                    <>
                      <p className="text-xs text-slate-500 mb-2">
                        Aquí se muestra el objeto <code>clean_summary</code>{" "}
                        tal como lo genera el backend, sin resumir, para que
                        puedas ver absolutamente todo lo que se registró en la
                        limpieza.
                      </p>
                      <pre className="text-[10px] md:text-xs bg-slate-900 text-slate-50 rounded-lg p-3 whitespace-pre overflow-auto max-h-[360px]">
                        {JSON.stringify(summary, null, 2)}
                      </pre>
                    </>
                  ) : (
                    <p className="text-sm text-slate-500">
                      No hay JSON de detalle disponible para este proceso.
                    </p>
                  )}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
