import arxiv
import os
import requests
import logging
import time
from src import config

def search_papers(query, max_results=3):
    """Search Arxiv for papers."""
    logging.info(f"Searching Arxiv for: {query}")
    
    attempts = config.RETRY_ATTEMPTS
    delay = config.RETRY_DELAY
    
    for attempt in range(attempts):
        try:
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for result in client.results(search):
                results.append({
                    'title': result.title,
                    'pdf_url': result.pdf_url,
                    'published': result.published,
                    'summary': result.summary
                })
            return results
            
        except Exception as e:
            logging.warning(f"Arxiv search failed (Attempt {attempt+1}/{attempts}): {e}")
            if attempt < attempts - 1:
                time.sleep(delay)
            else:
                logging.error("Max retries reached for Arxiv search.")
                return []

def download_pdf(url, output_dir, title):
    """Download PDF from URL."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_title = safe_title.replace(" ", "_")
    filename = f"{safe_title}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    if os.path.exists(filepath):
        logging.info(f"File already exists: {filepath}")
        return filepath
        
    logging.info(f"Downloading {url} to {filepath}...")
    
    attempts = config.RETRY_ATTEMPTS
    delay = config.RETRY_DELAY
    
    for attempt in range(attempts):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return filepath
            
        except Exception as e:
            logging.warning(f"Download failed (Attempt {attempt+1}/{attempts}): {e}")
            if attempt < attempts - 1:
                time.sleep(delay)
            else:
                logging.error(f"Max retries reached for downloading {url}")
                raise e
