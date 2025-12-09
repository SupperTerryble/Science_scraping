import argparse
import os
import subprocess
import time
import requests
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from src import db_manager, ingestor, extractor, scraper, image_extractor, config
from src.agents.chemistry_agent import ChemistryAgent
from src.agents.scoring_agent import ScoringAgent

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

def process_paper(file_path: str, compare: bool = False, analyze: bool = False, hybrid: bool = False):
    """Run the full pipeline on a single paper."""
    logging.info(f"Processing {file_path}...")
    
    # 1. Ingest (Text for Text Model)
    try:
        # For hybrid/text mode, we want text content.
        # ingestor.read_file returns images for PDF.
        # We need text. Using pypdf fallback here or assuming ingestor handles it.
        # For now, let's use a simple text extraction if it's a PDF
        text_content = ""
        if file_path.lower().endswith('.pdf'):
            from pypdf import PdfReader
            try:
                reader = PdfReader(file_path)
                for page in reader.pages[:10]: # Limit pages
                    text_content += page.extract_text() + "\n"
            except Exception as e:
                logging.warning(f"Text extraction failed: {e}")
        else:
            # Assume txt
            with open(file_path, 'r') as f:
                text_content = f.read()
            
    except Exception as e:
        logging.error(f"Failed to read file: {e}")
        return

    # 2. Extract
    logging.info("Extracting data...")
    
    data = {}
    
    if hybrid:
        logging.info("Running Hybrid Pipeline (Segment & Classify)...")
        
        # A. Text Extraction (Primary Recipe)
        logging.info("Step A: Text Extraction...")
        text_data = extractor.extract_synthesis_data(text_content, mode='text')
        data = text_data
        
        # B. Image Extraction & Classification
        logging.info("Step B: Image Extraction & Classification...")
        images = image_extractor.extract_images_from_pdf(file_path)
        
        relevant_images = []
        for img_obj in images:
            classification = extractor.classify_image(img_obj['image'])
            logging.info(f"Image {img_obj['page']}-{img_obj['index']}: {classification.get('type')} (Relevant: {classification.get('relevant')})")
            
            if classification.get('relevant') and classification.get('type') in ['graph', 'flowchart', 'table']:
                relevant_images.append(img_obj['image'])
        
        # C. Vision Extraction on Relevant Images
        if relevant_images:
            logging.info(f"Step C: Vision Extraction on {len(relevant_images)} relevant images...")
            # We can either merge this data or store it as 'evidence'
            # For now, let's just extract and log it, or merge if text failed
            vision_data = extractor.extract_synthesis_data(relevant_images, mode='vision')
            
            # Merge logic (Simple overwrite if vision has data, or keep text)
            # Better: Add vision data as 'supporting_evidence'
            data['visual_evidence_data'] = vision_data
            
            # If text failed to find target, use vision
            if data.get('target_material') == 'Unknown' and vision_data.get('target_material'):
                data['target_material'] = vision_data['target_material']
                
    else:
        # Legacy modes
        mode = 'dual' if compare else 'vision'
        # If content is text-only (e.g. .txt file), mode 'vision' falls back to text in extractor
        # But here we passed text_content to extractor? No, extractor expects images for vision mode.
        # We need to pass images if mode is vision/dual.
        
        content_for_extractor = text_content
        if mode in ['vision', 'dual'] and file_path.lower().endswith('.pdf'):
             content_for_extractor = ingestor.read_file(file_path, max_pages=5)

        data = extractor.extract_synthesis_data(content_for_extractor, mode=mode)
    
    if not data:
        logging.warning("No data extracted.")
        return
        
    logging.info(f"Extracted: {data.get('target_material')} via {data.get('method_type')}")

    # 3. Analyze (Chemistry & Scoring)
    chemistry_result = {}
    scoring_result = {}
    
    if analyze:
        logging.info("Running Analysis Agents...")
        
        # Chemistry Agent (Replaces Physics Agent)
        chem_agent = ChemistryAgent()
        chemistry_result = chem_agent.analyze(data)
        
        # Log Chemistry Warnings
        if not chemistry_result.get('physics_check_passed'):
            logging.warning(f"Physics Checks Failed: {chemistry_result.get('warnings')}")
        
        if not chemistry_result.get('chemistry_valid', True): # Default to True if not checked
             logging.warning(f"Chemistry Logic Error: {chemistry_result.get('chemistry_reason')}")
             
        if chemistry_result.get('warnings'):
            logging.info(f"Chemistry Warnings: {chemistry_result.get('warnings')}")
        else:
            logging.info("Chemistry Checks Passed.")
            
        # Scoring Agent
        score_agent = ScoringAgent()
        scoring_result = score_agent.calculate_score(
            metadata={'title': os.path.basename(file_path), 'authors': []},
            text_content=text_content[:5000]
        )
        logging.info(f"Scientific Score: {scoring_result.get('total_score')}")

    # 4. Save to DB
    logging.info("Saving to database...")
    # Initialize DB if needed
    db_manager.init_db()
    
    # Insert Paper
    paper_id = db_manager.insert_paper(
        title=os.path.basename(file_path),
        doi=f"file://{os.path.basename(file_path)}", # Dummy DOI for local files
        text_content=text_content[:500] + "..." # Store only start to save space/time
    )
    
    # Insert Synthesis (Use Normalized data if available, else Raw)
    save_data = chemistry_result if analyze else data
    
    synthesis_id = db_manager.insert_synthesis(
        paper_id=paper_id,
        target_material=save_data.get('target_material', 'Unknown'),
        method_type=save_data.get('method_type', 'Unknown'),
        description=save_data.get('description', '')
    )
    
    # Insert Precursors
    for prec in save_data.get('precursors', []):
        db_manager.insert_precursor(
            synthesis_id=synthesis_id,
            name=prec.get('name'),
            amount=prec.get('amount'),
            unit=prec.get('unit')
        )
        
    # Insert Conditions
    for cond in save_data.get('conditions', []):
        db_manager.insert_condition(
            synthesis_id=synthesis_id,
            parameter=cond.get('parameter'),
            value=cond.get('value'),
            unit=cond.get('unit')
        )
        
    print(f"Done processing {os.path.basename(file_path)}.")

def process_query(query: str, max_results: int = 3, compare: bool = False, analyze: bool = False, hybrid: bool = False, workers: int = 1):
    """Search, download, and process papers from Arxiv."""
    logging.info(f"Starting search for '{query}'...")
    results = scraper.search_papers(query, max_results=max_results)
    
    if not results:
        logging.warning("No papers found.")
        return
        
    download_dir = config.get_config('search.download_dir', os.path.join(DATA_DIR, 'downloads'))
    
    # Download all papers first (or could be done in parallel too, but let's keep it simple)
    pdf_paths = []
    for result in results:
        logging.info(f"Found: {result['title']}")
        try:
            pdf_path = scraper.download_pdf(result['pdf_url'], output_dir=download_dir, title=result['title'])
            pdf_paths.append(pdf_path)
        except Exception as e:
            logging.error(f"Error downloading {result['title']}: {e}")

    # Process in parallel
    if workers > 1:
        logging.info(f"Processing {len(pdf_paths)} papers with {workers} workers...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process_paper, path, compare, analyze, hybrid) for path in pdf_paths]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Worker failed: {e}")
    else:
        # Serial processing
        for path in pdf_paths:
            process_paper(path, compare=compare, analyze=analyze, hybrid=hybrid)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Synthesis Scraper Pipeline')
    parser.add_argument('--input', type=str, help='Path to input file (PDF or TXT)')
    parser.add_argument('--query', type=str, help='Search query for Arxiv')
    parser.add_argument('--max', type=int, default=config.get_config('search.max_results_default', 3), help='Max results for search')
    parser.add_argument('--compare', action='store_true', help='Run both Vision and Text models to compare')
    parser.add_argument('--analyze', action='store_true', help='Run Physics and Scoring agents')
    parser.add_argument('--hybrid', action='store_true', help='Run Hybrid Pipeline (Segment & Classify)')
    parser.add_argument('--workers', type=int, default=config.MAX_WORKERS, help='Number of parallel workers')
    
    args = parser.parse_args()
    
    ollama_process = None
    # Always start ollama now since we removed mock
    ollama_process = start_ollama()
        
    try:
        if args.query:
            process_query(args.query, max_results=args.max, compare=args.compare, analyze=args.analyze, hybrid=args.hybrid, workers=args.workers)
        elif args.input:
            process_paper(args.input, compare=args.compare, analyze=args.analyze, hybrid=args.hybrid)
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
