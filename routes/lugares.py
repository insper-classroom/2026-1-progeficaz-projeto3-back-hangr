from flask import Blueprint, request
from urllib.parse import quote as url_quote
import requests as http_requests
import os
from db import db
from triangulator import calcular_centro

bp = Blueprint('lugares', __name__)

GPS_THRESHOLD = 500  # accuracy ≤ 500m aceita WiFi desktop; IP puro fica acima de 1km

SLUG_QUERY = {
    "restaurantes": "restaurante",
    "bares":        "bar",
    "cafes":        "café",
    "jogos":        "arcade videogame",
    "parque":       "parque",
    "esportes":     "academia esporte",
}


@bp.route("/lugares", methods=["GET"])
def explorar_lugares():
    codigo = request.args.get("codigo", "").strip()
    slug   = request.args.get("slug",   "").strip()
    limit  = request.args.get("limit", "10")

    try:
        raio_usuario = int(request.args.get("raio", "2000"))
    except ValueError:
        raio_usuario = 2000

    if not codigo or not slug:
        return {"erro": "codigo e slug são obrigatórios"}, 400

    query = SLUG_QUERY.get(slug)
    if not query:
        return {"erro": "slug inválido"}, 400

    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404

    city = party.get("cidade", "")
    if not city:
        return {"erro": "Party sem cidade definida"}, 400

    api_key = os.getenv("FOURSQUARE_API_KEY")
    if not api_key:
        return {"erro": "Foursquare API key não configurada"}, 500

    # ── Localização do solicitante (enviada em tempo real pelo frontend) ──
    req_lat      = request.args.get("lat")
    req_lng      = request.args.get("lng")
    req_accuracy = request.args.get("accuracy")

    centro     = None
    raio_busca = raio_usuario
    modo_busca = "cidade"

    try:
        lat_f = float(req_lat) if req_lat else None
        lng_f = float(req_lng) if req_lng else None
        acc_f = float(req_accuracy) if req_accuracy else None
    except ValueError:
        lat_f = lng_f = acc_f = None

    if lat_f is not None and lng_f is not None and (acc_f is None or acc_f <= GPS_THRESHOLD):
        centro     = {"lat": lat_f, "lng": lng_f}
        modo_busca = "gps"
    else:
        membros_gps = [
            m for m in party.get("membros", [])
            if m.get("lat") is not None
            and m.get("lng") is not None
            and (m.get("accuracy") is None or m.get("accuracy") <= GPS_THRESHOLD)
        ]
        triangulo = calcular_centro(membros_gps, raio_metros=raio_usuario)
        if triangulo:
            centro     = triangulo["centro_busca"]
            raio_busca = triangulo["raio_final"]
            modo_busca = "triangulacao"

    if centro:
        url = (
            f"https://places-api.foursquare.com/places/search"
            f"?query={url_quote(query)}"
            f"&ll={centro['lat']},{centro['lng']}"
            f"&radius={raio_busca}"
            f"&limit={limit}"
        )
    else:
        url = (
            f"https://places-api.foursquare.com/places/search"
            f"?query={url_quote(query)}"
            f"&near={url_quote(city)}"
            f"&limit={limit}"
        )

    try:
        resp = http_requests.get(url, headers={
            "Accept":              "application/json",
            "Authorization":       f"Bearer {api_key}",
            "X-Places-Api-Version": "2025-06-17",
        }, timeout=10)
    except Exception as e:
        return {"erro": f"Falha ao contatar Foursquare: {str(e)}"}, 502

    data = resp.json()
    if not resp.ok:
        return {"erro": data.get("message", "Erro na Foursquare API")}, resp.status_code

    lugares = []
    for place in data.get("results", []):
        cat  = place.get("categories", [{}])[0] if place.get("categories") else {}
        icon = cat.get("icon", {})
        icon_url = (icon["prefix"] + "88" + icon["suffix"]) if icon.get("prefix") else None

        dist_m = place.get("distance")
        if dist_m is not None:
            distancia = f"{dist_m}m" if dist_m < 1000 else f"{dist_m / 1000:.1f}km"
        else:
            distancia = None

        loc = place.get("location", {})
        lat = place.get("latitude")
        lng = place.get("longitude")

        lugares.append({
            "id":        place.get("fsq_place_id"),
            "nome":      place.get("name"),
            "endereco":  loc.get("formatted_address"),
            "categoria": cat.get("name"),
            "icone":     icon_url,
            "distancia": distancia,
            "lat":       lat,
            "lng":       lng,
            "tel":       place.get("tel"),
            "website":   place.get("website"),
            "instagram": place.get("social_media", {}).get("instagram"),
        })

    return {
        "lugares":    lugares,
        "cidade":     city,
        "modo_busca": modo_busca,
    }
