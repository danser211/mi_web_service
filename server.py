from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson import ObjectId
import os
from datetime import datetime
import hashlib
import base64
import re
import certifi
import urllib.parse

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_temporal_123")

# Configuración para subir imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== CONEXIÓN MONGODB ====================
def get_mongo_client():
    """Función para obtener conexión a MongoDB con certificados SSL"""
    try:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("No se encontró MONGODB_URI en las variables de entorno")
        
        # Usar certifi para certificados SSL
        client = MongoClient(mongodb_uri, 
                           tlsCAFile=certifi.where(),
                           serverSelectionTimeoutMS=10000,
                           connectTimeoutMS=10000,
                           socketTimeoutMS=10000,
                           retryWrites=True,
                           w='majority')
        
        # Test de conexión
        client.admin.command('ping')
        print("✅ Conexión MongoDB exitosa")
        return client
    except Exception as e:
        print(f"❌ Error de conexión MongoDB: {e}")
        return None

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

# ==================== PELISPY - PÁGINA PRINCIPAL ====================
@app.route("/pelispy")
def pelispy():
    if 'usuario' not in session:
        flash("Debes iniciar sesión primero", "error")
        return redirect(url_for('iniciopy'))
    
    client = get_mongo_client()
    if not client:
        flash("Error de conexión a la base de datos", "error")
        return redirect(url_for('iniciopy'))
    
    try:
        db = client.cineTecDB
        
        # Obtener datos del usuario
        usuario_data = db.usuarios.find_one({"usuario": session['usuario']})
        
        if not usuario_data:
            flash("Usuario no encontrado", "error")
            return redirect(url_for('logout'))
        
        # Obtener datos del usuario
        descripcion_actual = usuario_data.get('descripcion', 'Hola, soy nuevo en CineTec')
        foto_actual = usuario_data.get('foto_perfil', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
        favoritos_actual = usuario_data.get('favoritos', [])
        
        # Actualizar sesión
        session['descripcion'] = descripcion_actual
        session['foto_perfil'] = foto_actual
        session['favoritos'] = favoritos_actual
        session['user_id'] = str(usuario_data['_id'])
        
        # Obtener todas las películas
        peliculas = list(db.peliculas.find({}))
        
        # Obtener calificaciones del usuario actual
        calificaciones_usuario = {}
        user_ratings = db.calificaciones.find({"usuario": session['usuario']})
        for cal in user_ratings:
            calificaciones_usuario[cal['pelicula']] = cal['calificacion']
        
        # Obtener promedio de todas las películas
        promedios = {}
        total_votos = {}
        for pelicula in peliculas:
            promedios[pelicula['titulo']] = pelicula.get('calificacion_promedio', 0)
            total_votos[pelicula['titulo']] = pelicula.get('total_calificaciones', 0)
        
        client.close()
        
        return render_template("pelispy.html", 
                             usuario=session['usuario'],
                             descripcion=descripcion_actual,
                             foto_perfil=foto_actual,
                             peliculas=peliculas,
                             promedios=promedios,
                             total_votos=total_votos,
                             favoritos=favoritos_actual,
                             calificaciones_usuario=calificaciones_usuario)
        
    except Exception as e:
        print(f"❌ Error en pelispy: {e}")
        client.close()
        flash("Error al cargar las películas", "error")
        return redirect(url_for('iniciopy'))

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
            session['descripcion'] = usuario_data.get('descripcion', 'Hola, soy nuevo en CineTec')
            session['foto_perfil'] = usuario_data.get('foto_perfil', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
            session['favoritos'] = usuario_data.get('favoritos', [])
            
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

# ==================== ACTUALIZAR ESTADO ====================
@app.route("/update_profile", methods=["POST"])
def update_profile():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    descripcion = request.form.get("descripcion", "").strip()
    
    if not descripcion:
        return jsonify({"success": False, "error": "El estado no puede estar vacío"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión a la base de datos"}), 500
    
    try:
        db = client.cineTecDB
        
        # Actualizar en MongoDB
        resultado = db.usuarios.update_one(
            {"usuario": session['usuario']},
            {"$set": {"descripcion": descripcion}}
        )
        
        if resultado.modified_count > 0 or resultado.matched_count > 0:
            # Actualizar sesión
            session['descripcion'] = descripcion
            
            client.close()
            return jsonify({
                "success": True, 
                "message": "Estado actualizado correctamente",
                "descripcion": descripcion
            })
        else:
            client.close()
            return jsonify({
                "success": False, 
                "message": "No se pudo actualizar el estado"
            })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== SUBIR FOTO ====================
@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    if 'foto' not in request.files:
        return jsonify({"success": False, "error": "No se envió ningún archivo"}), 400
    
    file = request.files['foto']
    
    if file.filename == '':
        return jsonify({"success": False, "error": "No se seleccionó ningún archivo"}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Leer archivo
            file_data = file.read()
            
            # Verificar tamaño
            if len(file_data) > 5 * 1024 * 1024:  # 5MB máximo
                return jsonify({"success": False, "error": "La imagen es demasiado grande (máximo 5MB)"}), 400
            
            # Convertir a base64
            foto_base64 = base64.b64encode(file_data).decode('utf-8')
            foto_url = f"data:image/jpeg;base64,{foto_base64}"
            
            client = get_mongo_client()
            if not client:
                return jsonify({"success": False, "error": "Error de conexión a la base de datos"}), 500
            
            db = client.cineTecDB
            
            # Guardar en MongoDB
            resultado = db.usuarios.update_one(
                {"usuario": session['usuario']},
                {"$set": {"foto_perfil": foto_url}}
            )
            
            if resultado.modified_count > 0 or resultado.matched_count > 0:
                # Actualizar sesión
                session['foto_perfil'] = foto_url
                
                client.close()
                return jsonify({
                    "success": True, 
                    "message": "Foto de perfil actualizada correctamente",
                    "foto_url": foto_url
                })
            else:
                client.close()
                return jsonify({
                    "success": False, 
                    "message": "No se pudo actualizar la foto de perfil"
                })
            
        except Exception as e:
            return jsonify({"success": False, "error": f"Error al procesar la imagen: {str(e)}"}), 500
    
    return jsonify({"success": False, "error": "Formato de archivo no permitido. Solo se permiten: PNG, JPG, JPEG, GIF"}), 400

# ==================== CALIFICAR PELÍCULA ====================
@app.route("/rate_movie", methods=["POST"])
def rate_movie():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    data = request.get_json()
    pelicula = data.get('pelicula')
    calificacion = data.get('calificacion')
    
    if not pelicula or not calificacion:
        return jsonify({"success": False, "error": "Datos incompletos"}), 400
    
    try:
        calificacion = int(calificacion)
        if calificacion < 1 or calificacion > 5:
            return jsonify({"success": False, "error": "Calificación debe ser entre 1 y 5"}), 400
    except:
        return jsonify({"success": False, "error": "Calificación inválida"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
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
                    "fecha": datetime.now(),
                    "nombre_usuario": session.get('nombre', session['usuario'])
                }
            },
            upsert=True
        )
        
        # Recalcular promedio de la película
        calificaciones = list(db.calificaciones.find({"pelicula": pelicula}))
        
        if calificaciones:
            total = sum(c['calificacion'] for c in calificaciones)
            promedio = total / len(calificaciones)
            
            # Actualizar la película
            db.peliculas.update_one(
                {"titulo": pelicula},
                {
                    "$set": {
                        "calificacion_promedio": round(promedio, 1),
                        "total_calificaciones": len(calificaciones)
                    }
                }
            )
            
            # Obtener el promedio actualizado
            pelicula_data = db.peliculas.find_one({"titulo": pelicula})
            promedio_actual = pelicula_data.get('calificacion_promedio', 0)
            total_votos = pelicula_data.get('total_calificaciones', 0)
        else:
            promedio_actual = 0
            total_votos = 0
        
        client.close()
        return jsonify({
            "success": True, 
            "message": "Calificación guardada",
            "promedio": promedio_actual,
            "total_votos": total_votos
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== FAVORITOS ====================
@app.route("/toggle_favorite", methods=["POST"])
def toggle_favorite():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    data = request.get_json()
    pelicula = data.get('pelicula')
    
    if not pelicula:
        return jsonify({"success": False, "error": "Película requerida"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Obtener el usuario actual
        usuario = db.usuarios.find_one({"usuario": session['usuario']})
        if not usuario:
            client.close()
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        favoritos = usuario.get('favoritos', [])
        
        # Verificar si la película ya está en favoritos
        if pelicula in favoritos:
            # Quitar de favoritos
            favoritos.remove(pelicula)
            mensaje = f'"{pelicula}" eliminada de favoritos'
            es_favorita = False
        else:
            # Agregar a favoritos
            favoritos.append(pelicula)
            mensaje = f'"{pelicula}" agregada a favoritos'
            es_favorita = True
        
        # Actualizar en la base de datos
        db.usuarios.update_one(
            {"usuario": session['usuario']},
            {"$set": {"favoritos": favoritos}}
        )
        
        # Actualizar en la sesión
        session['favoritos'] = favoritos
        
        client.close()
        return jsonify({
            "success": True, 
            "message": mensaje,
            "es_favorita": es_favorita,
            "favoritos": favoritos
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== OBTENER FAVORITOS ====================
@app.route("/get_favorites", methods=["GET"])
def get_favorites():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Obtener favoritos del usuario
        usuario = db.usuarios.find_one({"usuario": session['usuario']})
        if not usuario:
            client.close()
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        favoritos = usuario.get('favoritos', [])
        
        # Si no hay favoritos, retornar lista vacía
        if not favoritos:
            client.close()
            return jsonify({
                "success": True,
                "favoritas": [],
                "total": 0,
                "message": "No tienes películas favoritas"
            })
        
        # Obtener información de cada película favorita
        peliculas_favoritas = []
        for titulo in favoritos:
            pelicula = db.peliculas.find_one({"titulo": titulo})
            if pelicula:
                peliculas_favoritas.append({
                    "titulo": pelicula["titulo"],
                    "portada": pelicula.get("portada", ""),
                    "calificacion_promedio": pelicula.get("calificacion_promedio", 0),
                    "descripcion": pelicula.get("descripcion", ""),
                    "plataforma": pelicula.get("plataforma", "")
                })
        
        client.close()
        return jsonify({
            "success": True,
            "favoritas": peliculas_favoritas,
            "total": len(peliculas_favoritas),
            "message": f"Tienes {len(peliculas_favoritas)} películas favoritas"
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== OBTENER TODAS LAS CALIFICACIONES ====================
@app.route("/get_all_ratings", methods=["GET"])
def get_all_ratings():
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Obtener todas las películas con sus promedios
        peliculas = list(db.peliculas.find({}))
        
        ratings_data = {}
        for pelicula in peliculas:
            ratings_data[pelicula['titulo']] = {
                'promedio': pelicula.get('calificacion_promedio', 0),
                'total_votos': pelicula.get('total_calificaciones', 0)
            }
        
        client.close()
        return jsonify({
            "success": True,
            "ratings": ratings_data
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== OBTENER DATOS DEL USUARIO ====================
@app.route("/get_user_preferences", methods=["GET"])
def get_user_preferences():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Obtener datos del usuario
        usuario_data = db.usuarios.find_one({"usuario": session['usuario']})
        
        if not usuario_data:
            client.close()
            return jsonify({"success": False, "error": "Usuario no encontrado"}), 404
        
        # Obtener favoritos
        favoritos = usuario_data.get('favoritos', [])
        
        # Obtener calificaciones del usuario
        calificaciones_usuario = {}
        calificaciones_db = db.calificaciones.find({"usuario": session['usuario']})
        for cal in calificaciones_db:
            calificaciones_usuario[cal['pelicula']] = cal['calificacion']
        
        # Obtener promedios de todas las películas
        promedios = {}
        total_votos = {}
        peliculas = list(db.peliculas.find({}))
        for pelicula in peliculas:
            promedios[pelicula['titulo']] = pelicula.get('calificacion_promedio', 0)
            total_votos[pelicula['titulo']] = pelicula.get('total_calificaciones', 0)
        
        client.close()
        
        return jsonify({
            "success": True,
            "descripcion": usuario_data.get('descripcion', 'Hola, soy nuevo en CineTec'),
            "foto_perfil": usuario_data.get('foto_perfil', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'),
            "favoritos": favoritos,
            "calificaciones": calificaciones_usuario,
            "promedios": promedios,
            "total_votos": total_votos
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== COMENTARIOS ====================
@app.route("/add_comment", methods=["POST"])
def add_comment():
    if 'usuario' not in session:
        return jsonify({"success": False, "error": "No autorizado"}), 401
    
    data = request.get_json()
    pelicula = data.get('pelicula')
    comentario = data.get('comentario', '').strip()
    
    if not pelicula or not comentario:
        return jsonify({"success": False, "error": "Datos incompletos"}), 400
    
    if len(comentario) > 500:
        return jsonify({"success": False, "error": "Comentario muy largo (máx 500 caracteres)"}), 400
    
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        nuevo_comentario = {
            "usuario": session['usuario'],
            "nombre_usuario": session.get('nombre', session['usuario']),
            "pelicula": pelicula,
            "comentario": comentario,
            "fecha": datetime.now(),
            "likes": 0,
            "dislikes": 0
        }
        
        resultado = db.comentarios.insert_one(nuevo_comentario)
        
        nuevo_comentario['_id'] = str(resultado.inserted_id)
        nuevo_comentario['fecha'] = nuevo_comentario['fecha'].strftime("%d/%m/%Y %H:%M")
        
        client.close()
        
        return jsonify({
            "success": True, 
            "message": "Comentario agregado",
            "comentario": nuevo_comentario
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/get_comments/<pelicula>", methods=["GET"])
def get_comments(pelicula):
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        comentarios = list(db.comentarios.find({"pelicula": pelicula})
                          .sort("fecha", -1)
                          .limit(20))
        
        # Formatear comentarios
        comentarios_formateados = []
        for comentario in comentarios:
            comentario['_id'] = str(comentario['_id'])
            comentario['fecha'] = comentario['fecha'].strftime("%d/%m/%Y %H:%M")
            comentarios_formateados.append(comentario)
        
        client.close()
        
        return jsonify({
            "success": True,
            "comentarios": comentarios_formateados
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== HEALTH CHECK ====================
@app.route("/health")
def health_check():
    return jsonify({"status": "ok", "message": "Servidor funcionando"}), 200

# ==================== LOGOUT ====================
@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('index'))

# ==================== MANEJAR ERRORES ====================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# ==================== INICIAR APLICACIÓN ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🎬 INICIANDO CINETEC - SISTEMA DE PELÍCULAS")
    print("=" * 60)
    
    port = int(os.environ.get("PORT", 10000))
    
    print(f"🌐 Servidor en: http://localhost:{port}")
    print(f"🔧 Puerto: {port}")
    print("=" * 60)
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
        threaded=True
    )