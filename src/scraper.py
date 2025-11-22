import arxiv
import os
import requests
from typing import List, Dict

def search_papers(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search for papers on Arxiv.
    Returns a list of dictionaries with title, pdf_url, and doi (if available).
    """
    print(f"Searching Arxiv for: {query}")
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )
    
    results = []
    for result in client.results(search):
        results.append({
            "title": result.title,
            "pdf_url": result.pdf_url,
            "doi": result.doi or result.entry_id, # Fallback to entry_id if DOI is missing
            "summary": result.summary
        })
    return results

def download_pdf(url: str, output_dir: str, title: str = None) -> str:
    """
    Download a PDF from a URL to the output directory.
    Returns the local file path.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    if title:
        # Sanitize title for filename
        safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        safe_title = safe_title.replace(" ", "_")
        filename = f"{safe_title}.pdf"
    else:
        filename = url.split('/')[-1]
        if not filename.endswith('.pdf'):
            filename += '.pdf'
        
    filepath = os.path.join(output_dir, filename)
    
    if os.path.exists(filepath):
        print(f"File already exists: {filepath}")
        return filepath
        
    print(f"Downloading {url} to {filepath}...")
    response = requests.get(url)
    if response.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return filepath
    else:
        raise Exception(f"Failed to download PDF: {response.status_code}")
