"""
Cálculo de costo de envío para Gflex3D.

Sin API key  → usa tarifas planas reales por región (Chilexpress referencial).
Con API key  → consulta la API real de Chilexpress para precio exacto.

Para activar la API real agrega en tu .env:
    CHILEXPRESS_API_KEY=tu_clave_aqui

Obtén tu clave en: https://developers.chilexpress.cl
"""
import requests
from decimal import Decimal
from django.conf import settings


# Tarifas planas referenciales por región (CLP, paquete ~1 kg)
_TARIFAS = {
    'Metropolitana de Santiago': {'costo': 3990,  'dias': 1},
    'Valparaíso':                {'costo': 4490,  'dias': 2},
    "O'Higgins":                 {'costo': 4490,  'dias': 2},
    'Maule':                     {'costo': 4490,  'dias': 2},
    'Ñuble':                     {'costo': 4990,  'dias': 3},
    'Biobío':                    {'costo': 4990,  'dias': 3},
    'La Araucanía':              {'costo': 5490,  'dias': 3},
    'Los Ríos':                  {'costo': 5490,  'dias': 4},
    'Los Lagos':                 {'costo': 5490,  'dias': 4},
    'Coquimbo':                  {'costo': 5490,  'dias': 3},
    'Atacama':                   {'costo': 6490,  'dias': 4},
    'Antofagasta':               {'costo': 6490,  'dias': 4},
    'Tarapacá':                  {'costo': 6990,  'dias': 5},
    'Arica y Parinacota':        {'costo': 6990,  'dias': 5},
    'Aysén':                     {'costo': 7990,  'dias': 7},
    'Magallanes':                {'costo': 7990,  'dias': 7},
}
_DEFAULT = {'costo': 6990, 'dias': 5}

# Códigos de región para la API de Chilexpress
_CODIGOS_REGION = {
    'Metropolitana de Santiago': '13', 'Valparaíso': '05',
    "O'Higgins": '06', 'Maule': '07', 'Ñuble': '16',
    'Biobío': '08', 'La Araucanía': '09', 'Los Ríos': '14',
    'Los Lagos': '10', 'Coquimbo': '04', 'Atacama': '03',
    'Antofagasta': '02', 'Tarapacá': '01',
    'Arica y Parinacota': '15', 'Aysén': '11', 'Magallanes': '12',
}


def calcular_envio(region: str, peso_kg: float = 1.0) -> dict:
    """
    Devuelve {'costo': Decimal, 'dias': int, 'carrier': str}
    """
    api_key = getattr(settings, 'CHILEXPRESS_API_KEY', '')
    if api_key:
        resultado = _chilexpress_api(region, peso_kg, api_key)
        if resultado:
            return resultado

    tarifa = _TARIFAS.get(region, _DEFAULT)
    return {
        'costo':   Decimal(str(tarifa['costo'])),
        'dias':    tarifa['dias'],
        'carrier': 'Chilexpress',
    }


def _chilexpress_api(region: str, peso_kg: float, api_key: str) -> dict | None:
    """Consulta la API v2 de Chilexpress. Retorna None si falla."""
    codigo = _CODIGOS_REGION.get(region)
    if not codigo:
        return None

    BASE    = 'https://services.wschilexpress.com'
    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Content-Type': 'application/json',
    }

    try:
        # 1. Obtener código de comuna de la región
        r = requests.get(
            f'{BASE}/georeference/api/v1.0/coverage-areas',
            params={'RegionCode': codigo},
            headers=headers, timeout=5,
        )
        if r.status_code != 200:
            return None
        areas = r.json().get('data', {}).get('coverageAreas', [])
        if not areas:
            return None
        county_code = areas[0].get('countyCode', '')

        # 2. Cotizar envío
        r2 = requests.post(
            f'{BASE}/rating/api/v1.0/rates/courier',
            headers=headers,
            json={
                'originCountyCode':      'STGO',
                'destinationCountyCode': county_code,
                'package': {
                    'weight': max(1, int(peso_kg)),
                    'height': 10, 'width': 10, 'length': 10,
                },
                'productType':  3,
                'contentType':  1,
                'declaredWorth': '5000',
                'deliveryTime':  0,
            },
            timeout=5,
        )
        if r2.status_code != 200:
            return None
        opciones = r2.json().get('data', {}).get('courierServiceOptions', [])
        if not opciones:
            return None
        opcion = opciones[0]
        return {
            'costo':   Decimal(str(opcion.get('serviceValue', 5990))),
            'dias':    opcion.get('transit', 3),
            'carrier': 'Chilexpress',
        }
    except Exception:
        return None
