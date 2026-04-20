from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import os
import subprocess
import json


load_dotenv()

app = Flask(__name__)

# conecta no Mongo
client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("DB_NAME")]

@app.route("/")
def home():
    return {"message": "Hangr backend rodando"}

# rota de teste do mongo
@app.route("/test-db")
def test_db():
    collections = db.list_collection_names()
    return {"collections": collections}

# =========================
# CATEGORIAS
# =========================

@app.route("/categorias")
def get_categorias():
    categorias = list(db.categorias.find())

    for c in categorias:
        c["_id"] = str(c["_id"])

    return {"categorias": categorias}

@app.route("/categorias/macros")
def get_macros():
    categorias = list(db.categorias.find({"tipo": "macro"}))

    for c in categorias:
        c["_id"] = str(c["_id"])

    return {"categorias": categorias}

@app.route("/categorias/filhas")
def get_categorias_filhas():
    parent = request.args.get("parent")

    query = {}

    if parent:
        query["parent_slug"] = parent

    categorias = list(db.categorias.find(query))

    for c in categorias:
        c["_id"] = str(c["_id"])

    return {"categorias": categorias}

# =========================
# USUARIOS
# =========================

@app.route("/usuarios", methods=["POST"])
def criar_usuario():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    usuario = {
        "nome": data.get("nome"),
        "email": data.get("email"),
        "cidade": data.get("cidade"),
        "avatar_url": "",
        "criado_em": datetime.utcnow(),
        "ativo": True
    }

    result = db.usuarios.insert_one(usuario)

    usuario["_id"] = str(result.inserted_id)
    usuario["criado_em"] = usuario["criado_em"].isoformat() + "Z"

    return {"usuario": usuario}, 201

# =========================
# PREFERENCIAS USUARIO
# =========================

@app.route("/preferencias_usuario", methods=["POST"])
def criar_preferencias():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    usuario_id = data.get("usuario_id")
    categorias = data.get("categorias")

    if not usuario_id or not categorias:
        return {"erro": "usuario_id e categorias são obrigatórios"}, 400

    preferencias = []

    for c in categorias:
        preferencias.append({
            "usuario_id": usuario_id,
            "categoria_slug": c["slug"],
            "tipo": "like",
            "forca": c.get("forca", 1),
            "origem": "onboarding",
            "criado_em": datetime.utcnow()
        })

    result = db.preferencias_usuario.insert_many(preferencias)

    return {
        "mensagem": "Preferências salvas",
        "quantidade": len(result.inserted_ids)
    }, 201

# =========================
# PARTIES
# =========================

@app.route("/parties", methods=["POST"])
def criar_party():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    titulo = data.get("titulo")
    criada_por = data.get("criada_por")
    cidade = data.get("cidade")

    if not titulo or not criada_por or not cidade:
        return {"erro": "titulo, criada_por e cidade são obrigatórios"}, 400

    party = {
        "titulo": titulo,
        "criada_por": criada_por,
        "cidade": cidade,
        "status": "aberta",
        "codigo_convite": data.get("codigo_convite", ""),
        "criada_em": datetime.utcnow(),
        "expira_em": data.get("expira_em"),
        "ativa": True
    }

    result = db.parties.insert_one(party)

    party["_id"] = str(result.inserted_id)
    party["criada_em"] = party["criada_em"].isoformat() + "Z"

    return {"party": party}, 201

# =========================
# PARTY MEMBROS
# =========================

@app.route("/party_membros", methods=["POST"])
def adicionar_membro_party():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    party_id = data.get("party_id")
    usuario_id = data.get("usuario_id")

    if not party_id or not usuario_id:
        return {"erro": "party_id e usuario_id são obrigatórios"}, 400

    membro = {
        "party_id": party_id,
        "usuario_id": usuario_id,
        "papel": data.get("papel", "member"),
        "status_resposta": "pending",
        "entrou_em": datetime.utcnow()
    }

    result = db.party_membros.insert_one(membro)

    membro["_id"] = str(result.inserted_id)
    membro["entrou_em"] = membro["entrou_em"].isoformat() + "Z"

    return {"membro": membro}, 201

# =========================
# PARTY PREFERENCIAS
# =========================

@app.route("/party_preferencias", methods=["POST"])
def criar_party_preferencias():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    party_id = data.get("party_id")
    usuario_id = data.get("usuario_id")
    categorias = data.get("categorias")

    if not party_id or not usuario_id or not categorias:
        return {"erro": "party_id, usuario_id e categorias são obrigatórios"}, 400

    preferencias = []

    for categoria in categorias:
        slug = categoria.get("slug")
        if not slug:
            continue

        preferencias.append({
            "party_id": party_id,
            "usuario_id": usuario_id,
            "categoria_slug": slug,
            "tipo": categoria.get("tipo", "like"),
            "forca": categoria.get("forca", 1),
            "origem": "party",
            "criado_em": datetime.utcnow()
        })

    if not preferencias:
        return {"erro": "Nenhuma categoria válida foi enviada"}, 400

    result = db.party_preferencias.insert_many(preferencias)

    return {
        "mensagem": "Preferências da party salvas",
        "quantidade": len(result.inserted_ids)
    }, 201

# =========================
# BUSCAR LUGARES (MOCK)
# =========================

@app.route("/buscar_lugares", methods=["POST"])
def buscar_lugares():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    party_id = data.get("party_id")

    if not party_id:
        return {"erro": "party_id é obrigatório"}, 400

    preferencias = list(db.party_preferencias.find({"party_id": party_id}))

    for p in preferencias:
        p["_id"] = str(p["_id"])

    #MOCK SIMPLES (SEM FOURSQUARE)
    lugares_mock = [
        {
            "nome": "Sushi House",
            "categoria": "Japonês",
            "nota": 4.7
        },
        {
            "nome": "Izakaya Center",
            "categoria": "Japonês",
            "nota": 4.5
        }
    ]

    return {
        "mensagem": "Mock de lugares (sem Foursquare ainda)",
        "preferencias": preferencias,
        "lugares": lugares_mock
    }

# =========================
# QUATRO QUADRADOS
# =========================


@app.route("/foursquare")
def buscar_foursquare():
    query = request.args.get("query", "sushi")
    cidade = request.args.get("cidade", "Sao Paulo")

    result = subprocess.run(
        ["node", "hangr-backend/foursquare.js", query, cidade],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return {
            "erro": "Node falhou",
            "stderr": result.stderr,
            "stdout": result.stdout
        }, 500

    return result.stdout, 200, {"Content-Type": "application/json"}

if __name__ == "__main__":
    app.run(debug=True, port=8000)