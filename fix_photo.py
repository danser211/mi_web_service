print("🚀 Arreglando foto de perfil...")

from pymongo import MongoClient

# Conectar a MongoDB
client = MongoClient('mongodb+srv://cineTecUser:CineTec123456@cinetec-cluster.brahjlc.mongodb.net/cineTecDB?retryWrites=true&w=majority')
db = client.cineTecDB

print("✅ Conectado a MongoDB")

# Actualizar el usuario danser211 para quitar la foto grande
resultado = db.usuarios.update_one(
    {'usuario': 'danser211'},
    {'$set': {'foto_perfil': 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'}}
)

if resultado.modified_count > 0:
    print('✅ Foto de perfil restaurada a la default')
else:
    print('ℹ️ El usuario ya tenía la foto default')

client.close()
print("✅ Proceso completado")