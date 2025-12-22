#!/usr/bin/env python3
"""
Generador de dataset sintético de texto catalán
Usa textos de /data/ y fuentes de /fonts/ para crear imágenes de líneas y palabras
"""

import os
import json
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random
from collections import defaultdict
import re
from tqdm import tqdm

class SyntheticDatasetBuilder:
    def __init__(self, data_dir='data', fonts_dir='fonts', output_dir='output',
                 mode='lines', style='normal', verbose=False):
        self.data_dir = Path(data_dir)
        self.fonts_dir = Path(fonts_dir)
        self.output_dir = Path(output_dir)
        self.mode = mode  # 'lines' o 'words'
        self.style = style  # 'normal' o 'bold'
        self.verbose = verbose

        # Crear directorios de salida
        self.images_dir = self.output_dir / 'images'
        self.labels_dir = self.output_dir / 'labels'
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.labels_dir.mkdir(parents=True, exist_ok=True)

        # Estadísticas
        self.stats = {
            'fonts_with_bold': 0,
            'fonts_without_bold': 0,
            'fonts_used': 0,
            'fonts_skipped': 0,
            'images_generated': 0,
            'lines_generated': 0,
            'words_generated': 0
        }

        self.fonts = []
        self.texts = []

    def scan_fonts(self):
        """Escanea el directorio de fuentes y detecta las que tienen bold"""
        print("[1] Escaneando fuentes...")

        # Recorrer todas las carpetas de fuentes
        for category_dir in self.fonts_dir.iterdir():
            if not category_dir.is_dir():
                continue

            for font_dir in category_dir.iterdir():
                if not font_dir.is_dir():
                    continue

                # Buscar archivos de fuente en esta carpeta
                font_files = list(font_dir.glob('*.ttf')) + list(font_dir.glob('*.otf'))

                if not font_files:
                    continue

                # Clasificar archivos por estilo
                normal_fonts = []
                bold_fonts = []

                for font_file in font_files:
                    font_name_lower = font_file.name.lower()

                    # Detectar si es bold
                    if any(keyword in font_name_lower for keyword in ['bold', 'bd', 'heavy', 'black']):
                        # Excluir italic-bold si solo queremos bold
                        if 'italic' not in font_name_lower and 'oblique' not in font_name_lower:
                            bold_fonts.append(font_file)
                    # Detectar si es normal (no italic, no bold)
                    elif not any(keyword in font_name_lower for keyword in ['italic', 'oblique', 'bold', 'bd', 'heavy', 'black']):
                        normal_fonts.append(font_file)

                # Determinar si esta fuente tiene bold
                has_bold = len(bold_fonts) > 0

                if has_bold:
                    self.stats['fonts_with_bold'] += 1
                else:
                    self.stats['fonts_without_bold'] += 1

                # Decidir si usar esta fuente según el estilo requerido
                if self.style == 'bold':
                    if has_bold:
                        # Usar versión bold
                        self.fonts.append({
                            'path': bold_fonts[0],
                            'name': font_dir.name,
                            'category': category_dir.name,
                            'style': 'bold'
                        })
                        self.stats['fonts_used'] += 1
                    else:
                        self.stats['fonts_skipped'] += 1
                        if self.verbose:
                            print(f"  [SKIP] {category_dir.name}/{font_dir.name} - Sin bold")
                elif self.style == 'normal':
                    if normal_fonts:
                        # Usar versión normal
                        self.fonts.append({
                            'path': normal_fonts[0],
                            'name': font_dir.name,
                            'category': category_dir.name,
                            'style': 'normal'
                        })
                        self.stats['fonts_used'] += 1
                    else:
                        self.stats['fonts_skipped'] += 1
                        if self.verbose:
                            print(f"  [SKIP] {category_dir.name}/{font_dir.name} - Sin normal")

        print(f"  [OK] Fuentes escaneadas:")
        print(f"    Con bold: {self.stats['fonts_with_bold']}")
        print(f"    Sin bold: {self.stats['fonts_without_bold']}")
        print(f"    Fuentes usadas ({self.style}): {self.stats['fonts_used']}")
        print(f"    Fuentes saltadas: {self.stats['fonts_skipped']}")

    def load_texts(self):
        """Carga todos los textos del directorio data"""
        print("\n[2] Cargando textos...")

        for book_dir in self.data_dir.iterdir():
            if not book_dir.is_dir():
                continue

            for txt_file in book_dir.glob('*.txt'):
                try:
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Dividir en líneas
                    lines = [line.strip() for line in content.split('\n') if line.strip()]

                    for line in lines:
                        # Dividir cada línea en grupos de 5 palabras
                        words = line.split()

                        # Crear líneas de 5 palabras
                        for i in range(0, len(words), 5):
                            chunk = words[i:i+5]
                            if chunk:  # Solo agregar si hay palabras
                                self.texts.append({
                                    'text': ' '.join(chunk),
                                    'book': book_dir.name,
                                    'file': txt_file.name
                                })

                except Exception as e:
                    if self.verbose:
                        print(f"  [ERROR] Error leyendo {txt_file}: {e}")

        print(f"  [OK] {len(self.texts)} líneas de texto cargadas (5 palabras por línea)")

    def generate_image(self, text, font_info, font_size=32):
        """Genera una imagen de texto con la fuente especificada"""
        try:
            # Cargar fuente
            font = ImageFont.truetype(str(font_info['path']), font_size)

            # Calcular tamaño de la imagen
            # Crear imagen temporal para medir
            temp_img = Image.new('RGB', (1, 1), 'white')
            temp_draw = ImageDraw.Draw(temp_img)
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Añadir padding
            padding = 20
            img_width = text_width + 2 * padding
            img_height = text_height + 2 * padding

            # Crear imagen final
            img = Image.new('RGB', (img_width, img_height), 'white')
            draw = ImageDraw.Draw(img)

            # Dibujar texto (centrado verticalmente)
            x = padding
            y = padding - bbox[1]  # Ajuste para alineación
            draw.text((x, y), text, font=font, fill='black')

            return img

        except Exception as e:
            if self.verbose:
                print(f"  [ERROR] Error generando imagen: {e}")
            return None

    def generate_dataset(self, max_texts=None, font_size=32):
        """Genera el dataset sintético - todos los textos con todas las fuentes"""
        print(f"\n[3] Generando dataset ({self.mode})...")

        if not self.fonts:
            print("  [ERROR] No hay fuentes disponibles")
            return

        if not self.texts:
            print("  [ERROR] No hay textos disponibles")
            return

        # Limitar número de textos si se especifica
        texts_to_use = self.texts[:max_texts] if max_texts else self.texts

        print(f"  [INFO] Generando: {len(texts_to_use)} textos × {len(self.fonts)} fuentes")

        # Calcular total de items a procesar
        if self.mode == 'words':
            # Contar total de palabras
            total_words = sum(len(text_data['text'].split()) for text_data in texts_to_use)
            total_items = total_words * len(self.fonts)
        else:
            total_items = len(texts_to_use) * len(self.fonts)

        print(f"  Total imágenes esperadas: {total_items:,}")

        metadata = []

        # Barra de progreso
        with tqdm(total=total_items, desc="Generando imágenes", unit="img") as pbar:
            # Iterar sobre todas las fuentes
            for font_info in self.fonts:
                # Crear carpetas para esta fuente
                font_name = font_info['name']
                font_images_dir = self.images_dir / font_name
                font_labels_dir = self.labels_dir / font_name
                font_images_dir.mkdir(parents=True, exist_ok=True)
                font_labels_dir.mkdir(parents=True, exist_ok=True)

                # Contador por fuente
                font_sample_count = 0

                # Iterar sobre todos los textos
                for text_idx, text_data in enumerate(texts_to_use):
                    text = text_data['text']

                    # Si modo es 'words', extraer palabras
                    if self.mode == 'words':
                        words = text.split()
                        if not words:
                            continue
                        # Usar todas las palabras de la línea
                        words_to_render = words
                    else:  # 'lines'
                        words_to_render = [text]

                    # Para cada palabra/línea
                    for text_to_render in words_to_render:
                        # Generar imagen
                        img = self.generate_image(text_to_render, font_info, font_size)

                        if img is None:
                            pbar.update(1)
                            continue

                        # Guardar imagen en carpeta de fuente
                        img_filename = f"{font_sample_count:06d}.png"
                        img_path = font_images_dir / img_filename
                        img.save(img_path)

                        # Guardar label en carpeta de fuente
                        label_data = {
                            'image': f"{font_name}/{img_filename}",
                            'text': text_to_render,
                            'font_name': font_info['name'],
                            'font_category': font_info['category'],
                            'font_style': font_info['style'],
                            'source_book': text_data['book'],
                            'mode': self.mode
                        }

                        label_path = font_labels_dir / f"{font_sample_count:06d}.json"
                        with open(label_path, 'w', encoding='utf-8') as f:
                            json.dump(label_data, f, ensure_ascii=False, indent=2)

                        metadata.append(label_data)

                        font_sample_count += 1
                        self.stats['images_generated'] += 1

                        if self.mode == 'words':
                            self.stats['words_generated'] += 1
                        else:
                            self.stats['lines_generated'] += 1

                        # Actualizar barra de progreso
                        pbar.update(1)

        # Guardar metadata completa
        metadata_path = self.output_dir / 'metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"  [OK] {sample_count:,} imágenes generadas")

    def generate_summary(self):
        """Genera resumen del dataset"""
        print("\n" + "=" * 60)
        print("RESUMEN DE GENERACIÓN")
        print("=" * 60)
        print(f"Modo: {self.mode}")
        print(f"Estilo: {self.style}")
        print(f"\nFuentes:")
        print(f"  Con bold: {self.stats['fonts_with_bold']}")
        print(f"  Sin bold: {self.stats['fonts_without_bold']}")
        print(f"  Usadas: {self.stats['fonts_used']}")
        print(f"  Saltadas: {self.stats['fonts_skipped']}")
        print(f"\nImágenes generadas:")
        print(f"  Total: {self.stats['images_generated']}")
        if self.mode == 'words':
            print(f"  Palabras: {self.stats['words_generated']}")
        else:
            print(f"  Líneas: {self.stats['lines_generated']}")
        print(f"\nOutput: {self.output_dir.absolute()}")
        print(f"  Imágenes: {self.images_dir}")
        print(f"  Labels: {self.labels_dir}")
        print()

def main():
    parser = argparse.ArgumentParser(
        description='Generador de dataset sintético de texto catalán'
    )
    parser.add_argument('--data-dir', default='data', help='Directorio con textos (default: data)')
    parser.add_argument('--fonts-dir', default='fonts', help='Directorio con fuentes (default: fonts)')
    parser.add_argument('--output-dir', default='output', help='Directorio de salida (default: output)')
    parser.add_argument('--mode', choices=['lines', 'words'], default='lines',
                        help='Modo: lines (líneas completas) o words (palabras) (default: lines)')
    parser.add_argument('--style', choices=['normal', 'bold'], default='normal',
                        help='Estilo de fuente: normal o bold (default: normal)')
    parser.add_argument('--max-texts', type=int, default=None,
                        help='Número máximo de textos a usar (default: todos)')
    parser.add_argument('--font-size', type=int, default=32,
                        help='Tamaño de fuente en píxeles (default: 32)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Mostrar información detallada')

    args = parser.parse_args()

    print("=" * 60)
    print("GENERADOR DE DATASET SINTÉTICO - TEXTO CATALÁN")
    print("=" * 60)
    print()

    builder = SyntheticDatasetBuilder(
        data_dir=args.data_dir,
        fonts_dir=args.fonts_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        style=args.style,
        verbose=args.verbose
    )

    # Escanear fuentes
    builder.scan_fonts()

    # Cargar textos
    builder.load_texts()

    # Generar dataset
    builder.generate_dataset(
        max_texts=args.max_texts,
        font_size=args.font_size
    )

    # Resumen
    builder.generate_summary()

    print("[SUCCESS] Dataset generado correctamente!")

if __name__ == "__main__":
    main()
