from flask import Flask
from pymongo import MongoClient
from dotenv import load_dotenv
from flask import request
from datetime import datetime
import os

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

@app.route("/categorias")
def get_categorias():
    categorias = list(db.categorias.find())

    # Mongo retorna ObjectId, precisamos converter
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

if __name__ == "__main__":
    app.run(debug=True, port=8000)