import requests
import json
from typing import Dict, Any

class ScoringAgent:
    """
    Agent responsible for assessing the scientific pertinence of a paper.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate", model_name: str = "qwen3:8b"):
        self.ollama_url = ollama_url
        self.model_name = model_name

    def calculate_score(self, metadata: Dict[str, Any], text_content: str) -> Dict[str, Any]:
        """
        Calculate a scientific pertinence score (0-100).
        """
        # 1. Methodology Rigor (LLM Analysis)
        rigor_score, rigor_justification = self._analyze_rigor(text_content)
        
        # 2. Citation Count (Requires External API)
        # For now, we set to 0 or neutral if no API key is present, rather than faking it.
        citation_score = self._get_citation_score(metadata.get('title', ''))
        
        # 3. Author H-Index (Requires External API)
        author_score = self._get_author_score(metadata.get('authors', []))
        
        # Weighted Average
        # Rigor: 80% (since it's the only real metric we have right now), Citations: 10%, Authors: 10%
        # Adjust weights if APIs are missing
        if citation_score == 0 and author_score == 0:
            final_score = rigor_score # Fallback to just rigor
        else:
            final_score = (rigor_score * 0.6) + (citation_score * 0.2) + (author_score * 0.2)
        
        return {
            "total_score": round(final_score, 1),
            "breakdown": {
                "rigor_score": rigor_score,
                "citation_score": citation_score,
                "author_score": author_score
            },
            "justification": rigor_justification
        }

    def _analyze_rigor(self, text: str) -> (float, str):
        """Use LLM to analyze the experimental rigor of the text."""
        # Truncate text to avoid context limits
        snippet = text[:4000]
        
        prompt = f"""
        Analyze the following scientific text for experimental rigor.
        Look for:
        1. Clear characterization (XRD, NMR, SEM, etc.)
        2. Error bars or statistical analysis
        3. Detailed experimental procedures
        
        Text:
        {snippet}
        
        Return ONLY a JSON object:
        {{
            "score": <number 0-100>,
            "reason": "<short explanation>"
        }}
        """
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }
            response = requests.post(self.ollama_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                # Parse JSON from response string
                response_json = json.loads(data.get('response', '{}'))
                return float(response_json.get('score', 50)), response_json.get('reason', 'Analysis failed')
        except Exception as e:
            print(f"Error in rigor analysis: {e}")
            
        return 50.0, "Error during analysis, default score."

    def _get_citation_score(self, title: str) -> float:
        """Placeholder for citation score (Semantic Scholar API needed)."""
        # TODO: Integrate Semantic Scholar API
        return 0.0 

    def _get_author_score(self, authors: list) -> float:
        """Placeholder for author score."""
        # TODO: Integrate Author API
        return 0.0
