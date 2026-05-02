from flask import Blueprint, request
from bson import ObjectId
from datetime import datetime
import re
from db import db

bp = Blueprint('social', __name__)

CATS = {
    'restaurantes': ('Restaurantes', '🍽️'),
    'bares':        ('Bares',        '🍺'),
    'cafes':        ('Cafés',        '☕'),
    'jogos':        ('Jogos',        '🎮'),
    'parque':       ('Parque',       '🌳'),
    'esportes':     ('Esportes',     '⚽'),
}


def _fmt_dt(val):
    if val and not isinstance(val, str):
        return val.isoformat() + "Z"
    return val


def _match_de_votes(votes):
    contagem = {}
    for vote in votes:
        for cat in vote.get('categorias', []):
            slug = cat.get('slug')
            if slug:
                contagem[slug] = contagem.get(slug, 0) + cat.get('forca', 1)
    ranking = sorted(contagem.items(), key=lambda x: x[1], reverse=True)
    return ranking[0][0] if ranking else None


# ── Follow / unfollow ─────────────────────────────────────────────────────

@bp.route("/seguir", methods=["POST"])
def seguir():
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    seguidor_id = data.get("seguidor_id", "").strip()
    seguido_id  = data.get("seguido_id",  "").strip()

    if not seguidor_id or not seguido_id:
        return {"erro": "seguidor_id e seguido_id são obrigatórios"}, 400

    if seguidor_id == seguido_id:
        return {"erro": "Você não pode seguir a si mesmo"}, 400

    try:
        seguido = db.usuarios.find_one({"_id": ObjectId(seguido_id)})
    except Exception:
        return {"erro": "Usuário não encontrado"}, 404

    if not seguido:
        return {"erro": "Usuário não encontrado"}, 404

    if db.follows.find_one({"seguidor_id": seguidor_id, "seguido_id": seguido_id}):
        return {"mensagem": "Já segue"}, 200

    db.follows.insert_one({
        "seguidor_id": seguidor_id,
        "seguido_id":  seguido_id,
        "criado_em":   datetime.utcnow(),
    })
    return {"mensagem": "Seguindo"}, 201


@bp.route("/seguir", methods=["DELETE"])
def deixar_de_seguir():
    seguidor_id = request.args.get("seguidor_id", "").strip()
    seguido_id  = request.args.get("seguido_id",  "").strip()

    if not seguidor_id or not seguido_id:
        return {"erro": "seguidor_id e seguido_id são obrigatórios"}, 400

    db.follows.delete_one({"seguidor_id": seguidor_id, "seguido_id": seguido_id})
    return {"mensagem": "Deixou de seguir"}, 200


# ── List who you follow ───────────────────────────────────────────────────

@bp.route("/seguindo", methods=["GET"])
def listar_seguindo():
    usuario_id = request.args.get("usuario_id", "").strip()
    if not usuario_id:
        return {"erro": "usuario_id é obrigatório"}, 400

    follows = list(db.follows.find({"seguidor_id": usuario_id}))

    resultado = []
    for f in follows:
        try:
            u = db.usuarios.find_one({"_id": ObjectId(f["seguido_id"])})
            if u:
                resultado.append({
                    "_id":    str(u["_id"]),
                    "nome":   u.get("nome", ""),
                    "cidade": u.get("cidade", ""),
                })
        except Exception:
            pass

    return {"seguindo": resultado}


# ── Feed ──────────────────────────────────────────────────────────────────

@bp.route("/feed", methods=["GET"])
def feed():
    usuario_id = request.args.get("usuario_id", "").strip()
    if not usuario_id:
        return {"erro": "usuario_id é obrigatório"}, 400

    follows = list(db.follows.find({"seguidor_id": usuario_id}))
    ids_visíveis = [f["seguido_id"] for f in follows] + [usuario_id]

    parties = list(
        db.parties.find({
            "criada_por": {"$in": ids_visíveis},
            "status": "encerrada",
        }).sort("encerrada_em", -1).limit(40)
    )

    # Cache creator names to avoid N+1
    criadores_ids = {p["criada_por"] for p in parties}
    criadores = {}
    for cid in criadores_ids:
        try:
            u = db.usuarios.find_one({"_id": ObjectId(cid)})
            criadores[cid] = u.get("nome", "").split()[0] if u else ""
        except Exception:
            pass

    resultado = []
    for p in parties:
        resultado.append({
            "_id":            str(p["_id"]),
            "titulo":         p.get("titulo", ""),
            "cidade":         p.get("cidade", ""),
            "codigo_convite": p.get("codigo_convite", ""),
            "criada_por":     p.get("criada_por", ""),
            "criador_nome":   criadores.get(p.get("criada_por", ""), ""),
            "encerrada_em":   _fmt_dt(p.get("encerrada_em")),
            "criada_em":      _fmt_dt(p.get("criada_em")),
            "membros":        len(p.get("membros", [])),
            "match":          _match_de_votes(p.get("votes", [])),
            "minha":          p.get("criada_por") == usuario_id,
        })

    return {"feed": resultado}


# ── Search users ──────────────────────────────────────────────────────────

@bp.route("/usuarios/buscar", methods=["GET"])
def buscar_usuarios():
    q          = request.args.get("q", "").strip()
    usuario_id = request.args.get("usuario_id", "").strip()

    if len(q) < 2:
        return {"usuarios": []}

    regex = re.compile(re.escape(q), re.IGNORECASE)
    query = {"$or": [{"nome": regex}, {"email": regex}]}

    if usuario_id:
        try:
            query["_id"] = {"$ne": ObjectId(usuario_id)}
        except Exception:
            pass

    raw = list(db.usuarios.find(query).limit(10))

    seguindo_ids = set()
    if usuario_id:
        seguindo_ids = {f["seguido_id"] for f in db.follows.find({"seguidor_id": usuario_id})}

    return {
        "usuarios": [
            {
                "_id":      str(u["_id"]),
                "nome":     u.get("nome", ""),
                "cidade":   u.get("cidade", ""),
                "seguindo": str(u["_id"]) in seguindo_ids,
            }
            for u in raw
        ]
    }
