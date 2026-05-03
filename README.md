# hangr — backend

API REST em Flask para o Hangr, app de decisão de rolê em grupo.

**API em produção:** https://hangr.com.br/api

**Frontend em produção:** https://hangr.com.br

## Stack

- Python 3.11 + Flask
- MongoDB Atlas (pymongo)
- Foursquare Places API (busca de lugares)
- Google OAuth 2.0 (login com Google)

## Rodando localmente

```bash
cd hangr-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Crie um `.env` na raiz do backend:

```
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/<db>
FOURSQUARE_API_KEY=...
GOOGLE_CLIENT_ID=...
```

Depois:

```bash
python app.py
```

A API sobe em `http://localhost:8000`.

## Rotas

### Usuários
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/usuarios` | Lista todos os usuários |
| POST | `/usuarios` | Cadastro (nome, email, senha) |
| PATCH | `/usuarios/<id>` | Atualiza perfil |
| POST | `/login` | Login com email e senha |
| POST | `/login/google` | Login com token do Google |
| POST | `/preferencias_usuario` | Salva categorias favoritas do usuário |

### Parties
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/parties` | Lista parties do usuário |
| POST | `/parties` | Cria uma party |
| GET | `/parties/<codigo>` | Busca party pelo código de convite |
| POST | `/parties/<codigo>/membros` | Entra na party |
| DELETE | `/parties/<codigo>/membros/<usuario_id>` | Remove membro |
| PATCH | `/parties/<codigo>/membros/<usuario_id>` | Atualiza apelido do membro |
| POST | `/parties/<codigo>/votes` | Registra votos de categoria |
| GET | `/parties/<codigo>/match` | Calcula o match da votação |
| GET | `/parties/<codigo>/chat` | Mensagens do chat |
| POST | `/parties/<codigo>/chat` | Envia mensagem no chat |
| PATCH | `/parties/<codigo>/encerrar` | Encerra a party |

### Lugares
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/lugares` | Busca lugares via Foursquare (suporta GPS + triangulação) |

### Social
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/seguir` | Seguir usuário |
| DELETE | `/seguir` | Deixar de seguir |
| GET | `/seguindo` | Lista quem você segue |
| GET | `/feed` | Feed de parties encerradas |
| GET | `/usuarios/buscar` | Busca usuários por nome ou email |

### Categorias / Config
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/categorias` | Lista categorias ativas (do MongoDB) |
| GET | `/configuracoes` | Retorna configurações da aplicação |

## Estrutura

```
hangr-backend/
├── app.py              # entrada, registra blueprints
├── db.py               # conexão com MongoDB
├── triangulator.py     # cálculo de centro geográfico entre membros
├── routes/
│   ├── usuarios.py
│   ├── parties.py
│   ├── lugares.py
│   ├── social.py
│   └── categorias.py
└── requirements.txt
```
