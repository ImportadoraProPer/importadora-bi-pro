"""
Dashboard definitivo para importadoras - MVP comercial
Framework: Streamlit

Instalación:
    pip install streamlit pandas numpy plotly openpyxl

Ejecución:
    streamlit run app.py

Columnas esperadas en Excel/CSV:
    fecha
    sku
    producto
    categoria
    proveedor
    unidades_vendidas
    precio_venta
    costo_unitario
    stock_actual
    stock_minimo
    dias_entrega

Objetivo del dashboard:
- Detectar productos críticos
- Calcular capital inmovilizado
- Predecir demanda futura
- Recomendar compras
- Detectar productos muertos y sobrestock
- Exportar recomendaciones para gerencia/compras
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import hashlib

st.set_page_config(
    page_title="Importadora BI Pro",
    page_icon="📦",
    layout="wide"
)

# =====================================================
# CONTROL DE ACCESO - USUARIOS Y VENCIMIENTO
# =====================================================

# Usuarios demo. Cambia estos usuarios según tus clientes.
# La contraseña NO se guarda en texto plano: se guarda como hash SHA-256.
USUARIOS = {
    "admin": {
        "nombre": "Administrador",
        "empresa": "Importadora BI Pro",
        "password_hash": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",  # admin123
        "expira": "2030-12-31",
    },
    "cliente_demo": {
        "nombre": "Cliente Demo",
        "empresa": "Empresa Demo SAC",
        "password_hash": "d3ad9315b7be5dd53b31a273b3b3aba5defe700808305aa16a3062b76658a791",  # demo123
        "expira": "2026-12-31",
    },
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def login():
    st.title("🔐 Acceso privado")
    st.markdown("Ingrese sus credenciales para acceder al dashboard.")

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        ingresar = st.form_submit_button("Ingresar")

    if ingresar:
        user_data = USUARIOS.get(usuario)

        if user_data is None:
            st.error("Usuario o contraseña incorrectos.")
            st.stop()

        if hash_password(password) != user_data["password_hash"]:
            st.error("Usuario o contraseña incorrectos.")
            st.stop()

        fecha_expiracion = datetime.strptime(user_data["expira"], "%Y-%m-%d").date()
        hoy = datetime.now().date()

        if hoy > fecha_expiracion:
            st.error("Tu acceso ha expirado. Comunícate con el administrador.")
            st.stop()

        st.session_state["autenticado"] = True
        st.session_state["usuario"] = usuario
        st.session_state["nombre"] = user_data["nombre"]
        st.session_state["empresa"] = user_data["empresa"]
        st.session_state["expira"] = user_data["expira"]
        st.rerun()


def cerrar_sesion():
    for key in ["autenticado", "usuario", "nombre", "empresa", "expira"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


if "autenticado" not in st.session_state:
    login()
    st.stop()

with st.sidebar:
    st.success(f"Acceso: {st.session_state['empresa']}")
    st.caption(f"Usuario: {st.session_state['nombre']}")
    st.caption(f"Válido hasta: {st.session_state['expira']}")
    if st.button("Cerrar sesión"):
        cerrar_sesion()

# =====================================================
# DATOS DEMO
# =====================================================

@st.cache_data
def generar_datos_demo(n_productos=150, dias=240):
    np.random.seed(42)

    categorias = ["Ferretería", "Hogar", "Tecnología", "Repuestos", "Herramientas", "Accesorios"]
    proveedores = ["China", "EE.UU.", "Brasil", "México", "Canadá"]

    productos = []
    for i in range(1, n_productos + 1):
        categoria = np.random.choice(categorias)
        proveedor = np.random.choice(proveedores)
        costo = np.random.uniform(12, 280)
        margen = np.random.uniform(0.18, 0.70)
        precio = costo * (1 + margen)
        stock_actual = np.random.randint(0, 1200)
        stock_minimo = np.random.randint(15, 180)
        dias_entrega = np.random.randint(20, 95)

        productos.append({
            "sku": f"SKU-{i:04d}",
            "producto": f"Producto {i}",
            "categoria": categoria,
            "proveedor": proveedor,
            "precio_venta": round(precio, 2),
            "costo_unitario": round(costo, 2),
            "stock_actual": stock_actual,
            "stock_minimo": stock_minimo,
            "dias_entrega": dias_entrega,
        })

    productos_df = pd.DataFrame(productos)
    fechas = pd.date_range(datetime.today() - timedelta(days=dias), periods=dias, freq="D")

    ventas = []
    for _, row in productos_df.iterrows():
        demanda_base = np.random.gamma(shape=2.2, scale=4.5)
        estacionalidad = np.random.uniform(0.70, 1.45)

        for fecha in fechas:
            dia_mes = fecha.day
            factor = 1.25 if dia_mes in range(1, 8) else 1.0
            factor *= 1.15 if fecha.weekday() in [4, 5] else 1.0

            if np.random.rand() < 0.72:
                unidades = np.random.poisson(demanda_base * estacionalidad * factor)
            else:
                unidades = 0

            ventas.append({
                "fecha": fecha,
                "sku": row["sku"],
                "producto": row["producto"],
                "categoria": row["categoria"],
                "proveedor": row["proveedor"],
                "unidades_vendidas": unidades,
                "precio_venta": row["precio_venta"],
                "costo_unitario": row["costo_unitario"],
                "stock_actual": row["stock_actual"],
                "stock_minimo": row["stock_minimo"],
                "dias_entrega": row["dias_entrega"],
            })

    return pd.DataFrame(ventas)


# =====================================================
# PROCESAMIENTO
# =====================================================

def normalizar_columnas(df):
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def preparar_datos(df):
    df = normalizar_columnas(df)

    columnas_necesarias = [
        "fecha", "sku", "producto", "categoria", "proveedor",
        "unidades_vendidas", "precio_venta", "costo_unitario",
        "stock_actual", "stock_minimo", "dias_entrega"
    ]

    faltantes = [c for c in columnas_necesarias if c not in df.columns]
    if faltantes:
        st.error(f"Faltan columnas necesarias: {', '.join(faltantes)}")
        st.stop()

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    numericas = [
        "unidades_vendidas", "precio_venta", "costo_unitario",
        "stock_actual", "stock_minimo", "dias_entrega"
    ]

    for col in numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(subset=["fecha"])

    df["venta_soles"] = df["unidades_vendidas"] * df["precio_venta"]
    df["costo_soles"] = df["unidades_vendidas"] * df["costo_unitario"]
    df["margen_soles"] = df["venta_soles"] - df["costo_soles"]
    df["margen_pct"] = np.where(df["venta_soles"] > 0, df["margen_soles"] / df["venta_soles"], 0)

    return df


def calcular_resumen_producto(df, dias_prediccion=30):
    max_fecha = df["fecha"].max()
    ultimos_30 = df[df["fecha"] >= max_fecha - pd.Timedelta(days=30)]
    ultimos_90 = df[df["fecha"] >= max_fecha - pd.Timedelta(days=90)]
    ultimos_180 = df[df["fecha"] >= max_fecha - pd.Timedelta(days=180)]

    resumen = df.groupby(["sku", "producto", "categoria", "proveedor"], as_index=False).agg(
        unidades_total=("unidades_vendidas", "sum"),
        ventas_total=("venta_soles", "sum"),
        margen_total=("margen_soles", "sum"),
        precio_promedio=("precio_venta", "mean"),
        costo_promedio=("costo_unitario", "mean"),
    )

    ultimo_stock = (
        df.sort_values(["sku", "fecha"])
        .groupby("sku", as_index=False)
        .tail(1)[["sku", "stock_actual", "stock_minimo", "dias_entrega", "fecha"]]
        .rename(columns={"fecha": "fecha_ultimo_stock"})
    )

    resumen = resumen.merge(ultimo_stock, on="sku", how="left")

    demanda_30 = ultimos_30.groupby("sku", as_index=False).agg(demanda_30d=("unidades_vendidas", "sum"))
    demanda_90 = ultimos_90.groupby("sku", as_index=False).agg(demanda_90d=("unidades_vendidas", "sum"))
    demanda_180 = ultimos_180.groupby("sku", as_index=False).agg(demanda_180d=("unidades_vendidas", "sum"))

    resumen = resumen.merge(demanda_30, on="sku", how="left")
    resumen = resumen.merge(demanda_90, on="sku", how="left")
    resumen = resumen.merge(demanda_180, on="sku", how="left")
    resumen[["demanda_30d", "demanda_90d", "demanda_180d"]] = resumen[["demanda_30d", "demanda_90d", "demanda_180d"]].fillna(0)

    resumen["demanda_diaria_30"] = resumen["demanda_30d"] / 30
    resumen["demanda_diaria_90"] = resumen["demanda_90d"] / 90
    resumen["demanda_diaria_180"] = resumen["demanda_180d"] / 180

    resumen["demanda_diaria_predicha"] = (
        resumen["demanda_diaria_30"] * 0.55 +
        resumen["demanda_diaria_90"] * 0.30 +
        resumen["demanda_diaria_180"] * 0.15
    )

    resumen["demanda_predicha_30d"] = np.ceil(resumen["demanda_diaria_predicha"] * dias_prediccion)

    resumen["dias_cobertura"] = np.where(
        resumen["demanda_diaria_predicha"] > 0,
        resumen["stock_actual"] / resumen["demanda_diaria_predicha"],
        999
    )

    resumen["dias_para_quiebre"] = np.where(
        resumen["demanda_diaria_predicha"] > 0,
        resumen["stock_actual"] / resumen["demanda_diaria_predicha"],
        999
    )
    resumen["dias_para_quiebre"] = resumen["dias_para_quiebre"].round(1)

    resumen["margen_pct"] = np.where(
        resumen["ventas_total"] > 0,
        resumen["margen_total"] / resumen["ventas_total"],
        0
    )

    resumen["capital_inmovilizado"] = resumen["stock_actual"] * resumen["costo_promedio"]

    resumen["punto_reorden"] = np.ceil(
        resumen["demanda_diaria_predicha"] * resumen["dias_entrega"] + resumen["stock_minimo"]
    )

    resumen["cantidad_sugerida_compra"] = np.maximum(
        resumen["punto_reorden"] - resumen["stock_actual"],
        0
    )

    resumen["inversion_sugerida_compra"] = resumen["cantidad_sugerida_compra"] * resumen["costo_promedio"]

    condiciones_estado_compra = [
        (resumen["stock_actual"] <= resumen["stock_minimo"]) | (resumen["dias_para_quiebre"] <= 7),
        resumen["stock_actual"] < resumen["punto_reorden"],
        resumen["stock_actual"] <= resumen["punto_reorden"] * 1.15,
    ]
    estados_estado_compra = [
        "🔴 Urgente",
        "🟠 Comprar ahora",
        "🟡 Vigilar",
    ]
    resumen["estado"] = np.select(condiciones_estado_compra, estados_estado_compra, default="🟢 OK")

    condiciones = [
        resumen["demanda_90d"] == 0,
        resumen["stock_actual"] <= resumen["stock_minimo"],
        resumen["stock_actual"] < resumen["punto_reorden"],
        resumen["dias_cobertura"] > 180,
        resumen["dias_cobertura"] > 90,
    ]

    estados = [
        "Producto muerto",
        "Riesgo de quiebre",
        "Reponer pronto",
        "Sobrestock crítico",
        "Sobrestock moderado",
    ]

    resumen["estado_inventario"] = np.select(condiciones, estados, default="Saludable")

    resumen["score_prioridad_compra"] = (
        resumen["margen_total"].rank(pct=True) * 0.30 +
        resumen["demanda_30d"].rank(pct=True) * 0.35 +
        resumen["ventas_total"].rank(pct=True) * 0.20 +
        (1 / resumen["dias_cobertura"].replace(0, np.nan)).rank(pct=True).fillna(0) * 0.15
    )

    resumen["accion_recomendada"] = "Mantener"
    resumen.loc[resumen["estado_inventario"].isin(["Riesgo de quiebre", "Reponer pronto"]), "accion_recomendada"] = "Comprar / reponer"
    resumen.loc[resumen["estado_inventario"].isin(["Sobrestock crítico", "Sobrestock moderado"]), "accion_recomendada"] = "Liquidar / promocionar"
    resumen.loc[resumen["estado_inventario"] == "Producto muerto", "accion_recomendada"] = "Evaluar liquidación"

    return resumen.sort_values("score_prioridad_compra", ascending=False)


def exportar_excel(resumen):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Resumen_SKU", index=False)
        resumen[resumen["accion_recomendada"] == "Comprar / reponer"].to_excel(writer, sheet_name="Comprar", index=False)
        resumen[resumen["accion_recomendada"].isin(["Liquidar / promocionar", "Evaluar liquidación"])].to_excel(writer, sheet_name="Liquidar", index=False)
    output.seek(0)
    return output


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("📦 Importadora BI Pro")
st.sidebar.caption("Ventas, inventario, rotación, forecast y compras")

archivo = st.sidebar.file_uploader("Sube Excel o CSV", type=["xlsx", "csv"])

dias_prediccion = st.sidebar.slider("Días para predecir demanda", 15, 90, 30, step=15)

if archivo is not None:
    if archivo.name.endswith(".csv"):
        data = pd.read_csv(archivo)
    else:
        data = pd.read_excel(archivo)
else:
    data = generar_datos_demo()

ventas = preparar_datos(data)

fecha_min = ventas["fecha"].min().date()
fecha_max = ventas["fecha"].max().date()

rango = st.sidebar.date_input(
    "Rango de fechas",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max
)

categorias = sorted(ventas["categoria"].dropna().unique())
proveedores = sorted(ventas["proveedor"].dropna().unique())

cat_sel = st.sidebar.multiselect("Categorías", categorias, default=categorias)
prov_sel = st.sidebar.multiselect("Proveedores", proveedores, default=proveedores)

if isinstance(rango, tuple) and len(rango) == 2:
    inicio, fin = pd.to_datetime(rango[0]), pd.to_datetime(rango[1])
else:
    inicio, fin = ventas["fecha"].min(), ventas["fecha"].max()

ventas_filtradas = ventas[
    (ventas["fecha"] >= inicio) &
    (ventas["fecha"] <= fin) &
    (ventas["categoria"].isin(cat_sel)) &
    (ventas["proveedor"].isin(prov_sel))
]

if ventas_filtradas.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

resumen = calcular_resumen_producto(ventas_filtradas, dias_prediccion=dias_prediccion)

# =====================================================
# HEADER
# =====================================================

st.title("📊 Dashboard Definitivo para Importadoras")
st.markdown("Sistema de inteligencia comercial para inventario, ventas, rotación, forecast y compras.")

# =====================================================
# KPIs GERENCIALES
# =====================================================

ventas_total = ventas_filtradas["venta_soles"].sum()
margen_total = ventas_filtradas["margen_soles"].sum()
unidades_total = ventas_filtradas["unidades_vendidas"].sum()
margen_pct = margen_total / ventas_total if ventas_total > 0 else 0
capital_inmovilizado = resumen["capital_inmovilizado"].sum()
inversion_recomendada = resumen["inversion_sugerida_compra"].sum()

quiebre = (resumen["estado_inventario"] == "Riesgo de quiebre").sum()
reponer = (resumen["estado_inventario"] == "Reponer pronto").sum()
sobrestock = resumen["estado_inventario"].isin(["Sobrestock crítico", "Sobrestock moderado"]).sum()
muertos = (resumen["estado_inventario"] == "Producto muerto").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ventas", f"S/ {ventas_total:,.0f}")
col2.metric("Margen", f"S/ {margen_total:,.0f}")
col3.metric("Margen %", f"{margen_pct:.1%}")
col4.metric("Capital en inventario", f"S/ {capital_inmovilizado:,.0f}")

col5, col6, col7, col8 = st.columns(4)
col5.metric("SKU en quiebre", int(quiebre))
col6.metric("SKU por reponer", int(reponer))
col7.metric("SKU con sobrestock", int(sobrestock))
col8.metric("Productos muertos", int(muertos))

st.divider()

# =====================================================
# ALERTAS EJECUTIVAS
# =====================================================

st.subheader("🚨 Alertas gerenciales")

alertas = []
if quiebre > 0:
    alertas.append(f"Hay {quiebre} productos con riesgo de quiebre de stock.")
if sobrestock > 0:
    alertas.append(f"Hay {sobrestock} productos con sobrestock que podrían requerir promoción o liquidación.")
if muertos > 0:
    alertas.append(f"Hay {muertos} productos muertos sin ventas recientes.")
if inversion_recomendada > 0:
    alertas.append(f"La inversión sugerida de compra es aproximadamente S/ {inversion_recomendada:,.0f}.")

if alertas:
    for alerta in alertas:
        st.warning(alerta)
else:
    st.success("No se detectan alertas críticas con los filtros actuales.")

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Resumen ejecutivo",
    "Ventas",
    "Inventario",
    "Forecast y compras",
    "Rentabilidad",
    "Exportar"
])

with tab1:
    st.subheader("Resumen ejecutivo por categoría")

    resumen_cat = resumen.groupby("categoria", as_index=False).agg(
        skus=("sku", "count"),
        ventas=("ventas_total", "sum"),
        margen=("margen_total", "sum"),
        capital_inventario=("capital_inmovilizado", "sum"),
        compra_sugerida=("inversion_sugerida_compra", "sum"),
    )
    resumen_cat["margen_pct"] = np.where(resumen_cat["ventas"] > 0, resumen_cat["margen"] / resumen_cat["ventas"], 0)

    st.dataframe(resumen_cat, use_container_width=True)

    col_a, col_b = st.columns(2)
    fig1 = px.bar(resumen_cat, x="categoria", y="ventas", title="Ventas por categoría")
    col_a.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(resumen_cat, x="categoria", y="capital_inventario", title="Capital inmovilizado por categoría")
    col_b.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("Evolución de ventas")

    ventas_diarias = ventas_filtradas.groupby("fecha", as_index=False).agg(
        venta_soles=("venta_soles", "sum"),
        unidades=("unidades_vendidas", "sum")
    )

    fig = px.line(ventas_diarias, x="fecha", y="venta_soles", title="Ventas por fecha")
    st.plotly_chart(fig, use_container_width=True)

    top_productos = resumen.sort_values("ventas_total", ascending=False).head(20)
    fig_top = px.bar(top_productos, x="ventas_total", y="producto", orientation="h", title="Top 20 productos por ventas")
    st.plotly_chart(fig_top, use_container_width=True)

with tab3:
    st.subheader("Estado de inventario")

    estado = resumen.groupby("estado_inventario", as_index=False).agg(skus=("sku", "count"))
    fig_estado = px.bar(estado, x="estado_inventario", y="skus", title="SKU por estado de inventario")
    st.plotly_chart(fig_estado, use_container_width=True)

    st.markdown("### Productos críticos")
    criticos = resumen[resumen["estado_inventario"] != "Saludable"].copy()
    st.dataframe(
        criticos[[
            "sku", "producto", "categoria", "proveedor", "stock_actual", "stock_minimo",
            "demanda_30d", "demanda_predicha_30d", "dias_cobertura", "capital_inmovilizado",
            "estado_inventario", "accion_recomendada"
        ]],
        use_container_width=True
    )

with tab4:
    st.subheader("Forecast de demanda y recomendación de compra")

    comprar = resumen[resumen["accion_recomendada"] == "Comprar / reponer"].copy()
    comprar = comprar.sort_values("score_prioridad_compra", ascending=False)

    st.metric("Inversión sugerida total", f"S/ {comprar['inversion_sugerida_compra'].sum():,.0f}")

    st.dataframe(
        comprar[[
            "estado", "sku", "producto", "categoria", "proveedor", "stock_actual", "stock_minimo",
            "dias_para_quiebre", "dias_entrega", "demanda_30d", "demanda_predicha_30d", "punto_reorden",
            "cantidad_sugerida_compra", "inversion_sugerida_compra", "score_prioridad_compra"
        ]],
        use_container_width=True
    )

    top_forecast = resumen.sort_values("demanda_predicha_30d", ascending=False).head(20)
    fig_forecast = px.bar(
        top_forecast,
        x="demanda_predicha_30d",
        y="producto",
        orientation="h",
        title=f"Top 20 productos con mayor demanda predicha a {dias_prediccion} días"
    )
    st.plotly_chart(fig_forecast, use_container_width=True)

with tab5:
    st.subheader("Rentabilidad")

    col_a, col_b = st.columns(2)

    top_margen = resumen.sort_values("margen_total", ascending=False).head(20)
    fig_margen = px.bar(top_margen, x="margen_total", y="producto", orientation="h", title="Top productos por margen")
    col_a.plotly_chart(fig_margen, use_container_width=True)

    fig_matriz = px.scatter(
        resumen,
        x="demanda_30d",
        y="margen_pct",
        size="ventas_total",
        color="estado_inventario",
        hover_data=["sku", "producto", "categoria", "proveedor", "stock_actual", "capital_inmovilizado"],
        title="Matriz: demanda vs margen"
    )
    col_b.plotly_chart(fig_matriz, use_container_width=True)

    st.markdown("### Productos con alto capital inmovilizado")
    alto_capital = resumen.sort_values("capital_inmovilizado", ascending=False).head(30)
    st.dataframe(
        alto_capital[[
            "sku", "producto", "categoria", "proveedor", "stock_actual", "costo_promedio",
            "capital_inmovilizado", "demanda_90d", "dias_cobertura", "estado_inventario", "accion_recomendada"
        ]],
        use_container_width=True
    )

with tab6:
    st.subheader("Exportar información para gerencia y compras")

    st.markdown("Descarga un Excel con tres hojas: resumen general, productos para comprar y productos para liquidar.")

    archivo_excel = exportar_excel(resumen)
    st.download_button(
        "📥 Descargar reporte ejecutivo en Excel",
        data=archivo_excel,
        file_name="reporte_importadora_bi.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("### Base completa procesada")
    st.dataframe(resumen, use_container_width=True)

st.caption("Importadora BI Pro - MVP comercial para validar con empresas importadoras.")
