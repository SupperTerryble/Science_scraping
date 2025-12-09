import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import requests

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src import config
from src import scraper
from src import extractor

class TestPipeline(unittest.TestCase):
    def test_config_loading(self):
        """Test that config loads correctly."""
        self.assertEqual(config.get_config('search.max_results_default'), 3)
        self.assertEqual(config.get_config('processing.max_workers'), 4)

    @patch('src.scraper.arxiv.Client')
    def test_scraper_retry(self, mock_client):
        """Test scraper retry logic."""
        # Mock client to raise exception first then succeed
        mock_instance = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Test Paper"
        mock_result.pdf_url = "http://example.com/test.pdf"
        
        # First call raises exception, second returns results
        mock_instance.results.side_effect = [Exception("Network Error"), [mock_result]]
        mock_client.return_value = mock_instance
        
        # Reduce delay for test
        with patch('src.config.RETRY_DELAY', 0):
            results = scraper.search_papers("test query")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Test Paper")

    @patch('src.extractor.requests.post')
    def test_extractor_retry(self, mock_post):
        """Test extractor retry logic."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": '{"target_material": "Test Material"}'}
        
        # First call raises exception, second succeeds
        mock_post.side_effect = [requests.exceptions.ConnectionError("Connection Error"), mock_response]
        
        # Reduce delay for test
        with patch('src.config.RETRY_DELAY', 0):
            result = extractor.extract_synthesis_data("some text", mode='text')
            
        self.assertEqual(result.get('target_material'), "Test Material")

if __name__ == '__main__':
    unittest.main()
