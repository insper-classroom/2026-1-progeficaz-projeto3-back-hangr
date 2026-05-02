from flask import Blueprint, request
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from datetime import datetime
from db import db

bp = Blueprint('usuarios', __name__)


def _serialize(u):
    u["_id"] = str(u["_id"])
    if "criado_em" in u and not isinstance(u["criado_em"], str):
        u["criado_em"] = u["criado_em"].isoformat() + "Z"
    u.pop("senha_hash", None)
    return u


@bp.route("/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = list(db.usuarios.find())
    return {"usuarios": [_serialize(u) for u in usuarios], "total": len(usuarios)}


@bp.route("/usuarios", methods=["POST"])
def criar_usuario():
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    nome  = data.get("nome", "").strip()
    email = data.get("email", "").strip().lower()
    senha = data.get("senha", "").strip()

    if not nome or not email or not senha:
        return {"erro": "nome, email e senha são obrigatórios"}, 400
    if len(senha) < 6:
        return {"erro": "Senha deve ter no mínimo 6 caracteres."}, 400
    if db.usuarios.find_one({"email": email}):
        return {"erro": "Email já cadastrado."}, 409

    usuario = {
        "nome":       nome,
        "email":      email,
        "cidade":     data.get("cidade", "").strip(),
        "avatar_url": "",
        "senha_hash": generate_password_hash(senha),
        "criado_em":  datetime.utcnow(),
        "ativo":      True,
    }
    result = db.usuarios.insert_one(usuario)
    usuario["_id"]       = str(result.inserted_id)
    usuario["criado_em"] = usuario["criado_em"].isoformat() + "Z"
    del usuario["senha_hash"]
    return {"usuario": usuario}, 201


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    email = data.get("email", "").strip().lower()
    senha = data.get("senha", "").strip()

    if not email or not senha:
        return {"erro": "email e senha são obrigatórios"}, 400

    usuario = db.usuarios.find_one({"email": email})
    if not usuario or not check_password_hash(usuario.get("senha_hash", ""), senha):
        return {"erro": "Email ou senha incorretos."}, 401

    return {"usuario": _serialize(usuario)}


@bp.route("/usuarios/<id>", methods=["PATCH"])
def atualizar_usuario(id):
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    campos_permitidos = {"nome", "cidade", "avatar_url"}
    update = {k: v for k, v in data.items() if k in campos_permitidos}
    if not update:
        return {"erro": "Nenhum campo válido para atualizar"}, 400

    try:
        result = db.usuarios.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": update},
            return_document=True,
        )
    except Exception:
        return {"erro": "ID inválido"}, 400

    if not result:
        return {"erro": "Usuário não encontrado"}, 404

    return {"usuario": _serialize(result)}


@bp.route("/preferencias_usuario", methods=["POST"])
def salvar_preferencias():
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    usuario_id = data.get("usuario_id")
    categorias = data.get("categorias")

    if not usuario_id or not categorias:
        return {"erro": "usuario_id e categorias são obrigatórios"}, 400

    prefs = [
        {
            "usuario_id":     usuario_id,
            "categoria_slug": c["slug"],
            "tipo":           "like",
            "forca":          c.get("forca", 1),
            "origem":         "onboarding",
            "criado_em":      datetime.utcnow(),
        }
        for c in categorias if c.get("slug")
    ]
    if not prefs:
        return {"erro": "Nenhuma categoria válida"}, 400

    db.preferencias_usuario.insert_many(prefs)
    return {"mensagem": "Preferências salvas", "quantidade": len(prefs)}, 201
