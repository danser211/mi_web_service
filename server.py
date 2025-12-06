from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
import os
from datetime import datetime
import hashlib  # Para contraseñas simples

# ==================== CONFIGURACIÓN INICIAL ====================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_temporal_123")

# ==================== CONEXIÓN MONGODB SIMPLIFICADA ====================
try:
    # Obtener la cadena de conexión de Render
    mongodb_uri = os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        print("⚠️ No se encontró MONGODB_URI. Usando modo temporal.")
        raise ValueError("No hay conexión a MongoDB")
    
    print("🔗 Conectando a MongoDB...")
    
    # Conexión MUY simple
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
    
    # Probar conexión
    client.admin.command('ping')
    print("✅ ¡CONEXIÓN EXITOSA a MongoDB!")
    
    # Usar base de datos
    db = client.cineTecDB  # Nueva base de datos
    usuarios_collection = db.usuarios
    
    # Crear colección si no existe
    if "usuarios" not in db.list_collection_names():
        print("📁 Creando colección 'usuarios'...")
    
    mongo_disponible = True
    
except Exception as e:
    print(f"❌ Error conectando a MongoDB: {e}")
    print("⚠️ Usando modo temporal (en memoria)")
    mongo_disponible = False
    
    # Base de datos temporal en memoria
    usuarios_temporales = {}

# ==================== FUNCIONES AUXILIARES ====================
def hash_password(password):
    """Convierte contraseña a hash simple"""
    return hashlib.sha256(password.encode()).hexdigest()

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
    usuario = request.form.get("usuario")
    nombre = request.form.get("nombre")
    email = request.form.get("email")
    password = request.form.get("password")
    
    # Validaciones básicas
    if not all([usuario, nombre, email, password]):
        flash("Todos los campos son requeridos", "error")
        return redirect(url_for('registrow'))
    
    if len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres", "error")
        return redirect(url_for('registrow'))
    
    try:
        if mongo_disponible:
            # Verificar si usuario existe en MongoDB
            if usuarios_collection.find_one({"usuario": usuario}):
                flash("El usuario ya existe", "error")
                return redirect(url_for('registrow'))
            
            # Crear nuevo usuario
            nuevo_usuario = {
                "usuario": usuario,
                "nombre": nombre,
                "email": email,
                "password": hash_password(password),
                "fecha_registro": datetime.now(),
                "foto_perfil": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
            }
            
            # Insertar en MongoDB
            usuarios_collection.insert_one(nuevo_usuario)
            flash("¡Registro exitoso en MongoDB! Ahora puedes iniciar sesión", "success")
            
        else:
            # Modo temporal
            if usuario in usuarios_temporales:
                flash("El usuario ya existe", "error")
                return redirect(url_for('registrow'))
            
            usuarios_temporales[usuario] = {
                "nombre": nombre,
                "email": email,
                "password": password,
                "foto_perfil": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
            }
            flash("¡Registro exitoso (modo temporal)!", "success")
            
    except Exception as e:
        flash(f"Error en el registro: {str(e)[:50]}", "error")
    
    return redirect(url_for('iniciopy'))

# ==================== INICIO DE SESIÓN ====================
@app.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario")
    password = request.form.get("password")
    
    try:
        if mongo_disponible:
            # Buscar en MongoDB
            usuario_db = usuarios_collection.find_one({"usuario": usuario})
            
            if usuario_db and usuario_db["password"] == hash_password(password):
                session['usuario'] = usuario_db["usuario"]
                session['nombre'] = usuario_db["nombre"]
                session['foto_perfil'] = usuario_db.get("foto_perfil", "")
                
                flash(f"¡Bienvenido {usuario_db['nombre']}!", "success")
                return redirect(url_for('pelispy'))
            else:
                flash("Usuario o contraseña incorrectos", "error")
                
        else:
            # Modo temporal
            if usuario in usuarios_temporales and usuarios_temporales[usuario]["password"] == password:
                session['usuario'] = usuario
                session['nombre'] = usuarios_temporales[usuario]["nombre"]
                session['foto_perfil'] = usuarios_temporales[usuario]["foto_perfil"]
                
                flash(f"¡Bienvenido {usuarios_temporales[usuario]['nombre']}!", "success")
                return redirect(url_for('pelispy'))
            else:
                flash("Usuario o contraseña incorrectos", "error")
                
    except Exception as e:
        flash(f"Error en el inicio de sesión: {str(e)[:50]}", "error")
    
    return redirect(url_for('iniciopy'))

# ==================== CERRAR SESIÓN ====================
@app.route("/logout")
def logout():
    session.clear()
    flash("Has cerrado sesión correctamente", "success")
    return redirect(url_for('index'))

# ==================== PÁGINA DE PRUEBA ====================
@app.route("/prueba")
def prueba():
    """Página para probar la conexión"""
    if mongo_disponible:
        try:
            # Contar usuarios en MongoDB
            total_usuarios = usuarios_collection.count_documents({})
            estado = f"✅ CONECTADO a MongoDB - Usuarios: {total_usuarios}"
        except:
            estado = "⚠️ MongoDB disponible pero error al contar"
    else:
        estado = "❌ MODO TEMPORAL - No hay conexión a MongoDB"
    
    return f"""
    <h1>Prueba de Conexión - CineTec</h1>
    <p><strong>Estado:</strong> {estado}</p>
    <p><strong>MongoDB URI configurada:</strong> {'✅ Sí' if os.getenv('MONGODB_URI') else '❌ No'}</p>
    <p><strong>Python Version:</strong> {os.getenv('PYTHON_VERSION', 'No configurada')}</p>
    <p><strong>Fecha:</strong> {datetime.now()}</p>
    <a href="/">Volver al inicio</a>
    """

# ==================== INICIAR APLICACIÓN ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    print("=" * 60)
    print("🚀 CINETEC - CONEXIÓN A MONGODB")
    print("=" * 60)
    print(f"📊 Puerto: {port}")
    print(f"✅ MongoDB: {'CONECTADO' if mongo_disponible else 'MODO TEMPORAL'}")
    print(f"🔗 Prueba: http://localhost:{port}/prueba")
    print("=" * 60)
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )