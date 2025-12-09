import json
import requests
import base64
import io
import logging
import time
from typing import Dict, Any, List, Union
from PIL import Image
from src import config

# Prompt template for the LLM
PROMPT_TEMPLATE_VISION = """
You are an expert materials scientist. Analyze the provided images (pages of a scientific paper).
Extract the synthesis conditions for the target material.
CRITICAL: Pay special attention to TABLES and FIGURES (Graphs, Flowcharts).
Return ONLY a valid JSON object with the following structure, no other text:
{
    "target_material": "Name of the material synthesized",
    "visual_evidence": "Describe specific Tables or Figures you used to extract data (e.g., 'Table 1 lists reactants', 'Figure 2 shows the heating profile')",
    "method_type": "e.g., Sol-gel, Hydrothermal, Solid-state",
    "description": "Brief summary of the procedure",
    "precursors": [
        {"name": "Precursor 1", "amount": "Value", "unit": "Unit"},
        ...
    ],
    "conditions": [
        {"parameter": "Temperature", "value": "Value", "unit": "Unit"},
        {"parameter": "Time", "value": "Value", "unit": "Unit"},
        ...
    ]
}
"""

PROMPT_TEMPLATE_TEXT = """
You are an expert materials scientist. Analyze the provided text from a scientific paper.
Extract the synthesis conditions for the target material.
Return ONLY a valid JSON object with the following structure, no other text:
{
    "target_material": "Name of the material synthesized",
    "method_type": "e.g., Sol-gel, Hydrothermal, Solid-state",
    "description": "Brief summary of the procedure",
    "precursors": [
        {"name": "Precursor 1", "amount": "Value", "unit": "Unit"},
        ...
    ],
    "conditions": [
        {"parameter": "Temperature", "value": "Value", "unit": "Unit"},
        {"parameter": "Time", "value": "Value", "unit": "Unit"},
        ...
    ]
}
"""

PROMPT_CLASSIFY = """
Analyze this image from a scientific paper.
Classify it into one of the following categories:
- 'graph': A data plot, chart, or graph (e.g., XRD, TGA, Spectra).
- 'flowchart': A diagram showing a process flow or synthesis steps.
- 'molecule': A chemical structure or reaction scheme.
- 'microscopy': SEM/TEM images.
- 'other': Any other image (e.g., photo of setup, irrelevant icon).

Also determine if it contains specific data relevant to MATERIAL SYNTHESIS (e.g., reaction conditions, yield, precursors).

Return ONLY a valid JSON object:
{
    "type": "graph" | "flowchart" | "molecule" | "microscopy" | "other",
    "relevant": true | false,
    "description": "Brief description of the image content"
}
"""

OLLAMA_URL = config.OLLAMA_URL
MODEL_VISION = config.MODEL_VISION
MODEL_TEXT = config.MODEL_TEXT

def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def classify_image(image: Image.Image) -> Dict[str, Any]:
    """
    Classify an image using the Vision model.
    Returns a dict with 'type', 'relevant', and 'description'.
    """
    logging.info("Classifying image...")
    return _extract_llm(image, model=MODEL_VISION, prompt_template=PROMPT_CLASSIFY)

def extract_synthesis_data(content: Union[str, List[Image.Image], Image.Image], mode: str = 'vision') -> Dict[str, Any]:
    """
    Extract synthesis data from text or images using an LLM.
    
    Args:
        content: Text string OR list of PIL Images OR single PIL Image.
        mode: 'vision', 'text', 'dual', or 'hybrid'.
    """
    if mode == 'dual':
        return _extract_dual(content)
    elif mode == 'text':
        # Ensure content is text
        text_content = content if isinstance(content, str) else "Error: Image content passed to text mode"
        return _extract_llm(text_content, model=MODEL_TEXT, prompt_template=PROMPT_TEMPLATE_TEXT)
    elif mode == 'hybrid':
        # Hybrid mode is orchestrated by main.py, but if called here with a single image, treat as vision extraction
        # This is a fallback or for direct image extraction calls
        if isinstance(content, Image.Image):
             return _extract_llm([content], model=MODEL_VISION, prompt_template=PROMPT_TEMPLATE_VISION)
        return {}
    else: # vision (default)
        # Handle single image case
        if isinstance(content, Image.Image):
            content = [content]
        return _extract_llm(content, model=MODEL_VISION, prompt_template=PROMPT_TEMPLATE_VISION)

def _extract_dual(content: Union[str, List[Image.Image]]) -> Dict[str, Any]:
    """Run both Vision and Text extraction and compare."""
    logging.info("Running Dual Extraction Mode...")
    
    # 1. Vision Extraction
    vision_result = {}
    if isinstance(content, list):
        vision_result = _extract_llm(content, model=MODEL_VISION, prompt_template=PROMPT_TEMPLATE_VISION)
    else:
        logging.warning("Dual mode requested but no images provided for Vision model.")
        
    # 2. Text Extraction
    text_result = {}
    if isinstance(content, str):
         text_result = _extract_llm(content, model=MODEL_TEXT, prompt_template=PROMPT_TEMPLATE_TEXT)
    
    combined = {
        "mode": "dual",
        "vision_extraction": vision_result,
        "text_extraction": text_result,
        **vision_result # Flatten vision result as default
    }
    
    # Add comparison metadata
    combined['comparison'] = {
        "vision_material": vision_result.get('target_material'),
        "text_material": text_result.get('target_material'),
        "match": vision_result.get('target_material') == text_result.get('target_material')
    }
    
    return combined

def _extract_llm(content: Union[str, List[Image.Image], Image.Image], model: str, prompt_template: str) -> Dict[str, Any]:
    """Generic LLM extraction function."""
    images_b64 = []
    prompt = prompt_template
    
    if isinstance(content, list):
        # List of images
        logging.info(f"Processing {len(content)} images with {model}...")
        for img in content[:3]: 
            images_b64.append(image_to_base64(img))
    elif isinstance(content, Image.Image):
        # Single image
        logging.info(f"Processing single image with {model}...")
        images_b64.append(image_to_base64(content))
    else:
        # Text Mode
        logging.info(f"Processing text with {model}...")
        prompt += f"\nText:\n{content[:4000]}"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "images": images_b64 if images_b64 else None,
        "keep_alive": config.get_config('llm.keep_alive', -1),
        "options": {
            "num_ctx": config.get_config('llm.num_ctx', 2048)
        }
    }
    
    attempts = config.RETRY_ATTEMPTS
    delay = config.RETRY_DELAY
    
    for attempt in range(attempts):
        try:
            logging.info(f"Sending request to Ollama ({model}) (Attempt {attempt+1}/{attempts})...")
            response = requests.post(OLLAMA_URL, json=payload, timeout=config.get_config('llm.timeout', 120))
            response.raise_for_status()
            result = response.json()
            
            response_text = result.get("response", "")
            
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            else:
                logging.warning("No JSON found in response.")
                # Don't retry if it's just a parsing error, unless we want to ask LLM again? 
                # Usually it's better to just return empty or retry if we think it's transient.
                # Let's retry if no JSON found, maybe next generation is better.
                if attempt < attempts - 1:
                    continue
                return {}
                
        except Exception as e:
            logging.error(f"Error calling Ollama: {e}")
            if attempt < attempts - 1:
                time.sleep(delay)
            else:
                logging.error("Max retries reached for Ollama.")
                return {}
    return {}

def unload_model():
    """Explicitly unload the model from memory."""
    # Unload both potentially
    for model in [MODEL_VISION, MODEL_TEXT]:
        print(f"Unloading model {model}...")
        payload = {"model": model, "keep_alive": 0}
        try:
            requests.post(OLLAMA_URL, json=payload, timeout=5)
        except Exception:
            pass
