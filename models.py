from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Cliente(db.Model):
    __tablename__ = "cliente"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120))
    domicilio = db.Column(db.String(120))
    localidad = db.Column(db.String(100))
    documento = db.Column(db.String(20))
    telefono = db.Column(db.String(20))
    ingresos = db.Column(db.Float)
    lugar_trabajo = db.Column(db.String(120))
    monto_autorizado = db.Column(db.Float)

    # Relación 1 a 1 con Garante
    garante = db.relationship("Garante", backref="cliente", uselist=False, cascade="all, delete-orphan")

    # Relación 1 a muchos con Ventas y Pagos
    ventas = db.relationship("Venta", cascade="all, delete-orphan")
    pagos = db.relationship("PagoCliente", cascade="all, delete-orphan")

    @property
    def saldo_deudor(self):
        total_deuda = sum((v.total or 0) - (v.pago_a_cuenta or 0) for v in self.ventas)
        total_pagos = sum(p.monto for p in self.pagos)
        return round(total_deuda - total_pagos, 2)


class Garante(db.Model):
    __tablename__ = "garante"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120))
    domicilio = db.Column(db.String(120))
    localidad = db.Column(db.String(100))
    documento = db.Column(db.String(20))
    telefono = db.Column(db.String(20))
    ingresos = db.Column(db.Float)
    lugar_trabajo = db.Column(db.String(120))

    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))


class Venta(db.Model):
    __tablename__ = "ventas2"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    total = db.Column(db.Float)
    pago_a_cuenta = db.Column(db.Float)
    saldo_resultante = db.Column(db.Float)
    descripcion = db.Column(db.Text)
    metodo_pago = db.Column(db.String(50))  # efectivo, debito, etc.

    # Relación con items
    items = db.relationship("VentaItem", back_populates="venta", cascade="all, delete-orphan")


class VentaItem(db.Model):
    __tablename__ = "venta_items"
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("ventas2.id"), nullable=False)
    cantidad = db.Column(db.Integer)
    descripcion = db.Column(db.Text)
    precio_unitario = db.Column(db.Float)
    total = db.Column(db.Float)

    venta = db.relationship("Venta", back_populates="items")


class PagoCliente(db.Model):
    __tablename__ = "pagos_clientes"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    monto = db.Column(db.Float, nullable=False)
    metodo_pago = db.Column(db.String(50))


class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


