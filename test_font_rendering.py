#!/usr/bin/env python3
"""
Test font rendering to detect fonts that have character mapping but fail to render
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import argparse

def test_font_rendering(font_path, test_string="0123456789·çAaBbÇç", font_size=64):
    """
    Test if a font can actually render characters (not just have them in cmap)

    Returns:
        (bool, str): (success, message/error)
    """
    try:
        # Load font
        font = ImageFont.truetype(str(font_path), font_size)

        # Create test image
        img = Image.new('RGB', (800, 100), 'white')
        draw = ImageDraw.Draw(img)

        # Try to draw the test string
        draw.text((10, 10), test_string, font=font, fill='black')

        # Check if any character was replaced by .notdef (unknown glyph)
        # PIL doesn't give direct access to this, but we can check the rendered image
        # For a more thorough check, we test individual characters

        missing_chars = []
        for char in test_string:
            try:
                # Try to get bounding box for this character
                bbox = draw.textbbox((0, 0), char, font=font)
                width = bbox[2] - bbox[0]

                # If width is 0 or very small, the glyph might be missing
                if width < 2:
                    missing_chars.append(char)
            except Exception as e:
                missing_chars.append(char)

        if missing_chars:
            return False, f"Cannot render: {', '.join(set(missing_chars))}"

        return True, "All characters render correctly"

    except Exception as e:
        return False, f"Error loading font: {str(e)}"

def scan_fonts(fonts_dir='fonts', verbose=False):
    """Scan all fonts and test rendering"""
    fonts_dir = Path(fonts_dir)

    print("=" * 60)
    print("FONT RENDERING TEST")
    print("=" * 60)
    print()

    valid_count = 0
    invalid_count = 0
    invalid_fonts = []

    # Get all fonts
    font_files = list(fonts_dir.glob('**/*.ttf')) + list(fonts_dir.glob('**/*.otf'))

    print(f"Testing {len(font_files)} fonts...\n")

    for font_path in font_files:
        rel_path = font_path.relative_to(fonts_dir)
        success, message = test_font_rendering(font_path)

        if success:
            valid_count += 1
            if verbose:
                print(f"✓ {rel_path}")
        else:
            invalid_count += 1
            invalid_fonts.append((rel_path, message))
            print(f"✗ {rel_path}")
            print(f"  → {message}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total fonts: {len(font_files)}")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {invalid_count}")

    if invalid_fonts:
        print(f"\n{invalid_count} fonts cannot render all test characters")

    return invalid_fonts

def test_single_font(font_path, test_string="0123456789·çAaBbÇç", output_image=None):
    """Test a single font and optionally save test image"""
    font_path = Path(font_path)

    print(f"Testing font: {font_path.name}")
    print(f"Test string: {test_string}")
    print()

    success, message = test_font_rendering(font_path, test_string)

    print(f"Result: {message}")

    if output_image:
        # Create a visual test image
        try:
            font = ImageFont.truetype(str(font_path), 64)
            img = Image.new('RGB', (1000, 150), 'white')
            draw = ImageDraw.Draw(img)

            # Draw test string
            draw.text((10, 10), f"Font: {font_path.name}", font=ImageFont.load_default(), fill='black')
            draw.text((10, 50), test_string, font=font, fill='black')

            img.save(output_image)
            print(f"\nTest image saved: {output_image}")
        except Exception as e:
            print(f"\nError creating test image: {e}")

    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test font rendering capabilities')
    parser.add_argument('--fonts-dir', default='fonts', help='Fonts directory')
    parser.add_argument('--font', type=str, help='Test a single font file')
    parser.add_argument('--test-string', default='0123456789·çAaBb',
                        help='String to test rendering')
    parser.add_argument('--output', type=str, help='Output test image (only with --font)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all fonts')

    args = parser.parse_args()

    if args.font:
        # Test single font
        test_single_font(args.font, args.test_string, args.output)
    else:
        # Scan all fonts
        scan_fonts(args.fonts_dir, args.verbose)
