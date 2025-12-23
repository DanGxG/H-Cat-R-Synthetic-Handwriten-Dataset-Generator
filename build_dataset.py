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
import multiprocessing as mp
from functools import partial
import platform


# ============================================================================
# FUNCIONES GLOBALES PARA MULTIPROCESSING
# ============================================================================

def _generate_single_image(task, target_height=128):
    """
    Función worker para generar una imagen (compatible con multiprocessing)

    Args:
        task: dict con {
            'text': texto a renderizar,
            'font_path': ruta a la fuente,
            'split_dir': directorio del split,
            'img_filename': nombre del archivo de imagen,
            'text_data': datos del texto (book, etc),
            'font_info': info de la fuente
        }
        target_height: altura de la imagen

    Returns:
        dict con metadata o None si falla
    """
    try:
        text = task['text']
        font_path = task['font_path']
        split_dir = Path(task['split_dir'])
        img_filename = task['img_filename']

        # Generar imagen
        font_size = int(target_height * 0.7)
        font = ImageFont.truetype(str(font_path), font_size)

        # Medir texto
        temp_img = Image.new('RGB', (1, 1), 'white')
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Ajustar font_size para alcanzar target_height
        if text_height > 0:
            scale_factor = (target_height * 0.8) / text_height
            font_size = int(font_size * scale_factor)
            font = ImageFont.truetype(str(font_path), font_size)

            # Volver a medir
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

        # Crear imagen: altura fija, ancho variable
        img_width = max(text_width, 10)
        img_height = target_height

        # Crear imagen RGB
        img = Image.new('RGB', (img_width, img_height), 'white')
        draw = ImageDraw.Draw(img)

        # Centrar texto verticalmente
        y = (target_height - text_height) // 2 - bbox[1]
        draw.text((0, y), text, font=font, fill='black')

        # Guardar imagen
        img_path = split_dir / img_filename
        img.save(img_path)

        # Crear metadata
        metadata_entry = {
            'file_name': img_filename,
            'text': text,
            'font_name': task['font_info']['name'],
            'font_category': task['font_info']['category'],
            'font_style': task['font_info']['style'],
            'source_book': task['text_data']['book'],
            'mode': task['mode'],
            'split_name': task['split_name']  # Añadir para poder organizar después
        }

        return metadata_entry

    except Exception as e:
        # Retornar None si falla
        return None


class SyntheticDatasetBuilder:
    def __init__(self, data_dir='data', fonts_dir='fonts', output_dir='output',
                 mode='lines', style='normal', verbose=False,
                 train_split=0.8, val_split=0.1, num_workers=1, max_fonts_per_category=None):
        self.data_dir = Path(data_dir)
        self.fonts_dir = Path(fonts_dir)
        self.output_dir = Path(output_dir)
        self.mode = mode  # 'lines' o 'words'
        self.style = style  # 'normal' o 'bold'
        self.verbose = verbose
        self.num_workers = num_workers
        self.max_fonts_per_category = max_fonts_per_category  # Límite de fuentes por categoría

        # Proporciones de splits (train/val/test)
        self.train_split = train_split
        self.val_split = val_split
        self.test_split = 1.0 - train_split - val_split

        # Crear estructura HuggingFace: train/validation/test
        self.train_dir = self.output_dir / 'train'
        self.val_dir = self.output_dir / 'validation'
        self.test_dir = self.output_dir / 'test'

        for split_dir in [self.train_dir, self.val_dir, self.test_dir]:
            split_dir.mkdir(parents=True, exist_ok=True)

        # Estadísticas
        self.stats = {
            'fonts_with_bold': 0,
            'fonts_without_bold': 0,
            'fonts_used': 0,
            'fonts_skipped': 0,
            'images_generated': 0,
            'lines_generated': 0,
            'words_generated': 0,
            'train_samples': 0,
            'val_samples': 0,
            'test_samples': 0
        }

        self.fonts = []
        self.texts = []

    def scan_fonts(self):
        """Escanea el directorio de fuentes y detecta las que tienen bold"""
        print("[1] Escaneando fuentes...")

        # Agrupar fuentes por categoría antes de aplicar límite
        fonts_by_category = defaultdict(list)

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

                # Preparar información de fuente según el estilo requerido
                font_info = None
                if self.style == 'bold':
                    if has_bold:
                        font_info = {
                            'path': bold_fonts[0],
                            'name': font_dir.name,
                            'category': category_dir.name,
                            'style': 'bold'
                        }
                    else:
                        self.stats['fonts_skipped'] += 1
                        if self.verbose:
                            print(f"  [SKIP] {category_dir.name}/{font_dir.name} - Sin bold")
                elif self.style == 'normal':
                    if normal_fonts:
                        font_info = {
                            'path': normal_fonts[0],
                            'name': font_dir.name,
                            'category': category_dir.name,
                            'style': 'normal'
                        }
                    else:
                        self.stats['fonts_skipped'] += 1
                        if self.verbose:
                            print(f"  [SKIP] {category_dir.name}/{font_dir.name} - Sin normal")

                # Agregar a la categoría correspondiente
                if font_info:
                    fonts_by_category[category_dir.name].append(font_info)

        # Aplicar límite por categoría si está especificado
        category_stats = {}
        for category_name, category_fonts in fonts_by_category.items():
            available = len(category_fonts)

            if self.max_fonts_per_category is not None and available > self.max_fonts_per_category:
                # Mezclar aleatoriamente y tomar solo el límite
                random.shuffle(category_fonts)
                selected_fonts = category_fonts[:self.max_fonts_per_category]
                used = len(selected_fonts)
            else:
                # Usar todas las disponibles
                selected_fonts = category_fonts
                used = available

            self.fonts.extend(selected_fonts)
            category_stats[category_name] = {'available': available, 'used': used}

        # Actualizar estadísticas globales
        self.stats['fonts_used'] = len(self.fonts)

        # Mostrar resumen
        print(f"  [OK] Fuentes escaneadas:")
        print(f"    Con bold: {self.stats['fonts_with_bold']}")
        print(f"    Sin bold: {self.stats['fonts_without_bold']}")
        print(f"    Fuentes usadas ({self.style}): {self.stats['fonts_used']}")
        print(f"    Fuentes saltadas: {self.stats['fonts_skipped']}")

        # Mostrar estadísticas por categoría
        if self.max_fonts_per_category is not None:
            print(f"\n  [INFO] Límite por categoría: {self.max_fonts_per_category}")
        print(f"\n  Fuentes por categoría:")
        for category_name in sorted(category_stats.keys()):
            stats = category_stats[category_name]
            if stats['used'] < stats['available']:
                print(f"    {category_name}: {stats['used']}/{stats['available']} (limitado)")
            else:
                print(f"    {category_name}: {stats['used']}/{stats['available']}")

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

    def generate_image(self, text, font_info, target_height=128):
        """
        Genera una imagen de texto con altura fija y ancho variable (estilo IAM/TrOCR)
        Sin padding - el padding se añade durante el preprocesamiento de entrenamiento

        Args:
            text: Texto a renderizar
            font_info: Información de la fuente
            target_height: Altura objetivo en píxeles (default: 128 como IAM)
        """
        try:
            # Empezar con un tamaño de fuente estimado (70% de la altura objetivo)
            font_size = int(target_height * 0.7)
            font = ImageFont.truetype(str(font_info['path']), font_size)

            # Medir texto
            temp_img = Image.new('RGB', (1, 1), 'white')
            temp_draw = ImageDraw.Draw(temp_img)
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Ajustar font_size para alcanzar target_height
            if text_height > 0:
                scale_factor = (target_height * 0.8) / text_height
                font_size = int(font_size * scale_factor)
                font = ImageFont.truetype(str(font_info['path']), font_size)

                # Volver a medir
                bbox = temp_draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

            # Crear imagen: altura fija, ancho variable (como IAM)
            img_width = max(text_width, 10)  # Mínimo 10px de ancho
            img_height = target_height

            # Crear imagen RGB (como IAM)
            img = Image.new('RGB', (img_width, img_height), 'white')
            draw = ImageDraw.Draw(img)

            # Centrar texto verticalmente
            y = (target_height - text_height) // 2 - bbox[1]
            draw.text((0, y), text, font=font, fill='black')

            return img

        except Exception as e:
            if self.verbose:
                print(f"  [ERROR] Error generando imagen: {e}")
            return None

    def generate_dataset(self, max_texts=None, target_height=128):
        """Genera el dataset sintético en formato HuggingFace con splits train/val/test"""
        print(f"\n[3] Generando dataset ({self.mode})...")

        if not self.fonts:
            print("  [ERROR] No hay fuentes disponibles")
            return

        if not self.texts:
            print("  [ERROR] No hay textos disponibles")
            return

        # Limitar número de textos si se especifica
        texts_to_use = self.texts[:max_texts] if max_texts else self.texts

        # Mezclar textos para distribución aleatoria en splits
        random.shuffle(texts_to_use)

        print(f"  [INFO] Generando: {len(texts_to_use)} textos × {len(self.fonts)} fuentes")
        print(f"  [INFO] Splits: train={self.train_split:.0%}, val={self.val_split:.0%}, test={self.test_split:.0%}")
        if self.num_workers > 1:
            print(f"  [INFO] Usando {self.num_workers} workers en paralelo")

        # Calcular índices de splits
        n_texts = len(texts_to_use)
        train_end = int(n_texts * self.train_split)
        val_end = train_end + int(n_texts * self.val_split)

        # Dividir textos
        train_texts = texts_to_use[:train_end]
        val_texts = texts_to_use[train_end:val_end]
        test_texts = texts_to_use[val_end:]

        # Metadata por split (usando JSON Lines format)
        train_metadata = []
        val_metadata = []
        test_metadata = []

        # Calcular total de items a procesar
        if self.mode == 'words':
            total_words = sum(len(text_data['text'].split()) for text_data in texts_to_use)
            total_items = total_words * len(self.fonts)
        else:
            total_items = len(texts_to_use) * len(self.fonts)

        print(f"  Total imágenes esperadas: {total_items:,}")

        # Usar multiprocessing si num_workers > 1
        if self.num_workers > 1:
            self._generate_dataset_parallel(
                train_texts, val_texts, test_texts,
                train_metadata, val_metadata, test_metadata,
                target_height, total_items
            )
        else:
            self._generate_dataset_sequential(
                train_texts, val_texts, test_texts,
                train_metadata, val_metadata, test_metadata,
                target_height, total_items
            )

        # Guardar metadata.jsonl para cada split (formato JSON Lines)
        self._save_metadata_jsonl(self.train_dir / 'metadata.jsonl', train_metadata)
        self._save_metadata_jsonl(self.val_dir / 'metadata.jsonl', val_metadata)
        self._save_metadata_jsonl(self.test_dir / 'metadata.jsonl', test_metadata)

        # Crear dataset_info.json
        self._create_dataset_info()

        print(f"  [OK] {self.stats['images_generated']:,} imágenes generadas")
        print(f"    Train: {self.stats['train_samples']:,}")
        print(f"    Validation: {self.stats['val_samples']:,}")
        print(f"    Test: {self.stats['test_samples']:,}")

    def _generate_dataset_parallel(self, train_texts, val_texts, test_texts,
                                    train_metadata, val_metadata, test_metadata,
                                    target_height, total_items):
        """
        Genera dataset usando multiprocessing

        Thread-safety:
        - NO hay race conditions: nombres de archivo son pre-asignados (únicos)
        - NO hay conflictos de escritura: cada worker escribe archivos distintos
        - Metadata se recolecta en proceso principal (thread-safe)

        Distribución de carga:
        - Todas las tareas se preparan antes (load balancing automático)
        - imap_unordered distribuye equitativamente entre workers
        - Chunksize calculado dinámicamente para optimizar
        """

        # Preparar todas las tareas (pre-asignar nombres de archivo)
        # THREAD-SAFE: nombres se calculan ANTES de multiprocessing
        tasks = []
        counters = {'train': 0, 'validation': 0, 'test': 0}

        for font_info in self.fonts:
            for split_name, split_texts, split_dir in [
                ('train', train_texts, self.train_dir),
                ('validation', val_texts, self.val_dir),
                ('test', test_texts, self.test_dir)
            ]:
                for text_data in split_texts:
                    text = text_data['text']

                    # Si modo es 'words', extraer palabras
                    if self.mode == 'words':
                        words = text.split()
                        if not words:
                            continue
                        words_to_render = words
                    else:  # 'lines'
                        words_to_render = [text]

                    # Para cada palabra/línea
                    for text_to_render in words_to_render:
                        # Pre-asignar nombre único (evita race conditions)
                        img_filename = f"{counters[split_name]:08d}.png"
                        counters[split_name] += 1

                        task = {
                            'text': text_to_render,
                            'font_path': str(font_info['path']),
                            'split_dir': str(split_dir),
                            'img_filename': img_filename,
                            'text_data': text_data,
                            'font_info': font_info,
                            'mode': self.mode,
                            'split_name': split_name
                        }
                        tasks.append(task)

        # Calcular chunksize óptimo para distribución equitativa
        # Fórmula: total_tasks / (workers * 4) para buen balance
        optimal_chunksize = max(1, len(tasks) // (self.num_workers * 4))

        if self.verbose:
            print(f"  [INFO] Total tareas: {len(tasks):,}")
            print(f"  [INFO] Chunksize: {optimal_chunksize}")

        # Configurar método de inicio según el sistema operativo
        # Windows requiere 'spawn', Linux/Mac pueden usar 'fork' (más eficiente)
        if platform.system() == 'Windows':
            ctx = mp.get_context('spawn')
        else:
            ctx = mp.get_context('fork')

        # Procesar en paralelo con Pool
        worker_fn = partial(_generate_single_image, target_height=target_height)

        with ctx.Pool(processes=self.num_workers) as pool:
            # Usar imap_unordered para mejor rendimiento y load balancing
            # imap_unordered distribuye tareas dinámicamente (no estático)
            results = []
            for result in tqdm(
                pool.imap_unordered(worker_fn, tasks, chunksize=optimal_chunksize),
                total=len(tasks),
                desc="Generando imágenes",
                unit="img"
            ):
                if result is not None:
                    results.append(result)

        # Organizar metadata por split (thread-safe, en proceso principal)
        for result in results:
            # Remover split_name antes de guardar (no es necesario en metadata final)
            split_name = result.pop('split_name', 'train')

            if split_name == 'train':
                train_metadata.append(result)
            elif split_name == 'validation':
                val_metadata.append(result)
            else:
                test_metadata.append(result)

        # Actualizar estadísticas (solo una vez, después de organizar)
        self.stats['images_generated'] = len(results)
        self.stats['train_samples'] = len(train_metadata)
        self.stats['val_samples'] = len(val_metadata)
        self.stats['test_samples'] = len(test_metadata)

        # Contar por tipo
        if self.mode == 'words':
            self.stats['words_generated'] = self.stats['images_generated']
        else:
            self.stats['lines_generated'] = self.stats['images_generated']

    def _generate_dataset_sequential(self, train_texts, val_texts, test_texts,
                                      train_metadata, val_metadata, test_metadata,
                                      target_height, total_items):
        """Genera dataset secuencialmente (código original)"""

        # Contadores globales de imágenes
        global_train_count = 0
        global_val_count = 0
        global_test_count = 0

        # Barra de progreso
        with tqdm(total=total_items, desc="Generando imágenes", unit="img") as pbar:
            # Iterar sobre todas las fuentes
            for font_info in self.fonts:
                # Procesar cada split
                for split_name, split_texts, split_dir, split_metadata in [
                    ('train', train_texts, self.train_dir, train_metadata),
                    ('validation', val_texts, self.val_dir, val_metadata),
                    ('test', test_texts, self.test_dir, test_metadata)
                ]:
                    # Iterar sobre todos los textos del split
                    for text_idx, text_data in enumerate(split_texts):
                        text = text_data['text']

                        # Si modo es 'words', extraer palabras
                        if self.mode == 'words':
                            words = text.split()
                            if not words:
                                continue
                            words_to_render = words
                        else:  # 'lines'
                            words_to_render = [text]

                        # Para cada palabra/línea
                        for text_to_render in words_to_render:
                            # Generar imagen
                            img = self.generate_image(text_to_render, font_info, target_height)

                            if img is None:
                                pbar.update(1)
                                continue

                            # Determinar nombre de archivo según el split
                            if split_name == 'train':
                                img_filename = f"{global_train_count:08d}.png"
                                global_train_count += 1
                                self.stats['train_samples'] += 1
                            elif split_name == 'validation':
                                img_filename = f"{global_val_count:08d}.png"
                                global_val_count += 1
                                self.stats['val_samples'] += 1
                            else:  # test
                                img_filename = f"{global_test_count:08d}.png"
                                global_test_count += 1
                                self.stats['test_samples'] += 1

                            # Guardar imagen en carpeta de split
                            img_path = split_dir / img_filename
                            img.save(img_path)

                            # Crear entrada de metadata (formato HuggingFace)
                            metadata_entry = {
                                'file_name': img_filename,
                                'text': text_to_render,
                                'font_name': font_info['name'],
                                'font_category': font_info['category'],
                                'font_style': font_info['style'],
                                'source_book': text_data['book'],
                                'mode': self.mode
                            }

                            split_metadata.append(metadata_entry)

                            self.stats['images_generated'] += 1

                            if self.mode == 'words':
                                self.stats['words_generated'] += 1
                            else:
                                self.stats['lines_generated'] += 1

                            # Actualizar barra de progreso
                            pbar.update(1)

        # Guardar metadata.jsonl para cada split (formato JSON Lines)
        self._save_metadata_jsonl(self.train_dir / 'metadata.jsonl', train_metadata)
        self._save_metadata_jsonl(self.val_dir / 'metadata.jsonl', val_metadata)
        self._save_metadata_jsonl(self.test_dir / 'metadata.jsonl', test_metadata)

        # Crear dataset_info.json
        self._create_dataset_info()

        print(f"  [OK] {self.stats['images_generated']:,} imágenes generadas")
        print(f"    Train: {self.stats['train_samples']:,}")
        print(f"    Validation: {self.stats['val_samples']:,}")
        print(f"    Test: {self.stats['test_samples']:,}")

    def _save_metadata_jsonl(self, filepath, metadata_list):
        """Guarda metadata en formato JSON Lines (una línea por entrada)"""
        with open(filepath, 'w', encoding='utf-8') as f:
            for entry in metadata_list:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def _create_dataset_info(self):
        """Crea el archivo dataset_info.json con información del dataset"""
        dataset_info = {
            'description': 'Synthetic Catalan handwriting dataset',
            'version': '1.0.0',
            'splits': {
                'train': {
                    'name': 'train',
                    'num_samples': self.stats['train_samples']
                },
                'validation': {
                    'name': 'validation',
                    'num_samples': self.stats['val_samples']
                },
                'test': {
                    'name': 'test',
                    'num_samples': self.stats['test_samples']
                }
            },
            'features': {
                'file_name': {'dtype': 'string'},
                'text': {'dtype': 'string'},
                'font_name': {'dtype': 'string'},
                'font_category': {'dtype': 'string'},
                'font_style': {'dtype': 'string'},
                'source_book': {'dtype': 'string'},
                'mode': {'dtype': 'string'}
            },
            'mode': self.mode,
            'style': self.style,
            'total_samples': self.stats['images_generated'],
            'num_fonts': len(self.fonts)
        }

        dataset_info_path = self.output_dir / 'dataset_info.json'
        with open(dataset_info_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)

        if self.verbose:
            print(f"  [SAVED] {dataset_info_path}")

    def generate_summary(self):
        """Genera resumen del dataset"""
        print("\n" + "=" * 60)
        print("RESUMEN DE GENERACIÓN - FORMATO HUGGINGFACE")
        print("=" * 60)
        print(f"Modo: {self.mode}")
        print(f"Estilo: {self.style}")
        print(f"\nFuentes:")
        print(f"  Con bold: {self.stats['fonts_with_bold']}")
        print(f"  Sin bold: {self.stats['fonts_without_bold']}")
        print(f"  Usadas: {self.stats['fonts_used']}")
        print(f"  Saltadas: {self.stats['fonts_skipped']}")
        print(f"\nImágenes generadas:")
        print(f"  Total: {self.stats['images_generated']:,}")
        if self.mode == 'words':
            print(f"  Palabras: {self.stats['words_generated']:,}")
        else:
            print(f"  Líneas: {self.stats['lines_generated']:,}")
        print(f"\nSplits:")
        print(f"  Train: {self.stats['train_samples']:,} ({self.train_split:.0%})")
        print(f"  Validation: {self.stats['val_samples']:,} ({self.val_split:.0%})")
        print(f"  Test: {self.stats['test_samples']:,} ({self.test_split:.0%})")
        print(f"\nEstructura del dataset:")
        print(f"  {self.output_dir.absolute()}/")
        print(f"    ├── train/")
        print(f"    │   ├── metadata.jsonl")
        print(f"    │   └── [imágenes .png]")
        print(f"    ├── validation/")
        print(f"    │   ├── metadata.jsonl")
        print(f"    │   └── [imágenes .png]")
        print(f"    ├── test/")
        print(f"    │   ├── metadata.jsonl")
        print(f"    │   └── [imágenes .png]")
        print(f"    └── dataset_info.json")
        print()

def main():
    parser = argparse.ArgumentParser(
        description='Generador de dataset sintético de texto catalán en formato HuggingFace'
    )
    parser.add_argument('--data-dir', default='data', help='Directorio con textos (default: data)')
    parser.add_argument('--fonts-dir', default='fonts', help='Directorio con fuentes (default: fonts)')
    parser.add_argument('--output-dir', default='output', help='Directorio de salida (default: output)')
    parser.add_argument('--mode', choices=['lines', 'words'], default='lines',
                        help='Modo: lines (líneas completas) o words (palabras) (default: lines)')
    parser.add_argument('--style', choices=['normal', 'bold'], default='normal',
                        help='Estilo de fuente: normal o bold (default: normal)')
    parser.add_argument('--train-split', type=float, default=0.8,
                        help='Proporción de datos para entrenamiento (default: 0.8)')
    parser.add_argument('--val-split', type=float, default=0.1,
                        help='Proporción de datos para validación (default: 0.1)')
    parser.add_argument('--max-texts', type=int, default=None,
                        help='Número máximo de textos a usar (default: todos)')
    parser.add_argument('--font-size', type=int, default=128,
                        help='Altura de imagen en píxeles (default: 128, compatible con IAM/TrOCR)')
    parser.add_argument('--workers', '-j', type=int, default=1,
                        help='Número de workers paralelos (default: 1). Usa -1 para todos los cores')
    parser.add_argument('--max-fonts-per-category', type=int, default=None,
                        help='Número máximo de fuentes por categoría (default: todas)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Mostrar información detallada')

    args = parser.parse_args()

    # Determinar número de workers
    num_workers = args.workers
    if num_workers == -1:
        num_workers = mp.cpu_count()
    elif num_workers < 1:
        num_workers = 1

    print("=" * 60)
    print("GENERADOR DE DATASET SINTÉTICO - FORMATO HUGGINGFACE")
    print("=" * 60)
    print()

    builder = SyntheticDatasetBuilder(
        data_dir=args.data_dir,
        fonts_dir=args.fonts_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        style=args.style,
        train_split=args.train_split,
        val_split=args.val_split,
        num_workers=num_workers,
        max_fonts_per_category=args.max_fonts_per_category,
        verbose=args.verbose
    )

    # Escanear fuentes
    builder.scan_fonts()

    # Cargar textos
    builder.load_texts()

    # Generar dataset
    builder.generate_dataset(
        max_texts=args.max_texts,
        target_height=args.font_size  # Renombrado a target_height internamente
    )

    # Resumen
    builder.generate_summary()

    print("[SUCCESS] Dataset generado correctamente!")

if __name__ == "__main__":
    # Necesario para multiprocessing en Windows con método 'spawn'
    if platform.system() == 'Windows':
        mp.freeze_support()
    main()
