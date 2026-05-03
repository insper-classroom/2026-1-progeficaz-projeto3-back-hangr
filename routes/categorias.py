from flask import Blueprint
from db import db

bp = Blueprint('categorias', __name__)


@bp.route("/categorias", methods=["GET"])
def listar_categorias():
    cats = list(db.categorias.find({"ativo": True}, {"_id": 0}).sort("ordem", 1))
    return {"categorias": cats}


@bp.route("/configuracoes", methods=["GET"])
def listar_configuracoes():
    docs = list(db.configuracoes.find({}, {"_id": 0}))
    return {"configuracoes": {d["chave"]: d["valor"] for d in docs}}
