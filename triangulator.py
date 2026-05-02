"""
triangulator.py — Cálculo do ponto ótimo de encontro entre membros de uma party.

Algoritmo principal: Mediana Geométrica (Weiszfeld)
  - minimiza a soma das distâncias de todos os membros ao ponto central
  - mais justo que centroide (não é puxado por outliers)
  - converge em ~30 iterações para 2-10 usuários

Fallback: Centroide (média simples) quando só há 1 ponto ou Weiszfeld não converge.
"""

import math


# ─── Distância ────────────────────────────────────────────────────────────────

EARTH_RADIUS_M = 6_371_000  # metros

def haversine(lat1, lng1, lat2, lng2):
    """Distância em metros entre dois pontos geográficos (fórmula de Haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ─── Centroide ────────────────────────────────────────────────────────────────

def centroid(pontos):
    """Média simples das coordenadas. Rápido, mas pode ser puxado por outliers."""
    n = len(pontos)
    return (
        sum(p[0] for p in pontos) / n,
        sum(p[1] for p in pontos) / n,
    )


# ─── Mediana Geométrica (Weiszfeld) ───────────────────────────────────────────

def geometric_median(pontos, pesos=None, max_iter=100, tol=1e-9):
    """
    Encontra o ponto que minimiza a soma ponderada das distâncias a todos os pontos.
    Algoritmo de Weiszfeld: iteração rápida, converge para 2-10 pontos em <30 passos.
    """
    n = len(pontos)

    if n == 1:
        return pontos[0]

    if pesos is None:
        pesos = [1.0] * n

    # Ponto inicial: centroide ponderado
    total_peso = sum(pesos)
    lat = sum(p[0] * w for p, w in zip(pontos, pesos)) / total_peso
    lng = sum(p[1] * w for p, w in zip(pontos, pesos)) / total_peso

    for _ in range(max_iter):
        dists = [haversine(lat, lng, p[0], p[1]) for p in pontos]

        # Se o ponto atual coincide com um dos pontos de entrada, pequeno deslocamento
        dists = [max(d, 1e-6) for d in dists]

        denom = sum(w / d for w, d in zip(pesos, dists))
        new_lat = sum(w * p[0] / d for w, p, d in zip(pesos, pontos, dists)) / denom
        new_lng = sum(w * p[1] / d for w, p, d in zip(pesos, pontos, dists)) / denom

        if haversine(lat, lng, new_lat, new_lng) < tol:
            break

        lat, lng = new_lat, new_lng

    return lat, lng


# ─── Função principal ─────────────────────────────────────────────────────────

def calcular_centro(membros, raio_metros=2000):
    """
    Recebe lista de membros com 'lat' e 'lng', retorna ponto ótimo de busca.

    Parâmetros:
        membros      — list de dicts com chaves 'lat' e 'lng'
        raio_metros  — raio de busca individual de cada usuário (default 2000m)

    Retorna dict com:
        centro_busca  — {'lat': float, 'lng': float}
        raio_final    — raio sugerido para busca na API (metros)
        dispersao_m   — distância máxima de qualquer membro ao centro (metros)
        algoritmo     — 'geometric_median' | 'centroid' | 'unico'

    Retorna None se nenhum membro tiver localização válida.
    """
    pontos = [
        (float(m["lat"]), float(m["lng"]))
        for m in membros
        if m.get("lat") is not None and m.get("lng") is not None
    ]

    if not pontos:
        return None

    if len(pontos) == 1:
        return {
            "centro_busca": {"lat": pontos[0][0], "lng": pontos[0][1]},
            "raio_final":   raio_metros,
            "dispersao_m":  0,
            "algoritmo":    "unico",
        }

    # Mediana geométrica como ponto principal
    try:
        lat_c, lng_c = geometric_median(pontos)
        algoritmo = "geometric_median"
    except Exception:
        lat_c, lng_c = centroid(pontos)
        algoritmo = "centroid"

    # Dispersão: distância máxima do centro a qualquer membro
    dispersao = max(haversine(lat_c, lng_c, p[0], p[1]) for p in pontos)

    # Raio final cobre todos os membros + raio individual de busca, limitado a 15km
    raio_final = int(min(dispersao + raio_metros, 15_000))

    return {
        "centro_busca": {"lat": round(lat_c, 7), "lng": round(lng_c, 7)},
        "raio_final":   raio_final,
        "dispersao_m":  int(dispersao),
        "algoritmo":    algoritmo,
    }
