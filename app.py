from io import BytesIO
import pandas as pd
import streamlit as st

# =====================================
# CONFIGURACIÓN DE LA CONEXIÓN GOOGLE SHEETS
# =====================================
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1rHQTFw1ngpGi-vqRlICOkqoIMGhGquAIx7749OCFKzc/export?format=csv"
)

# =====================================
# MODULO: Dashboard de Repetitividad
# =====================================


def inicializar_session_state():
  """Inicializa todas las claves de sesión requeridas."""
  estado_inicial = {
      "df_cargado": None,
  }

  for clave, valor_defecto in estado_inicial.items():
    if clave not in st.session_state:
      st.session_state[clave] = valor_defecto


inicializar_session_state()

# =====================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =====================================

st.set_page_config(
    page_title="Dashboard Repetitividad", page_icon="⚡", layout="wide"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stAppViewContainer"] {
        background-color: #0b1120 !important; 
        color: #f3f4f6 !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1f2937 !important;
    }

    [data-testid="stSidebar"] * {
        color: #d1d5db !important;
    }

    label, [data-testid="stWidgetLabel"] p {
        color: #9ca3af !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    div[data-baseweb="input"], div[data-baseweb="select"] > div {
        background-color: #1f2937 !important;
        border: 1px solid #374151 !important;
        border-radius: 6px !important;
    }

    div[data-baseweb="input"] input, div[data-baseweb="select"] * {
        color: #f3f4f6 !important;
    }

    div[data-testid="stMetric"] {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-left: 3px solid #38bdf8;
        padding: 16px 20px;
        border-radius: 6px;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 600 !important;
        color: #f3f4f6 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #9ca3af !important;
    }

    button[kind="primary"] {
        background-color: #2563eb !important;
        border: 1px solid #1d4ed8 !important;
        color: white !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
        padding: 0.4rem 1rem !important;
    }

    [data-testid="stDownloadButton"] > button {
        background-color: #059669 !important;
        border: 1px solid #047857 !important;
        color: white !important;
        font-weight: 500 !important;
        border-radius: 6px !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: transparent;
        border-bottom: 1px solid #1f2937;
        padding-bottom: 0;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 4px 4px 0 0;
        color: #9ca3af !important;
        font-weight: 500;
        padding: 10px 16px;
    }

    .stTabs [aria-selected="true"] {
        background-color: #1f2937 !important;
        color: #38bdf8 !important;
        border-bottom: 2px solid #38bdf8 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# =====================================
# FUNCIONES HELPER (OPTIMIZADAS RAM)
# =====================================


@st.cache_data(ttl=600)
def cargar_datos_desde_google_sheets(url: str):
  try:
    df = pd.read_csv(url)
    df.columns = df.columns.str.lower().str.strip()

    if "fechatermino" in df.columns:
      df["fechatermino"] = pd.to_datetime(df["fechatermino"], errors="coerce")

    # Optimización de RAM convirtiendo columnas repetitivas a categorías
    columnas_categoria = ["status", "area", "tiposoltermino"]
    for col in columnas_categoria:
      if col in df.columns:
        df[col] = df[col].astype("category")

    es_valido, mensajes = validar_columnas_requeridas(df)
    if not es_valido:
      for msg in mensajes:
        st.error(msg)
      return None

    for msg in mensajes:
      if msg.startswith("⚠️"):
        st.warning(msg)

    return df
  except Exception as e:
    st.error(f"❌ Error al conectar con Google Sheets: {str(e)}")
    return None


def filtrar_por_fecha(
    datos: pd.DataFrame, fecha_inicio, fecha_fin
) -> pd.DataFrame:
  fecha_inicio_dt = pd.to_datetime(fecha_inicio)
  fecha_fin_dt = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1)
  return datos[
      (datos["fechatermino"] >= fecha_inicio_dt)
      & (datos["fechatermino"] <= fecha_fin_dt)
  ].copy(deep=False)


def obtener_rpu_normalizados(df: pd.DataFrame) -> pd.DataFrame:
  df_norm = df.copy(deep=False)
  df_norm["rpu_norm"] = df["rpu"].astype(str).str.strip()
  df_norm["numsolicitud_norm"] = df["numsolicitud"].astype(str).str.strip()
  return df_norm


def buscar_repetitivos_optimizado(
    periodo_b: pd.DataFrame, periodo_a: pd.DataFrame
) -> tuple:
  periodo_a_norm = obtener_rpu_normalizados(periodo_a)
  periodo_b_norm = obtener_rpu_normalizados(periodo_b)

  merge_result = periodo_b_norm.merge(
      periodo_a_norm[["rpu_norm", "numsolicitud_norm"]],
      on="rpu_norm",
      how="inner",
      suffixes=("_b", "_a"),
  )

  coincidencias = merge_result[
      merge_result["numsolicitud_norm_b"] != merge_result["numsolicitud_norm_a"]
  ].copy()

  if coincidencias.empty:
    return pd.DataFrame(), set()

  rpus_repetitivos = set(coincidencias["rpu_norm"].unique())
  resultado_final = []

  for rpu in rpus_repetitivos:
    regs_b = periodo_b_norm[periodo_b_norm["rpu_norm"] == rpu].copy(deep=False)
    regs_a_con_b = periodo_a_norm[
        periodo_a_norm["rpu_norm"] == rpu
    ].copy(deep=False)
    regs_a_con_b = regs_a_con_b[
        ~regs_a_con_b["numsolicitud_norm"].isin(
            regs_b["numsolicitud_norm"].unique()
        )
    ]

    todos_registros_rpu = pd.concat([regs_b, regs_a_con_b], ignore_index=True)
    todos_registros_rpu = todos_registros_rpu.sort_values(
        by="fechatermino", ascending=False
    )

    todos_registros_rpu["origen"] = "Visita previa"
    if len(todos_registros_rpu) > 0:
      todos_registros_rpu.iloc[
          0, todos_registros_rpu.columns.get_loc("origen")
      ] = "Última visita"

    todos_registros_rpu = todos_registros_rpu.drop(
        columns=["rpu_norm", "numsolicitud_norm"], errors="ignore"
    )
    resultado_final.append(todos_registros_rpu)

  if resultado_final:
    resultado = pd.concat(resultado_final, ignore_index=True)
    resultado = resultado.sort_values(
        by=["rpu", "fechatermino"], ascending=[True, False]
    )
    return resultado, rpus_repetitivos

  return pd.DataFrame(), rpus_repetitivos


def buscar_rpus_duplicados_en_periodo(df: pd.DataFrame) -> tuple:
  if df.empty:
    return pd.DataFrame(), set()

  df_norm = obtener_rpu_normalizados(df)
  agrupado = df_norm.groupby("rpu_norm")["numsolicitud_norm"].nunique()
  rpus_duplicados = agrupado[agrupado > 1].index.tolist()

  if not rpus_duplicados:
    return pd.DataFrame(), set()

  resultado = df_norm[df_norm["rpu_norm"].isin(rpus_duplicados)].copy()
  resultado = resultado.drop(
      columns=["rpu_norm", "numsolicitud_norm"], errors="ignore"
  )
  resultado = resultado.sort_values(
      by=["rpu", "fechatermino"], ascending=[True, False]
  )

  return resultado, set(rpus_duplicados)


def obtener_top_rpus_repetitivos(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
  if df.empty:
    return pd.DataFrame(columns=["area", "rpu", "cantidad_solicitudes"])

  df_norm = obtener_rpu_normalizados(df)
  solicitudes_por_rpu = (
      df_norm.groupby("rpu_norm")["numsolicitud_norm"].nunique().reset_index()
  )
  solicitudes_por_rpu.columns = ["rpu_norm", "cantidad_solicitudes"]
  solicitudes_por_rpu = solicitudes_por_rpu[
      solicitudes_por_rpu["cantidad_solicitudes"] > 1
  ]

  if solicitudes_por_rpu.empty:
    return pd.DataFrame(columns=["area", "rpu", "cantidad_solicitudes"])

  df_norm_con_area = df_norm.copy()
  if "area" not in df_norm_con_area.columns:
    df_norm_con_area["area"] = "Sin especificar"

  area_por_rpu = (
      df_norm_con_area.groupby("rpu_norm")["area"]
      .agg(lambda x: x.mode()[0] if not x.mode().empty else "Sin especificar")
      .reset_index()
  )

  rpu_original = (
      df_norm[["rpu_norm", "rpu"]].drop_duplicates().reset_index(drop=True)
  )

  resultado = solicitudes_por_rpu.merge(area_por_rpu, on="rpu_norm")
  resultado = resultado.merge(rpu_original, on="rpu_norm")
  resultado = resultado[["area", "rpu", "cantidad_solicitudes"]].copy()
  resultado = resultado.sort_values("cantidad_solicitudes", ascending=False)

  return resultado.head(top_n).reset_index(drop=True)


def agregar_etiqueta_visita(
    df: pd.DataFrame,
    columna_rpu: str = "rpu",
    columna_fecha: str = "fechatermino",
) -> pd.DataFrame:
  if df.empty:
    return df

  resultado = df.copy()
  resultado["origen"] = "Visita previa"

  if columna_rpu in resultado.columns and columna_fecha in resultado.columns:
    idx_ultima_visita = resultado.groupby(columna_rpu)[columna_fecha].idxmax()
    resultado.loc[idx_ultima_visita, "origen"] = "Última visita"

  return resultado


def obtener_top_rpe_repetitivo(
    df: pd.DataFrame, top_n: int = 10
) -> pd.DataFrame:
  if df.empty:
    return pd.DataFrame(columns=["rpeejecuta", "cantidad_ordenes"])

  df_filtrado = df[df.get("origen", "") == "Visita previa"].copy()

  if df_filtrado.empty:
    return pd.DataFrame(columns=["rpeejecuta", "cantidad_ordenes"])

  resultado = (
      df_filtrado.groupby("rpeejecuta")
      .size()
      .reset_index(name="cantidad_ordenes")
  )
  resultado = resultado.sort_values("cantidad_ordenes", ascending=False)

  return resultado.head(top_n).reset_index(drop=True)


COLUMNAS_REPORTE = {
    "obligatorias": ["rpu", "numsolicitud", "fechatermino"],
    "opcionales": ["tiposoltermino", "area", "rpeejecuta"],
    "final": ["origen"],
}


def validar_columnas_requeridas(
    df: pd.DataFrame, columnas_requeridas: list = None
) -> tuple:
  if columnas_requeridas is None:
    columnas_requeridas = COLUMNAS_REPORTE["obligatorias"]

  columnas_faltantes = [
      col for col in columnas_requeridas if col not in df.columns
  ]
  mensajes = []

  if columnas_faltantes:
    mensajes.append(f"❌ Columnas faltantes: {', '.join(columnas_faltantes)}")
    return False, mensajes

  if "fechatermino" in df.columns:
    fechas_validas = (
        pd.to_datetime(df["fechatermino"], errors="coerce").notna().sum()
    )
    total_fechas = len(df)

    if fechas_validas == 0:
      mensajes.append("❌ No hay fechas válidas en la columna 'fechatermino'")
      return False, mensajes
    elif fechas_validas < total_fechas:
      porcentaje_invalidas = (
          (total_fechas - fechas_validas) / total_fechas
      ) * 100
      mensajes.append(
          f"⚠️ {porcentaje_invalidas:.1f}% de fechas inválidas"
          f" ({total_fechas - fechas_validas} registros)"
      )

  for col in ["rpu", "numsolicitud"]:
    if col in df.columns:
      vacios = df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum()
      if vacios > 0:
        porcentaje = (vacios / len(df)) * 100
        mensajes.append(
            f"⚠️ {porcentaje:.1f}% de valores vacíos en '{col}' ({vacios}"
            " registros)"
        )

  return True, mensajes


def generar_excel_descarga(df: pd.DataFrame) -> bytes:
  output = BytesIO()
  # xlsxwriter optimiza el uso de RAM al generar archivos Excel
  with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df.to_excel(writer, sheet_name="Repetitivos", index=False)
  output.seek(0)
  return output.getvalue()


# =====================================
# SIDEBAR: SINCRONIZACIÓN DE GOOGLE SHEETS
# =====================================

st.sidebar.markdown("### 🔄 Base de Datos (Cloud)")

if st.sidebar.button(
    "🔄 Sincronizar Datos", type="primary", use_container_width=True
):
  cargar_datos_desde_google_sheets.clear()
  st.sidebar.success("¡Base de datos sincronizada!")

df_temp = cargar_datos_desde_google_sheets(GOOGLE_SHEET_URL)
if df_temp is not None and not df_temp.empty:
  st.session_state.df_cargado = df_temp

st.sidebar.markdown("---")

if st.session_state.df_cargado is not None:
  st.sidebar.success(
      f"**Estado:** Conectado a Google Sheets\n\n📊 **Registros Totales:**"
      f" {len(st.session_state.df_cargado):,}"
  )
else:
  st.sidebar.error(
      "❌ No se pudo conectar a Google Sheets. Verifica la URL de exportación."
  )

st.sidebar.markdown("---")
st.sidebar.caption("Dashboard de Análisis v3.5.2 | CFE Optimización")

# =====================================
# PANEL PRINCIPAL
# =====================================

st.markdown(
    '<h1 class="main-header">⚡ Dashboard de Repetitividad</h1>',
    unsafe_allow_html=True,
)

if st.session_state.df_cargado is None:
  st.warning(
      "⚠️ No hay datos disponibles. Configura la URL de Google Sheets en el"
      " código y presiona 'Sincronizar Datos'."
  )
  st.stop()

tab1, tab2 = st.tabs(["📊 Análisis de Repetitivas", "🔧 RPU Duplicados en Período"])

df = st.session_state.df_cargado

with tab1:
  st.markdown(
      f"""
    <div class="card-info">
        <strong>🌐 Fuente:</strong> Google Sheets (Sincronizado) | 
        <strong>Total de registros:</strong> {len(df):,}
    </div>
    """,
      unsafe_allow_html=True,
  )

  columnas_requeridas = ["rpu", "numsolicitud", "fechatermino"]
  columnas_faltantes = [
      col for col in columnas_requeridas if col not in df.columns
  ]

  if columnas_faltantes:
    st.error(
        f"Faltan columnas requeridas en el archivo: {', '.join(columnas_faltantes)}"
    )
  else:
    st.subheader("⚙️ Filtros de Análisis")

    fecha_min = df["fechatermino"].min().date()
    fecha_max = df["fechatermino"].max().date()

    col1, col2, col3 = st.columns([2, 2, 1.5])

    with col1:
      st.markdown("**📅 Período Base (BD)**")
      fecha_inicio_a = st.date_input(
          "Inicio BD",
          value=fecha_min,
          min_value=fecha_min,
          max_value=fecha_max,
          key="inicio_a",
      )
      fecha_fin_a = st.date_input("Fin BD", value=fecha_max, key="fin_a")

    with col2:
      st.markdown("**📅 Período Repetitividad**")
      fecha_inicio_b = st.date_input(
          "Inicio Repetitividad", value=fecha_min, key="inicio_b"
      )
      fecha_fin_b = st.date_input(
          "Fin Repetitividad", value=fecha_max, key="fin_b"
      )

    with col3:
      st.markdown("**🏷️ Filtro de Status**")
      if "status" in df.columns:
        status_disponibles = sorted(
            df["status"].dropna().astype(str).unique()
        )
        status_seleccionados = st.multiselect(
            "Status", options=status_disponibles, default=status_disponibles
        )
      else:
        status_seleccionados = []
        st.caption("Columna STATUS no detectada.")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(
        "🔍 Filtrar y Procesar Repetitivos",
        type="primary",
        use_container_width=True,
    ):
      datos = df.copy()

      if len(status_seleccionados) > 0 and "status" in datos.columns:
        datos = datos[datos["status"].astype(str).isin(status_seleccionados)]

      if datos.empty:
        st.warning(
            "⚠️ No se encontraron registros con los criterios seleccionados."
        )
      else:
        periodo_a = filtrar_por_fecha(datos, fecha_inicio_a, fecha_fin_a)
        periodo_b = filtrar_por_fecha(datos, fecha_inicio_b, fecha_fin_b)

        if periodo_a.empty or periodo_b.empty:
          st.warning(
              "⚠️ Uno de los rangos de fechas seleccionados no contiene"
              " registros."
          )
        else:
          resultado, rpus_repetitivos = buscar_repetitivos_optimizado(
              periodo_b, periodo_a
          )

          if not resultado.empty:
            st.markdown("---")

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Registros Periodo B", f"{len(periodo_b):,}")
            kpi2.metric("RPUs Repetitivos", f"{len(rpus_repetitivos):,}")
            kpi3.metric("Registros Finales", f"{len(resultado):,}")

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📋 Tabla de Resultantes")

            columnas_tabla = ["rpu", "numsolicitud", "fechatermino"]
            columnas_opcionales = ["tiposoltermino", "area", "rpeejecuta"]
            columnas_disponibles = [
                col for col in columnas_opcionales if col in resultado.columns
            ]

            columnas_tabla.extend(columnas_disponibles)
            columnas_tabla.append("origen")

            tabla = resultado[columnas_tabla].copy()

            if "rpeejecuta" in tabla.columns:
              tabla["rpeejecuta"] = tabla.apply(
                  lambda row: (
                      "Cancelada"
                      if (
                          pd.isna(row.get("rpeejecuta"))
                          or str(row.get("rpeejecuta", "")).strip() == ""
                          or str(row.get("status", "")).strip() == "5"
                      )
                      else row.get("rpeejecuta")
                  ),
                  axis=1,
              )

            renombrar = {
                "rpu": "RPU",
                "numsolicitud": "Orden",
                "fechatermino": "Fecha Término",
                "tiposoltermino": "Tipo Solicitud",
                "area": "Área",
                "rpeejecuta": "RPE atendió",
                "origen": "Origen",
            }

            tabla.columns = [renombrar.get(col, col) for col in tabla.columns]

            st.dataframe(tabla, use_container_width=True, hide_index=True)

            archivo_excel = generar_excel_descarga(tabla)
            st.download_button(
                label="📥 Descargar Reporte Excel",
                data=archivo_excel,
                file_name="RPU_Repetitivos.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
          else:
            st.success(
                "✅ No se hallaron coincidencia de RPUs repetitivos entre los"
                " rangos seleccionados."
            )

with tab2:
  st.markdown(
      f"""
    <div class="card-info">
        <strong>🌐 Fuente:</strong> Google Sheets (Sincronizado) | 
        <strong>Total de registros:</strong> {len(df):,}
    </div>
    """,
      unsafe_allow_html=True,
  )

  st.subheader("🔍 Filtros de Búsqueda de Duplicados")

  col1, col2, col3 = st.columns(3)

  fecha_min = (
      df["fechatermino"].min().date()
      if "fechatermino" in df.columns
      else pd.Timestamp.now().date()
  )
  fecha_max = (
      df["fechatermino"].max().date()
      if "fechatermino" in df.columns
      else pd.Timestamp.now().date()
  )

  with col1:
    fecha_inicio = st.date_input(
        "📅 Fecha Inicio", value=fecha_min, key="fecha_inicio_proximo"
    )

  with col2:
    fecha_fin = st.date_input(
        "📅 Fecha Fin", value=fecha_max, key="fecha_fin_proximo"
    )

  with col3:
    if "status" in df.columns:
      status_disponibles = sorted(df["status"].dropna().astype(str).unique())
      status_seleccionados = st.multiselect(
          "🏷️ Status",
          options=status_disponibles,
          default=status_disponibles,
          key="status_proximo",
      )
    else:
      status_seleccionados = []

  st.markdown("<br>", unsafe_allow_html=True)

  if st.button(
      "🔍 Identificar Duplicados", type="primary", use_container_width=True
  ):
    datos = df.copy()

    if len(status_seleccionados) > 0 and "status" in datos.columns:
      datos = datos[datos["status"].astype(str).isin(status_seleccionados)]

    if datos.empty:
      st.warning("⚠️ No se encontraron registros con los criterios definidos.")
    else:
      datos = filtrar_por_fecha(datos, fecha_inicio, fecha_fin)

      if datos.empty:
        st.warning("⚠️ El rango de fechas seleccionado no cuenta con datos.")
      else:
        resultado, rpus_duplicados = buscar_rpus_duplicados_en_periodo(datos)

        if not resultado.empty:
          st.markdown("---")

          kpi1, kpi2, kpi3 = st.columns(3)
          kpi1.metric("Total Registros", f"{len(datos):,}")
          kpi2.metric("RPUs Duplicados", f"{len(rpus_duplicados):,}")
          kpi3.metric("Registros Reportados", f"{len(resultado):,}")

          st.markdown("<br>", unsafe_allow_html=True)
          st.subheader("📋 Lista de RPUs Duplicados")

          resultado_con_origen = agregar_etiqueta_visita(resultado)

          columnas_tabla = ["rpu", "numsolicitud", "fechatermino"]
          columnas_opcionales = [
              "tiposoltermino",
              "area",
              "rpeejecuta",
              "status",
          ]
          columnas_disponibles = [
              col
              for col in columnas_opcionales
              if col in resultado_con_origen.columns
          ]

          columnas_tabla.extend(columnas_disponibles)
          columnas_tabla.append("origen")

          tabla = resultado_con_origen[columnas_tabla].copy()

          if "rpeejecuta" in tabla.columns:
            tabla["rpeejecuta"] = tabla.apply(
                lambda row: (
                    "Cancelada"
                    if (
                        pd.isna(row.get("rpeejecuta"))
                        or str(row.get("rpeejecuta", "")).strip() == ""
                        or str(row.get("status", "")).strip() == "5"
                    )
                    else row.get("rpeejecuta")
                ),
                axis=1,
            )

          renombrar_tabla = {
              "rpu": "RPU",
              "numsolicitud": "Orden",
              "fechatermino": "Fecha Término",
              "tiposoltermino": "Tipo Solicitud",
              "area": "Área",
              "rpeejecuta": "RPE atendió",
              "status": "Status",
              "origen": "Origen",
          }

          tabla.columns = [
              renombrar_tabla.get(col, col) for col in tabla.columns
          ]

          st.dataframe(tabla, use_container_width=True, hide_index=True)

          archivo_excel = generar_excel_descarga(tabla)
          st.download_button(
              label="📥 Descargar Excel de Duplicados",
              data=archivo_excel,
              file_name="RPU_Duplicados.xlsx",
              mime=(
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              ),
              use_container_width=True,
          )

          st.markdown("---")

          col_top1, col_top2 = st.columns(2)

          with col_top1:
            st.subheader("🏆 Top 30 RPUs Repetitivos")
            top_rpus = obtener_top_rpus_repetitivos(datos, top_n=30)

            if not top_rpus.empty:
              top_rpus_display = top_rpus[
                  ["area", "rpu", "cantidad_solicitudes"]
              ].copy()
              top_rpus_display.columns = ["Área", "RPU", "Cant. Solicitudes"]
              top_rpus_display.insert(
                  0, "Rank", range(1, len(top_rpus_display) + 1)
              )
              st.dataframe(
                  top_rpus_display, use_container_width=True, hide_index=True
              )

          with col_top2:
            st.subheader("👤 Top 10 RPEs Más Repetitivos")
            top_rpe = obtener_top_rpe_repetitivo(
                resultado_con_origen, top_n=10
            )

            if not top_rpe.empty:
              top_rpe_display = top_rpe[["rpeejecuta", "cantidad_ordenes"]].copy()
              top_rpe_display.columns = ["RPE Atendió", "Cant. Órdenes"]
              top_rpe_display.insert(
                  0, "Rank", range(1, len(top_rpe_display) + 1)
              )
              st.dataframe(
                  top_rpe_display, use_container_width=True, hide_index=True
              )
            else:
              st.info("No se hallaron visitas previas asociadas a un RPE.")

        else:
          st.success("✅ Sin registros de RPU duplicados en el período indicado.")