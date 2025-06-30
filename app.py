from flask import Flask, render_template, request, redirect, url_for, jsonify
from config import Config
from models import db, Cliente, Garante, Venta, VentaItem,PagoCliente
from datetime import date, datetime
from sqlalchemy import func, and_
import json
from flask_login import login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = "una-clave-secreta"

app.config.from_object(Config)

# Vincular app con SQLAlchemy
db.init_app(app)

# Crear tablas automáticamente (solo en desarrollo)
with app.app_context():
    db.create_all()

# ---------- RUTAS CLIENTES ----------

def safe_float(value):
    try:
        return float(value.strip()) if value.strip() else None
    except:
        return None

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
        cliente.nombre = request.form["nombre_cliente"]
        cliente.domicilio = request.form["domicilio_cliente"]
        cliente.localidad = request.form["localidad_cliente"]
        cliente.documento = request.form["documento_cliente"]
        cliente.telefono = request.form["telefono_cliente"]
        cliente.ingresos = request.form["ingresos_cliente"]
        cliente.lugar_trabajo = request.form["trabajo_cliente"]
        cliente.monto_autorizado = request.form["monto_autorizado"]

        if garante:
            garante.nombre = request.form["nombre_garante"]
            garante.domicilio = request.form["domicilio_garante"]
            garante.localidad = request.form["localidad_garante"]
            garante.documento = request.form["documento_garante"]
            garante.telefono = request.form["telefono_garante"]
            garante.ingresos = request.form["ingresos_garante"]
            garante.lugar_trabajo = request.form["trabajo_garante"]

        db.session.commit()
        return redirect(url_for("index"))

    return render_template("editar.html", cliente=cliente, garante=garante)


@app.route("/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
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


from datetime import datetime
import pytz
from datetime import datetime
import pytz
from flask import jsonify

@app.route("/ventas/guardar", methods=["POST"])
@login_required
def guardar_venta():
    cliente_id = request.form.get("cliente_id")

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

    # Hora Argentina naive
    tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
    ahora_ar = datetime.now(tz_ar).replace(tzinfo=None)

    venta = Venta(
        cliente_id=cliente_id,
        total=total_operacion,
        pago_a_cuenta=pago_a_cuenta,
        saldo_resultante=saldo_resultante,
        fecha=ahora_ar
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

    # Enviar URL del comprobante como respuesta
    return jsonify({ "redirect_url": url_for('comprobante', venta_id=venta.id) })





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

from datetime import datetime, time, date

from sqlalchemy import union_all

from collections import namedtuple
from sqlalchemy.sql import text

from datetime import datetime, time
from flask import render_template, request
from models import Cliente, Venta, PagoCliente  # Asegurate de tener estos importados

from flask import render_template, request
from models import Cliente, Venta, PagoCliente
from datetime import datetime, time, date
import pytz

@app.route("/movimientos")
@login_required
def movimientos():
    cliente_id = request.args.get("cliente_id")
    clientes = Cliente.query.all()
    movimientos = []

    # Definir zona horaria de Argentina
    tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")

    if cliente_id:
        ventas = Venta.query.filter_by(cliente_id=cliente_id).all()
        pagos = PagoCliente.query.filter_by(cliente_id=cliente_id).all()

        for v in ventas:
            fecha = v.fecha
            if isinstance(fecha, date) and not isinstance(fecha, datetime):
                fecha = datetime.combine(fecha, time.min)
            fecha = tz_ar.localize(fecha) if fecha.tzinfo is None else fecha.astimezone(tz_ar)

            movimientos.append({
                "id": v.id,
                "fecha": fecha,
                "total": v.total,
                "pago_a_cuenta": v.pago_a_cuenta,
                "saldo_resultante": v.saldo_resultante,
                "tipo": "venta",
                "descripcion": v.descripcion,
                "items": [
                    {
                        "cantidad": item.cantidad,
                        "descripcion": item.descripcion,
                        "precio_unitario": item.precio_unitario,
                        "total": item.total
                    }
                    for item in v.items
                ]
            })

        for p in pagos:
            fecha = p.fecha
            if isinstance(fecha, date) and not isinstance(fecha, datetime):
                fecha = datetime.combine(fecha, time.min)
            fecha = tz_ar.localize(fecha) if fecha.tzinfo is None else fecha.astimezone(tz_ar)

            movimientos.append({
                "id": f"pago-{p.id}",
                "fecha": fecha,
                "total": 0,
                "pago_a_cuenta": p.monto,
                "saldo_resultante": None,
                "tipo": "pago",
                "descripcion": "Pago suelto",
                "items": []
            })

        # Ordenar por fecha más reciente primero
        movimientos.sort(key=lambda x: x["fecha"], reverse=True)

    return render_template(
        "movimientos.html",
        clientes=clientes,
        movimientos=movimientos,
        cliente_id_seleccionado=cliente_id
    )








@app.route("/pagos", methods=["GET", "POST"])
@login_required
def registrar_pago():
    clientes = Cliente.query.all()

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id")
        monto = request.form.get("monto")

        try:
            monto = float(monto)
        except (ValueError, TypeError):
            monto = 0.0

        cliente = Cliente.query.get(cliente_id)

        if cliente and monto > 0:
            # Hora Argentina naive
            tz_ar = pytz.timezone("America/Argentina/Buenos_Aires")
            ahora_ar = datetime.now(tz_ar).replace(tzinfo=None)

            nuevo_pago = PagoCliente(
                cliente_id=cliente.id,
                monto=monto,
                fecha=ahora_ar
            )
            db.session.add(nuevo_pago)
            db.session.commit()
            return redirect(url_for('pago_exitoso', pago_id=nuevo_pago.id))

    return render_template("pago_cliente.html", clientes=clientes)


@app.route("/pago-exitoso/<int:pago_id>")
def pago_exitoso(pago_id):
    return render_template("pago_exitoso.html", pago_id=pago_id)



@app.route('/comprobante/<int:venta_id>')
def comprobante(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    cliente = venta.cliente

    # Obtener deuda total del cliente (no solo esta venta)
    deuda_total = db.session.query(
        func.coalesce(func.sum(Venta.total - Venta.pago_a_cuenta), 0)
    ).filter_by(cliente_id=cliente.id).scalar()

    return render_template("comprobante.html", venta=venta, cliente=cliente, deuda_total=deuda_total)


@app.route("/comprobante-pago/<int:pago_id>")
def comprobante_pago(pago_id):
    pago = PagoCliente.query.get_or_404(pago_id)
    cliente = Cliente.query.get_or_404(pago.cliente_id)

    saldo_antes = cliente.saldo_deudor + pago.monto
    saldo_actual = cliente.saldo_deudor

    return render_template("comprobante_pago.html", pago=pago, cliente=cliente,
                           saldo_antes=saldo_antes, saldo_actual=saldo_actual)


@app.route("/morosos")
def morosos():
    clientes = Cliente.query.all()
    clientes_morosos = [c for c in clientes if c.saldo_deudor > 0]
    total_deuda = sum(c.saldo_deudor for c in clientes_morosos)
    return render_template("morosos.html", clientes=clientes_morosos, total_deuda=total_deuda)



from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_message = "Por favor, iniciá sesión para continuar."
login_manager.login_message_category = "warning"
login_manager.init_app(app)
login_manager.login_view = "login"  # ruta que usaremos para iniciar sesión

from flask_login import login_user, logout_user, login_required, current_user

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from models import Usuario  # ajustá según tu estructura

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = Usuario.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('index'))  # o la vista principal que uses
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
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
