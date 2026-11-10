"""Validación de archivos de comprobante de transferencia (web y app)."""
import os

EXTENSIONES_COMPROBANTE = {
    '.pdf': b'%PDF',
    '.png': b'\x89PNG',
    '.jpg': b'\xff\xd8\xff',
    '.jpeg': b'\xff\xd8\xff',
}
TAMANO_MAXIMO_COMPROBANTE = 5 * 1024 * 1024  # 5 MB


def validar_archivo_comprobante(archivo):
    """Devuelve un mensaje de error, o None si el archivo es válido."""
    extension = os.path.splitext(archivo.name)[1].lower()
    if extension not in EXTENSIONES_COMPROBANTE:
        return 'Formato no permitido. Subí un PDF, PNG o JPG.'
    if archivo.size > TAMANO_MAXIMO_COMPROBANTE:
        return 'El archivo supera el máximo de 5 MB.'
    cabecera = archivo.read(8)
    archivo.seek(0)
    if not cabecera.startswith(EXTENSIONES_COMPROBANTE[extension]):
        return 'El contenido del archivo no coincide con su formato.'
    return None
