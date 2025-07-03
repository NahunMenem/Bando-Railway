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
    metodo_pago = request.form.get("metodo_pago")  # <-- NUEVO

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
        fecha=ahora_ar,
        metodo_pago=metodo_pago  # <-- NUEVO
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
def registrar_pago():
    clientes = Cliente.query.all()

    if request.method == "POST":
        cliente_id = request.form["cliente_id"]
        monto = float(request.form["monto"])
        metodo_pago = request.form["metodo_pago"]

        cliente = Cliente.query.get(cliente_id)
        if cliente:
            nuevo_pago = PagoCliente(cliente_id=cliente.id, monto=monto, metodo_pago=metodo_pago)
            db.session.add(nuevo_pago)
            db.session.commit()
            return redirect(url_for('pago_exitoso', pago_id=nuevo_pago.id))

    return render_template("pago_cliente.html", clientes=clientes)


@app.route("/pago-exitoso/<int:pago_id>")
def pago_exitoso(pago_id):
    return render_template("pago_exitoso.html", pago_id=pago_id)



@app.route("/comprobante/<int:venta_id>")
def comprobante(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    cliente = Cliente.query.get_or_404(venta.cliente_id)

    ventas_anteriores = db.session.query(
        func.coalesce(func.sum(Venta.total - Venta.pago_a_cuenta), 0)
    ).filter(
        Venta.cliente_id == cliente.id,
        Venta.id < venta.id
    ).scalar()

    pagos_anteriores = db.session.query(
        func.coalesce(func.sum(PagoCliente.monto), 0)
    ).filter(
        PagoCliente.cliente_id == cliente.id,
        PagoCliente.fecha < venta.fecha
    ).scalar()

    deuda_anterior = round((ventas_anteriores or 0) - (pagos_anteriores or 0), 2)
    deuda_total = round(deuda_anterior + venta.saldo_resultante, 2)

    return render_template("comprobante.html", venta=venta, cliente=cliente,
                           deuda_anterior=deuda_anterior, deuda_total=deuda_total)





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



@app.route("/eliminar_movimiento/<tipo>/<int:id>", methods=["POST"])
@login_required
def eliminar_movimiento(tipo, id):
    if tipo == "venta":
        movimiento = Venta.query.get_or_404(id)
    elif tipo == "pago":
        movimiento = PagoCliente.query.get_or_404(id)
    else:
        flash("Tipo de movimiento inválido", "danger")
        return redirect(request.referrer)

    db.session.delete(movimiento)
    db.session.commit()
    flash("Movimiento eliminado correctamente", "success")
    return redirect(request.referrer)



from sqlalchemy import extract

@app.route("/caja", methods=["GET", "POST"])
@login_required
def caja():
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")

    # Filtro de fechas
    ventas_query = db.session.query(Venta)
    pagos_query = db.session.query(PagoCliente)

    if desde and hasta:
        ventas_query = ventas_query.filter(Venta.fecha.between(desde, hasta))
        pagos_query = pagos_query.filter(PagoCliente.fecha.between(desde, hasta))

    ventas = ventas_query.all()
    pagos = pagos_query.all()

    total_ventas = sum(venta.total for venta in ventas)
    total_ingresado = sum((venta.pago_a_cuenta or 0) for venta in ventas) + sum(p.monto for p in pagos)

    # Agrupar ventas por método de pago (solo el monto pagado)
    ventas_por_metodo = (
        db.session.query(Venta.metodo_pago, func.sum(Venta.pago_a_cuenta))
        .filter(Venta.pago_a_cuenta != None)
    )
    if desde and hasta:
        ventas_por_metodo = ventas_por_metodo.filter(Venta.fecha.between(desde, hasta))
    ventas_por_metodo = ventas_por_metodo.group_by(Venta.metodo_pago).all()

    # Agrupar pagos de clientes por método de pago
    pagos_por_metodo = (
        db.session.query(PagoCliente.metodo_pago, func.sum(PagoCliente.monto))
    )
    if desde and hasta:
        pagos_por_metodo = pagos_por_metodo.filter(PagoCliente.fecha.between(desde, hasta))
    pagos_por_metodo = pagos_por_metodo.group_by(PagoCliente.metodo_pago).all()

    # Unificar ambos resultados
    totales_por_metodo = {}

    for metodo, total in ventas_por_metodo:
        if metodo:
            totales_por_metodo[metodo] = totales_por_metodo.get(metodo, 0) + float(total)

    for metodo, total in pagos_por_metodo:
        if metodo:
            totales_por_metodo[metodo] = totales_por_metodo.get(metodo, 0) + float(total)

    return render_template(
        "caja.html",
        total_ventas=total_ventas,
        total_ingresado=total_ingresado,
        totales_por_metodo=totales_por_metodo,
        desde=desde,
        hasta=hasta
    )


# ---------- MAIN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

