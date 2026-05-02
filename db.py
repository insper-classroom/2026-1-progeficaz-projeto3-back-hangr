from pymongo import MongoClient
from dotenv import load_dotenv
import certifi, os

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"), tls=True, tlsCAFile=certifi.where())
db = client[os.getenv("DB_NAME")]
