#!/usr/bin/env python3
"""
Verify and clean book text files by replacing guillemets with angle brackets.
Replaces » with > and « with < in all .txt files.
"""

import os
from pathlib import Path
from tqdm import tqdm
import argparse

class BookCleaner:
    def __init__(self, data_dir='data', verbose=False, dry_run=False):
        self.data_dir = Path(data_dir)
        self.verbose = verbose
        self.dry_run = dry_run

        # Characters to replace
        self.replacements = {
            '»': '>',
            '«': '<'
        }

        self.stats = {
            'total_files': 0,
            'files_with_guillemets': 0,
            'files_cleaned': 0,
            'total_replacements': 0,
            'errors': 0
        }

        self.files_with_guillemets = []  # Store info about files with guillemets

    def get_all_text_files(self):
        """Get all .txt files from data directory"""
        text_files = []

        if not self.data_dir.exists():
            print(f"[ERROR] Data directory not found: {self.data_dir}")
            return []

        # Traverse all subdirectories
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.lower().endswith('.txt'):
                    file_path = Path(root) / file
                    # Get relative path from data_dir
                    rel_path = file_path.relative_to(self.data_dir)
                    text_files.append({
                        'path': file_path,
                        'relative': rel_path,
                        'book': rel_path.parts[0] if len(rel_path.parts) > 0 else 'Unknown'
                    })

        return text_files

    def check_and_clean_file(self, file_path):
        """Check if a file contains guillemets and clean them"""
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Count occurrences
            count_right = content.count('»')
            count_left = content.count('«')
            total_guillemets = count_right + count_left

            if total_guillemets == 0:
                return False, 0, None

            # Replace guillemets
            new_content = content
            for old_char, new_char in self.replacements.items():
                new_content = new_content.replace(old_char, new_char)

            return True, total_guillemets, new_content

        except Exception as e:
            return None, 0, str(e)

    def clean_all_files(self):
        """Clean all text files in the data directory"""
        print("=" * 60)
        print("BOOK CLEANER - Replace Guillemets with Angle Brackets")
        print("=" * 60)
        print()

        # Get all text files
        print("[1] Scanning data directory...")
        text_files = self.get_all_text_files()

        if not text_files:
            print("[ERROR] No text files found")
            return

        print(f"  [OK] Found {len(text_files)} text files")
        self.stats['total_files'] = len(text_files)

        # Check and clean each file
        print(f"\n[2] Checking and cleaning files...")

        for file_info in tqdm(text_files, desc="Processing files", unit="file"):
            file_path = file_info['path']
            has_guillemets, count, new_content = self.check_and_clean_file(file_path)

            if has_guillemets is None:
                # Error occurred
                self.stats['errors'] += 1
                if self.verbose:
                    print(f"  [ERROR] {file_info['relative']}: {new_content}")
                continue

            if has_guillemets:
                self.stats['files_with_guillemets'] += 1
                self.stats['total_replacements'] += count
                self.files_with_guillemets.append({
                    'path': file_path,
                    'relative': file_info['relative'],
                    'book': file_info['book'],
                    'count': count
                })

                if self.verbose:
                    print(f"  [CLEAN] {file_info['relative']} - {count} replacements")

                # Write cleaned content
                if not self.dry_run:
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        self.stats['files_cleaned'] += 1
                    except Exception as e:
                        self.stats['errors'] += 1
                        if self.verbose:
                            print(f"  [ERROR] Failed to write {file_info['relative']}: {e}")
                else:
                    if self.verbose:
                        print(f"  [DRY RUN] Would clean: {file_info['relative']}")

        # Summary
        print(f"\n[3] Cleaning Summary:")
        print(f"  Total files checked: {self.stats['total_files']}")
        print(f"  Files with guillemets: {self.stats['files_with_guillemets']}")
        if not self.dry_run:
            print(f"  Files cleaned: {self.stats['files_cleaned']}")
        print(f"  Total replacements: {self.stats['total_replacements']}")
        if self.stats['errors'] > 0:
            print(f"  Errors: {self.stats['errors']}")

        if self.files_with_guillemets:
            print(f"\n[4] Files with guillemets by book:")
            # Group by book
            by_book = {}
            for file in self.files_with_guillemets:
                book = file['book']
                if book not in by_book:
                    by_book[book] = []
                by_book[book].append(file)

            for book, files in sorted(by_book.items()):
                total_replacements = sum(f['count'] for f in files)
                print(f"  {book}: {len(files)} files, {total_replacements} replacements")
                if self.verbose:
                    for file in files[:5]:  # Show first 5
                        print(f"    - {file['relative'].name}: {file['count']} replacements")
                    if len(files) > 5:
                        print(f"    ... and {len(files) - 5} more")

    def generate_report(self, output_file='book_cleaning_report.txt'):
        """Generate a detailed report of cleaning"""
        if not self.files_with_guillemets:
            return

        print(f"\n[5] Generating report: {output_file}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("BOOK CLEANING REPORT\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Total files checked: {self.stats['total_files']}\n")
            f.write(f"Files with guillemets: {self.stats['files_with_guillemets']}\n")
            if not self.dry_run:
                f.write(f"Files cleaned: {self.stats['files_cleaned']}\n")
            f.write(f"Total replacements: {self.stats['total_replacements']}\n\n")

            f.write("=" * 60 + "\n")
            f.write("FILES WITH GUILLEMETS\n")
            f.write("=" * 60 + "\n\n")

            # Group by book
            by_book = {}
            for file in self.files_with_guillemets:
                book = file['book']
                if book not in by_book:
                    by_book[book] = []
                by_book[book].append(file)

            for book, files in sorted(by_book.items()):
                total_replacements = sum(f['count'] for f in files)
                f.write(f"\n{book} ({len(files)} files, {total_replacements} replacements)\n")
                f.write("-" * 60 + "\n")
                for file_info in files:
                    f.write(f"  File: {file_info['relative'].name}\n")
                    f.write(f"  Replacements: {file_info['count']}\n\n")

        print(f"  [OK] Report saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Clean book text files by replacing guillemets (» «) with angle brackets (> <)'
    )
    parser.add_argument('--data-dir', default='data', help='Data directory (default: data)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be cleaned without actually cleaning')
    parser.add_argument('--report', default='book_cleaning_report.txt', help='Output report file')

    args = parser.parse_args()

    cleaner = BookCleaner(
        data_dir=args.data_dir,
        verbose=args.verbose,
        dry_run=args.dry_run
    )

    # Clean all files
    cleaner.clean_all_files()

    # Generate report if there were files with guillemets
    if cleaner.files_with_guillemets:
        cleaner.generate_report(args.report)

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Total files: {cleaner.stats['total_files']}")
    print(f"Files with guillemets: {cleaner.stats['files_with_guillemets']}")
    if not args.dry_run:
        print(f"Files cleaned: {cleaner.stats['files_cleaned']}")
    print(f"Total replacements: {cleaner.stats['total_replacements']}")
    print()

    if args.dry_run:
        print("[DRY RUN] No files were actually modified")
        print("Run without --dry-run to clean the files")
    else:
        print("[SUCCESS] Book cleaning complete!")
        print("Guillemets (» «) have been replaced with angle brackets (> <)")

if __name__ == "__main__":
    main()
