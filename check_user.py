# Crea un archivo llamado check_user.py
print("Verificando usuario en MongoDB...")

from pymongo import MongoClient
import hashlib

# Conectar a MongoDB
client = MongoClient("mongodb+srv://cineTecUser:CineTec123456@cinetec-cluster.brahjlc.mongodb.net/?retryWrites=true&w=majority")
db = client.cineTecDB

# Listar todos los usuarios
usuarios = list(db.usuarios.find({}, {"usuario": 1, "nombre": 1, "email": 1}))
print(f"\nTotal usuarios encontrados: {len(usuarios)}")
for user in usuarios:
    print(f"- Usuario: {user['usuario']}, Nombre: {user.get('nombre', 'N/A')}")

client.close()