from flask import Flask, render_template, request
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()  # Cargar variables del archivo .env

app = Flask(__name__)

# Obtener la URL de conexión desde el archivo .env
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/registrar", methods=["POST"])
def registrar():
    nombre = request.form.get("nombre")
    correo = request.form.get("correo")
    mensaje = request.form.get("mensaje")

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO contactos (nombre, correo, mensaje)
            VALUES (%s, %s, %s)
        """, (nombre, correo, mensaje))

        conn.commit()
        cur.close()
        conn.close()

        return "Registro guardado correctamente 😎"

    except Exception as e:
        return f"Error al guardar: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True)
