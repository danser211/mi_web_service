from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson import ObjectId
import os
from datetime import datetime
import hashlib
import base64
import re

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_temporal_123")

# Configuración para subir imágenes
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== CONEXIÓN MONGODB ====================
def get_mongo_client():
    """Función para obtener conexión a MongoDB"""
    try:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("No se encontró MONGODB_URI en las variables de entorno")
        
        client = MongoClient(mongodb_uri, 
                           serverSelectionTimeoutMS=5000,
                           connectTimeoutMS=5000,
                           retryWrites=True,
                           w='majority')
        
        # Test de conexión
        client.admin.command('ping')
        print("✅ Conexión MongoDB exitosa")
        return client
    except Exception as e:
        print(f"❌ Error de conexión MongoDB: {e}")
        return None

# ==================== DICCIONARIO DE PELÍCULAS ====================
# Información completa de todas las películas
PELICULAS_INFO = {
    "El Resplandor": {
        "titulo": "El Resplandor",
        "portada": "https://m.media-amazon.com/images/M/MV5BZWFlYmY2MGEtZjVkYS00YzU4LTg0YjQtYzY1ZGE3NTA5NGQxXkEyXkFqcGdeQXVyMTQxNzMzNDI@._V1_.jpg",
        "plataforma": "Amazon Prime",
        "descripcion": "Un escritor acepta un trabajo de cuidador en un hotel aislado durante el invierno, donde su cordura se desmorona lentamente."
    },
    "El Padrino": {
        "titulo": "El Padrino",
        "portada": "https://m.media-amazon.com/images/M/MV5BM2MyNjYxNmUtYTAwNi00MTYxLWJmNWYtYzZlODY3ZTk3OTFlXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg",
        "plataforma": "Netflix",
        "descripcion": "La saga de la familia Corleone, una poderosa dinastía de la mafia italiana en Nueva York."
    },
    "El Caballero Oscuro": {
        "titulo": "El Caballero Oscuro",
        "portada": "https://m.media-amazon.com/images/M/MV5BMTMxNTMwODM0NF5BMl5BanBnXkFtZTcwODAyMTk2Mw@@._V1_.jpg",
        "plataforma": "HBO Max",
        "descripcion": "Batman se enfrenta al Joker, un criminal psicótico que quiere sumir a Gotham en la anarquía."
    },
    "La Lista de Schindler": {
        "titulo": "La Lista de Schindler",
        "portada": "https://m.media-amazon.com/images/M/MV5BNDE4OTMxMTctNmRhYy00NWE2LTg3YzItYTk3M2UwOTU5Njg4XkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg",
        "plataforma": "Disney+",
        "descripcion": "Un empresario alemán salva a más de mil refugiados judíos durante el Holocausto."
    },
    "Matrix": {
        "titulo": "Matrix",
        "portada": "https://m.media-amazon.com/images/M/MV5BNzQzOTk3OTAtNDQ0Zi00ZTVkLWI0MTEtMDllZjNkYzNjNTc4L2ltYWdlXkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg",
        "plataforma": "HBO Max",
        "descripcion": "Un hacker descubre que su realidad es una simulación creada por máquinas inteligentes."
    },
    "Origen": {
        "titulo": "Origen",
        "portada": "https://m.media-amazon.com/images/M/MV5BMjAxMzY3NjcxNF5BMl5BanBnXkFtZTcwNTI5OTM0Mw@@._V1_.jpg",
        "plataforma": "Netflix",
        "descripcion": "Un ladrón que roba secretos corporativos mediante el uso de tecnología para compartir sueños."
    },
    "Pulp Fiction": {
        "titulo": "Pulp Fiction",
        "portada": "https://m.media-amazon.com/images/M/MV5BNGNhMDIzZTUtNTBlZi00MTRlLWFjM2ItYzViMjE3YzI5MjljXkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg",
        "plataforma": "Amazon Prime",
        "descripcion": "Las vidas de dos matones, un boxeador y una pareja de atracadores se entrelazan."
    },
    "El Señor de los Anillos": {
        "titulo": "El Señor de los Anillos",
        "portada": "https://m.media-amazon.com/images/M/MV5BN2EyZjM3NzUtNWUzMi00MTgxLWI0NTctMzY4M2VlOTdjZWRiXkEyXkFqcGdeQXVyNDUzOTQ5MjY@._V1_.jpg",
        "plataforma": "HBO Max",
        "descripcion": "Un hobbit debe destruir un anillo poderoso en el Monte del Destino para salvar la Tierra Media."
    },
    "Forrest Gump": {
        "titulo": "Forrest Gump",
        "portada": "https://m.media-amazon.com/images/M/MV5BNWIwODRlZTUtY2U3ZS00Yzg1LWJhNzYtMmZiYmEyNmU1NjMzXkEyXkFqcGdeQXVyMTQxNzMzNDI@._V1_.jpg",
        "plataforma": "Netflix",
        "descripcion": "La vida de un hombre con discapacidad intelectual que vive eventos históricos cruciales."
    },
    "Interestelar": {
        "titulo": "Interestelar",
        "portada": "https://m.media-amazon.com/images/M/MV5BZjdkOTU3MDktN2IxOS00OGEyLWFmMjktY2FiMmZkNWIyODZiXkEyXkFqcGdeQXVyMTMxODk2OTU@._V1_.jpg",
        "plataforma": "Amazon Prime",
        "descripcion": "Un grupo de exploradores viaja a través de un agujero de gusano en el espacio para asegurar la supervivencia humana."
    },
    "El Rey León": {
        "titulo": "El Rey León",
        "portada": "https://m.media-amazon.com/images/M/MV5BYTYxNGMyZTYtMjE3MS00MzNjLWFjNmYtMDk3N2FmM2JiM2M1XkEyXkFqcGdeQXVyNjY5NDU4NzI@._V1_.jpg",
        "plataforma": "Disney+",
        "descripcion": "Simba, un león joven, debe reclamar su lugar como rey después de la muerte de su padre."
    },
    "Gladiador": {
        "titulo": "Gladiador",
        "portada": "https://m.media-amazon.com/images/M/MV5BMDliMmNhNDEtODUyOS00MjNlLTgxODEtN2U3NzIxMGVkZTA1L2ltYWdlXkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg",
        "plataforma": "Netflix",
        "descripcion": "Un general romano traicionado se convierte en gladiador para vengar la muerte de su familia."
    },
    "Reservoir Dogs": {
        "titulo": "Reservoir Dogs",
        "portada": "https://m.media-amazon.com/images/M/MV5BZmExNmEwYWItYmQzOS00YjA5LTk2MjktZjEyZDE1Y2QxNjA1XkEyXkFqcGdeQXVyMTQxNzMzNDI@._V1_.jpg",
        "plataforma": "Amazon Prime",
        "descripcion": "Después de un robo fallido, los criminales sospechan que hay un informante entre ellos."
    },
    "Titanic": {
        "titulo": "Titanic",
        "portada": "https://m.media-amazon.com/images/M/MV5BMDdmZGU3NDQtY2E5My00ZTliLWIzOTUtMTY4ZGI1YjdiNjk3XkEyXkFqcGdeQXVyNTA4NzY1MzY@._V1_.jpg",
        "plataforma": "Netflix",
        "descripcion": "Una joven de alta sociedad y un artista pobre se enamoran a bordo del lujoso trasatlántico."
    },
    "Jurassic Park": {
        "titulo": "Jurassic Park",
        "portada": "https://m.media-amazon.com/images/M/MV5BMjM2MDgxMDg0Nl5BMl5BanBnXkFtZTgwNTM2OTM5NDE@._V1_.jpg",
        "plataforma": "Amazon Prime",
        "descripcion": "Un parque temático con dinosaurios clonados se convierte en una pesadilla cuando los animales escapan."
    },
    "El Silencio de los Inocentes": {
        "titulo": "El Silencio de los Inocentes",
        "portada": "https://m.media-amazon.com/images/M/MV5BNjNhZTk0ZmEtNjJhMi00YzFlLWE1MmEtYzM1M2ZmMGMwMTU4XkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg",
        "plataforma": "HBO Max",
        "descripcion": "Una joven agente del FBI busca la ayuda de un brillante asesino en serie para atrapar a otro."
    },
    "Star Wars": {
        "titulo": "Star Wars: Una Nueva Esperanza",
        "portada": "https://m.media-amazon.com/images/M/MV5BNzVlY2MwMjktM2E4OS00Y2Y3LWE3ZjctYzhkZGM3YzA1ZWM2XkEyXkFqcGdeQXVyNzkwMjQ5NzM@._V1_.jpg",
        "plataforma": "Disney+",
        "descripcion": "Luke Skywalker se une a la rebelión para rescatar a la princesa Leia y derrotar al Imperio Galáctico."
    },
    "Terminator 2": {
        "titulo": "Terminator 2: El Juicio Final",
        "portada": "https://m.media-amazon.com/images/M/MV5BMGU2NzRmZjUtOGUxYS00ZjdjLWEwZWItY2NlM2JhNjkxNTFmXkEyXkFqcGdeQXVyNjU0OTQ0OTY@._V1_.jpg",
        "plataforma": "Netflix",
        "descripcion": "Un cyborg es enviado del futuro para proteger al joven John Connor de un Terminator más avanzado."
    },
    "Avatar": {
        "titulo": "Avatar",
        "portada": "https://m.media-amazon.com/images/M/MV5BMTYwOTEwNjAzMl5BMl5BanBnXkFtZTcwODc5MTUwMw@@._V1_.jpg",
        "plataforma": "Disney+",
        "descripcion": "Un marine parapléjico es enviado a la luna Pandora en una misión única, pero se enfrenta a un dilema moral."
    },
    "El Gran Hotel Budapest": {
        "titulo": "El Gran Hotel Budapest",
        "portada": "https://m.media-amazon.com/images/M/MV5BMzM5NjUxOTEyMl5BMl5BanBnXkFtZTgwNjEyMDM0MDE@._V1_.jpg",
        "plataforma": "Amazon Prime",
        "descripcion": "Las aventuras de Gustave H, un legendario conserje de hotel, y Zero Moustafa, su joven amigo."
    }
}

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

# ==================== LOGIN MEJORADO ====================
@app.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "").strip()
    
    print(f"\n🔐 Intento de login para usuario: {usuario}")
    
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
        
        if not usuario_data:
            print(f"❌ Usuario no encontrado: {usuario}")
            flash("Usuario o contraseña incorrectos", "error")
            client.close()
            return redirect(url_for('iniciopy'))
        
        # Verificar contraseña
        password_hash = hash_password(password)
        if usuario_data["password"] != password_hash:
            print(f"❌ Contraseña incorrecta para: {usuario}")
            flash("Usuario o contraseña incorrectos", "error")
            client.close()
            return redirect(url_for('iniciopy'))
        
        # ÉXITO: Configurar sesión PERO SIN FOTO en base64
        session['usuario'] = usuario_data["usuario"]
        session['nombre'] = usuario_data["nombre"]
        session['user_id'] = str(usuario_data["_id"])
        session['descripcion'] = usuario_data.get('descripcion', 'Hola, soy nuevo en CineTec')
        
        # NO guardar la foto completa en la sesión, solo la URL si no es base64
        foto_perfil = usuario_data.get('foto_perfil', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
        if foto_perfil.startswith('http'):
            session['foto_perfil'] = foto_perfil
        else:
            # Si es base64, usar la default para no inflar la cookie
            session['foto_perfil'] = 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'
        
        session['favoritos'] = usuario_data.get('favoritos', [])
        
        print(f"✅ Login exitoso para: {usuario}")
        print(f"✅ Sesión establecida (tamaño reducido)")
        
        flash(f"¡Bienvenido {usuario_data['nombre']}!", "success")
        client.close()
        return redirect(url_for('pelispy'))
            
    except Exception as e:
        print(f"❌ Error en login: {e}")
        client.close()
        flash(f"Error en el inicio de sesión: {str(e)}", "error")
        return redirect(url_for('iniciopy'))

# ==================== PELISPY ====================
@app.route("/pelispy")
def pelispy():
    if 'usuario' not in session:
        print("❌ No hay sesión, redirigiendo a login")
        flash("Debes iniciar sesión primero", "error")
        return redirect(url_for('iniciopy'))
    
    print(f"✅ Usuario autenticado: {session['usuario']}")
    
    client = get_mongo_client()
    if not client:
        flash("Error de conexión a la base de datos", "error")
        return redirect(url_for('iniciopy'))
    
    try:
        db = client.cineTecDB
        
        # Verificar que el usuario aún existe
        usuario_data = db.usuarios.find_one({"usuario": session['usuario']})
        if not usuario_data:
            print(f"❌ Usuario no encontrado en DB: {session['usuario']}")
            session.clear()
            flash("Tu cuenta ya no existe", "error")
            return redirect(url_for('iniciopy'))
        
        # Obtener datos actualizados del usuario
        descripcion_actual = usuario_data.get('descripcion', 'Hola, soy nuevo en CineTec')
        foto_actual = usuario_data.get('foto_perfil', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png')
        favoritos_actual = usuario_data.get('favoritos', [])
        
        # Obtener películas usando el diccionario PELICULAS_INFO
        peliculas = []
        for titulo, info in PELICULAS_INFO.items():
            pelicula_info = {
                'titulo': titulo,
                'descripcion': info.get('descripcion', ''),
                'portada': info.get('portada', ''),
                'plataforma': info.get('plataforma', ''),
                'calificacion_promedio': 0,
                'total_calificaciones': 0
            }
            
            # Intentar obtener calificaciones desde MongoDB
            try:
                calificacion_data = db.calificaciones.aggregate([
                    {'$match': {'pelicula': titulo}},
                    {'$group': {
                        '_id': '$pelicula',
                        'promedio': {'$avg': '$calificacion'},
                        'total_votos': {'$sum': 1}
                    }}
                ])
                
                calificacion_result = list(calificacion_data)
                if calificacion_result:
                    pelicula_info['calificacion_promedio'] = round(calificacion_result[0]['promedio'], 1)
                    pelicula_info['total_calificaciones'] = calificacion_result[0]['total_votos']
            except Exception as e:
                print(f"⚠️ Error obteniendo calificaciones para {titulo}: {e}")
                # Continuar con valores por defecto
            
            peliculas.append(pelicula_info)
        
        # Obtener calificaciones del usuario actual
        calificaciones_usuario = {}
        try:
            user_ratings = db.calificaciones.find({"usuario": session['usuario']})
            for cal in user_ratings:
                calificaciones_usuario[cal['pelicula']] = cal['calificacion']
        except Exception as e:
            print(f"⚠️ Error obteniendo calificaciones del usuario: {e}")
        
        # Crear diccionarios de promedios y total_votos
        promedios = {}
        total_votos = {}
        for pelicula in peliculas:
            promedios[pelicula['titulo']] = pelicula.get('calificacion_promedio', 0)
            total_votos[pelicula['titulo']] = pelicula.get('total_calificaciones', 0)
        
        client.close()
        
        print(f"✅ Datos cargados: {len(peliculas)} películas, {len(favoritos_actual)} favoritos")
        
        # Renderizar el template con los datos
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
        import traceback
        traceback.print_exc()  # Esto mostrará el error completo en la consola
        
        if 'client' in locals():
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
    
    print(f"\n📝 Intento de registro: {usuario}")
    
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
        
        print(f"✅ Registro exitoso: {usuario}")
        flash("¡Registro exitoso! Ahora puedes iniciar sesión", "success")
        return redirect(url_for('iniciopy'))
        
    except Exception as e:
        client.close()
        print(f"❌ Error en registro: {e}")
        flash(f"Error en el registro: {str(e)}", "error")
        return redirect(url_for('registrow'))

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
                # NO actualizar la sesión con la foto base64
                # Solo actualizamos en MongoDB, la sesión mantiene la URL default
                
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
        else:
            promedio = 0
        
        client.close()
        return jsonify({
            "success": True, 
            "message": "Calificación guardada",
            "promedio": round(promedio, 1),
            "total_votos": len(calificaciones)
        })
        
    except Exception as e:
        client.close()
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== FAVORITOS - TOGGLE ====================
@app.route("/toggle_favorite", methods=["POST"])
def toggle_favorite():
    """Agrega o elimina una película de favoritos en MongoDB"""
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
    """Obtiene las películas favoritas del usuario desde MongoDB"""
    try:
        # Verificar si el usuario está en sesión
        if 'usuario' not in session:
            return jsonify({
                'success': False,
                'error': 'Usuario no autenticado'
            }), 401
        
        # Obtener usuario de la sesión
        usuario_actual = session['usuario']
        
        client = get_mongo_client()
        if not client:
            return jsonify({
                'success': False,
                'error': 'Error de conexión a MongoDB'
            }), 500
        
        db = client.cineTecDB
        
        # Buscar usuario en MongoDB
        usuario = db.usuarios.find_one({'usuario': usuario_actual})
        
        if not usuario:
            client.close()
            return jsonify({
                'success': False,
                'error': 'Usuario no encontrado en la base de datos'
            }), 404
        
        # Obtener lista de favoritos del usuario
        favoritos_usuario = usuario.get('favoritos', [])
        
        # Si no hay favoritos, retornar lista vacía
        if not favoritos_usuario:
            client.close()
            return jsonify({
                'success': True,
                'favoritas': [],
                'total': 0,
                'message': 'No tienes películas favoritas todavía'
            })
        
        # Obtener información completa de cada película favorita
        peliculas_favoritas = []
        
        for pelicula_nombre in favoritos_usuario:
            if pelicula_nombre in PELICULAS_INFO:
                pelicula_info = PELICULAS_INFO[pelicula_nombre].copy()
                
                # Obtener calificación promedio de la película desde la colección de calificaciones
                try:
                    calificacion_data = db.calificaciones.aggregate([
                        {'$match': {'pelicula': pelicula_nombre}},
                        {'$group': {
                            '_id': '$pelicula',
                            'promedio': {'$avg': '$calificacion'},
                            'total_votos': {'$sum': 1}
                        }}
                    ])
                    
                    calificacion_result = list(calificacion_data)
                    if calificacion_result:
                        pelicula_info['calificacion_promedio'] = calificacion_result[0]['promedio']
                        pelicula_info['total_votos'] = calificacion_result[0]['total_votos']
                    else:
                        pelicula_info['calificacion_promedio'] = 0
                        pelicula_info['total_votos'] = 0
                except:
                    pelicula_info['calificacion_promedio'] = 0
                    pelicula_info['total_votos'] = 0
                
                peliculas_favoritas.append(pelicula_info)
        
        client.close()
        return jsonify({
            'success': True,
            'favoritas': peliculas_favoritas,
            'total': len(peliculas_favoritas),
            'message': f'Tienes {len(peliculas_favoritas)} películas favoritas'
        })
        
    except Exception as e:
        print(f"❌ Error en get_favorites: {str(e)}")
        if 'client' in locals():
            client.close()
        return jsonify({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        }), 500

# ==================== OBTENER TODAS LAS CALIFICACIONES ====================
@app.route("/get_all_ratings", methods=["GET"])
def get_all_ratings():
    client = get_mongo_client()
    if not client:
        return jsonify({"success": False, "error": "Error de conexión"}), 500
    
    try:
        db = client.cineTecDB
        
        # Agregar pipeline de agregación para obtener promedios
        pipeline = [
            {
                '$group': {
                    '_id': '$pelicula',
                    'promedio': {'$avg': '$calificacion'},
                    'total_votos': {'$sum': 1}
                }
            }
        ]
        
        resultados = list(db.calificaciones.aggregate(pipeline))
        
        ratings = {}
        for resultado in resultados:
            ratings[resultado['_id']] = {
                'promedio': round(resultado['promedio'], 1),
                'total_votos': resultado['total_votos']
            }
        
        client.close()
        return jsonify({'success': True, 'ratings': ratings})
        
    except Exception as e:
        print(f"❌ Error en get_all_ratings: {str(e)}")
        client.close()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== OBTENER DATOS DEL USUARIO ====================
@app.route("/get_user_preferences", methods=["GET"])
def get_user_preferences():
    """Obtiene todas las preferencias del usuario desde MongoDB"""
    try:
        if 'usuario' not in session:
            return jsonify({'success': False, 'error': 'No autenticado'}), 401
        
        usuario_actual = session['usuario']
        
        client = get_mongo_client()
        if not client:
            return jsonify({'success': False, 'error': 'Error de conexión'}), 500
        
        db = client.cineTecDB
        
        # Obtener datos del usuario
        usuario_data = db.usuarios.find_one({'usuario': usuario_actual})
        
        if not usuario_data:
            client.close()
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        
        # Obtener favoritos
        favoritos = usuario_data.get('favoritos', [])
        
        # Obtener calificaciones del usuario
        calificaciones_usuario = {}
        calificaciones = db.calificaciones.find({'usuario': usuario_actual})
        for calif in calificaciones:
            calificaciones_usuario[calif['pelicula']] = calif['calificacion']
        
        # Obtener promedios generales de todas las películas
        promedios = {}
        total_votos = {}
        pipeline = [
            {
                '$group': {
                    '_id': '$pelicula',
                    'promedio': {'$avg': '$calificacion'},
                    'total_votos': {'$sum': 1}
                }
            }
        ]
        
        resultados = list(db.calificaciones.aggregate(pipeline))
        for resultado in resultados:
            promedios[resultado['_id']] = round(resultado['promedio'], 1)
            total_votos[resultado['_id']] = resultado['total_votos']
        
        client.close()
        
        return jsonify({
            'success': True,
            'descripcion': usuario_data.get('descripcion', 'Hola, soy nuevo en CineTec'),
            'foto_perfil': usuario_data.get('foto_perfil', 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png'),
            'favoritos': favoritos,
            'calificaciones': calificaciones_usuario,
            'promedios': promedios,
            'total_votos': total_votos
        })
        
    except Exception as e:
        print(f"❌ Error en get_user_preferences: {str(e)}")
        if 'client' in locals():
            client.close()
        return jsonify({'success': False, 'error': str(e)}), 500

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

# ==================== LOGOUT ====================
@app.route("/logout")
def logout():
    print(f"\n👋 Logout para: {session.get('usuario', 'N/A')}")
    session.clear()
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('index'))

# ==================== HEALTH CHECK ====================
@app.route("/health")
def health_check():
    return jsonify({"status": "ok", "message": "Servidor funcionando"}), 200

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