#!/usr/bin/env python3
"""
Script para descargar fuentes Catalanas desde un CSV y organizarlas por categoría
Uso: python download_fonts.py <archivo_csv> [--output-dir fonts]
"""

import csv
import requests
import os
import sys
import time
import argparse
from pathlib import Path
import re
import zipfile
import io

def sanitize_filename(filename):
    """Sanitiza el nombre del archivo eliminando caracteres inválidos"""
    # Reemplazar caracteres inválidos en Windows/Linux
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Eliminar espacios múltiples
    filename = re.sub(r'\s+', '_', filename)
    # Limitar longitud
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def download_font(download_url, font_folder, font_name):
    """Descarga una fuente, la descomprime y guarda los archivos en una carpeta"""

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        print(f"  Descargando: {font_name}...", end=' ')
        response = requests.get(download_url, headers=headers, timeout=30)
        response.raise_for_status()

        file_size = len(response.content) / 1024  # KB

        # Verificar si es un ZIP
        if response.content[:2] == b'PK':  # ZIP file magic number
            try:
                # Descomprimir el ZIP
                with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                    # Extraer todos los archivos a la carpeta de la fuente
                    zf.extractall(font_folder)
                    num_files = len(zf.namelist())
                    print(f"[OK] ({file_size:.1f} KB, {num_files} archivos extraídos)")
                    return True
            except zipfile.BadZipFile:
                print(f"[ERROR] Archivo ZIP corrupto")
                return False
        else:
            # Si no es ZIP, guardar el archivo directamente (TTF/OTF)
            # Intentar determinar la extensión
            if b'OTTO' in response.content[:4]:
                ext = '.otf'
            elif b'\x00\x01\x00\x00' in response.content[:4] or b'true' in response.content[:4]:
                ext = '.ttf'
            else:
                ext = '.font'  # Extensión genérica

            output_file = font_folder / f"{font_name}{ext}"
            with open(output_file, 'wb') as f:
                f.write(response.content)

            print(f"[OK] ({file_size:.1f} KB, archivo directo)")
            return True

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Descargar fuentes Catalanas y organizarlas por categoría')
    parser.add_argument('csv_file', help='Archivo CSV con las fuentes a descargar')
    parser.add_argument('--output-dir', default='fonts', help='Directorio base para guardar las fuentes (default: fonts)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay en segundos entre descargas (default: 1.0)')
    parser.add_argument('--skip-existing', action='store_true', help='Saltar fuentes que ya existen')

    args = parser.parse_args()

    # Verificar que el CSV existe
    if not os.path.exists(args.csv_file):
        print(f"[ERROR] El archivo CSV no existe: {args.csv_file}")
        sys.exit(1)

    # Crear directorio base si no existe
    base_dir = Path(args.output_dir)
    base_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("DESCARGA DE FUENTES CATALANAS")
    print("=" * 60)
    print(f"CSV: {args.csv_file}")
    print(f"Directorio destino: {args.output_dir}")
    print(f"Delay entre descargas: {args.delay}s")
    print("=" * 60)
    print()

    # Leer el CSV
    fonts_to_download = []
    categories = set()

    try:
        with open(args.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('supports_catalan') == 'True':
                    fonts_to_download.append(row)
                    categories.add(row['category'])
    except Exception as e:
        print(f"[ERROR] Error leyendo CSV: {e}")
        sys.exit(1)

    print(f"Total de fuentes a descargar: {len(fonts_to_download)}")
    print(f"Categorías: {', '.join(sorted(categories))}")
    print()

    # Crear carpetas para cada categoría
    for category in categories:
        category_dir = base_dir / category
        category_dir.mkdir(exist_ok=True)
        print(f"[OK] Carpeta creada/verificada: {category_dir}")

    print()
    print("Iniciando descarga...")
    print("=" * 60)

    # Estadísticas
    stats = {
        'downloaded': 0,
        'skipped': 0,
        'failed': 0
    }

    # Descargar cada fuente
    for i, font in enumerate(fonts_to_download, 1):
        font_name = font['name']
        category = font['category']
        download_url = font['download_url']

        print(f"\n[{i}/{len(fonts_to_download)}] {category} / {font_name}")

        # Sanitizar nombre y crear carpeta para la fuente
        safe_name = sanitize_filename(font_name)
        font_folder = base_dir / category / safe_name

        # Verificar si ya existe
        if args.skip_existing and font_folder.exists():
            print(f"  [SKIP] Ya existe: {font_folder}")
            stats['skipped'] += 1
            continue

        # Crear carpeta para la fuente
        font_folder.mkdir(parents=True, exist_ok=True)

        # Descargar y extraer
        success = download_font(download_url, font_folder, font_name)

        if success:
            stats['downloaded'] += 1
        else:
            stats['failed'] += 1
            # Si falla, eliminar la carpeta vacía
            try:
                if font_folder.exists() and not any(font_folder.iterdir()):
                    font_folder.rmdir()
            except:
                pass

        # Delay entre descargas para ser respetuosos con el servidor
        if i < len(fonts_to_download):
            time.sleep(args.delay)

    # Resultados finales
    print()
    print("=" * 60)
    print("RESULTADOS:")
    print("=" * 60)
    print(f"  Descargadas: {stats['downloaded']}")
    print(f"  Saltadas: {stats['skipped']}")
    print(f"  Errores: {stats['failed']}")
    print(f"  Total procesadas: {len(fonts_to_download)}")
    print()

    # Mostrar resumen por categoría
    print("Resumen por categoría:")
    for category in sorted(categories):
        category_dir = base_dir / category
        num_fonts = len([d for d in category_dir.iterdir() if d.is_dir()])
        print(f"  {category}: {num_fonts} fuente(s)")

    print()
    print("[SUCCESS] Descarga completada!")
    print(f"Las fuentes están organizadas en: {base_dir.absolute()}")

if __name__ == "__main__":
    main()
