import os
import json
import logging
import time
from src import scraper, extractor, ingestor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("batch_runner.log"),
        logging.StreamHandler()
    ]
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DOWNLOAD_DIR = os.path.join(DATA_DIR, 'downloads')
RESULTS_FILE = "batch_results.json"

def run_batch(query="MOF synthesis", limit=20):
    """
    Run batch testing: 
    1. Download 20 papers.
    2. Run Vision Extraction on all.
    3. Run Text Extraction on all.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # 1. Get Papers
    logging.info(f"Searching for {limit} papers with query '{query}'...")
    results = scraper.search_papers(query, max_results=limit)
    
    pdf_paths = []
    for res in results:
        try:
            path = scraper.download_pdf(res['pdf_url'], output_dir=DOWNLOAD_DIR, title=res['title'])
            pdf_paths.append(path)
        except Exception as e:
            logging.error(f"Failed to download {res['title']}: {e}")
            
    if not pdf_paths:
        logging.error("No papers found/downloaded.")
        return

    # 2. Vision Pass
    logging.info("=== STARTING VISION PASS ===")
    vision_results = {}
    for i, path in enumerate(pdf_paths):
        logging.info(f"Vision Processing {i+1}/{len(pdf_paths)}: {os.path.basename(path)}")
        try:
            content = ingestor.read_file(path, max_pages=3) # Limit pages for speed
            data = extractor.extract_synthesis_data(content, mode='vision')
            vision_results[os.path.basename(path)] = data
        except Exception as e:
            logging.error(f"Vision failed for {path}: {e}")
            vision_results[os.path.basename(path)] = {"error": str(e)}
        
        # Optional: Sleep to let GPU cool down if needed?
        # time.sleep(2) 

    # Unload Vision Model
    extractor.unload_model()
    
    # 3. Text Pass
    logging.info("=== STARTING TEXT PASS ===")
    text_results = {}
    for i, path in enumerate(pdf_paths):
        logging.info(f"Text Processing {i+1}/{len(pdf_paths)}: {os.path.basename(path)}")
        try:
            # For text pass, we need text content. Ingestor handles PDF->Text?
            # ingestor.read_file returns images for PDF. We need to force text or use OCR.
            # Current ingestor.read_file returns images if PDF.
            # We need a way to get text. 
            # Let's assume for now we use the 'clean_text' on the images (which is empty/placeholder) 
            # UNLESS we modify ingestor to support text extraction from PDF (pypdf).
            
            # Quick fix: Use pypdf directly here or modify ingestor.
            # Let's use pypdf here for simplicity if ingestor doesn't support it well yet.
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = ""
            for page in reader.pages[:5]:
                text += page.extract_text() + "\n"
            
            data = extractor.extract_synthesis_data(text, mode='text')
            text_results[os.path.basename(path)] = data
        except Exception as e:
            logging.error(f"Text failed for {path}: {e}")
            text_results[os.path.basename(path)] = {"error": str(e)}

    # Unload Text Model
    extractor.unload_model()

    # 4. Save Results
    output = {
        "vision": vision_results,
        "text": text_results
    }
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
        
    logging.info(f"Batch run complete. Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    
    run_batch(limit=args.limit)
