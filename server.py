from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient, ReturnDocument
from bson import ObjectId
import os
from datetime import datetime
import hashlib
import base64
from werkzeug.utils import secure_filename
import re

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_temporal_123")

# Configuración para subir imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== CONEXIÓN MONGODB ====================
def get_mongo_client():
    """Función para obtener conexión a MongoDB"""
    try:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("No se encontró MONGODB_URI en las variables de entorno")
        
        client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  # Test de conexión
        return client
    except Exception as e:
        print(f"❌ Error de conexión MongoDB: {e}")
        return None

def init_database():
    """Inicializar la base de datos si no existe"""
    client = get_mongo_client()
    if client:
        db = client.cineTecDB
        
        # Crear colecciones si no existen
        collections = db.list_collection_names()
        
        if 'usuarios' not in collections:
            db.create_collection('usuarios')
            print("✅ Colección 'usuarios' creada")
        
        if 'peliculas' not in collections:
            db.create_collection('peliculas')
            print("✅ Colección 'peliculas' creada")
            
            # Insertar películas de ejemplo
            peliculas_ejemplo = get_peliculas_ejemplo()
            db.peliculas.insert_many(peliculas_ejemplo)
            print("✅ Películas de ejemplo insertadas")
        
        if 'comentarios' not in collections:
            db.create_collection('comentarios')
            print("✅ Colección 'comentarios' creada")
        
        if 'calificaciones' not in collections:
            db.create_collection('calificaciones')
            print("✅ Colección 'calificaciones' creada")
        
        client.close()
        return True
    return False

def get_peliculas_ejemplo():
    """Datos de ejemplo para películas"""
    return [
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
        # ... (agrega las otras 18 películas similares)
    ]

# ==================== FUNCIONES AUXILIARES ====================
def hash_password(password):
    """Convierte contraseña a hash"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Validar formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_name(name):
    """Validar que solo contenga letras y espacios"""
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$'
    return re.match(pattern, name) is not None

def validate_username(username):
    """Validar formato de usuario"""
    pattern = r'^[a-zA-Z0-9_]{3,20}$'
    return re.match(pattern, username) is not None

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
    
    client = get_mongo_client()
    if client:
        db = client.cineTecDB
        
        # Obtener datos del usuario
        usuario_data = db.usuarios.find_one({"usuario": session['usuario']})
        
        # Obtener películas
        peliculas = list(db.peliculas.find())
        
        # Obtener calificaciones del usuario
        calificaciones_usuario = {}
        calificaciones = db.calificaciones.find({"usuario": session['usuario']})
        for cal in calificaciones:
            calificaciones_usuario[cal['pelicula']] = cal['calificacion']
        
        # Obtener películas favoritas del usuario
        favoritos_usuario = usuario_data.get('favoritos', []) if usuario_data else []
        
        # Obtener comentarios para cada película
        peliculas_con_comentarios = []
        for pelicula in peliculas:
            comentarios = list(db.comentarios.find({"pelicula": pelicula['titulo']}).sort("fecha", -1).limit(5))
            peliculas_con_comentarios.append({
                **pelicula,
                'comentarios': comentarios,
                'calificacion_usuario': calificaciones_usuario.get(pelicula['titulo'], 0),
                'es_favorita': pelicula['titulo'] in favoritos_usuario
            })
        
        client.close()
        
        return render_template("pelispy.html", 
                             usuario=session.get('usuario'),
                             descripcion=usuario_data.get('descripcion', ''),
                             foto_perfil=usuario_data.get('foto_perfil', ''),
                             peliculas=peliculas_con_comentarios)
    
    flash("Error de conexión a la base de datos", "error")
    return redirect(url_for('iniciopy'))

@app.route("/health")
def health_check():
    """Endpoint para verificar que el servidor funciona"""
    return jsonify({"status": "ok", "message": "Servidor funcionando"}), 200

# ==================== REGISTRO ====================
@app.route("/register", methods=["POST"])
def register():
    usuario = request.form.get("usuario", "").strip()
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()
    
    # Validaciones
    if not all([usuario, nombre, email, password]):
        flash("Todos los campos son requeridos", "error")
        return redirect(url_for('registrow'))
    
    if not validate_username(usuario):
        flash("Usuario inválido. Solo letras, números y guiones bajos (3-20 caracteres)", "error")
        return redirect(url_for('registrow'))
    
    if not validate_name(nombre):
        flash("Nombre inválido. Solo letras y espacios", "error")
        return redirect(url_for('registrow'))
    
    if not validate_email(email):
        flash("Email inválido. Debe tener formato: usuario@dominio.com", "error")
        return redirect(url_for('registrow'))
    
    if len(password) < 8:
        flash("La contraseña debe tener al menos 8 caracteres", "error")
        return redirect(url_for('registrow'))
    
    client = get_mongo_client()
    if not client:
        flash("Error de conexión a la base de datos. Intenta más tarde.", "error")
        return redirect(url_for('registrow'))
    
    try:
        db = client.cineTecDB
        
        # Verificar si usuario ya existe
        if db.usuarios.find_one({"usuario": usuario}):
            flash("El usuario ya existe", "error")
            client.close()
            return redirect(url_for('registrow'))
        
        # Verificar si email ya existe
        if db.usuarios.find_one({"email": email}):
            flash("El email ya está registrado", "error")
            client.close()
            return redirect(url_for('registrow'))
        
        # Crear nuevo usuario
        nuevo_usuario = {
            "usuario": usuario,
            "nombre": nombre,
            "email": email,
            "password": hash_password(password),
            "descripcion": "Hola, soy nuevo en CineTec!",
            "foto_perfil": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
            "fecha_registro": datetime.now(),
            "favoritos": [],
            "rol": "usuario"
        }
        
        db.usuarios.insert_one(nuevo_usuario)
        client.close()
        
        flash("¡Registro exitoso! Ahora puedes iniciar sesión", "success")
        return redirect(url_for('iniciopy'))
        
    except Exception as e:
        client.close()
        flash(f"Error en el registro: {str(e)}", "error")
        return redirect(url_for('registrow'))

# ==================== LOGIN ====================
@app.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "").strip()
    
    if not usuario or not password:
        flash("Usuario y contraseña requeridos", "error")
        return redirect(url_for('iniciopy'))
    
    client = get_mongo_client()
    if not client:
        flash("Error de conexión a la base de datos", "error")
        return redirect(url_for('iniciopy'))
    
    try:
        db = client.cineTecDB
        
        # Buscar usuario
        usuario_data = db.usuarios.find_one({"usuario": usuario})
        
        if usuario_data and usuario_data["password"] == hash_password(password):
            # Configurar sesión
            session['usuario'] = usuario_data["usuario"]
            session['nombre'] = usuario_data["nombre"]
            session['user_id'] = str(usuario_data["_id"])
            
            flash(f"¡Bienvenido {usuario_data['nombre']}!", "success")
            client.close()
            return redirect(url_for('pelispy'))
        else:
            flash("Usuario o contraseña incorrectos", "error")
            client.close()
            return redirect(url_for('iniciopy'))
            
    except Exception as e:
        client.close()
        flash(f"Error en el inicio de sesión: {str(e)}", "error")
        return redirect(url_for('iniciopy'))

# ==================== ACTUALIZAR PERFIL ====================
@app.route("/update_profile", methods=["POST"])
def update_profile():
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    descripcion = request.form.get("descripcion", "").strip()
    
    client = get_mongo_client()
    if not client:
        return jsonify({"error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Actualizar descripción
        db.usuarios.update_one(
            {"usuario": session['usuario']},
            {"$set": {"descripcion": descripcion}}
        )
        
        client.close()
        return jsonify({"success": True, "message": "Perfil actualizado"})
        
    except Exception as e:
        client.close()
        return jsonify({"error": str(e)}), 500

# ==================== SUBIR FOTO ====================
@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    if 'foto' not in request.files:
        return jsonify({"error": "No se envió archivo"}), 400
    
    file = request.files['foto']
    
    if file.filename == '':
        return jsonify({"error": "No se seleccionó archivo"}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Convertir imagen a base64 para guardar en MongoDB
            file_data = file.read()
            foto_base64 = base64.b64encode(file_data).decode('utf-8')
            
            client = get_mongo_client()
            if not client:
                return jsonify({"error": "Error de conexión"}), 500
            
            db = client.cineTecDB
            
            # Guardar en MongoDB como string base64
            db.usuarios.update_one(
                {"usuario": session['usuario']},
                {"$set": {
                    "foto_perfil": f"data:image/jpeg;base64,{foto_base64}",
                    "foto_actualizada": datetime.now()
                }}
            )
            
            client.close()
            
            return jsonify({
                "success": True, 
                "message": "Foto actualizada",
                "foto_url": f"data:image/jpeg;base64,{foto_base64}"
            })
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Formato de archivo no permitido"}), 400

# ==================== CALIFICAR PELÍCULA ====================
@app.route("/rate_movie", methods=["POST"])
def rate_movie():
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    data = request.get_json()
    pelicula = data.get('pelicula')
    calificacion = data.get('calificacion')
    
    if not pelicula or not calificacion:
        return jsonify({"error": "Datos incompletos"}), 400
    
    try:
        calificacion = int(calificacion)
        if calificacion < 1 or calificacion > 5:
            return jsonify({"error": "Calificación debe ser entre 1 y 5"}), 400
    except:
        return jsonify({"error": "Calificación inválida"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Guardar calificación del usuario
        db.calificaciones.update_one(
            {
                "usuario": session['usuario'],
                "pelicula": pelicula
            },
            {
                "$set": {
                    "calificacion": calificacion,
                    "fecha": datetime.now()
                }
            },
            upsert=True
        )
        
        # Recalcular promedio de la película
        calificaciones = list(db.calificaciones.find({"pelicula": pelicula}))
        if calificaciones:
            total = sum(c['calificacion'] for c in calificaciones)
            promedio = total / len(calificaciones)
            
            db.peliculas.update_one(
                {"titulo": pelicula},
                {
                    "$set": {
                        "calificacion_promedio": round(promedio, 1),
                        "total_calificaciones": len(calificaciones)
                    }
                }
            )
        
        client.close()
        return jsonify({
            "success": True, 
            "message": "Calificación guardada",
            "promedio": promedio if 'promedio' in locals() else 0
        })
        
    except Exception as e:
        client.close()
        return jsonify({"error": str(e)}), 500

# ==================== AGREGAR/QUITAR FAVORITOS ====================
@app.route("/toggle_favorite", methods=["POST"])
def toggle_favorite():
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    data = request.get_json()
    pelicula = data.get('pelicula')
    
    if not pelicula:
        return jsonify({"error": "Película requerida"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        usuario = db.usuarios.find_one({"usuario": session['usuario']})
        favoritos = usuario.get('favoritos', [])
        
        if pelicula in favoritos:
            # Quitar de favoritos
            favoritos.remove(pelicula)
            mensaje = "Película eliminada de favoritos"
        else:
            # Agregar a favoritos
            favoritos.append(pelicula)
            mensaje = "Película agregada a favoritos"
        
        db.usuarios.update_one(
            {"usuario": session['usuario']},
            {"$set": {"favoritos": favoritos}}
        )
        
        client.close()
        return jsonify({
            "success": True, 
            "message": mensaje,
            "es_favorita": pelicula not in favoritos  # Estado después del cambio
        })
        
    except Exception as e:
        client.close()
        return jsonify({"error": str(e)}), 500

# ==================== AGREGAR COMENTARIO ====================
@app.route("/add_comment", methods=["POST"])
def add_comment():
    if 'usuario' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    data = request.get_json()
    pelicula = data.get('pelicula')
    comentario = data.get('comentario', '').strip()
    
    if not pelicula or not comentario:
        return jsonify({"error": "Datos incompletos"}), 400
    
    if len(comentario) > 500:
        return jsonify({"error": "Comentario muy largo (máx 500 caracteres)"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        nuevo_comentario = {
            "usuario": session['usuario'],
            "nombre_usuario": session.get('nombre', 'Anónimo'),
            "pelicula": pelicula,
            "comentario": comentario,
            "fecha": datetime.now(),
            "likes": 0,
            "dislikes": 0
        }
        
        db.comentarios.insert_one(nuevo_comentario)
        
        # Obtener comentario recién insertado con ID
        nuevo_comentario['_id'] = str(nuevo_comentario['_id'])
        nuevo_comentario['fecha'] = nuevo_comentario['fecha'].strftime("%d/%m/%Y %H:%M")
        
        client.close()
        
        return jsonify({
            "success": True, 
            "message": "Comentario agregado",
            "comentario": nuevo_comentario
        })
        
    except Exception as e:
        client.close()
        return jsonify({"error": str(e)}), 500

# ==================== OBTENER COMENTARIOS ====================
@app.route("/get_comments/<pelicula>", methods=["GET"])
def get_comments(pelicula):
    client = get_mongo_client()
    if not client:
        return jsonify({"error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        comentarios = list(db.comentarios.find({"pelicula": pelicula})
                          .sort("fecha", -1)
                          .limit(20))
        
        # Convertir ObjectId a string y formatear fecha
        for comentario in comentarios:
            comentario['_id'] = str(comentario['_id'])
            comentario['fecha'] = comentario['fecha'].strftime("%d/%m/%Y %H:%M")
        
        client.close()
        
        return jsonify({
            "success": True,
            "comentarios": comentarios
        })
        
    except Exception as e:
        client.close()
        return jsonify({"error": str(e)}), 500

# ==================== LOGOUT ====================
@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('index'))

# ==================== INICIALIZAR APLICACIÓN ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🎬 INICIANDO CINETEC - SISTEMA DE PELÍCULAS")
    print("=" * 60)
    
    # Inicializar base de datos
    print("📊 Inicializando base de datos...")
    if init_database():
        print("✅ Base de datos inicializada correctamente")
    else:
        print("⚠️ No se pudo inicializar la base de datos")
    
    port = int(os.environ.get("PORT", 10000))
    
    print(f"🌐 Servidor en: http://localhost:{port}")
    print(f"🔧 Puerto: {port}")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print("=" * 60)
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )