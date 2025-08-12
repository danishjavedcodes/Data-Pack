# TARUMResearch Dataset Builder

A Streamlit dashboard and modular pipeline to scrape images from Unsplash using their official API, preprocess them (watermark removal, resizing, standardization), generate prompts (captions), classify image types, perform quality control, and export the final dataset in multiple formats (CSV, JSON, Parquet, HDF5).

## Features

### 🎯 **Image Collection**
- **Official Unsplash API** - Reliable access using documented endpoints
- **Production rate limits** - 5000 requests/hour with proper API key
- **High-quality images** - 1080px width images by default
- **No blocking issues** - Official API prevents 403 errors

### 🔧 **Image Processing**
- **Batch preprocessing**: resize, format conversion, simple enhancements
- **Optional watermark removal** using heuristic algorithms
- **Quality filtering** - minimum size requirements
- **Format standardization** - consistent output formats

### 🤖 **AI-Powered Features**
- **Local prompt generation** using BLIP captioning model (runs on CPU/GPU)
- **Image type classification** via zero-shot CLIP (photograph, illustration, vector)
- **Quality control**: duplicate detection with perceptual hashes
- **Smart filtering** - exclude low-quality or inappropriate content

### 📊 **Dataset Management**
- **Multiple export formats**: CSV, JSON, Parquet, HDF5
- **SQLite metadata storage** - track all image information
- **Interactive dashboard** - view, filter, and manage images
- **Comprehensive statistics** - detailed analytics and reporting

## Quickstart

### 1. Setup Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Get Unsplash API Key (Optional)
For production use, get a free API key from [Unsplash Developers](https://unsplash.com/developers):
- Register as a developer
- Create a new application
- Copy your Access Key
- Update the scraper with your key for 5000 requests/hour

### 3. Launch Dashboard
```bash
# Local access
streamlit run app.py

# Public access with ngrok
python run_with_pyngrok.py
```

### 4. Use the Dashboard
Navigate through the sidebar:
- **Scrape**: Search Unsplash with keywords, set limits
- **Preprocess**: Select and process images
- **Create Dataset**: Generate prompts, run QC, export
- **View Images**: Browse, filter, and inspect your collection

## Data Layout
```
data/
├── raw/           # Downloaded original images
├── processed/     # Processed images (resized, enhanced)
├── final/         # Exported dataset files
└── metadata.db    # SQLite database with all metadata
```

## API Configuration

### Current Setup
- **Application ID**: 790856
- **Access Key**: IDIRKPCHUQLvHbPXkJ4nN3BVduzGLYXUq_FC-PsYkp8
- **Rate Limit**: 5000 requests/hour (Production)
- **Status**: Production mode active

### Benefits
- ✅ **No 403 errors** - Official API access
- ✅ **High rate limits** - 5000 vs 50 requests/hour
- ✅ **Stable access** - Reliable and consistent
- ✅ **Full features** - All API endpoints available

## Technical Details

### Dependencies
- **Streamlit** - Web dashboard interface
- **httpx** - Modern HTTP client for API calls
- **Pillow/OpenCV** - Image processing
- **Transformers** - BLIP and CLIP models
- **Pandas** - Data manipulation and export
- **SQLite** - Local metadata storage

### Models Used
- **BLIP** - Image captioning and prompt generation
- **CLIP** - Zero-shot image classification
- **ImageHash** - Perceptual hashing for duplicates

## Notes

- **API Compliance**: Uses official Unsplash API following their guidelines
- **Rate Limiting**: Automatically respects API rate limits
- **Attribution**: Properly attributes photographers as required
- **Quality Control**: Manual review recommended for final datasets
- **GPU Recommended**: For faster processing of large datasets

## Deployment

### Local Development
```bash
streamlit run app.py
```

### Public Access (ngrok)
```bash
python run_with_pyngrok.py
```

### Production Deployment
- Set up proper API keys
- Configure environment variables
- Use production-grade hosting
- Monitor rate limits and usage