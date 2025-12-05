from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ==================== CONFIGURACIÓN INICIAL ====================
load_dotenv()  # Cargar variables del archivo .env

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_por_defecto")

# ==================== CLASE DUMMY DB PARA FALLBACK ====================
class DummyDB:
    def find_one(self, *args, **kwargs): 
        return None
    def insert_one(self, *args, **kwargs): 
        return type('obj', (object,), {'inserted_id': 'dummy'})()
    def update_one(self, *args, **kwargs): 
        return type('obj', (object,), {'matched_count': 0})()
    def count_documents(self, *args, **kwargs):
        return 0

# ==================== CONEXIÓN MONGODB ====================
try:
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        raise ValueError("❌ ERROR: MONGODB_URI no está definida en .env")
    
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)  # Timeout de 5 segundos
    # Verificar conexión
    client.admin.command('ping')
    print("✅ Conexión a MongoDB exitosa")
    
    db = client.registro
    usuarios_collection = db.usuarios
    mongo_disponible = True
    
except Exception as e:
    print(f"❌ Error conectando a MongoDB: {e}")
    print("⚠️ Usando base de datos dummy para desarrollo")
    usuarios_collection = DummyDB()
    mongo_disponible = False

# ==================== HEALTH CHECK ====================
@app.route("/health")
def health():
    """Endpoint para verificar que la app está funcionando"""
    try:
        if not mongo_disponible:
            return jsonify({
                "status": "degraded",
                "message": "Aplicación funcionando pero MongoDB no disponible",
                "timestamp": datetime.now().isoformat(),
                "database": "disconnected",
                "mode": "development"
            }), 200
        
        # Verificar conexión a MongoDB
        client.admin.command('ping')
        return jsonify({
            "status": "healthy",
            "message": "Aplicación funcionando correctamente",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "version": "1.0.0",
            "mode": "production"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "message": f"Error en la aplicación: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "database": "error"
        }), 500

# ==================== RUTAS PRINCIPALES ====================
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

# ==================== REGISTRO DE USUARIO ====================
@app.route("/register", methods=["POST"])
def register():
    if not mongo_disponible:
        flash("Base de datos no disponible temporalmente", "error")
        return redirect(url_for('registrow'))
    
    usuario = request.form.get("usuario")
    nombre = request.form.get("nombre")
    email = request.form.get("email")
    password = request.form.get("password")
    
    # Validaciones básicas
    if not all([usuario, nombre, email, password]):
        flash("Todos los campos son requeridos", "error")
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
    
    try:
        # Validar que el usuario no exista
        if usuarios_collection.find_one({"usuario": usuario}):
            flash("El usuario ya existe", "error")
            return redirect(url_for('registrow'))
        
        # Validar que el email no exista
        if usuarios_collection.find_one({"email": email}):
            flash("El email ya está registrado", "error")
            return redirect(url_for('registrow'))
        
        # Crear usuario
        hashed_password = generate_password_hash(password)
        nuevo_usuario = {
            "usuario": usuario,
            "nombre": nombre,
            "email": email,
            "password": hashed_password,
            "descripcion": "Nuevo usuario de CineTec",
            "foto_perfil": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
            "fecha_registro": datetime.now(),
            "ultimo_acceso": datetime.now()
        }
        
        usuarios_collection.insert_one(nuevo_usuario)
        flash("¡Registro exitoso! Ahora puedes iniciar sesión", "success")
        
    except Exception as e:
        flash(f"Error en el registro: {str(e)}", "error")
    
    return redirect(url_for('iniciopy'))

# ==================== INICIO DE SESIÓN ====================
@app.route("/login", methods=["POST"])
def login():
    if not mongo_disponible:
        flash("Base de datos no disponible temporalmente", "error")
        return redirect(url_for('iniciopy'))
    
    usuario = request.form.get("usuario")
    password = request.form.get("password")
    
    try:
        usuario_db = usuarios_collection.find_one({"usuario": usuario})
        
        if usuario_db and check_password_hash(usuario_db["password"], password):
            session['usuario'] = usuario_db["usuario"]
            session['nombre'] = usuario_db["nombre"]
            session['descripcion'] = usuario_db.get("descripcion", "")
            session['foto_perfil'] = usuario_db.get("foto_perfil", "https://cdn-icons-png.flaticon.com/512/3135/3135715.png")
            
            # Actualizar último acceso
            usuarios_collection.update_one(
                {"usuario": usuario},
                {"$set": {"ultimo_acceso": datetime.now()}}
            )
            
            flash(f"¡Bienvenido {usuario_db['nombre']}!", "success")
            return redirect(url_for('pelispy'))
        else:
            flash("Usuario o contraseña incorrectos", "error")
            
    except Exception as e:
        flash(f"Error en el inicio de sesión: {str(e)}", "error")
    
    return redirect(url_for('iniciopy'))

# ==================== ACTUALIZAR DESCRIPCIÓN ====================
@app.route("/update_status", methods=["POST"])
def update_status():
    if 'usuario' not in session:
        flash("Debes iniciar sesión primero", "error")
        return redirect(url_for('iniciopy'))
    
    if not mongo_disponible:
        flash("Base de datos no disponible", "error")
        return redirect(url_for('pelispy'))
    
    nueva_descripcion = request.form.get("descripcion")
    if nueva_descripcion and len(nueva_descripcion.strip()) > 0:
        try:
            usuarios_collection.update_one(
                {"usuario": session['usuario']},
                {"$set": {"descripcion": nueva_descripcion.strip()}}
            )
            session['descripcion'] = nueva_descripcion.strip()
            flash("Estado actualizado correctamente", "success")
        except Exception as e:
            flash(f"Error al actualizar estado: {str(e)}", "error")
    
    return redirect(url_for('pelispy'))

# ==================== ACTUALIZAR FOTO DE PERFIL ====================
@app.route("/update_profile_pic", methods=["POST"])
def update_profile_pic():
    if 'usuario' not in session:
        flash("Debes iniciar sesión primero", "error")
        return redirect(url_for('iniciopy'))
    
    if not mongo_disponible:
        flash("Base de datos no disponible", "error")
        return redirect(url_for('pelispy'))
    
    nueva_foto = request.form.get("foto_url")
    if nueva_foto and nueva_foto.startswith(('http://', 'https://')):
        try:
            usuarios_collection.update_one(
                {"usuario": session['usuario']},
                {"$set": {"foto_perfil": nueva_foto}}
            )
            session['foto_perfil'] = nueva_foto
            flash("Foto de perfil actualizada", "success")
        except Exception as e:
            flash(f"Error al actualizar foto: {str(e)}", "error")
    else:
        flash("URL de foto inválida", "error")
    
    return redirect(url_for('pelispy'))

# ==================== CERRAR SESIÓN ====================
@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('index'))

# ==================== API PARA OBTENER DATOS ====================
@app.route("/api/usuarios")
def api_usuarios():
    """API para obtener lista de usuarios"""
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    if not mongo_disponible:
        return jsonify({"error": "Base de datos no disponible"}), 503
    
    try:
        usuarios = list(usuarios_collection.find({}, {
            "_id": 0,
            "usuario": 1,
            "nombre": 1,
            "descripcion": 1,
            "fecha_registro": 1
        }).sort("fecha_registro", -1).limit(50))
        
        # Convertir fechas
        for usuario in usuarios:
            if 'fecha_registro' in usuario:
                usuario['fecha_registro'] = usuario['fecha_registro'].isoformat()
        
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== PÁGINA DE ESTADO ====================
@app.route("/status")
def status():
    """Página para ver el estado del sistema"""
    try:
        total_usuarios = usuarios_collection.count_documents({}) if mongo_disponible else 0
        return jsonify({
            "app": "CineTec",
            "status": "running",
            "database": "connected" if mongo_disponible else "disconnected",
            "total_usuarios": total_usuarios,
            "timestamp": datetime.now().isoformat(),
            "mongo_disponible": mongo_disponible
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== MANEJADOR DE ERRORES ====================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Por favor, intenta más tarde",
        "timestamp": datetime.now().isoformat()
    }), 500

@app.errorhandler(400)
def bad_request(e):
    return jsonify({
        "error": "Solicitud incorrecta",
        "message": "Verifica los datos enviados"
    }), 400

# ==================== MIDDLEWARE PARA CACHÉ ====================
@app.after_request
def add_header(response):
    """
    Agrega headers de caché para mejorar rendimiento
    """
    # Cache por 5 minutos para archivos estáticos
    if request.path.startswith('/static/') or request.path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg')):
        response.cache_control.max_age = 300
        response.cache_control.public = True
        response.cache_control.s_maxage = 300
    # Cache corto para páginas principales (1 minuto)
    elif request.path in ['/', '/iniciopy', '/registrow']:
        response.cache_control.max_age = 60
        response.cache_control.public = True
    # No cache para páginas dinámicas y API
    else:
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
    
    # Seguridad básica
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    
    return response

# ==================== INICIAR APLICACIÓN ====================
if __name__ == "__main__":
    # Configuración OPTIMIZADA para producción
    port = int(os.environ.get("PORT", 5000))
    
    print("=" * 50)
    print("🚀 Iniciando CineTec")
    print(f"📊 Puerto: {port}")
    print(f"✅ MongoDB: {'CONECTADO' if mongo_disponible else 'DESCONECTADO'}")
    print(f"🔗 Health Check: http://localhost:{port}/health")
    print(f"🔗 Estado: http://localhost:{port}/status")
    print("=" * 50)
    
    # OPCIONES DE PRODUCCIÓN:
    # - debug=False: No mostrar errores detallados (más seguro y rápido)
    # - threaded=True: Atender múltiples solicitudes simultáneamente
    # - use_reloader=False: Evitar doble inicio (problemas en Render)
    app.run(
        host="0.0.0.0",      # Aceptar conexiones de cualquier IP
        port=port,           # Puerto definido por Render o 5000
        debug=False,         # IMPORTANTE: False en producción
        threaded=True,       # Mejor concurrencia
        use_reloader=False   # Evita problemas en servicios como Render
    )