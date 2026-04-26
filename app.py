from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
import certifi
import os
import subprocess
import json


load_dotenv()

app = Flask(__name__)
CORS(app)

# conecta no Mongo
client = MongoClient(os.getenv("MONGO_URI"), tlsCAFile=certifi.where())
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

@app.route("/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = list(db.usuarios.find())
    for u in usuarios:
        u["_id"] = str(u["_id"])
        if "criado_em" in u and not isinstance(u["criado_em"], str):
            u["criado_em"] = u["criado_em"].isoformat() + "Z"
    return {"usuarios": usuarios, "total": len(usuarios)}

@app.route("/usuarios", methods=["POST"])
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
        "nome": nome,
        "email": email,
        "cidade": data.get("cidade", "").strip(),
        "avatar_url": "",
        "senha_hash": generate_password_hash(senha),
        "criado_em": datetime.utcnow(),
        "ativo": True
    }

    result = db.usuarios.insert_one(usuario)

    usuario["_id"] = str(result.inserted_id)
    usuario["criado_em"] = usuario["criado_em"].isoformat() + "Z"
    del usuario["senha_hash"]

    return {"usuario": usuario}, 201


@app.route("/login", methods=["POST"])
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

    usuario["_id"] = str(usuario["_id"])
    if "criado_em" in usuario and not isinstance(usuario["criado_em"], str):
        usuario["criado_em"] = usuario["criado_em"].isoformat() + "Z"
    del usuario["senha_hash"]

    return {"usuario": usuario}

@app.route("/usuarios/<id>", methods=["PATCH"])
def atualizar_usuario(id):
    data = request.get_json()
    if not data:
        return {"erro": "JSON inválido"}, 400

    campos_permitidos = {"nome", "cidade", "avatar_url"}
    update = {k: v for k, v in data.items() if k in campos_permitidos}

    if not update:
        return {"erro": "Nenhum campo válido para atualizar"}, 400

    result = db.usuarios.find_one_and_update(
        {"_id": ObjectId(id)},
        {"$set": update},
        return_document=True
    )

    if not result:
        return {"erro": "Usuário não encontrado"}, 404

    result["_id"] = str(result["_id"])
    if "criado_em" in result and not isinstance(result["criado_em"], str):
        result["criado_em"] = result["criado_em"].isoformat() + "Z"
    result.pop("senha_hash", None)

    return {"usuario": result}

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

@app.route("/parties", methods=["GET"])
def listar_parties():
    usuario_id = request.args.get("usuario_id")

    if usuario_id:
        membros = list(db.party_membros.find({"usuario_id": usuario_id}))
        parties = []
        for m in membros:
            try:
                p = db.parties.find_one({"_id": ObjectId(m["party_id"])})
                if p:
                    parties.append(p)
            except Exception:
                pass
    else:
        parties = list(db.parties.find().sort("criada_em", -1).limit(50))

    for p in parties:
        p["_id"] = str(p["_id"])
        if "criada_em" in p and not isinstance(p["criada_em"], str):
            p["criada_em"] = p["criada_em"].isoformat() + "Z"

    return {"parties": parties}


@app.route("/parties/codigo/<codigo>", methods=["GET"])
def get_party_by_codigo(codigo):
    party = db.parties.find_one({"codigo_convite": codigo.upper()})
    if not party:
        return {"erro": "Convite inválido ou expirado."}, 404

    party["_id"] = str(party["_id"])
    if "criada_em" in party and not isinstance(party["criada_em"], str):
        party["criada_em"] = party["criada_em"].isoformat() + "Z"

    return {"party": party}


@app.route("/parties/<id>", methods=["GET"])
def get_party(id):
    try:
        party = db.parties.find_one({"_id": ObjectId(id)})
    except Exception:
        return {"erro": "ID inválido"}, 400

    if not party:
        return {"erro": "Party não encontrada"}, 404

    party["_id"] = str(party["_id"])
    if "criada_em" in party and not isinstance(party["criada_em"], str):
        party["criada_em"] = party["criada_em"].isoformat() + "Z"

    return {"party": party}


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

@app.route("/party_membros", methods=["GET"])
def listar_membros():
    party_id = request.args.get("party_id")
    if not party_id:
        return {"erro": "party_id é obrigatório"}, 400

    membros = list(db.party_membros.find({"party_id": party_id}))
    for m in membros:
        m["_id"] = str(m["_id"])
        if "entrou_em" in m and not isinstance(m["entrou_em"], str):
            m["entrou_em"] = m["entrou_em"].isoformat() + "Z"

    return {"membros": membros}


@app.route("/party_membros", methods=["POST"])
def adicionar_membro_party():
    data = request.get_json()

    if not data:
        return {"erro": "JSON inválido"}, 400

    party_id = data.get("party_id")
    usuario_id = data.get("usuario_id")

    if not party_id or not usuario_id:
        return {"erro": "party_id e usuario_id são obrigatórios"}, 400

    existing = db.party_membros.find_one({"party_id": party_id, "usuario_id": usuario_id})
    if existing:
        existing["_id"] = str(existing["_id"])
        if "entrou_em" in existing and not isinstance(existing["entrou_em"], str):
            existing["entrou_em"] = existing["entrou_em"].isoformat() + "Z"
        return {"membro": existing}, 200

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

@app.route("/party_preferencias", methods=["GET"])
def listar_party_preferencias():
    party_id   = request.args.get("party_id")
    usuario_id = request.args.get("usuario_id")

    query = {}
    if party_id:   query["party_id"]   = party_id
    if usuario_id: query["usuario_id"] = usuario_id

    prefs = list(db.party_preferencias.find(query))
    for p in prefs:
        p["_id"] = str(p["_id"])
        if "criado_em" in p and not isinstance(p["criado_em"], str):
            p["criado_em"] = p["criado_em"].isoformat() + "Z"

    return {"preferencias": prefs}


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
# MATCH
# =========================

@app.route("/match/<party_id>", methods=["GET"])
def calcular_match(party_id):
    prefs   = list(db.party_preferencias.find({"party_id": party_id}))
    membros = list(db.party_membros.find({"party_id": party_id}))

    votos    = {}
    votantes = set()
    for p in prefs:
        slug = p["categoria_slug"]
        votos[slug] = votos.get(slug, 0) + p.get("forca", 1)
        votantes.add(p["usuario_id"])

    ranking = sorted(votos.items(), key=lambda x: x[1], reverse=True)

    return {
        "match": ranking[0][0] if ranking else None,
        "ranking": [{"slug": k, "votos": v} for k, v in ranking],
        "total_membros": len(membros),
        "total_votaram": len(votantes)
    }

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