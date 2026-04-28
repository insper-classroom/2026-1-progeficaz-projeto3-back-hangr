from flask import Blueprint, request
from bson import ObjectId
from datetime import datetime
from db import db

bp = Blueprint('parties', __name__)


def _fmt_dt(val):
    if val and not isinstance(val, str):
        return val.isoformat() + "Z"
    return val


def _serialize_party(p):
    p["_id"] = str(p["_id"])
    p["criada_em"] = _fmt_dt(p.get("criada_em"))
    for m in p.get("membros", []):
        m["entrou_em"] = _fmt_dt(m.get("entrou_em"))
    for v in p.get("votes", []):
        v["criado_em"] = _fmt_dt(v.get("criado_em"))
    return p


# ── List parties ──────────────────────────────────────────────────────────

@bp.route("/parties", methods=["GET"])
def listar_parties():
    usuario_id = request.args.get("usuario_id")
    query = {"membros.usuario_id": usuario_id} if usuario_id else {}
    parties = list(db.parties.find(query).sort("criada_em", -1).limit(50))
    return {"parties": [_serialize_party(p) for p in parties]}


# ── Create party ──────────────────────────────────────────────────────────

@bp.route("/parties", methods=["POST"])
def criar_party():
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    titulo     = data.get("titulo")
    criada_por = data.get("criada_por")
    cidade     = data.get("cidade")

    if not titulo or not criada_por or not cidade:
        return {"erro": "titulo, criada_por e cidade são obrigatórios"}, 400

    party = {
        "titulo":         titulo,
        "criada_por":     criada_por,
        "cidade":         cidade,
        "status":         "aberta",
        "codigo_convite": data.get("codigo_convite", ""),
        "criada_em":      datetime.utcnow(),
        "ativa":          True,
        "membros":        [],
        "votes":          [],
    }
    result = db.parties.insert_one(party)
    party["_id"]       = str(result.inserted_id)
    party["criada_em"] = party["criada_em"].isoformat() + "Z"
    return {"party": party}, 201


# ── Get party by invite code ──────────────────────────────────────────────

@bp.route("/parties/<codigo>", methods=["GET"])
def get_party(codigo):
    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404
    return {"party": _serialize_party(party)}


# ── Add member (embedded) ─────────────────────────────────────────────────

@bp.route("/parties/<codigo>/membros", methods=["POST"])
def adicionar_membro(codigo):
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    usuario_id = data.get("usuario_id")
    if not usuario_id:
        return {"erro": "usuario_id é obrigatório"}, 400

    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404

    existing = next((m for m in party.get("membros", []) if m["usuario_id"] == usuario_id), None)
    if existing:
        existing["entrou_em"] = _fmt_dt(existing.get("entrou_em"))
        return {"membro": existing}, 200

    try:
        usuario = db.usuarios.find_one({"_id": ObjectId(usuario_id)})
        nome = usuario.get("nome", "") if usuario else ""
    except Exception:
        nome = ""

    membro = {
        "usuario_id": usuario_id,
        "papel":      data.get("papel", "member"),
        "nickname":   None,
        "lat":        data.get("lat"),
        "lng":        data.get("lng"),
        "accuracy":   data.get("accuracy"),
        "entrou_em":  datetime.utcnow(),
        "nome":       nome,
    }

    db.parties.update_one(
        {"codigo_convite": codigo.upper()},
        {"$push": {"membros": membro}},
    )

    membro["entrou_em"] = membro["entrou_em"].isoformat() + "Z"
    return {"membro": membro}, 201


# ── Kick member ───────────────────────────────────────────────────────────

@bp.route("/parties/<codigo>/membros/<usuario_id>", methods=["DELETE"])
def kickar_membro(codigo, usuario_id):
    host_id = request.args.get("host_id")
    if not host_id:
        return {"erro": "host_id é obrigatório"}, 400

    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404

    host = next(
        (m for m in party.get("membros", []) if m["usuario_id"] == host_id and m["papel"] == "host"),
        None,
    )
    if not host:
        return {"erro": "Sem permissão"}, 403

    if usuario_id == host_id:
        return {"erro": "Host não pode se remover"}, 400

    db.parties.update_one(
        {"codigo_convite": codigo.upper()},
        {"$pull": {"membros": {"usuario_id": usuario_id}}},
    )
    return {"mensagem": "Membro removido"}, 200


# ── Update nickname ───────────────────────────────────────────────────────

@bp.route("/parties/<codigo>/membros/<usuario_id>", methods=["PATCH"])
def atualizar_nickname(codigo, usuario_id):
    data = request.get_json()
    if not data or "nickname" not in data:
        return {"erro": "nickname é obrigatório"}, 400

    nickname = data["nickname"].strip() if data["nickname"] else None

    result = db.parties.find_one_and_update(
        {"codigo_convite": codigo.upper(), "membros.usuario_id": usuario_id},
        {"$set": {"membros.$.nickname": nickname}},
        return_document=True,
    )
    if not result:
        return {"erro": "Membro não encontrado"}, 404

    membro = next((m for m in result.get("membros", []) if m["usuario_id"] == usuario_id), None)
    if membro:
        membro["entrou_em"] = _fmt_dt(membro.get("entrou_em"))

    return {"membro": membro}


# ── Submit vote ───────────────────────────────────────────────────────────

@bp.route("/parties/<codigo>/votes", methods=["POST"])
def votar(codigo):
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    usuario_id = data.get("usuario_id")
    categorias = data.get("categorias")

    if not usuario_id or not categorias:
        return {"erro": "usuario_id e categorias são obrigatórios"}, 400

    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404

    voto = {
        "usuario_id": usuario_id,
        "categorias": categorias,
        "criado_em":  datetime.utcnow(),
    }

    # Upsert: remove old vote then push new one
    db.parties.update_one(
        {"codigo_convite": codigo.upper()},
        {"$pull": {"votes": {"usuario_id": usuario_id}}},
    )
    db.parties.update_one(
        {"codigo_convite": codigo.upper()},
        {"$push": {"votes": voto}},
    )

    return {"mensagem": "Voto registrado"}, 201


# ── Calculate match ───────────────────────────────────────────────────────

@bp.route("/parties/<codigo>/match", methods=["GET"])
def calcular_match(codigo):
    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404

    contagem = {}
    votantes = set()

    for vote in party.get("votes", []):
        votantes.add(vote["usuario_id"])
        for cat in vote.get("categorias", []):
            slug  = cat.get("slug")
            forca = cat.get("forca", 1)
            if slug:
                contagem[slug] = contagem.get(slug, 0) + forca

    ranking = sorted(contagem.items(), key=lambda x: x[1], reverse=True)

    return {
        "match":         ranking[0][0] if ranking else None,
        "ranking":       [{"slug": k, "votos": v} for k, v in ranking],
        "total_membros": len(party.get("membros", [])),
        "total_votaram": len(votantes),
    }


# ── Chat ─────────────────────────────────────────────────────────────────

@bp.route("/parties/<codigo>/chat", methods=["GET"])
def get_chat(codigo):
    party = db.parties.find_one({"codigo_convite": codigo.upper()}, {"chat": 1})
    if not party:
        return {"erro": "Party não encontrada"}, 404
    return {"mensagens": party.get("chat", [])}


@bp.route("/parties/<codigo>/chat", methods=["POST"])
def enviar_mensagem(codigo):
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    usuario_id = data.get("usuario_id", "").strip()
    nome       = data.get("nome", "User").strip()
    texto      = data.get("texto", "").strip()[:200]

    if not usuario_id or not texto:
        return {"erro": "usuario_id e texto são obrigatórios"}, 400

    msg = {
        "id":         str(ObjectId()),
        "usuario_id": usuario_id,
        "nome":       nome or "User",
        "texto":      texto,
        "criado_em":  datetime.utcnow().isoformat() + "Z",
    }

    result = db.parties.update_one(
        {"codigo_convite": codigo.upper()},
        {"$push": {"chat": {"$each": [msg], "$slice": -100}}},
    )
    if result.matched_count == 0:
        return {"erro": "Party não encontrada"}, 404

    return {"mensagem": "Enviado", "msg": msg}, 201


# ── Close party ───────────────────────────────────────────────────────────

@bp.route("/parties/<codigo>/encerrar", methods=["PATCH"])
def encerrar_party(codigo):
    host_id = request.args.get("host_id")
    if not host_id:
        return {"erro": "host_id é obrigatório"}, 400

    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Party não encontrada"}, 404

    host = next(
        (m for m in party.get("membros", []) if m["usuario_id"] == host_id and m["papel"] == "host"),
        None,
    )
    if not host:
        return {"erro": "Sem permissão"}, 403

    db.parties.update_one(
        {"codigo_convite": codigo.upper()},
        {"$set": {"ativa": False, "status": "encerrada", "encerrada_em": datetime.utcnow()}},
    )
    return {"mensagem": "Party encerrada"}, 200
