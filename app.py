from flask import Flask
from flask_cors import CORS
from routes.usuarios    import bp as usuarios_bp
from routes.parties     import bp as parties_bp
from routes.lugares     import bp as lugares_bp
from routes.social      import bp as social_bp
from routes.categorias  import bp as categorias_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(usuarios_bp)
app.register_blueprint(parties_bp)
app.register_blueprint(lugares_bp)
app.register_blueprint(social_bp)
app.register_blueprint(categorias_bp)


@app.route("/")
def home():
    return {"message": "Hangr backend rodando"}


if __name__ == "__main__":
    app.run(debug=True, port=8000)
