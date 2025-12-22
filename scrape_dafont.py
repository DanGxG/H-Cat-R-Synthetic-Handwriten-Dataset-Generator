#!/usr/bin/env python3
"""
DaFont Scraper for Catalan-Compatible Fonts
Finds fonts that support Catalan special characters, particularly l·l
"""

import requests
from bs4 import BeautifulSoup
import time
import csv
from urllib.parse import urljoin
import argparse
import io
import zipfile
from fontTools.ttLib import TTFont

class DaFontScraper:
    def __init__(self, use_accent_filter=True, verbose=False):
        self.base_url = "https://www.dafont.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.catalan_chars = ['à', 'è', 'é', 'í', 'ï', 'ò', 'ó', 'ú', 'ü', 'ç', '·']
        self.use_accent_filter = use_accent_filter
        self.verbose = verbose
        # DaFont filter parameters
        self.filter_params = "&a=on" if use_accent_filter else ""

    def get_page(self, url):
        """Fetch a page with error handling"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.ProxyError as e:
            print(f"❌ Network Error: DaFont appears to be blocked by your network/proxy")
            print(f"   You may need to run this script from a different network")
            print(f"   Error: {e}")
            return None
        except requests.RequestException as e:
            print(f"❌ Error fetching {url}: {e}")
            return None

    def get_font_categories(self):
        """Get all font categories from DaFont"""
        # Hardcoded list of major DaFont categories
        # This is more reliable than trying to scrape them
        categories = [
            ("Sans Serif", f"{self.base_url}/theme.php?cat=501"),
            ("Serif", f"{self.base_url}/theme.php?cat=502"),
            ("Fixed Width", f"{self.base_url}/theme.php?cat=503"),
            ("Various", f"{self.base_url}/theme.php?cat=504"),
            ("Script", f"{self.base_url}/theme.php?cat=601"),
            ("School", f"{self.base_url}/theme.php?cat=602"),
            ("Handwritten", f"{self.base_url}/theme.php?cat=603"),
            ("Brush", f"{self.base_url}/theme.php?cat=604"),
            ("Calligraphy", f"{self.base_url}/theme.php?cat=605"),
            ("Graffiti", f"{self.base_url}/theme.php?cat=606"),
            ("Typewriter", f"{self.base_url}/theme.php?cat=607"),
            ("Fancy", f"{self.base_url}/theme.php?cat=701"),
            ("Retro", f"{self.base_url}/theme.php?cat=702"),
            ("Modern", f"{self.base_url}/theme.php?cat=703"),
            ("Decorative", f"{self.base_url}/theme.php?cat=704"),
            ("Cartoon", f"{self.base_url}/theme.php?cat=801"),
            ("Bitmap", f"{self.base_url}/theme.php?cat=901"),
            ("Gothic", f"{self.base_url}/theme.php?cat=902"),
            ("Medieval", f"{self.base_url}/theme.php?cat=903"),
            ("Celtic", f"{self.base_url}/theme.php?cat=904"),
            ("Techno", f"{self.base_url}/theme.php?cat=101"),
            ("LCD", f"{self.base_url}/theme.php?cat=102"),
            ("Holiday", f"{self.base_url}/theme.php?cat=201"),
            ("Valentines", f"{self.base_url}/theme.php?cat=202"),
            ("Halloween", f"{self.base_url}/theme.php?cat=203"),
            ("Christmas", f"{self.base_url}/theme.php?cat=204"),
        ]

        return categories

    def scrape_category(self, category_url, category_name, max_pages=3):
        """Scrape fonts from a category"""
        fonts = []

        for page in range(1, max_pages + 1):
            if page == 1:
                # Add accent filter to the URL
                if '?' in category_url:
                    url = f"{category_url}{self.filter_params}&page={page}"
                else:
                    url = f"{category_url}?psize=m{self.filter_params}&page={page}"
            else:
                # DaFont pagination format
                if '?' in category_url:
                    url = f"{category_url}{self.filter_params}&page={page}"
                else:
                    url = f"{category_url}?psize=m{self.filter_params}&page={page}"

            print(f"  Scraping: {url}")
            html = self.get_page(url)
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')

            # Find font entries
            font_divs = soup.find_all('div', class_='lv1left')
            if not font_divs:
                # Try alternative structure
                font_divs = soup.find_all('div', style=lambda x: x and 'font-size' in x)

            for font_div in font_divs:
                font_link = font_div.find('a', href=True)
                if font_link:
                    font_name = font_link.get_text(strip=True)
                    font_url = urljoin(self.base_url, font_link['href'])

                    # Get font details page
                    font_info = self.get_font_details(font_url)
                    if font_info:
                        font_info['name'] = font_name
                        font_info['url'] = font_url
                        font_info['category'] = category_name
                        fonts.append(font_info)

            time.sleep(1)  # Be polite to the server

        return fonts

    def get_font_details(self, font_url):
        """Get detailed information about a font"""
        html = self.get_page(font_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        info = {
            'supports_catalan': False,
            'download_url': None
        }

        # Look for download link
        for link in soup.find_all('a', href=True):
            if link.get_text(strip=True).lower() == 'download':
                info['download_url'] = urljoin(self.base_url, link['href'])
                break

        # Check font file for Catalan support by downloading and inspecting it
        if info['download_url']:
            catalan_support = self.check_character_support(info['download_url'])
            info['supports_catalan'] = catalan_support

        return info

    def check_character_support(self, download_url):
        """
        Check if a font supports Catalan-specific characters, numbers, and punctuation by downloading and inspecting the font file.
        Since we're using the accent filter (&a=on), we need to verify:
        - U+00B7 (middle dot ·)
        - U+00E7 (ç with cedilla)
        - U+0030 to U+0039 (digits 0-9)
        - U+002D (hyphen -)
        - U+003C and U+003E (< >)
        - U+0028 and U+0029 (parentheses)
        """
        if not download_url:
            if self.verbose:
                print("      [X] No download URL available")
            return False

        # Download the font file
        try:
            response = requests.get(download_url, headers=self.headers, timeout=30)
            response.raise_for_status()
        except Exception as e:
            if self.verbose:
                print(f"      [X] Failed to download font: {e}")
            return False

        # Extract font file from ZIP if needed
        font_data = None
        font_filename = None

        if response.content[:2] == b'PK':  # ZIP file
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                    # Find TTF or OTF files
                    font_files = [f for f in zf.namelist() if f.lower().endswith(('.ttf', '.otf'))]

                    if not font_files:
                        if self.verbose:
                            print("      [X] No font files found in ZIP")
                        return False

                    # Check the first font file
                    font_filename = font_files[0]
                    font_data = zf.read(font_filename)

            except Exception as e:
                if self.verbose:
                    print(f"      [X] Failed to extract ZIP: {e}")
                return False
        else:
            # Direct font file
            font_data = response.content
            font_filename = "font"

        # Load and check the font
        try:
            font = TTFont(io.BytesIO(font_data))
            cmap = font.getBestCmap()

            if not cmap:
                if self.verbose:
                    print("      [X] No character map found in font")
                return False

        except Exception as e:
            if self.verbose:
                print(f"      [X] Failed to load font: {e}")
            return False

        # Check for Catalan-specific characters, numbers, and punctuation
        catalan_chars = {
            0x00B7: ('middle dot', '·'),
            0x00E7: ('c with cedilla', 'ç'),
            0x0030: ('0 (zero)', '0'),
            0x0031: ('1 (one)', '1'),
            0x0032: ('2 (two)', '2'),
            0x0033: ('3 (three)', '3'),
            0x0034: ('4 (four)', '4'),
            0x0035: ('5 (five)', '5'),
            0x0036: ('6 (six)', '6'),
            0x0037: ('7 (seven)', '7'),
            0x0038: ('8 (eight)', '8'),
            0x0039: ('9 (nine)', '9'),
            0x002D: ('hyphen-minus', '-'),
            0x003C: ('less than', '<'),
            0x003E: ('greater than', '>'),
            0x0028: ('left parenthesis', '('),
            0x0029: ('right parenthesis', ')'),
        }

        results = {}
        for codepoint, (name, char) in catalan_chars.items():
            if codepoint in cmap:
                glyph_name = cmap[codepoint]
                results[codepoint] = True
                if self.verbose:
                    print(f"      [OK] Found {char} (U+{codepoint:04X}) - {name} [glyph: {glyph_name}]")
            else:
                results[codepoint] = False
                if self.verbose:
                    print(f"      [X] Missing {char} (U+{codepoint:04X}) - {name}")

        # STRICT REQUIREMENT: ALL required characters must be present (Catalan chars + numbers + punctuation)
        if all(results.values()):
            if self.verbose:
                print(f"      [ACCEPT] Font has all required characters (Catalan chars + numbers + punctuation)")
            return True
        else:
            if self.verbose:
                missing = [f"{char}" for cp, (name, char) in catalan_chars.items() if not results.get(cp)]
                print(f"      [REJECT] Font missing: {', '.join(missing)}")
            return False

    def search_with_preview(self, search_text="l·l", category=""):
        """
        Alternative method: Use DaFont's preview feature to test fonts
        This simulates what you'd see when typing in the preview box
        """
        print(f"\nSearching fonts that can display: '{search_text}'")

        # DaFont's preview URL format
        preview_url = f"{self.base_url}/search.php?q={search_text}"
        if category:
            preview_url += f"&cat={category}"

        html = self.get_page(preview_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        compatible_fonts = []

        # Parse search results
        # This is a simplified version - actual implementation would need to be
        # adjusted based on DaFont's current HTML structure

        return compatible_fonts

    def save_results(self, fonts, filename='catalan_fonts.csv'):
        """Save results to CSV"""
        if not fonts:
            print("No fonts to save")
            return

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'category', 'url', 'supports_catalan', 'download_url'])
            writer.writeheader()
            writer.writerows(fonts)

        print(f"\n[OK] Results saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Scrape DaFont for Catalan-compatible fonts')
    parser.add_argument('--categories', type=int, default=3, help='Number of categories to scrape')
    parser.add_argument('--category-filter', type=str, default=None,
                        help='Filter by category name(s), comma-separated (e.g., "Handwritten,Script,Brush")')
    parser.add_argument('--pages', type=int, default=2, help='Number of pages per category')
    parser.add_argument('--output', default='catalan_fonts.csv', help='Output CSV file')
    parser.add_argument('--no-accent-filter', action='store_true',
                        help='Disable DaFont accent filter (include all fonts)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed character detection information')

    args = parser.parse_args()

    scraper = DaFontScraper(use_accent_filter=not args.no_accent_filter, verbose=args.verbose)

    print("Starting DaFont scraper for Catalan fonts...")
    print("=" * 60)
    if scraper.use_accent_filter:
        print("[OK] Using DaFont's accent filter (&a=on)")
    else:
        print("[WARNING] Accent filter disabled - checking all fonts")

    # Get categories
    print("\nFetching font categories...")
    categories = scraper.get_font_categories()
    print(f"Found {len(categories)} categories")

    # Filter categories by name if specified
    if args.category_filter:
        filter_names = [name.strip() for name in args.category_filter.split(',')]
        filtered_categories = [(name, url) for name, url in categories if name in filter_names]

        if not filtered_categories:
            print(f"\n[ERROR] No categories found matching: {', '.join(filter_names)}")
            print(f"Available categories: {', '.join([name for name, _ in categories])}")
            return

        categories_to_scrape = filtered_categories
        print(f"Filtered to {len(categories_to_scrape)} category(ies): {', '.join([name for name, _ in categories_to_scrape])}")
    else:
        categories_to_scrape = categories[:args.categories]

    all_fonts = []
    catalan_fonts = []

    # Scrape fonts from each category
    for i, (cat_name, cat_url) in enumerate(categories_to_scrape, 1):
        print(f"\n[{i}/{len(categories_to_scrape)}] Scraping category: {cat_name}")
        fonts = scraper.scrape_category(cat_url, cat_name, max_pages=args.pages)
        all_fonts.extend(fonts)

        # Filter for Catalan support
        catalan_in_category = [f for f in fonts if f.get('supports_catalan')]
        catalan_fonts.extend(catalan_in_category)
        print(f"  [OK] Found {len(catalan_in_category)} Catalan-compatible fonts in this category")

        time.sleep(2)  # Be respectful to the server

    # Results
    print("\n" + "=" * 60)
    print(f"RESULTS:")
    print(f"  Total fonts scraped: {len(all_fonts)}")
    print(f"  Catalan-compatible fonts: {len(catalan_fonts)}")

    if catalan_fonts:
        print(f"\nCatalan-compatible fonts found:")
        for font in catalan_fonts[:10]:  # Show first 10
            print(f"  • {font['name']}")
            print(f"    {font['url']}")

    # Save results
    scraper.save_results(catalan_fonts, args.output)

    print("\n[SUCCESS] Scraping complete!")

if __name__ == "__main__":
    main()