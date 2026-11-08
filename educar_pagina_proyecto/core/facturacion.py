"""Facturación mensual (RF-M04, RF-M07 y base de RF-M08).

Arma la factura de un alumno con los servicios activos del período:
cuota del nivel, deportes, transporte (opcional y mensual) y comedor.
El total lo calcula el servidor; la app solo lo muestra.
"""
import re
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .models import (
    Arancel,
    Factura,
    InscripcionDeportiva,
    InscripcionTransporte,
    ItemFactura,
    TutorTutoraAlumno,
    ValorComedor,
)

PATRON_PERIODO = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')


class FacturacionError(ValueError):
    """Falta un dato para facturar (curso, valor, tutor). Se muestra al administrador."""


def validar_periodo(periodo):
    if not PATRON_PERIODO.match(periodo or ''):
        raise FacturacionError('El período debe tener el formato AAAA-MM.')
    return periodo


def vencimiento_para(periodo):
    """Vencimiento: día 10 del mes siguiente al período (supuesto a confirmar con Administración)."""
    anio, mes = (int(p) for p in periodo.split('-'))
    anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return date(anio, mes, 10)


def calcular_items(alumno):
    """Lista de (tipo, descripción, importe) de los servicios activos del alumno."""
    items = []

    curso = alumno.id_curso
    if curso is None:
        raise FacturacionError(f'El alumno {alumno.legajo} no tiene curso asignado.')
    arancel = Arancel.objects.filter(nivel=curso.nivel).first()
    if arancel is None:
        raise FacturacionError(f'No hay arancel configurado para el nivel {curso.nivel}.')
    items.append(('cuota', f'Cuota mensual - {curso.nivel}', arancel.monto))

    inscripciones_deporte = InscripcionDeportiva.objects.filter(
        alumno=alumno, estado='Activa',
    ).select_related('grupo__disciplina')
    for inscripcion in inscripciones_deporte:
        disciplina = inscripcion.grupo.disciplina
        if disciplina.valor is None:
            raise FacturacionError(f'El deporte {disciplina.nombre} no tiene valor configurado.')
        items.append(('deporte', f'Deporte - {disciplina.nombre}', disciplina.valor))

    inscripciones_transporte = InscripcionTransporte.objects.filter(
        alumno=alumno, estado='Activa',
    ).select_related('recorrido')
    for inscripcion in inscripciones_transporte:
        recorrido = inscripcion.recorrido
        if recorrido.valor is None:
            raise FacturacionError(f'El recorrido {recorrido.nombre} no tiene valor configurado.')
        items.append(('transporte', f'Transporte - {recorrido.nombre}', recorrido.valor))

    if alumno.inscripto_comedor:
        valor_comedor = ValorComedor.objects.first()
        if valor_comedor is None:
            raise FacturacionError('No hay valor de comedor configurado.')
        items.append(('comedor', 'Servicio de comedor', valor_comedor.monto))

    return items


def tutor_de_alumno(alumno):
    vinculo = TutorTutoraAlumno.objects.filter(id_alumno=alumno).select_related('id_tutor').first()
    if vinculo is None:
        raise FacturacionError(f'El alumno {alumno.legajo} no tiene tutor vinculado.')
    return vinculo.id_tutor


@transaction.atomic
def generar_factura(alumno, periodo, emision=None):
    """Crea la factura del período. Si ya existe, la devuelve sin duplicarla.

    Devuelve (factura, creada).
    """
    validar_periodo(periodo)
    existente = Factura.objects.filter(alumno=alumno, periodo=periodo).first()
    if existente is not None:
        return existente, False

    items = calcular_items(alumno)
    tutor = tutor_de_alumno(alumno)
    total = sum((importe for _, _, importe in items), Decimal('0'))

    factura = Factura.objects.create(
        alumno=alumno,
        tutor=tutor,
        periodo=periodo,
        emision=emision or date.today(),
        vencimiento=vencimiento_para(periodo),
        total=total,
    )
    ItemFactura.objects.bulk_create([
        ItemFactura(factura=factura, tipo=tipo, descripcion=descripcion, importe=importe)
        for tipo, descripcion, importe in items
    ])
    return factura, True


def _dinero(valor):
    return f'${Decimal(valor):,.2f}'


def generar_pdf_factura(factura):
    """PDF de la factura con el desglose por ítem. Devuelve los bytes del archivo."""
    alumno = factura.alumno
    persona_alumno = alumno.id_persona
    persona_tutor = factura.tutor.id_persona

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, alto = A4
    y = alto - 60

    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(50, y, 'Educar para Transformar')
    y -= 20
    pdf.setFont('Helvetica', 11)
    pdf.drawString(50, y, f'Factura del período {factura.periodo}')
    y -= 30

    datos = [
        f'Alumno: {persona_alumno.apellido}, {persona_alumno.nombre} (legajo {alumno.legajo})',
        f'Tutor: {persona_tutor.apellido}, {persona_tutor.nombre}',
        f'Emisión: {factura.emision:%d/%m/%Y}',
        f'Vencimiento: {factura.vencimiento:%d/%m/%Y}',
    ]
    for linea in datos:
        pdf.drawString(50, y, linea)
        y -= 16

    y -= 14
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(50, y, 'Concepto')
    pdf.drawRightString(545, y, 'Importe')
    y -= 6
    pdf.line(50, y, 545, y)
    y -= 16

    pdf.setFont('Helvetica', 10)
    for item in factura.items.all():
        pdf.drawString(50, y, item.descripcion)
        pdf.drawRightString(545, y, _dinero(item.importe))
        y -= 16

    y -= 6
    pdf.line(50, y, 545, y)
    y -= 18
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(50, y, 'Total')
    pdf.drawRightString(545, y, _dinero(factura.total))

    pdf.setFont('Helvetica', 8)
    pdf.drawString(50, 40, 'Pago por transferencia bancaria. No se reciben pagos en efectivo.')
    pdf.save()
    return buffer.getvalue()
