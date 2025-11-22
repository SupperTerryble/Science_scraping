import argparse
import os
import subprocess
import time
import requests
import sys
import logging
from src import db_manager, ingestor, extractor, scraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def is_ollama_running():
    """Check if Ollama is already running."""
    try:
        requests.get("http://localhost:11434/api/tags", timeout=1)
        return True
    except requests.exceptions.ConnectionError:
        return False

def start_ollama():
    """Start Ollama serve as a subprocess."""
    if is_ollama_running():
        logging.info("Ollama is already running.")
        return None

    logging.info("Starting Ollama...")
    # Redirect output to devnull to keep console clean, or log to file
    process = subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for it to be ready
    logging.info("Waiting for Ollama to be ready...")
    for _ in range(30): # Wait up to 30 seconds
        if is_ollama_running():
            logging.info("Ollama is ready.")
            return process
        time.sleep(1)
    
    logging.error("Failed to start Ollama.")
    process.terminate()
    return None

def stop_ollama(process):
    """Stop the Ollama subprocess."""
    if process:
        logging.info("Stopping Ollama...")
        process.terminate()
        process.wait()
        logging.info("Ollama stopped.")

def process_paper(file_path: str, mock: bool = True):
    """Run the full pipeline on a single paper."""
    logging.info(f"Processing {file_path}...")
    
    # 1. Ingest
    try:
        # Limit to 5 pages to save RAM
        content = ingestor.read_file(file_path, max_pages=5)
        # clean_text is not needed for images, but we keep a string representation for DB
        text_preview = "Image Content" if isinstance(content, list) else ingestor.clean_text(content)
    except Exception as e:
        logging.error(f"Failed to read file: {e}")
        return

    # 2. Extract
    logging.info("Extracting data...")
    data = extractor.extract_synthesis_data(content, mock=mock)
    
    if not data:
        logging.warning("No data extracted.")
        return
        
    logging.info(f"Extracted: {data.get('target_material')} via {data.get('method_type')}")
    if data.get('visual_evidence'):
        logging.info(f"Visual Evidence: {data.get('visual_evidence')}")

    # 3. Save to DB
    logging.info("Saving to database...")
    # Initialize DB if needed
    db_manager.init_db()
    
    # Insert Paper
    paper_id = db_manager.insert_paper(
        title=os.path.basename(file_path),
        doi=f"file://{os.path.basename(file_path)}", # Dummy DOI for local files
        text_content=text_preview[:500] + "..." # Store only start to save space/time
    )
    
    # Insert Synthesis
    synthesis_id = db_manager.insert_synthesis(
        paper_id=paper_id,
        target_material=data.get('target_material', 'Unknown'),
        method_type=data.get('method_type', 'Unknown'),
        description=data.get('description', '')
    )
    
    # Insert Precursors
    for prec in data.get('precursors', []):
        db_manager.insert_precursor(
            synthesis_id=synthesis_id,
            name=prec.get('name'),
            amount=prec.get('amount'),
            unit=prec.get('unit')
        )
        
    # Insert Conditions
    for cond in data.get('conditions', []):
        db_manager.insert_condition(
            synthesis_id=synthesis_id,
            parameter=cond.get('parameter'),
            value=cond.get('value'),
            unit=cond.get('unit')
        )
        
    print("Done.")

def process_query(query: str, max_results: int = 3, mock: bool = True):
    """Search, download, and process papers from Arxiv."""
    logging.info(f"Starting search for '{query}'...")
    results = scraper.search_papers(query, max_results=max_results)
    
    if not results:
        logging.warning("No papers found.")
        return
        
    for result in results:
        logging.info(f"Found: {result['title']}")
        try:
            pdf_path = scraper.download_pdf(result['pdf_url'], output_dir=os.path.join(DATA_DIR, 'downloads'), title=result['title'])
            process_paper(pdf_path, mock=mock)
        except Exception as e:
            logging.error(f"Error processing {result['title']}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Synthesis Scraper Pipeline')
    parser.add_argument('--input', type=str, help='Path to input file (PDF or TXT)')
    parser.add_argument('--query', type=str, help='Search query for Arxiv')
    parser.add_argument('--max', type=int, default=3, help='Max results for search')
    parser.add_argument('--mock', action='store_true', help='Use mock LLM extraction')
    
    args = parser.parse_args()
    
    ollama_process = None
    if not args.mock:
        ollama_process = start_ollama()
        
    try:
        if args.query:
            process_query(args.query, max_results=args.max, mock=args.mock)
        elif args.input:
            process_paper(args.input, mock=args.mock)
        else:
            print("Error: Please provide either --input or --query")
    finally:
        logging.info("Cleaning up...")
        try:
            extractor.unload_model()
        except Exception as e:
            logging.error(f"Error unloading model: {e}")
            
        if ollama_process:
            stop_ollama(ollama_process)
