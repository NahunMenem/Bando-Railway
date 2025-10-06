from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from config import Config
from models import db, Cliente, Garante, Venta, VentaItem, PagoCliente, Usuario
from datetime import date, datetime, time
from sqlalchemy import func, and_, extract
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import json
import pytz
import os
from dotenv import load_dotenv
from sqlalchemy.sql import text


app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Podés reemplazarla con otra más segura

app.config.from_object(Config)

# Vincular app con SQLAlchemy
db.init_app(app)

# Crear tablas automáticamente (solo en desarrollo)
with app.app_context():
    db.create_all()


# ---------- FUNCIÓN AUXILIAR ----------
def safe_float(value):
    """Convierte cadenas vacías o con coma a float o None."""
    try:
        if not value or value.strip() == "":
            return None
        value = value.replace(",", ".")  # Aceptar '10,5' como 10.5
        return float(value)
    except ValueError:
        return None


# ---------- RUTAS CLIENTES ----------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        cliente = Cliente(
            nombre=request.form["nombre_cliente"],
            domicilio=request.form["domicilio_cliente"],
            localidad=request.form["localidad_cliente"],
            documento=request.form["documento_cliente"],
            telefono=request.form["telefono_cliente"],
            ingresos=safe_float(request.form["ingresos_cliente"]),
            lugar_trabajo=request.form["trabajo_cliente"],
            monto_autorizado=safe_float(request.form["monto_autorizado"]),
        )
        db.session.add(cliente)
        db.session.commit()

        garante = Garante(
            nombre=request.form["nombre_garante"],
            domicilio=request.form["domicilio_garante"],
            localidad=request.form["localidad_garante"],
            documento=request.form["documento_garante"],
            telefono=request.form["telefono_garante"],
            ingresos=safe_float(request.form["ingresos_garante"]),
            lugar_trabajo=request.form["trabajo_garante"],
            cliente_id=cliente.id
        )
        db.session.add(garante)
        db.session.commit()
        return redirect(url_for("index"))

    clientes = Cliente.query.all()
    return render_template("index.html", clientes=clientes)


@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    garante = cliente.garante

    if request.method == "POST":
        # Cliente
        cliente.nombre = request.form["nombre_cliente"]
        cliente.domicilio = request.form["domicilio_cliente"]
        cliente.localidad = request.form["localidad_cliente"]
        cliente.documento = request.form["documento_cliente"]
        cliente.telefono = request.form["telefono_cliente"]
        cliente.ingresos = safe_float(request.form.get("ingresos_cliente", ""))
        cliente.lugar_trabajo = request.form["trabajo_cliente"]
        cliente.monto_autorizado = safe_float(request.form.get("monto_autorizado", ""))

        # Garante
        if garante:
            garante.nombre = request.form["nombre_garante"]
            garante.domicilio = request.form["domicilio_garante"]
            garante.localidad = request.form["localidad_garante"]
            garante.documento = request.form["documento_garante"]
            garante.telefono = request.form["telefono_garante"]
            garante.ingresos = safe_float(request.form.get("ingresos_garante", ""))
            garante.lugar_trabajo = request.form["trabajo_garante"]

        db.session.commit()
        return redirect(url_for("index"))

    return render_template("editar.html", cliente=cliente, garante=garante)


@app.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    # Primero eliminamos registros relacionados
    if cliente.garante:
        db.session.delete(cliente.garante)

    # Eliminar ventas y sus ítems asociados
    for venta in cliente.ventas:
        for item in venta.items:
            db.session.delete(item)
        db.session.delete(venta)

    # Eliminar pagos asociados
    for pago in cliente.pagos:
        db.session.delete(pago)

    # Finalmente eliminar el cliente
    db.session.delete(cliente)
    db.session.commit()

    return redirect(url_for("index"))


# ---------- RUTAS VENTAS ----------
@app.route("/ventas")
@login_required
def ventas():
    clientes = Cliente.query.all()
    for cliente in clientes:
        total_deuda = db.session.query(
            func.coalesce(func.sum(Venta.total - Venta.pago_a_cuenta), 0)
        ).filter(Venta.cliente_id == cliente.id).scalar()

    return render_template("ventas.html", clientes=clientes, fecha_hoy=date.today().strftime("%Y-%m-%d"))


@app.route("/ventas/guardar", methods=["POST"])
@login_required
def guardar_venta():
    cliente_id = request.form.get("cliente_id")
    metodo_pago = request.form.get("metodo_pago")

    try:
        pago_a_cuenta = float(request.form.get("pago_a_cuenta", "0") or 0)
    except ValueError:
        pago_a_cuenta = 0.0

    try:
        items = json.loads(request.form.get("items_json", "[]"))
    except json.JSONDecodeError:
        items = []

    total_operacion = sum(item["cantidad"] * item["precio_unitario"] for item in items)
    saldo_resultante = total_operacion - pago_a_cuenta

    tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
    ahora_ar = datetime.now(tz_ar).replace(tzinfo=None)

    venta = Venta(
        cliente_id=cliente_id,
        total=total_operacion,
        pago_a_cuenta=pago_a_cuenta,
        saldo_resultante=saldo_resultante,
        fecha=ahora_ar,
        metodo_pago=metodo_pago
    )
    db.session.add(venta)
    db.session.flush()

    for item in items:
        venta_item = VentaItem(
            venta_id=venta.id,
            cantidad=item["cantidad"],
            descripcion=item["descripcion"],
            precio_unitario=item["precio_unitario"],
            total=item["total"]
        )
        db.session.add(venta_item)

    db.session.commit()
    return jsonify({"redirect_url": url_for('comprobante', venta_id=venta.id)})


# ---------- API CLIENTE ----------
@app.route("/api/cliente/<int:cliente_id>")
def api_cliente(cliente_id):
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        return {"error": "Cliente no encontrado"}, 404

    total_deuda = db.session.query(
        func.coalesce(func.sum(Venta.total - Venta.pago_a_cuenta), 0)
    ).filter(Venta.cliente_id == cliente_id).scalar()

    return {
        "id": cliente.id,
        "nombre": cliente.nombre,
        "monto_autorizado": round(cliente.monto_autorizado or 0, 2),
        "saldo": round(total_deuda or 0, 2)
    }


# ---------- LOGIN ----------
login_manager = LoginManager()
login_manager.login_message = "Por favor, iniciá sesión para continuar."
login_manager.login_message_category = "warning"
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))


# ---------- MAIN ----------
if __name__ == "__main__":
    load_dotenv()  # Solo para local
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


