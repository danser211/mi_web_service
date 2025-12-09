# setup_database.py
from pymongo import MongoClient
from datetime import datetime
import os

# Conectar a MongoDB
client = MongoClient("mongodb+srv://cineTecUser:CineTec123456@cinetec-cluster.brahjlc.mongodb.net/?retryWrites=true&w=majority")
db = client.cineTecDB

# Crear colección de películas si no existe
peliculas = [
    {
        "titulo": "El Resplandor",
        "descripcion": "Un escritor acepta un trabajo de cuidador en un hotel aislado durante el invierno, donde su cordura se desmorona lentamente.",
        "plataforma": "Amazon Prime",
        "portada": "https://image.tmdb.org/t/p/w300/9O7gLzmreU0nGkIB6K3BsJbzvNv.jpg",
        "calificacion_promedio": 0,
        "total_calificaciones": 0
    },
    {
        "titulo": "El Padrino",
        "descripcion": "La saga de la familia Corleone, una poderosa dinastía de la mafia italiana en Nueva York.",
        "plataforma": "Netflix",
        "portada": "https://image.tmdb.org/t/p/w300/3Tf8vXykYhzHdT0BtsYTp570JGQ.jpg",
        "calificacion_promedio": 0,
        "total_calificaciones": 0
    },
    {
        "titulo": "El Caballero Oscuro",
        "descripcion": "Batman se enfrenta al Joker, un criminal psicótico que quiere sumir a Gotham en la anarquía.",
        "plataforma": "HBO Max",
        "portada": "https://image.tmdb.org/t/p/w300/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
        "calificacion_promedio": 0,
        "total_calificaciones": 0
    },
    {
        "titulo": "La Lista de Schindler",
        "descripcion": "Un empresario alemán salva a más de mil refugiados judíos durante el Holocausto.",
        "plataforma": "Disney+",
        "portada": "https://image.tmdb.org/t/p/w300/sF1U4EUQS8YHUYjNl3pMGNIQyr0.jpg",
        "calificacion_promedio": 0,
        "total_calificaciones": 0
    },
    {
        "titulo": "Matrix",
        "descripcion": "Un hacker descubre que su realidad es una simulación creada por máquinas inteligentes.",
        "plataforma": "HBO Max",
        "portada": "https://image.tmdb.org/t/p/w300/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        "calificacion_promedio": 0,
        "total_calificaciones": 0
    }
]

# Insertar películas
db.peliculas.delete_many({})  # Limpiar primero
db.peliculas.insert_many(peliculas)

print(f"✅ Insertadas {len(peliculas)} películas")

# Crear índices
db.calificaciones.create_index([("usuario", 1), ("pelicula", 1)], unique=True)
db.comentarios.create_index([("pelicula", 1), ("fecha", -1)])
db.usuarios.create_index([("usuario", 1)], unique=True)

print("✅ Índices creados")
print("✅ Base de datos configurada correctamente")
