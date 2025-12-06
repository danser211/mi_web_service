from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from dotenv import load_dotenv
import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import ssl

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

# ==================== CONEXIÓN MONGODB PARA RENDER (PYTHON 3.11) ====================
try:
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        # Intenta obtener de variables directas (Render)
        mongodb_uri = os.environ.get("MONGODB_URI")
        if not mongodb_uri:
            print("⚠️ MongoDB URI no encontrada. Usando modo desarrollo.")
            raise ValueError("MONGODB_URI no configurada")
    
    print(f"🔗 Configurando conexión para Render...")
    
    # SOLUCIÓN DEFINITIVA - Configuración probada
    client = MongoClient(
        mongodb_uri,
        # Parámetros CRÍTICOS para Render:
        tls=True,                          # TLS obligatorio para Atlas
        tlsAllowInvalidCertificates=False, # Seguridad normal
        retryWrites=True,                  # Reintentar escrituras
        
        # Timeouts optimizados para red de Render:
        connectTimeoutMS=15000,            # 15 segundos para conectar
        socketTimeoutMS=20000,             # 20 segundos para operaciones
        serverSelectionTimeoutMS=15000,    # 15 segundos para seleccionar servidor
        
        # Pool de conexiones pequeño (evita memoria):
        maxPoolSize=10,                    # Máximo 10 conexiones
        minPoolSize=2,                     # Mínimo 2 siempre activas
        maxIdleTimeMS=30000,               # Cerrar conexiones inactivas después de 30s
        
        # Opciones adicionales:
        appname="CineTec-Render-Prod",
        compressors='none',                # Sin compresión (más estable)
        zlibCompressionLevel=None,
        
        # Reconexión automática:
        retryReads=True,
        heartbeatFrequencyMS=10000         # Latido cada 10s
    )
    
    # Prueba de conexión CON MANEJO DE ERROR
    print("🔄 Probando conexión a MongoDB...")
    try:
        inicio = datetime.now()
        client.admin.command('ping', maxTimeMS=5000)
        tiempo = (datetime.now() - inicio).total_seconds()
        print(f"✅ MongoDB conectado exitosamente ({tiempo:.2f}s)")
        
        # Verificar que podemos acceder a la base de datos
        db = client.registro
        # Intentar una operación simple
        db.command('ping')
        
        usuarios_collection = db.usuarios
        mongo_disponible = True
        
    except Exception as ping_error:
        print(f"⚠️ Error en ping: {ping_error}")
        # Aún así intentamos usar la conexión
        db = client.registro
        usuarios_collection = db.usuarios
        mongo_disponible = True
        
except Exception as e:
    print(f"❌ Error de conexión principal: {str(e)[:100]}")
    print("🛡️ Activando modo desarrollo seguro")
    
    class DummyDB:
        """Base de datos dummy que no crashea la app"""
        def __init__(self):
            self.data = {}
            self.next_id = 1
            
        def find_one(self, query=None):
            # Simular que no encuentra nada
            return None
            
        def insert_one(self, document):
            # Simular inserción exitosa
            doc_id = f"dummy_{self.next_id}"
            self.next_id += 1
            return type('obj', (object,), {'inserted_id': doc_id})()
            
        def update_one(self, filter, update):
            # Simular actualización
            return type('obj', (object,), {'matched_count': 0})()
            
        def count_documents(self, filter):
            return 0
    
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

# ==================== REGISTRO DE USUARIO OPTIMIZADO ====================
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
        # ⚡ OPTIMIZACIÓN: Usar índice para búsquedas más rápidas
        # Primero verificar si el usuario existe
        if usuarios_collection.find_one({"usuario": usuario}):
            flash("El usuario ya existe", "error")
            return redirect(url_for('registrow'))
        
        # Luego verificar email
        if usuarios_collection.find_one({"email": email}):
            flash("El email ya está registrado", "error")
            return redirect(url_for('registrow'))
        
        # Crear usuario con datos optimizados
        hashed_password = generate_password_hash(password)
        ahora = datetime.now()
        nuevo_usuario = {
            "usuario": usuario,
            "nombre": nombre,
            "email": email,
            "password": hashed_password,
            "descripcion": "Nuevo usuario de CineTec",
            "foto_perfil": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
            "fecha_registro": ahora,
            "ultimo_acceso": ahora
        }
        
        # ⚡ Insertar de manera optimizada
        resultado = usuarios_collection.insert_one(nuevo_usuario)
        
        # Verificar que se insertó correctamente
        if resultado.inserted_id:
            flash("¡Registro exitoso! Ahora puedes iniciar sesión", "success")
        else:
            flash("Error al registrar usuario", "error")
        
    except Exception as e:
        flash(f"Error en el registro: {str(e)}", "error")
    
    return redirect(url_for('iniciopy'))

# ==================== INICIO DE SESIÓN OPTIMIZADO ====================
@app.route("/login", methods=["POST"])
def login():
    if not mongo_disponible:
        flash("Base de datos no disponible temporalmente", "error")
        return redirect(url_for('iniciopy'))
    
    usuario = request.form.get("usuario")
    password = request.form.get("password")
    
    try:
        # ⚡ Buscar solo los campos necesarios para mejorar velocidad
        usuario_db = usuarios_collection.find_one(
            {"usuario": usuario},
            {"usuario": 1, "nombre": 1, "password": 1, "descripcion": 1, "foto_perfil": 1}
        )
        
        if usuario_db and check_password_hash(usuario_db["password"], password):
            session['usuario'] = usuario_db["usuario"]
            session['nombre'] = usuario_db["nombre"]
            session['descripcion'] = usuario_db.get("descripcion", "")
            session['foto_perfil'] = usuario_db.get("foto_perfil", "https://cdn-icons-png.flaticon.com/512/3135/3135715.png")
            
            # ⚡ Actualizar último acceso de manera eficiente
            usuarios_collection.update_one(
                {"usuario": usuario},
                {"$set": {"ultimo_acceso": datetime.now()}},
                upsert=False  # No crear si no existe
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
            # ⚡ Actualización optimizada
            resultado = usuarios_collection.update_one(
                {"usuario": session['usuario']},
                {"$set": {"descripcion": nueva_descripcion.strip()}}
            )
            
            if resultado.modified_count > 0:
                session['descripcion'] = nueva_descripcion.strip()
                flash("Estado actualizado correctamente", "success")
            else:
                flash("No se pudo actualizar el estado", "warning")
                
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
            resultado = usuarios_collection.update_one(
                {"usuario": session['usuario']},
                {"$set": {"foto_perfil": nueva_foto}}
            )
            
            if resultado.modified_count > 0:
                session['foto_perfil'] = nueva_foto
                flash("Foto de perfil actualizada", "success")
            else:
                flash("No se pudo actualizar la foto", "warning")
                
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

# ==================== API PARA OBTENER DATOS OPTIMIZADA ====================
@app.route("/api/usuarios")
def api_usuarios():
    """API para obtener lista de usuarios"""
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    if not mongo_disponible:
        return jsonify({"error": "Base de datos no disponible"}), 503
    
    try:
        # ⚡ OPTIMIZACIÓN: Limitar a 20 usuarios y usar proyección específica
        usuarios = list(usuarios_collection.find(
            {},  # Sin filtro
            {  # Solo campos necesarios
                "_id": 0,
                "usuario": 1,
                "nombre": 1,
                "descripcion": 1,
                "fecha_registro": 1,
                "foto_perfil": 1
            }
        ).sort("fecha_registro", -1).limit(20))  # ⚡ Solo 20 registros
        
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
            "mongo_disponible": mongo_disponible,
            "optimized_for": "Render"
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

# ==================== MIDDLEWARE PARA CACHÉ OPTIMIZADO ====================
@app.after_request
def add_header(response):
    """
    Agrega headers de caché para mejorar rendimiento en Render
    """
    # Cache por 10 minutos para archivos estáticos (más tiempo para Render)
    if request.path.startswith('/static/') or request.path.endswith(('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg')):
        response.cache_control.max_age = 600
        response.cache_control.public = True
        response.cache_control.s_maxage = 600
    # Cache corto para páginas principales (2 minutos)
    elif request.path in ['/', '/iniciopy', '/registrow']:
        response.cache_control.max_age = 120
        response.cache_control.public = True
    # No cache para páginas dinámicas y API
    else:
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
    
    # Seguridad básica para Render
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Server'] = 'CineTec'  # Ocultar información del servidor
    
    return response

# ==================== INICIAR APLICACIÓN OPTIMIZADO PARA RENDER ====================
if __name__ == "__main__":
    # Configuración OPTIMIZADA para Render
    port = int(os.environ.get("PORT", 5000))
    
    print("=" * 60)
    print("🚀 INICIANDO CINETEC - VERSIÓN OPTIMIZADA PARA RENDER")
    print("=" * 60)
    print(f"📊 Puerto: {port}")
    print(f"✅ MongoDB: {'CONECTADO' if mongo_disponible else 'DESCONECTADO'}")
    if mongo_disponible:
        print(f"📈 Pool de conexiones: 2-10 conexiones simultáneas")
        print(f"⚡ Timeouts: Conectar=15s, Operaciones=20s")
    print(f"🔗 Health Check: http://localhost:{port}/health")
    print(f"🔗 Estado del sistema: http://localhost:{port}/status")
    print("=" * 60)
    print("✨ Configuración aplicada:")
    print("   • TLS/SSL habilitado con certificados")
    print("   • Pool de conexiones optimizado para Render")
    print("   • Timeouts aumentados para red de Render")
    print("   • Caché extendido para archivos estáticos")
    print("=" * 60)
    
    # ⚡ CONFIGURACIÓN DE PRODUCCIÓN PARA RENDER:
    app.run(
        host="0.0.0.0",      # Aceptar conexiones de cualquier IP
        port=port,           # Puerto definido por Render
        debug=False,         # IMPORTANTE: False en producción
        threaded=True,       # Atender múltiples solicitudes
        use_reloader=False,  # Evitar problemas en Render
        # ⚡ Nuevos parámetros para mejor rendimiento:
        processes=1,         # Usar 1 proceso (Render maneja la escalabilidad)
        load_dotenv=False    # Ya cargamos .env al inicio
    )