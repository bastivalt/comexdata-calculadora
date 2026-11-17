"""ComexData Analytics · calculadora de referencia de costos y plazos de importación (prototipo)."""
import os

import pandas as pd
import streamlit as st

from motor import (BANDAS, FACTOR_ALERTA, MUESTRA_OK, NIVELES_FLETE, VIAS, Referencias, banda_de, cotizar,
                   limpiar_codigo)

AQUI = os.path.dirname(os.path.abspath(__file__))
st.set_page_config(page_title='ComexData Analytics', page_icon='📦', layout='wide')

st.markdown("""
<style>
.block-container {padding-top: 1.6rem; max-width: 1180px;}
.cx-ribbon {background: rgba(255,193,7,.16); border: 1px solid rgba(255,193,7,.55); border-radius: 8px;
            padding: .5rem .8rem; font-size: .88rem; margin-bottom: 1rem;}
.cx-card {border: 1px solid rgba(128,128,128,.35); border-radius: 10px; padding: .9rem 1rem; height: 100%;}
.cx-card h4 {margin: 0 0 .25rem 0; font-size: .85rem; font-weight: 600; opacity: .75; text-transform: uppercase; letter-spacing: .03em;}
.cx-big {font-size: 1.55rem; font-weight: 700; line-height: 1.2;}
.cx-sub {font-size: .82rem; opacity: .75; margin-top: .25rem;}
.cx-alert {border-radius: 8px; padding: .7rem .9rem; margin: .6rem 0 1rem 0; border-left: 5px solid;}
.cx-alert.alta {background: rgba(220,53,69,.14); border-color: #dc3545;}
.cx-alert.sobre {background: rgba(255,153,0,.15); border-color: #ff9900;}
.cx-alert.ok {background: rgba(40,167,69,.14); border-color: #28a745;}
.cx-alert.bajo, .cx-alert.muy_bajo {background: rgba(47,111,219,.14); border-color: #2f6fdb;}
.cx-badge {display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .78rem; font-weight: 600; border: 1px solid;}
.cx-badge.Alta {background: rgba(40,167,69,.18); border-color: #28a745;}
.cx-badge.Media {background: rgba(255,193,7,.2); border-color: #e0a800;}
.cx-badge.Baja {background: rgba(220,53,69,.16); border-color: #dc3545;}
.cx-bar {position: relative; height: 104px; margin: .4rem 0 1.2rem 0;}
.cx-track {position: absolute; top: 34px; left: 0; right: 0; height: 14px; background: rgba(128,128,128,.12); border-radius: 7px;}
.cx-p1090 {position: absolute; top: 34px; height: 14px; background: rgba(47,111,219,.25); border-radius: 7px;}
.cx-p2575 {position: absolute; top: 34px; height: 14px; background: rgba(47,111,219,.65); border-radius: 7px;}
.cx-med {position: absolute; top: 29px; width: 3px; height: 24px; background: currentColor; border-radius: 2px;}
.cx-quote {position: absolute; top: 12px; width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 14px solid;}
.cx-lbl {position: absolute; font-size: .72rem; opacity: .8; transform: translateX(-50%); white-space: nowrap;}
.cx-qlbl {position: absolute; top: -6px; font-size: .74rem; font-weight: 600; transform: translateX(-50%); white-space: nowrap;}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ utilidades
def n(x, d=0):
    """Formato chileno: miles con punto, decimales con coma."""
    s = f'{x:,.{d}f}'
    return s.replace(',', '#').replace('.', ',').replace('#', '.')


def usd(x, d=2):
    return f'USD {n(x, d)}'


@st.cache_resource
def cargar():
    ref = Referencias(os.path.join(AQUI, 'referencias'))
    p = os.path.join(AQUI, 'paises.csv')
    paises = dict(pd.read_csv(p, dtype=str).values) if os.path.exists(p) else {}
    return ref, paises


try:
    REF, PAISES = cargar()
except Exception as e:  # noqa: BLE001
    st.error(f'No pude cargar las tablas de referencia de la carpeta "referencias": {e}')
    st.stop()


def nombre_origen(cod):
    return f'{PAISES.get(cod, "Código " + cod)} ({cod})'


def barra_rango(f, cotizacion=None, color_cot='#dc3545'):
    """Barra HTML con el rango p10-p90, p25-p75, la mediana y, si hay, la cotización."""
    p10, p25, p50, p75, p90 = (f['p10'], f['p25'], f['p50'], f['p75'], f['p90'])
    tope = max(p90, cotizacion or 0) * 1.12
    pos = lambda v: max(0.0, min(100.0, v / tope * 100))  # noqa: E731
    html = ['<div class="cx-bar">',
            '<div class="cx-track"></div>',
            f'<div class="cx-p1090" style="left:{pos(p10):.1f}%;width:{pos(p90) - pos(p10):.1f}%"></div>',
            f'<div class="cx-p2575" style="left:{pos(p25):.1f}%;width:{pos(p75) - pos(p25):.1f}%"></div>',
            f'<div class="cx-med" style="left:{pos(p50):.1f}%"></div>']
    for v, t, fila in [(p10, 'p10', 0), (p25, 'p25', 1), (p50, 'mediana', 0), (p75, 'p75', 1), (p90, 'p90', 0)]:
        top = 54 + fila * 24
        html.append(f'<div class="cx-lbl" style="left:{pos(v):.1f}%;top:{top}px">{t} {n(v)}</div>')
    if cotizacion:
        html.append(f'<div class="cx-quote" style="left:calc({pos(cotizacion):.1f}% - 8px);border-top-color:{color_cot}"></div>')
        html.append(f'<div class="cx-qlbl" style="left:{pos(cotizacion):.1f}%;color:{color_cot}">tu cotización {n(cotizacion)}</div>')
    html.append('</div>')
    return ''.join(html)


def ficha_texto(r):
    e = r['entrada']
    L = ['COMEXDATA ANALYTICS · Ficha de referencia (orientativa)',
         f'Datos de Aduanas {r["datos_desde"]} a {r["datos_hasta"]}', '',
         f'Producto: {e["codigo"]} | Origen: {nombre_origen(e["origen"])} | Vía: {VIAS[e["via"]]}',
         f'FOB: {usd(e["fob"])} | Peso: {n(e["peso_kg"])} kg', '']
    if r['flete']:
        f = r['flete']['usd']
        L.append(f'Flete de referencia (p25-p75): {usd(f["p25"], 0)} a {usd(f["p75"], 0)} | mediana {usd(f["p50"], 0)} '
                 f'| nivel: {r["flete"]["nivel_texto"]} (n={r["flete"]["n"]})')
    if r['alerta']:
        L.append(f'Cotización ingresada: {usd(e["cotizacion_flete"], 0)} → {r["alerta"][1]}')
    L.append('')
    L.append('Costo hasta pagar a Aduanas (arancel + IVA):')
    for nom, fila in r['totales'].items():
        txt = f'  Flete {nom} ({usd(fila["flete"], 0)}), CIF {usd(fila["cif"], 0)}'
        for k, lab in [('general', 'sin preferencia'), ('preferencial', 'con preferencia')]:
            if k in fila:
                txt += f' | {lab}: {usd(fila[k]["total"], 0)}'
        L.append(txt)
    if r['plazo']:
        d = r['plazo']['dias']
        L.append(f'Plazo (conocimiento de embarque a aceptación de la declaración): {n(d["p25"])} a {n(d["p75"])} días, mediana {n(d["p50"])}')
    L.append(f'Confianza de la ficha: {r["confianza"]}')
    for a in r['avisos']:
        L.append(f'Aviso: {a}')
    L += ['', 'No incluye: honorarios de agente, cargos de puerto/terminal, almacenaje, transporte nacional, comisiones bancarias.',
          'Es una referencia basada en declaraciones pasadas, no una cotización ni asesoría aduanera.']
    return '\n'.join(L)


# ------------------------------------------------------------------ encabezado
st.title('📦 ComexData Analytics')
st.caption('Referencia de costos y plazos de importación a Chile, calculada con declaraciones reales de Aduanas')
st.markdown(f'<div class="cx-ribbon"><b>Prototipo.</b> Datos de Aduanas (DIN) de {REF.meta["periodo_desde"][:4]}-{REF.meta["periodo_desde"][4:]} '
            f'a {REF.meta["periodo_hasta"][:4]}-{REF.meta["periodo_hasta"][4:]}. Es una referencia orientativa basada en declaraciones pasadas, '
            f'no una cotización ni asesoría aduanera.</div>', unsafe_allow_html=True)

tab_calc, tab_met = st.tabs(['Calculadora', 'Metodología y límites'])

# ------------------------------------------------------------------ calculadora
with tab_calc:
    codigos_origen = list(REF.origenes_frecuentes.index)
    idx_china = codigos_origen.index('336') if '336' in codigos_origen else 0
    with st.form('consulta'):
        c1, c2, c3 = st.columns([1.1, 1.1, 1])
        codigo = c1.text_input('Código arancelario del producto', value='85183000',
                               help='8 dígitos (por ejemplo 85183000 o 8518.30.00). Si solo conoces 6 dígitos, también sirve.')
        origen = c2.selectbox('País de origen', codigos_origen, index=idx_china, format_func=nombre_origen,
                              help='Los países se ordenan por número de declaraciones.')
        via = c3.selectbox('Vía de transporte', list(VIAS), format_func=lambda v: VIAS[v])
        c4, c5, c6 = st.columns(3)
        fob = c4.number_input('Valor FOB (USD)', min_value=0.0, value=10000.0, step=100.0,
                              help='Precio de la mercancía puesta a bordo en el origen, sin flete ni seguro.')
        peso = c5.number_input('Peso total (kg)', min_value=0.0, value=1200.0, step=10.0)
        cotiz = c6.number_input('Cotización de flete (USD, opcional)', min_value=0.0, value=0.0, step=50.0,
                                help='Si ya tienes una cotización de flete internacional, ingrésala (0 = sin cotización).')
        enviar = st.form_submit_button('Calcular referencia', type='primary')

    if enviar:
        try:
            st.session_state['r'] = cotizar(REF, codigo, origen, via, fob, peso, cotiz if cotiz > 0 else None)
            st.session_state['err'] = None
        except ValueError as e:
            st.session_state['err'] = str(e)
            st.session_state['r'] = None

    if st.session_state.get('err'):
        st.warning(st.session_state['err'])

    r = st.session_state.get('r')
    if r:
        e = r['entrada']
        fl = r['flete']
        st.subheader(f'Ficha de referencia · {e["codigo"]} · {nombre_origen(e["origen"])} · {VIAS[e["via"]]}')
        st.markdown(f'Confianza de la ficha: <span class="cx-badge {r["confianza"]}">{r["confianza"]}</span>', unsafe_allow_html=True)

        # --- resumen
        clave = 'cotizacion' if e['cotizacion_flete'] else 'típico (p50)'
        fila_t = r['totales'].get(clave)
        k1, k2, k3 = st.columns(3)
        with k1:
            if fila_t:
                gen, pre = fila_t.get('general'), fila_t.get('preferencial')
                cuerpo = ''
                if gen:
                    cuerpo += f'<div class="cx-big">{usd(gen["total"], 0)}</div><div class="cx-sub">sin preferencia (arancel {n(gen["tasa_pct"], 1)}%)</div>'
                if pre:
                    cuerpo += f'<div class="cx-big" style="margin-top:.5rem">{usd(pre["total"], 0)}</div><div class="cx-sub">con preferencia (arancel {n(pre["tasa_pct"], 1)}%)</div>'
                if not cuerpo:
                    cuerpo = '<div class="cx-sub">Sin datos de arancel para este código.</div>'
                titulo = 'Total a pagar a Aduanas' + (' (con tu cotización)' if e['cotizacion_flete'] else ' (flete típico)')
                st.markdown(f'<div class="cx-card"><h4>{titulo}</h4>{cuerpo}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="cx-card"><h4>Total a pagar a Aduanas</h4><div class="cx-sub">Ingresa una cotización de flete para calcularlo: no hay referencia de flete.</div></div>', unsafe_allow_html=True)
        with k2:
            if fl:
                f = fl['usd']
                st.markdown(f'<div class="cx-card"><h4>Flete de referencia</h4><div class="cx-big">{n(f["p25"])} – {n(f["p75"])} USD</div>'
                            f'<div class="cx-sub">rango habitual (p25–p75) · mediana {n(f["p50"])} · {n(fl["usd"]["p25"] / e["peso_kg"], 2)}–{n(fl["usd"]["p75"] / e["peso_kg"], 2)} USD/kg</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="cx-card"><h4>Flete de referencia</h4><div class="cx-sub">Sin referencia para esta vía y peso.</div></div>', unsafe_allow_html=True)
        with k3:
            pz = r['plazo']
            if pz:
                d = pz['dias']
                st.markdown(f'<div class="cx-card"><h4>Plazo de referencia</h4><div class="cx-big">{n(d["p25"])} – {n(d["p75"])} días</div>'
                            f'<div class="cx-sub">mediana {n(d["p50"])} días · desde conocimiento de embarque hasta aceptación de la declaración</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="cx-card"><h4>Plazo de referencia</h4><div class="cx-sub">Sin datos de plazo.</div></div>', unsafe_allow_html=True)

        # --- alerta de cotización
        if r['alerta']:
            tipo, texto = r['alerta']
            titulo = {'alta': '⚠️ Cotización de flete alta', 'sobre': 'ℹ️ Cotización sobre lo habitual', 'ok': '✅ Cotización dentro de lo habitual',
                      'bajo': 'ℹ️ Cotización baja', 'muy_bajo': 'ℹ️ Cotización muy baja'}[tipo]
            st.markdown(f'<div class="cx-alert {tipo}"><b>{titulo}</b><br>{texto}<br><span style="font-size:.82rem;opacity:.8">'
                        f'Ojo: tu cotización puede incluir cargos que el flete declarado en Aduanas no incluye; compara siempre qué cubre cada una.</span></div>', unsafe_allow_html=True)

        # --- flete
        st.markdown('### Flete')
        if fl:
            color = {'alta': '#dc3545', 'sobre': '#ff9900', 'ok': '#28a745', 'bajo': '#2f6fdb', 'muy_bajo': '#2f6fdb'}.get(r['alerta'][0] if r['alerta'] else 'ok')
            st.markdown(barra_rango(fl['usd'], e['cotizacion_flete'], color), unsafe_allow_html=True)
            st.caption('Barra clara: rango p10–p90 (80% de los casos). Barra oscura: p25–p75 (mitad central). Línea: mediana. Valores en USD totales.')
            tabla = pd.DataFrame({
                'Percentil': ['p10', 'p25 (límite inferior habitual)', 'p50 (mediana)', 'p75 (límite superior habitual)', 'p90'],
                'USD totales': [n(fl['usd'][k]) for k in ['p10', 'p25', 'p50', 'p75', 'p90']],
                'USD por kg': [n(fl['usd_por_kg'][k], 2) for k in ['p10', 'p25', 'p50', 'p75', 'p90']],
                '% de tu FOB': [n(fl['usd'][k] / e['fob'] * 100, 1) + '%' for k in ['p10', 'p25', 'p50', 'p75', 'p90']]})
            st.dataframe(tabla, hide_index=True, width='stretch')
            baja = ' · ⚠️ muestra baja' if fl['muestra_baja'] else ''
            st.caption(f'Nivel de referencia usado: **{fl["nivel_texto"]}** · {n(fl["n"])} declaraciones · rango de peso {fl["banda"]} kg{baja}')
        else:
            st.info('No hay referencia de flete para esta vía y rango de peso.')

        # --- costo hasta Aduanas
        st.markdown('### Costo hasta pagar a Aduanas')
        if r['totales']:
            fila = fila_t or next(iter(r['totales'].values()))
            etiqueta = 'con tu cotización' if e['cotizacion_flete'] else 'con flete típico (p50)'
            filas = [('Valor FOB', e['fob'], e['fob']), ('Flete', fila['flete'], fila['flete']),
                     (f'Seguro (supuesto {n(r["seguro"]["pct_p50"], 2)}% del FOB)', r['seguro']['usd'], r['seguro']['usd']),
                     ('**CIF (base de impuestos)**', fila['cif'], fila['cif'])]
            gen, pre = fila.get('general'), fila.get('preferencial')
            filas.append((f'Arancel ({n(gen["tasa_pct"], 1) if gen else "–"}% / {n(pre["tasa_pct"], 1) if pre else "–"}%)',
                          gen['arancel'] if gen else None, pre['arancel'] if pre else None))
            filas.append(('IVA 19% sobre (CIF + arancel)', gen['iva'] if gen else None, pre['iva'] if pre else None))
            filas.append(('**Total a Aduanas (arancel + IVA)**', gen['total'] if gen else None, pre['total'] if pre else None))
            df = pd.DataFrame(filas, columns=['Concepto', 'Sin preferencia (USD)', 'Con preferencia (USD)'])
            for c in df.columns[1:]:
                df[c] = df[c].apply(lambda v: '–' if v is None else n(v, 2))
            df['Concepto'] = df['Concepto'].str.replace('**', '', regex=False)
            st.dataframe(df, hide_index=True, width='stretch')
            st.caption(f'Cálculo {etiqueta}. Fórmula: CIF = FOB + flete + seguro; arancel = tasa × CIF; IVA = 19% × (CIF + arancel).')
            if not e['cotizacion_flete'] and len(r['totales']) == 3:
                b, a = r['totales']['bajo (p25)'], r['totales']['alto (p75)']
                partes = []
                for k, lab in [('general', 'sin preferencia'), ('preferencial', 'con preferencia')]:
                    if k in b:
                        partes.append(f'{lab}: {usd(b[k]["total"], 0)} a {usd(a[k]["total"], 0)}')
                st.caption('Rango del total según el flete (p25 a p75): ' + ' · '.join(partes))
            av = r['arancel']
            for k, lab in [('general', 'Sin preferencia'), ('preferencial', 'Con preferencia')]:
                if k in av:
                    a = av[k]
                    extra = ' ⚠️ tasa poco concluyente' if a['pct_items_con_esa_tasa'] < 60 or a['n_items'] < MUESTRA_OK else ''
                    st.caption(f'{lab}: tasa {n(a["tasa_pct"], 1)}% (la más frecuente; en {n(a["pct_items_con_esa_tasa"], 0)}% de {n(a["n_items"])} ítems, nivel {a["nivel"]}){extra}')
            if 'preferencial' in av:
                st.caption('Para usar la tasa preferencial hay que cumplir las reglas de origen del acuerdo y presentar el certificado correspondiente.')
        else:
            st.info('Sin datos para calcular el costo. Ingresa una cotización de flete y un código con arancel conocido.')

        # --- plazo y mercado
        cA, cB = st.columns(2)
        with cA:
            st.markdown('### Plazo')
            if r['plazo']:
                d = r['plazo']['dias']
                st.write(f'Rango habitual (p25–p75): **{n(d["p25"])} a {n(d["p75"])} días** · mediana {n(d["p50"])} · '
                         f'p10–p90: {n(d["p10"])} a {n(d["p90"])} días')
                st.caption(f'Nivel: {r["plazo"]["nivel"]} · {n(r["plazo"]["n"])} declaraciones. Mide desde la fecha del conocimiento de embarque '
                           f'hasta la aceptación de la declaración; no incluye despacho ni entrega en tu bodega.')
        with cB:
            st.markdown('### Contexto de mercado')
            mk = r['mercado']
            if mk:
                st.write(f'**{n(mk["declaraciones"])}** declaraciones de este producto desde este origen en el período, '
                         f'hechas por **{n(mk["importadores"])}** importadores.')
                st.write(f'**{n(mk["pct_preferencial"], 0)}%** de ellas usó una preferencia arancelaria.')
            else:
                st.caption('Sin información de mercado para este código y origen (se necesitan 8 dígitos y al menos 3 declaraciones).')

        # --- avisos
        if r['avisos']:
            st.markdown('### Avisos')
            for a in r['avisos']:
                st.warning(a)

        st.download_button('Descargar ficha (texto)', ficha_texto(r), file_name=f'ficha_{e["codigo"]}_{e["origen"]}.txt')

# ------------------------------------------------------------------ metodología
with tab_met:
    st.markdown(f"""
### Qué es esto
Una **referencia** de lo que han pagado y demorado otros importadores en situaciones parecidas, calculada con las declaraciones de importación
publicadas por el Servicio Nacional de Aduanas ({REF.meta['periodo_desde'][:4]}-{REF.meta['periodo_desde'][4:]} a {REF.meta['periodo_hasta'][:4]}-{REF.meta['periodo_hasta'][4:]},
{n(REF.meta['declaraciones_flete'])} declaraciones con flete en USD). No es una cotización, no reemplaza a tu agente de aduanas ni a un forwarder.

### Cómo se calcula el costo hasta Aduanas
1. **CIF** = FOB + flete + seguro.
2. **Arancel** = tasa × CIF. Se muestran dos escenarios: *sin preferencia* (régimen general) y *con preferencia* (acuerdo comercial). La tasa es la más frecuente en las declaraciones históricas del mismo producto (y origen, si hay datos).
3. **IVA** = 19% × (CIF + arancel).
4. **Total a Aduanas** = arancel + IVA.

### Cómo se elige la referencia de flete
Se busca el nivel más específico que tenga al menos 10 declaraciones, y se avisa cuando son menos de {MUESTRA_OK}:
""")
    st.table(pd.DataFrame({'Nivel': [f'{k}. {v}' for k, v in NIVELES_FLETE.items()],
                           'Qué compara': ['Mismo producto (6 dígitos), mismo origen, misma vía y rango de peso', 'Mismo producto y vía, cualquier origen',
                                           'Mismo capítulo arancelario (2 dígitos) y vía', 'Solo vía y rango de peso'],
                           'Cuándo conviene': ['La más precisa', 'Precisión intermedia', 'Orden de magnitud', 'Último recurso']}))
    st.markdown("""
### Qué tan bien funciona (prueba con datos reales)
Se construyeron las referencias con 9 meses y se probaron en los 3 meses siguientes (declaraciones que el modelo no había visto):
- **Plazo:** la mitad central del rango (p25–p75) contuvo el 57% de los casos reales y el rango p10–p90 el 84%; error mediano de 4 días.
- **Arancel:** la tasa más frecuente acertó en 82% de los ítems con referencia de producto + origen, contra 62% de la alternativa "siempre 0%".
- **Flete:** solo cuando existe referencia de producto + origen (alrededor de 1 de cada 5 declaraciones) el rango es angosto (error mediano 28%).
  En el resto, el rango es amplio: sirve como orden de magnitud. La mitad central del rango contuvo cerca de 45–48% de los casos reales.
- **Alerta de cotización:** se activa cuando supera 1,2 veces el p90, algo que ocurre en cerca de 1 de cada 10 fletes reales.

### Límites que debes conocer
- **No incluye:** honorarios de agente de aduanas, cargos de puerto o terminal, almacenaje o sobreestadía, transporte nacional, comisiones bancarias.
- **El flete es el declarado en Aduanas**, no necesariamente el pagado. En compras CIF o CFR lo pagó el vendedor. La dispersión es grande incluso entre casos parecidos.
- **Seguro:** en muchas declaraciones aparece un valor fijo de 2% del FOB, que parece ser un valor por defecto. Aquí se usa el valor típico de la vía y puede subestimar ese caso.
- **Vía terrestre:** muchas declaraciones usan un flete de 5% del FOB como valor por defecto; la referencia de flete es poco confiable.
- **Solo dólares:** las referencias usan declaraciones en USD (cerca del 81% del total).
- **Plazo:** va del conocimiento de embarque a la aceptación de la declaración. No es el plazo hasta tener la mercancía en bodega.
- **Preferencia arancelaria:** exige cumplir reglas de origen y presentar certificado; aquí solo se muestra la tasa.
- **Productos con pocos datos:** el sistema baja de nivel y lo avisa. Si el código no existe en los datos, no se puede estimar el arancel.
- **Pasado ≠ futuro:** las referencias reflejan lo ocurrido; cambios de tarifas, tratados o rutas pueden alterarlas.
""")
