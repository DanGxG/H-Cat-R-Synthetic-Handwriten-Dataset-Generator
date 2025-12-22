#!/usr/bin/env python3
"""
Script para scrapear libros validados de Wikisource en catalán
Objetivo: Crear dataset sintético de líneas y palabras
"""

import requests
from bs4 import BeautifulSoup
import time
import os
from pathlib import Path
import argparse
import json
from urllib.parse import urljoin, urlparse
import re

class WikisourceScraper:
    def __init__(self, output_dir='data', delay=1.0, verbose=False):
        self.base_url = "https://ca.wikisource.org"
        self.output_dir = Path(output_dir)
        self.delay = delay
        self.verbose = verbose
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Crear directorio de salida
        self.output_dir.mkdir(exist_ok=True)

    def get_page(self, url):
        """Obtiene el contenido de una página"""
        try:
            if self.verbose:
                print(f"    Fetching: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"    [ERROR] Error fetching {url}: {e}")
            return None

    def sanitize_filename(self, filename):
        """Sanitiza el nombre del archivo"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', '_', filename)
        if len(filename) > 200:
            filename = filename[:200]
        return filename

    def get_validated_books(self):
        """Obtiene la lista de libros validados de la categoría"""
        url = "https://ca.wikisource.org/wiki/Categoria:Llibres_validats"

        print("[1] Obteniendo lista de libros validados...")
        html = self.get_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        books = []

        # Buscar todos los grupos de categoría
        category_groups = soup.find_all('div', class_='mw-category-group')

        for group in category_groups:
            # Encontrar todos los enlaces en el grupo
            links = group.find_all('a')
            for link in links:
                if link.get('href'):
                    book_url = urljoin(self.base_url, link['href'])
                    book_title = link.get_text(strip=True)
                    books.append({
                        'title': book_title,
                        'url': book_url
                    })

        print(f"  [OK] Encontrados {len(books)} libros validados")
        return books

    def get_validated_pages(self, book_url):
        """Obtiene las páginas validadas de un libro"""
        html = self.get_page(book_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        validated_pages = []

        # Buscar la lista de páginas del índice
        pagelist = soup.find('div', class_='prp-index-pagelist')
        if not pagelist:
            if self.verbose:
                print(f"    [WARNING] No se encontró prp-index-pagelist")
            return []

        # Buscar enlaces con quality4 (páginas validadas)
        quality4_links = pagelist.find_all('a', class_=lambda x: x and 'prp-pagequality-4' in x and 'quality4' in x)

        for link in quality4_links:
            if link.get('href'):
                page_url = urljoin(self.base_url, link['href'])
                page_title = link.get('title', link.get_text(strip=True))
                validated_pages.append({
                    'title': page_title,
                    'url': page_url
                })

        if self.verbose:
            print(f"    [OK] Encontradas {len(validated_pages)} páginas validadas")

        return validated_pages

    def extract_page_content(self, page_url):
        """Extrae el contenido de texto de una página"""
        html = self.get_page(page_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Estructura: prp-page-qualityheader quality4 -> hermano pagetext -> dentro mw-content-ltr mw-parser-output
        quality_header = soup.find('div', class_=lambda x: x and 'prp-page-qualityheader' in x and 'quality4' in x)

        if not quality_header:
            if self.verbose:
                print(f"    [WARNING] No se encontró prp-page-qualityheader quality4")
            return None

        # Buscar el hermano siguiente que es pagetext
        pagetext = quality_header.find_next_sibling('div', class_='pagetext')

        if not pagetext:
            if self.verbose:
                print(f"    [WARNING] No se encontró pagetext después de quality4")
            return None

        # Dentro de pagetext, buscar mw-content-ltr mw-parser-output
        page_content = pagetext.find('div', class_='mw-content-ltr mw-parser-output')

        if not page_content:
            if self.verbose:
                print(f"    [WARNING] No se encontró mw-content-ltr mw-parser-output dentro de pagetext")
            return None

        # Extraer texto
        # Eliminar scripts, styles, etc.
        for tag in page_content(['script', 'style', 'sup', 'ref']):
            tag.decompose()

        # Obtener texto
        text = page_content.get_text(separator='\n', strip=True)

        # Limpiar texto
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        return {
            'text': '\n'.join(lines),
            'lines': lines,
            'num_lines': len(lines),
            'num_words': sum(len(line.split()) for line in lines)
        }

    def save_content(self, book_title, page_title, content, book_index, page_index):
        """Guarda el contenido extraído"""
        # Crear estructura de carpetas: data/[libro]/
        safe_book_name = self.sanitize_filename(book_title)
        book_dir = self.output_dir / safe_book_name
        book_dir.mkdir(exist_ok=True)

        # Nombre del archivo de página
        safe_page_name = self.sanitize_filename(page_title)

        # Guardar como texto plano
        txt_file = book_dir / f"{page_index:04d}_{safe_page_name}.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(content['text'])

        # Guardar metadatos como JSON
        json_file = book_dir / f"{page_index:04d}_{safe_page_name}.json"
        metadata = {
            'book_title': book_title,
            'page_title': page_title,
            'book_index': book_index,
            'page_index': page_index,
            'num_lines': content['num_lines'],
            'num_words': content['num_words']
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        if self.verbose:
            print(f"    [SAVED] {txt_file.name} ({content['num_lines']} líneas, {content['num_words']} palabras)")

    def scrape_all(self, max_books=None):
        """Scrape completo de Wikisource catalán"""
        print("=" * 60)
        print("WIKISOURCE CATALÁN - SCRAPER DE LIBROS VALIDADOS")
        print("=" * 60)
        print()

        # Obtener lista de libros
        books = self.get_validated_books()

        if not books:
            print("[ERROR] No se encontraron libros")
            return

        # Limitar número de libros si se especifica
        if max_books:
            books = books[:max_books]
            print(f"\n[INFO] Limitado a {max_books} libros")

        print(f"\n[2] Procesando {len(books)} libros...")
        print("=" * 60)

        total_pages = 0
        total_lines = 0
        total_words = 0

        # Procesar cada libro
        for book_idx, book in enumerate(books, 1):
            print(f"\n[{book_idx}/{len(books)}] Libro: {book['title']}")
            print(f"  URL: {book['url']}")

            # Obtener páginas validadas
            pages = self.get_validated_pages(book['url'])

            if not pages:
                print(f"  [SKIP] No hay páginas validadas")
                continue

            print(f"  [INFO] Procesando {len(pages)} páginas validadas...")

            # Procesar cada página
            for page_idx, page in enumerate(pages, 1):
                if self.verbose:
                    print(f"  [{page_idx}/{len(pages)}] Página: {page['title']}")

                # Extraer contenido
                content = self.extract_page_content(page['url'])

                if content and content['num_lines'] > 0:
                    # Guardar contenido
                    self.save_content(
                        book['title'],
                        page['title'],
                        content,
                        book_idx,
                        page_idx
                    )

                    total_pages += 1
                    total_lines += content['num_lines']
                    total_words += content['num_words']
                else:
                    if self.verbose:
                        print(f"    [SKIP] Sin contenido válido")

                # Delay entre páginas
                time.sleep(self.delay)

            # Delay entre libros
            time.sleep(self.delay * 2)

        # Resumen final
        print("\n" + "=" * 60)
        print("RESUMEN FINAL")
        print("=" * 60)
        print(f"  Libros procesados: {len(books)}")
        print(f"  Páginas guardadas: {total_pages}")
        print(f"  Total líneas: {total_lines:,}")
        print(f"  Total palabras: {total_words:,}")
        print(f"\n[SUCCESS] Dataset guardado en: {self.output_dir.absolute()}")
        print()

def main():
    parser = argparse.ArgumentParser(
        description='Scraper de Wikisource en catalán para crear dataset sintético'
    )
    parser.add_argument('--output-dir', default='data', help='Directorio de salida (default: data)')
    parser.add_argument('--max-books', type=int, default=None, help='Número máximo de libros a procesar')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay entre requests en segundos (default: 1.0)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar información detallada')

    args = parser.parse_args()

    scraper = WikisourceScraper(
        output_dir=args.output_dir,
        delay=args.delay,
        verbose=args.verbose
    )

    scraper.scrape_all(max_books=args.max_books)

if __name__ == "__main__":
    main()
