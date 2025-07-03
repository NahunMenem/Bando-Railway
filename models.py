from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

db = SQLAlchemy()

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120))
    domicilio = db.Column(db.String(120))
    localidad = db.Column(db.String(100))
    documento = db.Column(db.String(20))
    telefono = db.Column(db.String(20))
    ingresos = db.Column(db.Float)
    lugar_trabajo = db.Column(db.String(120))
    monto_autorizado = db.Column(db.Float)

    garante = db.relationship('Garante', backref='cliente', uselist=False)
    @property
    def saldo_deudor(self):
        total_deuda = sum((v.total or 0) - (v.pago_a_cuenta or 0) for v in self.ventas)
        total_pagos = sum(p.monto for p in self.pagos)
        return round(total_deuda - total_pagos, 2)

class Garante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120))
    domicilio = db.Column(db.String(120))
    localidad = db.Column(db.String(100))
    documento = db.Column(db.String(20))
    telefono = db.Column(db.String(20))
    ingresos = db.Column(db.Float)
    lugar_trabajo = db.Column(db.String(120))

    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from datetime import datetime
class Venta(db.Model):
    __tablename__ = 'ventas2'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))
    fecha = db.Column(db.DateTime, default=lambda: datetime.now(timezone("America/Argentina/Buenos_Aires")).replace(tzinfo=None))

    total = db.Column(db.Float)
    pago_a_cuenta = db.Column(db.Float)
    saldo_resultante = db.Column(db.Float)
    descripcion = db.Column(db.Text)
    
    items = db.relationship("VentaItem", back_populates="venta", cascade="all, delete-orphan")
    cliente = db.relationship("Cliente", backref="ventas")
    metodo_pago = db.Column(db.String(50))  # efectivo, debito, etc.




class VentaItem(db.Model):
    __tablename__ = 'venta_items'
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas2.id'), nullable=False)
    cantidad = db.Column(db.Integer)
    descripcion = db.Column(db.Text)
    precio_unitario = db.Column(db.Float)
    total = db.Column(db.Float)

    venta = db.relationship("Venta", back_populates="items")


class PagoCliente(db.Model):
    __tablename__ = 'pagos_clientes'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    monto = db.Column(db.Float, nullable=False)
    metodo_pago = db.Column(db.String(50))  # efectivo, debito, etc.


    cliente = db.relationship("Cliente", backref="pagos")


# models.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'  # Asegurate que coincida con la tabla

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)  # usamos 'password' y no 'password_hash'
    role = db.Column(db.String(50))  # opcional si lo usás

    def check_password(self, password):
        return self.password == password  # compara en texto plano



