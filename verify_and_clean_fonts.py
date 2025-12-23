#!/usr/bin/env python3
"""
Verify existing fonts for Catalan character, number, and punctuation support.
Remove fonts that don't support all required characters.
"""

import os
import shutil
from pathlib import Path
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm
import argparse

class FontVerifier:
    def __init__(self, fonts_dir='fonts', verbose=False, dry_run=False):
        self.fonts_dir = Path(fonts_dir)
        self.verbose = verbose
        self.dry_run = dry_run

        # Required characters
        self.required_chars = {
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

        self.stats = {
            'total_fonts': 0,
            'valid_fonts': 0,
            'invalid_fonts': 0,
            'removed_fonts': 0,
            'errors': 0
        }

        self.invalid_fonts = []  # Store info about invalid fonts

    def check_font_file(self, font_path):
        """
        Check if a font file supports all required characters
        Uses both cmap check AND actual rendering test
        """
        try:
            # Step 1: Check cmap (character mapping table)
            font = TTFont(str(font_path))
            cmap = font.getBestCmap()

            if not cmap:
                return False, "No character map found"

            # Check for all required characters in cmap
            missing_in_cmap = []
            for codepoint, (name, char) in self.required_chars.items():
                if codepoint not in cmap:
                    missing_in_cmap.append(char)

            if missing_in_cmap:
                return False, f"Missing in cmap: {', '.join(missing_in_cmap)}"

            # Step 2: Test actual rendering with PIL (more robust check)
            # This catches fonts that have cmap entries but fail to render
            try:
                pil_font = ImageFont.truetype(str(font_path), 32)
                test_img = Image.new('RGB', (200, 50), 'white')
                draw = ImageDraw.Draw(test_img)

                # Test each required character
                cannot_render = []
                for codepoint, (name, char) in self.required_chars.items():
                    try:
                        # Try to get bounding box - if it fails, font can't render it
                        bbox = draw.textbbox((0, 0), char, font=pil_font)
                        width = bbox[2] - bbox[0]

                        # Some fonts have glyphs with 0 width for missing chars
                        if width <= 0:
                            cannot_render.append(char)

                    except Exception:
                        cannot_render.append(char)

                if cannot_render:
                    return False, f"Cannot render: {', '.join(cannot_render)}"

            except Exception as e:
                return False, f"PIL rendering error: {str(e)}"

            return True, "All characters supported and renderable"

        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_all_font_files(self):
        """Get all font files from fonts directory"""
        font_files = []

        if not self.fonts_dir.exists():
            print(f"[ERROR] Fonts directory not found: {self.fonts_dir}")
            return []

        # Traverse all subdirectories
        for root, dirs, files in os.walk(self.fonts_dir):
            for file in files:
                if file.lower().endswith(('.ttf', '.otf')):
                    font_path = Path(root) / file
                    # Get relative path from fonts_dir
                    rel_path = font_path.relative_to(self.fonts_dir)
                    font_files.append({
                        'path': font_path,
                        'relative': rel_path,
                        'category': rel_path.parts[0] if len(rel_path.parts) > 1 else 'Unknown',
                        'font_folder': rel_path.parts[1] if len(rel_path.parts) > 2 else rel_path.parts[0]
                    })

        return font_files

    def verify_all_fonts(self):
        """Verify all fonts in the fonts directory"""
        print("=" * 60)
        print("FONT VERIFICATION - Catalan Characters + Numbers + Punctuation")
        print("=" * 60)
        print()

        # Get all font files
        print("[1] Scanning fonts directory...")
        font_files = self.get_all_font_files()

        if not font_files:
            print("[ERROR] No font files found")
            return

        print(f"  [OK] Found {len(font_files)} font files")
        self.stats['total_fonts'] = len(font_files)

        # Verify each font
        print(f"\n[2] Verifying fonts...")

        for font_info in tqdm(font_files, desc="Checking fonts", unit="font"):
            font_path = font_info['path']
            is_valid, message = self.check_font_file(font_path)

            if is_valid:
                self.stats['valid_fonts'] += 1
                if self.verbose:
                    print(f"  [OK] {font_info['relative']}")
            else:
                self.stats['invalid_fonts'] += 1
                self.invalid_fonts.append({
                    'path': font_path,
                    'relative': font_info['relative'],
                    'category': font_info['category'],
                    'font_folder': font_info['font_folder'],
                    'reason': message
                })
                if self.verbose:
                    print(f"  [X] {font_info['relative']} - {message}")

        # Summary
        print(f"\n[3] Verification Summary:")
        print(f"  Total fonts checked: {self.stats['total_fonts']}")
        print(f"  Valid fonts: {self.stats['valid_fonts']}")
        print(f"  Invalid fonts: {self.stats['invalid_fonts']}")

        if self.invalid_fonts:
            print(f"\n[4] Invalid fonts by category:")
            # Group by category
            by_category = {}
            for font in self.invalid_fonts:
                cat = font['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(font)

            for category, fonts in sorted(by_category.items()):
                print(f"  {category}: {len(fonts)} fonts")
                if self.verbose:
                    for font in fonts[:5]:  # Show first 5
                        print(f"    - {font['font_folder']}: {font['reason']}")
                    if len(fonts) > 5:
                        print(f"    ... and {len(fonts) - 5} more")

    def remove_invalid_fonts(self):
        """Remove invalid font folders"""
        if not self.invalid_fonts:
            print("\n[OK] No invalid fonts to remove")
            return

        print(f"\n[5] Removing invalid fonts...")

        if self.dry_run:
            print("  [DRY RUN] The following would be removed:")

        # Group by font folder (so we remove entire font folders, not individual files)
        folders_to_remove = set()
        for font in self.invalid_fonts:
            # Get the font folder path (category/font_name)
            font_folder = font['path'].parent
            folders_to_remove.add(font_folder)

        for folder in tqdm(sorted(folders_to_remove), desc="Removing folders", unit="folder"):
            try:
                if self.dry_run:
                    print(f"  [DRY RUN] Would remove: {folder.relative_to(self.fonts_dir)}")
                else:
                    shutil.rmtree(folder)
                    self.stats['removed_fonts'] += 1
                    if self.verbose:
                        print(f"  [REMOVED] {folder.relative_to(self.fonts_dir)}")
            except Exception as e:
                self.stats['errors'] += 1
                print(f"  [ERROR] Failed to remove {folder.relative_to(self.fonts_dir)}: {e}")

        if not self.dry_run:
            print(f"\n  [OK] Removed {self.stats['removed_fonts']} font folders")
            if self.stats['errors'] > 0:
                print(f"  [WARNING] {self.stats['errors']} errors occurred")

    def generate_report(self, output_file='font_verification_report.txt'):
        """Generate a detailed report of invalid fonts"""
        if not self.invalid_fonts:
            return

        print(f"\n[6] Generating report: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("FONT VERIFICATION REPORT\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Total fonts checked: {self.stats['total_fonts']}\n")
            f.write(f"Valid fonts: {self.stats['valid_fonts']}\n")
            f.write(f"Invalid fonts: {self.stats['invalid_fonts']}\n\n")

            f.write("=" * 60 + "\n")
            f.write("INVALID FONTS DETAILS\n")
            f.write("=" * 60 + "\n\n")

            # Group by category
            by_category = {}
            for font in self.invalid_fonts:
                cat = font['category']
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(font)

            for category, fonts in sorted(by_category.items()):
                f.write(f"\n{category} ({len(fonts)} fonts)\n")
                f.write("-" * 60 + "\n")
                for font in fonts:
                    f.write(f"  Font: {font['font_folder']}\n")
                    f.write(f"  Path: {font['relative']}\n")
                    f.write(f"  Reason: {font['reason']}\n\n")

        print(f"  [OK] Report saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Verify and clean fonts that don\'t support Catalan characters, numbers, and punctuation'
    )
    parser.add_argument('--fonts-dir', default='fonts', help='Fonts directory (default: fonts)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without actually removing')
    parser.add_argument('--no-remove', action='store_true', help='Only verify, don\'t remove invalid fonts')
    parser.add_argument('--report', default='font_verification_report.txt', help='Output report file')

    args = parser.parse_args()

    verifier = FontVerifier(
        fonts_dir=args.fonts_dir,
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    # Verify all fonts
    verifier.verify_all_fonts()

    # Generate report if there are invalid fonts
    if verifier.invalid_fonts:
        verifier.generate_report(args.report)

    # Remove invalid fonts unless --no-remove is specified
    if not args.no_remove:
        verifier.remove_invalid_fonts()

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Total fonts: {verifier.stats['total_fonts']}")
    print(f"Valid fonts: {verifier.stats['valid_fonts']}")
    print(f"Invalid fonts: {verifier.stats['invalid_fonts']}")
    if not args.no_remove and not args.dry_run:
        print(f"Removed: {verifier.stats['removed_fonts']} font folders")
    print()

    if args.dry_run:
        print("[DRY RUN] No files were actually removed")
        print("Run without --dry-run to remove invalid fonts")
    elif args.no_remove:
        print("[NO REMOVE] Fonts were verified but not removed")
        print("Run without --no-remove to remove invalid fonts")
    else:
        print("[SUCCESS] Font verification and cleanup complete!")

if __name__ == "__main__":
    main()
