import os
from pypdf import PdfReader
from pdf2image import convert_from_path
from typing import List, Union
from PIL import Image

def read_file(file_path: str, max_pages: int = 5) -> Union[str, List[Image.Image]]:
    """Read content from a file. Returns text or list of images (limited to max_pages)."""
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    if ext == '.pdf':
        # Return images for multimodal analysis
        return pdf_to_images(file_path, max_pages=max_pages)
    elif ext == '.txt':
        return read_text(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

def read_text(file_path: str) -> str:
    """Read content from a text file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def pdf_to_images(file_path: str, max_pages: int = 5) -> List[Image.Image]:
    """Convert PDF pages to PIL Images (limited to max_pages)."""
    try:
        print(f"Converting PDF to images (first {max_pages} pages): {file_path}")
        # convert_from_path loads all by default, use last_page to limit
        images = convert_from_path(file_path, last_page=max_pages)
        return images
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        return []

def clean_text(text: str) -> str:
    """Basic text cleaning (Legacy for text-only mode)."""
    if not isinstance(text, str):
        return ""
    text = " ".join(text.split())
    return text
