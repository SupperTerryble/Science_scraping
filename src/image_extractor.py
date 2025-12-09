import fitz  # PyMuPDF
import io
from PIL import Image
import logging
from typing import List, Dict, Any

def extract_images_from_pdf(pdf_path: str, min_width: int = 200, min_height: int = 200) -> List[Dict[str, Any]]:
    """
    Extracts images from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file.
        min_width: Minimum width to consider an image valid (filters icons).
        min_height: Minimum height to consider an image valid.
        
    Returns:
        List of dictionaries containing:
        - 'image': PIL Image object
        - 'page': Page number (1-indexed)
        - 'index': Image index on page
        - 'size': (width, height)
    """
    extracted_images = []
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num, page in enumerate(doc):
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                try:
                    image = Image.open(io.BytesIO(image_bytes))
                    width, height = image.size
                    
                    # Filter small images (likely logos, icons, or noise)
                    if width >= min_width and height >= min_height:
                        extracted_images.append({
                            "image": image,
                            "page": page_num + 1,
                            "index": img_index,
                            "size": (width, height),
                            "xref": xref
                        })
                    else:
                        logging.debug(f"Skipping small image on page {page_num+1}: {width}x{height}")
                        
                except Exception as e:
                    logging.warning(f"Failed to process image {img_index} on page {page_num+1}: {e}")
                    
        doc.close()
        logging.info(f"Extracted {len(extracted_images)} images from {pdf_path}")
        return extracted_images
        
    except Exception as e:
        logging.error(f"Error opening PDF {pdf_path}: {e}")
        return []
