import json
import requests
import base64
import io
from typing import Dict, Any, List, Union
from PIL import Image

# Prompt template for the LLM
PROMPT_TEMPLATE = """
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

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llava" # Using Vision model

def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def extract_synthesis_data(content: Union[str, List[Image.Image]], mock: bool = False) -> Dict[str, Any]:
    """
    Extract synthesis data from text or images using an LLM.
    
    Args:
        content: Text string OR list of PIL Images.
        mock: If True, returns a dummy response for testing.
    """
    if mock:
        return mock_extraction(str(content))
    
    images_b64 = []
    prompt = PROMPT_TEMPLATE
    
    if isinstance(content, list):
        # It's a list of images
        print(f"Processing {len(content)} images with LLaVA...")
        # Limit to first 3 pages to avoid context overflow/timeout for now
        for img in content[:3]: 
            images_b64.append(image_to_base64(img))
    else:
        # Fallback for text-only (if passed)
        prompt += f"\nText:\n{content[:4000]}"

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "images": images_b64 if images_b64 else None,
        "keep_alive": -1, # Keep model loaded indefinitely
        "options": {
            "num_ctx": 2048 # Limit context to save VRAM (4096 is default)
        }
    }
    
    try:
        print(f"Sending request to Ollama ({MODEL_NAME})...")
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Parse JSON from the response
        response_text = result.get("response", "")
        print(f"Raw LLM Response: {response_text[:200]}...") # Debug log
        
        # Robust JSON extraction
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            print("No JSON found in response.")
            return {}
            
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama: {e}")
        return {}

def unload_model():
    """Explicitly unload the model from memory."""
    print(f"Unloading model {MODEL_NAME}...")
    payload = {
        "model": MODEL_NAME,
        "keep_alive": 0
    }
    try:
        requests.post(OLLAMA_URL, json=payload)
        print("Model unloaded.")
    except Exception as e:
        print(f"Error unloading model: {e}")

def mock_extraction(text: str) -> Dict[str, Any]:
    """Mock extraction logic for testing."""
    # Simple heuristic to make it look somewhat dynamic based on text content
    target = "Unknown Material"
    if "MOF-5" in text:
        target = "MOF-5"
    elif "ZIF-8" in text:
        target = "ZIF-8"
        
    return {
        "target_material": target,
        "method_type": "Solvothermal",
        "description": "Mock synthesis description extracted from text.",
        "precursors": [
            {"name": "Zinc nitrate hexahydrate", "amount": "2.0", "unit": "g"},
            {"name": "2-methylimidazole", "amount": "1.5", "unit": "g"}
        ],
        "conditions": [
            {"parameter": "Temperature", "value": "120", "unit": "C"},
            {"parameter": "Time", "value": "24", "unit": "h"}
        ]
    }
