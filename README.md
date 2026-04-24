# Synthetic Catalan Handwriting Dataset Generator

Synthetic text dataset generator for training OCR models.

## 📋 Description

This project allows you to:
- Generate a synthetic dataset in **HuggingFace** format
- Parallel processing with multiple cores for acceleration

## 🗂️ Project Structure

```
.
├── download_fonts.py              # Font downloader
├── verify_and_clean_fonts.py     # Font verifier and cleaner
├── verify_and_clean_books.py     # Text verifier and cleaner
├── build_dataset.py               # Synthetic dataset generator
├── test_font_rendering.py        # Font rendering test utility
├── data/                          # Texts (by book)
├── fonts/                         # Fonts (by category)
└── output/                        # Generated dataset
    ├── train/
    │   ├── 00000000.png
    │   ├── ...
    │   └── metadata.jsonl
    ├── validation/
    │   ├── 00000000.png
    │   ├── ...
    │   └── metadata.jsonl
    ├── test/
    │   ├── 00000000.png
    │   ├── ...
    │   └── metadata.jsonl
    └── dataset_info.json
```

## 🚀 Installation

### Prerequisites
- Python 3.8+
- pip

### Install Dependencies

```bash
pip install -r requirements.txt
```

Main libraries:
- `Pillow` - Image generation
- `fontTools` - Font manipulation
- `tqdm` - Progress bars
- `datasets` - (Optional) For loading dataset with HuggingFace

## 📖 Complete Workflow

### 1. Download Handwriting Fonts

```bash
# Download fonts
python download_fonts.py -v

# Download with limit
python download_fonts.py --max-pages 5 --max-fonts 50 -v

# Additional options
python download_fonts.py --output-dir fonts --delay 2.0 -v
```

**Parameters:**
- `--output-dir`: Output directory (default: `fonts`)
- `--max-pages`: Maximum pages per category
- `--max-fonts`: Maximum fonts to download
- `--delay`: Delay between requests in seconds (default: 2.0)
- `-v, --verbose`: Show detailed information

---

### 2. Verify and Clean Fonts

**IMPORTANT!** This step removes fonts that cannot render Catalan characters or numbers.

```bash
# Preview what would be removed (dry run)
python verify_and_clean_fonts.py --dry-run -v

# Verify and remove invalid fonts
python verify_and_clean_fonts.py -v

# Only verify, don't remove
python verify_and_clean_fonts.py --no-remove -v
```

**Parameters:**
- `--fonts-dir`: Fonts directory (default: `fonts`)
- `--dry-run`: Show what would be removed without actually removing
- `--no-remove`: Only verify, don't remove
- `--report`: Report file (default: `font_verification_report.txt`)
- `-v, --verbose`: Show detailed information

**Verified characters:**
- Catalan characters: `·` (punt volat), `ç` (ce trencada)
- Numbers: 0-9
- Punctuation: `-, <, >, (, )`

The script performs **double verification**:
1. Checks if the font has characters in its table (cmap)
2. **Tests actual rendering** of each character with PIL (detects fonts with cmap but no glyphs)

---

### 3. Verify and Clean Texts (Optional)

```bash
# Verify books
python verify_and_clean_books.py -v

# View statistics without cleaning
python verify_and_clean_books.py --no-clean -v
```

---

### 4. Generate Synthetic Dataset

**Main step!** Generates the dataset in HuggingFace format compatible with TrOCR.

```bash
# Basic generation (1 core, may be slow)
python build_dataset.py --mode lines --style normal -v

# PARALLEL generation (recommended - uses all cores)
python build_dataset.py --mode lines --style normal --workers -1 -v

# Generation with 8 specific cores
python build_dataset.py --mode lines --style normal --workers 8 -v

# Limit fonts per category (e.g., 10 fonts from each: Handwritten, Script, Brush, etc.)
python build_dataset.py --mode lines --style normal --max-fonts-per-category 10 --workers -1 -v

# Generate dataset with only Handwritten fonts
python build_dataset.py --mode lines --style normal --category-filter Handwritten --workers -1 -v

# Generate dataset with custom output name (saves to output_handwritten/)
python build_dataset.py --mode lines --style normal --output-name handwritten --workers -1 -v

# Combine: only Handwritten fonts, saved to output_handwritten/
python build_dataset.py --mode lines --style normal --category-filter Handwritten --output-name handwritten --max-fonts-per-category 20 --workers -1 -v

# Full generation with all options
python build_dataset.py \
    --data-dir data \
    --fonts-dir fonts \
    --output-dir output \
    --mode lines \
    --style normal \
    --train-split 0.8 \
    --val-split 0.1 \
    --font-size 128 \
    --max-fonts-per-category 50 \
    --workers -1 \
    -v
```

**Main Parameters:**
- `--mode`: `lines` (5-word lines) or `words` (individual words) - default: `lines`
- `--style`: `normal` or `bold` - default: `normal`
- `--workers, -j`: Number of parallel cores. Use `-1` for all cores - default: `1`
- `--font-size`: Image height in pixels - default: `128` (IAM/TrOCR compatible)
- `--train-split`: Training proportion - default: `0.8` (80%)
- `--val-split`: Validation proportion - default: `0.1` (10%)
- `--max-texts`: Maximum number of texts to use
- `--max-fonts-per-category`: Maximum fonts per category (e.g., Handwritten, Script, Brush)
- `--category-filter`: Filter by specific category (e.g., Handwritten, Brush, Script, Calligraphy)
- `--output-name`: Custom name for output directory (e.g., `handwritten` → `output_handwritten`)
- `-v, --verbose`: Show detailed information

**Output Formats:**
- Images: RGB PNG, 128px height, variable width
- Metadata: JSON Lines (`.jsonl`) per split
- Dataset info: `dataset_info.json` with complete information

**Generated Splits:**
- Train: 80% (default)
- Validation: 10% (default)
- Test: 10% (automatic: 1 - train - val)

```bash
# Check how many cores you have
nproc                        # Linux/Mac
echo %NUMBER_OF_PROCESSORS%  # Windows
```

---

## 🧪 Testing and Utilities

### Font Rendering Test

```bash
# Test all fonts
python test_font_rendering.py --fonts-dir fonts -v

# Test a specific font
python test_font_rendering.py --font fonts/Brush/Amore_Mio/font.ttf

# Test with output image
python test_font_rendering.py \
    --font fonts/Brush/Amore_Mio/font.ttf \
    --output test_render.png
```

---

## 📊 Using the Dataset with TrOCR

### Load the Dataset

```python
from datasets import load_dataset

# Load generated dataset
dataset = load_dataset('imagefolder', data_dir='./output')

# View splits
print(dataset.keys())  # dict_keys(['train', 'validation', 'test'])

# View statistics
print(f"Train: {len(dataset['train'])} samples")
print(f"Validation: {len(dataset['validation'])} samples")
print(f"Test: {len(dataset['test'])} samples")

# View example
sample = dataset['train'][0]
print(f"Image: {sample['image']}")  # PIL Image
print(f"Text: {sample['text']}")    # String
```

### Fine-tune TrOCR

```python
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# Load pre-trained model
processor = TrOCRProcessor.from_pretrained('microsoft/trocr-base-handwritten')
model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-base-handwritten')

# Load dataset
dataset = load_dataset('imagefolder', data_dir='./output')

# Fine-tune (see HuggingFace Transformers documentation)
# ...
```

---

## 📝 Dataset Format

### File Structure

```
output/
├── train/
│   ├── 00000000.png          # Image (128px height, variable width)
│   ├── 00000001.png
│   ├── ...
│   └── metadata.jsonl        # Metadata in JSON Lines format
├── validation/
│   ├── 00000000.png
│   ├── ...
│   └── metadata.jsonl
├── test/
│   ├── 00000000.png
│   ├── ...
│   └── metadata.jsonl
└── dataset_info.json         # Dataset information
```

### metadata.jsonl Format

Each line is a JSON object:

```json
{"file_name": "00000000.png", "text": "això és una prova de", "font_name": "Amatic_SC", "font_category": "Handwriting", "font_style": "normal", "source_book": "Llibre_Example", "mode": "lines"}
{"file_name": "00000001.png", "text": "text en català amb números", "font_name": "Architects_Daughter", "font_category": "Handwriting", "font_style": "normal", "source_book": "Llibre_Example", "mode": "lines"}
```

### dataset_info.json

```json
{
  "description": "Synthetic dataset",
  "version": "1.0.0",
  "splits": {
    "train": {"name": "train", "num_samples": 80000},
    "validation": {"name": "validation", "num_samples": 10000},
    "test": {"name": "test", "num_samples": 10000}
  },
  "features": {
    "file_name": {"dtype": "string"},
    "text": {"dtype": "string"},
    "font_name": {"dtype": "string"},
    "font_category": {"dtype": "string"},
    "font_style": {"dtype": "string"},
    "source_book": {"dtype": "string"},
    "mode": {"dtype": "string"}
  },
  "mode": "lines",
  "style": "normal",
  "total_samples": 100000,
  "num_fonts": 2000
}
```

---

## 🎯 Technical Specifications

### Images

- **Format**: RGB PNG
- **Fixed height**: 128 pixels (compatible with IAM Database)
- **Variable width**: According to text length
- **No padding**: Padding is added during training
- **TrOCR preprocessing**: Automatic resize to 384×384 internally

### Texts

- **Language**: Catalan
- **Source**: Wikisource (validated books)
- **Lines mode**: 5-word chunks
- **Words mode**: Individual words

### Fonts

- **Type**: Handwriting/manuscript style
- **Verification**: Double check (cmap + rendering)
- **Required characters**: Catalan (·, ç), numbers (0-9), punctuation

---

## ⚙️ Compatibility

### Operating Systems

- ✅ **Windows** (multiprocessing with 'spawn' method)
- ✅ **Linux** (multiprocessing with 'fork' method, more efficient)
- ✅ **macOS** (multiprocessing with 'fork' method)

### ML Frameworks

- ✅ **HuggingFace Transformers** (TrOCR, ViT, etc.)
- ✅ **HuggingFace Datasets**
- ✅ **PyTorch**
- ✅ **TensorFlow** (with conversion)

---

## 🔧 Multiprocessing Technical Details

### Thread-Safety and Race Conditions

The code is designed to **completely avoid race conditions**:

1. **Unique pre-assigned filenames**:
   - Filenames (`00000000.png`, `00000001.png`, etc.) are calculated **BEFORE** launching workers
   - Each task has a guaranteed unique name
   - ✅ **No write conflicts**

2. **No concurrent writes**:
   - Each worker writes **different** files (pre-assigned names)
   - No locks or semaphores needed
   - ✅ **Thread-safe by design**

3. **Metadata in main process**:
   - Workers return metadata (don't write it)
   - Collection happens in main process
   - ✅ **No race conditions in metadata**

4. **Statistics updated at the end**:
   - Counters are updated **after** collecting all results
   - ✅ **No double counting**

### Equitable Load Distribution

The system guarantees **equitable distribution** among workers:

1. **Task preparation**:
   - All tasks are prepared beforehand (complete list)
   - Known total: `N_fonts × N_texts × words_per_text`

2. **Dynamic load balancing**:
   - Uses `pool.imap_unordered()` (not `map()`)
   - Workers dynamically take tasks from the pool
   - If a worker finishes quickly, it takes more tasks
   - ✅ **Automatic balancing**

3. **Optimized chunksize**:
   - Formula: `chunksize = max(1, total_tasks / (workers × 4))`
   - Example: 100,000 tasks with 8 workers = chunksize ~3,125
   - Reduces communication overhead
   - ✅ **Maximum efficiency**

4. **Method by OS**:
   - **Windows**: `'spawn'` method (required, slower)
   - **Linux/Mac**: `'fork'` method (faster, COW - Copy-On-Write)

### Expected Performance

**Note**: Efficiency decreases with more workers due to:
- Inter-process communication overhead
- I/O contention (disk)
- Memory bandwidth limits

**Recommendation**: Use `workers = number_of_cores - 2` to leave room for the OS.

---

## 🐛 Troubleshooting

### Fonts generate "unknown" characters (â–')

**Solution**: Run the font verifier with rendering:

```bash
python verify_and_clean_fonts.py -v
```

The script performs double verification (cmap + actual rendering).

### Dataset generation is very slow

**Solution**: Use multiprocessing with all cores:

```bash
python build_dataset.py --workers -1 -v
```

### Error "RuntimeError: context has already been set"

**Solution**: This can occur on Windows. Make sure:
- You're running the script as `python build_dataset.py` (not importing it)
- You have the latest code version with `mp.freeze_support()`

---

## 📚 References

- **TrOCR Paper**: [TrOCR: Transformer-based Optical Character Recognition with Pre-trained Models](https://arxiv.org/abs/2109.10282)
- **TrOCR HuggingFace**: [microsoft/trocr-base-handwritten](https://huggingface.co/microsoft/trocr-base-handwritten)
- **IAM Database**: [IAM Handwriting Database](https://fki.tic.heia-fr.ch/databases/iam-handwriting-database)
- **Wikisource Català**: [Categoria:Llibres validats](https://ca.wikisource.org/wiki/Categoria:Llibres_validats)

---

## 📄 License

This project is for educational and research purposes. Fonts have their own individual licenses. Wikisource texts are in the public domain or under free licenses.

---

## 🤝 Contributions

Suggestions and improvements are welcome. This is a research project for synthetic dataset generation.

---

## ✨ Quick Commands (Cheatsheet)

```bash
# 1. Download fonts
python download_fonts.py -v

# 2. Clean fonts
python verify_and_clean_fonts.py -v

# 3. Generate dataset (PARALLEL - RECOMMENDED)
python build_dataset.py --mode lines --style normal --workers -1 -v

# 3b. Generate dataset with limited fonts per category (faster, good for testing)
python build_dataset.py --mode lines --style normal --max-fonts-per-category 10 --workers -1 -v

# 3c. Generate specialized dataset (Handwritten only)
python build_dataset.py --mode lines --category-filter Handwritten --output-name handwritten --workers -1 -v

# 3d. Generate multiple specialized datasets
python build_dataset.py --category-filter Handwritten --output-name handwritten --max-fonts-per-category 50 --workers -1 -v
python build_dataset.py --category-filter Brush --output-name brush --max-fonts-per-category 30 --workers -1 -v
python build_dataset.py --category-filter Script --output-name script --max-fonts-per-category 40 --workers -1 -v

# 4. Load dataset
python -c "from datasets import load_dataset; ds = load_dataset('imagefolder', data_dir='./output'); print(ds)"

# 4b. Load specialized dataset
python -c "from datasets import load_dataset; ds = load_dataset('imagefolder', data_dir='./output_handwritten'); print(ds)"
```

**Ready to generate your synthetic dataset!** 🚀
