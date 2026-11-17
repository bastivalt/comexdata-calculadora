"""Motor de cálculo de ComexData Analytics.

Calcula una referencia (no una cotización oficial) de costos hasta pagar a Aduanas y de plazo, usando tablas
de referencia construidas con declaraciones de importación reales de Aduanas (datos abiertos, DIN).

Todo el cálculo es en dólares (USD). Los percentiles salen de declaraciones en USD.
"""
import json
import os
import re

import pandas as pd

IVA = 0.19
BANDAS = [(0, 10, '0-10'), (10, 50, '10-50'), (50, 200, '50-200'), (200, 1000, '200-1000'),
          (1000, 5000, '1000-5000'), (5000, float('inf'), '5000+')]
VIAS = {'1': 'Marítima', '4': 'Aérea', '11': 'Courier / aéreo express', '7': 'Terrestre (carretero)'}
NIVELES_FLETE = {1: 'Producto + origen', 2: 'Producto (cualquier origen)', 3: 'Capítulo arancelario', 4: 'Solo vía y rango de peso'}
MUESTRA_OK = 30          # bajo este número de declaraciones se avisa "muestra baja"
FACTOR_ALERTA = 1.2      # alerta fuerte cuando la cotización supera 1,2 veces el p90 de la referencia


def banda_de(peso_kg):
    for lo, hi, nombre in BANDAS:
        if lo < peso_kg <= hi:
            return nombre
    return None


def limpiar_codigo(texto):
    """Deja solo los dígitos del código arancelario (acepta puntos y espacios)."""
    return re.sub(r'\D', '', str(texto or ''))


class Referencias:
    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.meta = json.load(open(os.path.join(carpeta, 'ref_meta.json')))
        flete = pd.read_parquet(os.path.join(carpeta, 'ref_flete.parquet'))
        self.seguro = pd.read_parquet(os.path.join(carpeta, 'ref_seguro.parquet')).set_index('via')
        plazo = pd.read_parquet(os.path.join(carpeta, 'ref_plazo.parquet'))
        self.arancel = pd.read_parquet(os.path.join(carpeta, 'ref_arancel.parquet'))
        self.mercado = pd.read_parquet(os.path.join(carpeta, 'ref_mercado.parquet'))
        for df in (flete, plazo, self.arancel, self.mercado):
            for c in df.columns:
                if str(df[c].dtype) in ('string', 'str') or df[c].dtype == object:
                    df[c] = df[c].astype(str)
        # índices de búsqueda rápida
        self._f = {}
        for r in flete.to_dict('records'):
            nv = int(r['nivel'])
            if nv == 1:
                k = (1, r['via'], r['prod6'], r['origen'], r['banda'])
            elif nv == 2:
                k = (2, r['via'], r['prod6'], r['banda'])
            elif nv == 3:
                k = (3, r['via'], r['capitulo'], r['banda'])
            else:
                k = (4, r['via'], r['banda'])
            self._f[k] = r
        self._p = {}
        for r in plazo.to_dict('records'):
            self._p[(r['via'], r['origen'])] = r
        self._a = {}
        for r in self.arancel.to_dict('records'):
            self._a[(r['escenario'], r['prod8'], r['origen'])] = r
        self._m = {(r['prod8'], r['origen']): r for r in self.mercado.to_dict('records')}
        self.origenes_frecuentes = (self.mercado.groupby('origen')['n_declaraciones'].sum()
                                    .sort_values(ascending=False))

    # ------------------------------------------------------------------ búsquedas
    def _buscar_flete(self, via, prod6, origen, banda, capitulo):
        for k in [(1, via, prod6, origen, banda), (2, via, prod6, banda), (3, via, capitulo, banda), (4, via, banda)]:
            if k in self._f:
                return self._f[k]
        return None

    def _buscar_plazo(self, via, origen):
        return self._p.get((via, origen)) or self._p.get((via, '*'))

    def _tasa(self, escenario, codigo, origen):
        """Devuelve (fila, nivel_texto). Con 8 dígitos usa producto+origen y luego producto; con 6 busca por prefijo."""
        if len(codigo) == 8:
            r = self._a.get((escenario, codigo, origen))
            if r is not None:
                return r, 'producto + origen'
            r = self._a.get((escenario, codigo, '*'))
            if r is not None:
                return r, 'producto (cualquier origen)'
            return None, None
        # prefijo (6 dígitos o menos): tasa más frecuente entre los productos que empiezan con ese prefijo
        sub = self.arancel[(self.arancel['escenario'] == escenario) & (self.arancel['prod8'].str.startswith(codigo))]
        for nivel_txt, cond in [('producto + origen', sub['origen'] == origen), ('producto (cualquier origen)', sub['origen'] == '*')]:
            s = sub[cond]
            if len(s):
                g = s.groupby('tasa_pct')['n_items'].sum().sort_values(ascending=False)
                total = int(s['n_items'].sum())
                return {'tasa_pct': float(g.index[0]), 'n_items': total,
                        'pct_items_con_esa_tasa': round(float(g.iloc[0]) / total * 100, 1)}, nivel_txt + ' (por prefijo del código)'
        return None, None

    def _mercado(self, codigo, origen):
        if len(codigo) == 8:
            return self._m.get((codigo, origen))
        return None

    def codigo_conocido(self, codigo):
        return bool(self.mercado['prod8'].str.startswith(codigo).any())


# ---------------------------------------------------------------------- cálculo principal
def _confianza(nivel, n):
    if nivel == 1 and n >= MUESTRA_OK:
        return 'Alta'
    if (nivel == 1) or (nivel == 2 and n >= MUESTRA_OK):
        return 'Media'
    return 'Baja'


def _costos(cif, tasa_pct):
    arancel = cif * tasa_pct / 100
    iva = (cif + arancel) * IVA
    return {'tasa_pct': tasa_pct, 'arancel': arancel, 'iva': iva, 'total': arancel + iva}


def evaluar_cotizacion(cotiz, ref_p10, ref_p25, ref_p75, ref_p90):
    """Compara una cotización de flete (USD totales) con el rango de referencia (USD totales)."""
    if cotiz > ref_p90 * FACTOR_ALERTA:
        return ('alta', f'Muy por encima de lo habitual: es {cotiz / ref_p75:.1f} veces el límite superior del rango habitual. '
                        f'Solo cerca de 1 de cada 10 fletes reales supera el {int((FACTOR_ALERTA - 1) * 100)}% sobre el p90.')
    if cotiz > ref_p75:
        return ('sobre', f'Sobre el rango habitual (p25–p75), pero dentro de lo observado: es {cotiz / ref_p75:.1f} veces el límite superior.')
    if cotiz >= ref_p25:
        return ('ok', 'Dentro del rango habitual (p25–p75).')
    if cotiz >= ref_p10:
        return ('bajo', 'Bajo el rango habitual, pero dentro de lo observado. Conviene confirmar qué incluye.')
    return ('muy_bajo', 'Muy por debajo de lo observado. Verifica qué incluye la cotización (puede no incluir todos los cargos).')


def cotizar(ref, codigo, origen, via, fob, peso_kg, cotizacion_flete=None):
    """Devuelve un diccionario con la ficha completa. Lanza ValueError si faltan datos mínimos."""
    codigo = limpiar_codigo(codigo)
    if len(codigo) < 4 or len(codigo) > 8:
        raise ValueError('El código arancelario debe tener entre 4 y 8 dígitos (idealmente 8, por ejemplo 85183000).')
    if via not in VIAS:
        raise ValueError('Vía de transporte no soportada.')
    if fob is None or fob <= 0:
        raise ValueError('Ingresa un valor FOB mayor que cero.')
    if peso_kg is None or peso_kg <= 0:
        raise ValueError('Ingresa un peso mayor que cero.')
    banda = banda_de(peso_kg)
    prod6 = codigo[:6] if len(codigo) >= 6 else None
    capitulo = codigo[:2]
    avisos = []
    out = {'entrada': {'codigo': codigo, 'origen': origen, 'via': via, 'fob': fob, 'peso_kg': peso_kg,
                       'cotizacion_flete': cotizacion_flete},
           'avisos': avisos, 'datos_hasta': ref.meta['periodo_hasta'], 'datos_desde': ref.meta['periodo_desde']}

    # ---- flete
    fl = ref._buscar_flete(via, prod6 or '', origen, banda, capitulo)
    if len(codigo) < 6:
        avisos.append('Con menos de 6 dígitos solo se usa la referencia por capítulo. Para una referencia más precisa ingresa el código completo de 8 dígitos.')
    if fl is not None:
        nivel = int(fl['nivel'])
        out['flete'] = {
            'nivel': nivel, 'nivel_texto': NIVELES_FLETE[nivel], 'n': int(fl['n']), 'banda': banda,
            'usd': {k: float(fl[f'kg_{k}']) * peso_kg for k in ['p10', 'p25', 'p50', 'p75', 'p90']},
            'usd_por_kg': {k: float(fl[f'kg_{k}']) for k in ['p10', 'p25', 'p50', 'p75', 'p90']},
            'pct_fob': {k: float(fl[f'pct_{k}']) for k in ['p10', 'p25', 'p50', 'p75', 'p90']},
            'muestra_baja': int(fl['n']) < MUESTRA_OK}
        if via == '7':
            avisos.append('Vía terrestre: en esta vía muchas declaraciones usan un flete de 5% del FOB como valor por defecto, '
                          'por eso la referencia de flete es poco confiable. Úsala solo como orden de magnitud.')
    else:
        out['flete'] = None
        avisos.append('No hay referencia de flete para esta vía y rango de peso.')

    # ---- seguro (supuesto)
    if via in ref.seguro.index:
        s = ref.seguro.loc[via]
        seg_pct = float(s['pct_p50'])
        out['seguro'] = {'pct_p50': seg_pct, 'pct_p25': float(s['pct_p25']), 'pct_p75': float(s['pct_p75']), 'usd': fob * seg_pct / 100}
    else:
        out['seguro'] = {'pct_p50': 0.0, 'pct_p25': 0.0, 'pct_p75': 0.0, 'usd': 0.0}

    # ---- flete usado para el CIF
    if cotizacion_flete is not None and cotizacion_flete > 0:
        escenarios_flete = {'cotizacion': float(cotizacion_flete)}
    elif out['flete']:
        escenarios_flete = {'bajo (p25)': out['flete']['usd']['p25'], 'típico (p50)': out['flete']['usd']['p50'],
                            'alto (p75)': out['flete']['usd']['p75']}
    else:
        escenarios_flete = {}
    out['escenarios_flete'] = escenarios_flete

    # ---- arancel: dos escenarios
    out['arancel'] = {}
    for e in ['general', 'preferencial']:
        r, nivel_txt = ref._tasa(e, codigo, origen)
        if r is not None:
            out['arancel'][e] = {'tasa_pct': float(r['tasa_pct']), 'n_items': int(r['n_items']), 'nivel': nivel_txt,
                                 'pct_items_con_esa_tasa': float(r['pct_items_con_esa_tasa'])}
    if not out['arancel']:
        avisos.append('No hay declaraciones con ese código en los datos. No se pudo estimar el arancel: consulta la tasa en el arancel de Aduanas.')

    # ---- totales
    out['totales'] = {}
    for nombre_f, flete_usd in escenarios_flete.items():
        cif = fob + flete_usd + out['seguro']['usd']
        fila = {'cif': cif, 'flete': flete_usd}
        for e, a in out['arancel'].items():
            fila[e] = _costos(cif, a['tasa_pct'])
        out['totales'][nombre_f] = fila

    # ---- alerta de cotización
    out['alerta'] = None
    if cotizacion_flete and out['flete']:
        f = out['flete']['usd']
        out['alerta'] = evaluar_cotizacion(float(cotizacion_flete), f['p10'], f['p25'], f['p75'], f['p90'])
        out['alerta_relacion_p75'] = float(cotizacion_flete) / f['p75']

    # ---- plazo
    pz = ref._buscar_plazo(via, origen)
    if pz is not None:
        out['plazo'] = {'dias': {k: float(pz[f'dias_{k}']) for k in ['p10', 'p25', 'p50', 'p75', 'p90']}, 'n': int(pz['n']),
                        'nivel': 'vía + origen' if pz['origen'] != '*' else 'solo vía (sin datos suficientes del origen)',
                        'muestra_baja': int(pz['n']) < MUESTRA_OK}
    else:
        out['plazo'] = None

    # ---- mercado
    mk = ref._mercado(codigo, origen)
    out['mercado'] = ({'declaraciones': int(mk['n_declaraciones']), 'importadores': int(mk['n_importadores']),
                       'pct_preferencial': float(mk['pct_preferencial'])} if mk is not None else None)
    if mk is None and len(codigo) == 8 and out['arancel']:
        avisos.append('No hay declaraciones de ese producto desde ese origen en los datos. La referencia usa información de otros orígenes o del capítulo.')

    # ---- confianza
    if out['flete']:
        out['confianza'] = _confianza(out['flete']['nivel'], out['flete']['n'])
        if via == '7':
            out['confianza'] = 'Baja'
    else:
        out['confianza'] = 'Baja'
    return out
