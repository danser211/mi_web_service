from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
import re
from werkzeug.security import generate_password_hash, check_password_hash

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_por_defecto")

# Conexión a MongoDB
mongodb_uri = os.getenv("MONGODB_URI")
client = MongoClient(mongodb_uri)
db = client.registro
usuarios_collection = db.usuarios

# RUTAS PRINCIPALES
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/iniciopy")
def iniciopy():
    return render_template("iniciopy.html")

@app.route("/registrow")
def registrow():
    return render_template("registrow.html")

@app.route("/pelispy")
def pelispy():
    if 'usuario' not in session:
        flash("Debes iniciar sesión primero", "error")
        return redirect(url_for('iniciopy'))
    return render_template("pelispy.html")

# REGISTRO DE USUARIO
@app.route("/register", methods=["POST"])
def register():
    usuario = request.form.get("usuario")
    nombre = request.form.get("nombre")
    email = request.form.get("email")
    password = request.form.get("password")
    
    # Validaciones
    if not usuario or not nombre or not email or not password:
        flash("Todos los campos son requeridos", "error")
        return redirect(url_for('registrow'))
    
    # Validar que el usuario no exista
    if usuarios_collection.find_one({"usuario": usuario}):
        flash("El usuario ya existe", "error")
        return redirect(url_for('registrow'))
    
    # Validar que el email no exista
    if usuarios_collection.find_one({"email": email}):
        flash("El email ya está registrado", "error")
        return redirect(url_for('registrow'))
    
    # Validar nombre solo letras
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', nombre):
        flash("El nombre solo puede contener letras", "error")
        return redirect(url_for('registrow'))
    
    # Validar email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        flash("Email inválido", "error")
        return redirect(url_for('registrow'))
    
    # Validar contraseña (mínimo 8 caracteres)
    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres", "error")
        return redirect(url_for('registrow'))
    
    # Crear usuario
    hashed_password = generate_password_hash(password)
    nuevo_usuario = {
        "usuario": usuario,
        "nombre": nombre,
        "email": email,
        "password": hashed_password,
        "descripcion": "Nuevo usuario de CinePlus",
        "foto_perfil": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
    }
    
    usuarios_collection.insert_one(nuevo_usuario)
    flash("¡Registro exitoso! Ahora puedes iniciar sesión", "success")
    return redirect(url_for('iniciopy'))

# INICIO DE SESIÓN
@app.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario")
    password = request.form.get("password")
    
    usuario_db = usuarios_collection.find_one({"usuario": usuario})
    
    if usuario_db and check_password_hash(usuario_db["password"], password):
        session['usuario'] = usuario_db["usuario"]
        session['nombre'] = usuario_db["nombre"]
        session['descripcion'] = usuario_db.get("descripcion", "")
        session['foto_perfil'] = usuario_db.get("foto_perfil", "https://cdn-icons-png.flaticon.com/512/3135/3135715.png")
        flash(f"¡Bienvenido {usuario_db['nombre']}!", "success")
        return redirect(url_for('pelispy'))
    else:
        flash("Usuario o contraseña incorrectos", "error")
        return redirect(url_for('iniciopy'))

# ACTUALIZAR DESCRIPCIÓN
@app.route("/update_status", methods=["POST"])
def update_status():
    if 'usuario' not in session:
        return redirect(url_for('iniciopy'))
    
    nueva_descripcion = request.form.get("descripcion")
    if nueva_descripcion:
        usuarios_collection.update_one(
            {"usuario": session['usuario']},
            {"$set": {"descripcion": nueva_descripcion}}
        )
        session['descripcion'] = nueva_descripcion
        flash("Estado actualizado correctamente", "success")
    
    return redirect(url_for('pelispy'))

# ACTUALIZAR FOTO DE PERFIL
@app.route("/update_profile_pic", methods=["POST"])
def update_profile_pic():
    if 'usuario' not in session:
        return redirect(url_for('iniciopy'))
    
    nueva_foto = request.form.get("foto_url")
    if nueva_foto:
        usuarios_collection.update_one(
            {"usuario": session['usuario']},
            {"$set": {"foto_perfil": nueva_foto}}
        )
        session['foto_perfil'] = nueva_foto
        flash("Foto de perfil actualizada", "success")
    
    return redirect(url_for('pelispy'))

# CERRAR SESIÓN
@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('index'))

# MANEJADOR DE ERRORES
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

# INICIAR APLICACIÓN
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)