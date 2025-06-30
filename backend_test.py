#!/usr/bin/env python3
import requests
import json
import time
import os
import sys
from urllib.parse import urljoin
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get backend URL from frontend/.env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.strip().split('=')[1].strip('"\'')
    except Exception as e:
        logger.error(f"Error reading backend URL: {e}")
        sys.exit(1)

# Main backend URL
BACKEND_URL = get_backend_url()
API_BASE_URL = urljoin(BACKEND_URL, '/api/')

logger.info(f"Using backend URL: {BACKEND_URL}")
logger.info(f"API base URL: {API_BASE_URL}")

class WebsiteAnalyzerTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "test_details": []
        }
    
    def log_test_result(self, test_name, passed, details=None):
        """Log test result and update counters"""
        status = "PASSED" if passed else "FAILED"
        logger.info(f"Test: {test_name} - {status}")
        if details:
            logger.info(f"Details: {details}")
        
        self.test_results["total_tests"] += 1
        if passed:
            self.test_results["passed_tests"] += 1
        else:
            self.test_results["failed_tests"] += 1
        
        self.test_results["test_details"].append({
            "name": test_name,
            "status": status,
            "details": details
        })
    
    def test_root_endpoint(self):
        """Test the root API endpoint"""
        try:
            response = self.session.get(urljoin(API_BASE_URL, '/'))
            passed = response.status_code == 200 and "message" in response.json()
            self.log_test_result("Root API Endpoint", passed, response.json())
            return passed
        except Exception as e:
            self.log_test_result("Root API Endpoint", False, str(e))
            return False
    
    def test_analyze_endpoint(self, url="example.com"):
        """Test the analyze endpoint with a test URL"""
        try:
            payload = {"url": url}
            response = self.session.post(urljoin(API_BASE_URL, '/analyze'), json=payload)
            
            if response.status_code != 200:
                self.log_test_result("Analyze Endpoint", False, f"Status code: {response.status_code}, Response: {response.text}")
                return None
            
            result = response.json()
            passed = "session_id" in result and "status" in result and result["status"] == "started"
            self.log_test_result("Analyze Endpoint", passed, result)
            
            if passed:
                return result["session_id"]
            return None
        except Exception as e:
            self.log_test_result("Analyze Endpoint", False, str(e))
            return None
    
    def test_progress_endpoint(self, session_id):
        """Test the progress endpoint with a session ID"""
        try:
            max_attempts = 30
            for attempt in range(max_attempts):
                response = self.session.get(urljoin(API_BASE_URL, f'/progress/{session_id}'))
                
                if response.status_code != 200:
                    self.log_test_result("Progress Endpoint", False, f"Status code: {response.status_code}, Response: {response.text}")
                    return False
                
                progress_data = response.json()
                logger.info(f"Progress: {progress_data['progress']}%, Status: {progress_data['status']}, Message: {progress_data['message']}")
                
                # If analysis is completed or failed, break the loop
                if progress_data["status"] in ["completed", "error"]:
                    break
                
                # Wait before checking again
                time.sleep(2)
            
            passed = "progress" in progress_data and "status" in progress_data
            self.log_test_result("Progress Endpoint", passed, progress_data)
            return passed and progress_data["status"] == "completed"
        except Exception as e:
            self.log_test_result("Progress Endpoint", False, str(e))
            return False
    
    def test_result_endpoint(self, session_id):
        """Test the result endpoint with a session ID"""
        try:
            # Wait a bit to ensure the analysis is complete
            time.sleep(5)
            
            response = self.session.get(urljoin(API_BASE_URL, f'/result/{session_id}'))
            
            if response.status_code != 200:
                self.log_test_result("Result Endpoint", False, f"Status code: {response.status_code}, Response: {response.text}")
                return None
            
            result_data = response.json()
            
            # Check for required fields in the result
            required_fields = [
                "session_id", "url", "overall_score", "performance_score", 
                "seo_score", "technical_score", "accessibility_score", 
                "analysis_data", "ai_insights"
            ]
            
            missing_fields = [field for field in required_fields if field not in result_data]
            
            if missing_fields:
                self.log_test_result("Result Endpoint", False, f"Missing fields: {missing_fields}")
                return None
            
            # Check if AI insights are present
            ai_insights_valid = "recommendations" in result_data["ai_insights"]
            
            passed = len(missing_fields) == 0 and ai_insights_valid
            self.log_test_result("Result Endpoint", passed, {
                "session_id": result_data["session_id"],
                "url": result_data["url"],
                "scores": {
                    "overall": result_data["overall_score"],
                    "performance": result_data["performance_score"],
                    "seo": result_data["seo_score"],
                    "technical": result_data["technical_score"],
                    "accessibility": result_data["accessibility_score"]
                },
                "ai_insights_valid": ai_insights_valid,
                "recommendation_count": len(result_data["ai_insights"].get("recommendations", []))
            })
            
            return result_data if passed else None
        except Exception as e:
            self.log_test_result("Result Endpoint", False, str(e))
            return None
    
    def test_analyses_endpoint(self):
        """Test the analyses endpoint to get recent analyses"""
        try:
            response = self.session.get(urljoin(API_BASE_URL, '/analyses'))
            
            if response.status_code != 200:
                self.log_test_result("Analyses Endpoint", False, f"Status code: {response.status_code}, Response: {response.text}")
                return False
            
            analyses = response.json()
            passed = isinstance(analyses, list)
            
            self.log_test_result("Analyses Endpoint", passed, {
                "count": len(analyses),
                "sample": analyses[0] if analyses else None
            })
            
            return passed
        except Exception as e:
            self.log_test_result("Analyses Endpoint", False, str(e))
            return False
    
    def test_error_handling(self):
        """Test error handling with invalid inputs"""
        try:
            # Test with empty URL
            payload = {"url": ""}
            response = self.session.post(urljoin(API_BASE_URL, '/analyze'), json=payload)
            empty_url_handled = response.status_code == 400
            
            # Test with invalid session ID
            invalid_session_response = self.session.get(urljoin(API_BASE_URL, '/progress/invalid-session-id'))
            invalid_session_handled = invalid_session_response.status_code == 404
            
            # Test with invalid result ID
            invalid_result_response = self.session.get(urljoin(API_BASE_URL, '/result/invalid-result-id'))
            invalid_result_handled = invalid_result_response.status_code == 404
            
            passed = empty_url_handled and invalid_session_handled and invalid_result_handled
            
            self.log_test_result("Error Handling", passed, {
                "empty_url_handled": empty_url_handled,
                "invalid_session_handled": invalid_session_handled,
                "invalid_result_handled": invalid_result_handled
            })
            
            return passed
        except Exception as e:
            self.log_test_result("Error Handling", False, str(e))
            return False
    
    def test_ai_insights_generation(self, result_data):
        """Test AI insights generation from analysis results"""
        try:
            if not result_data or "ai_insights" not in result_data:
                self.log_test_result("AI Insights Generation", False, "No result data or AI insights available")
                return False
            
            ai_insights = result_data["ai_insights"]
            
            # Check if recommendations exist
            if "recommendations" not in ai_insights:
                self.log_test_result("AI Insights Generation", False, "No recommendations in AI insights")
                return False
            
            recommendations = ai_insights["recommendations"]
            
            # Check if there are recommendations
            if not recommendations:
                self.log_test_result("AI Insights Generation", False, "Empty recommendations list")
                return False
            
            # Check recommendation structure
            required_fields = ["title", "description", "priority", "impact"]
            valid_recommendations = all(all(field in rec for field in required_fields) for rec in recommendations)
            
            passed = valid_recommendations
            self.log_test_result("AI Insights Generation", passed, {
                "recommendation_count": len(recommendations),
                "sample_recommendation": recommendations[0] if recommendations else None,
                "valid_structure": valid_recommendations
            })
            
            return passed
        except Exception as e:
            self.log_test_result("AI Insights Generation", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        logger.info("Starting backend tests for AI-Powered Website Analyzer")
        
        # Test root endpoint
        self.test_root_endpoint()
        
        # Test analyze endpoint with a valid URL
        session_id = self.test_analyze_endpoint("example.com")
        
        if session_id:
            # Test progress tracking
            progress_completed = self.test_progress_endpoint(session_id)
            
            if progress_completed:
                # Test result retrieval
                result_data = self.test_result_endpoint(session_id)
                
                if result_data:
                    # Test AI insights generation
                    self.test_ai_insights_generation(result_data)
        
        # Test analyses endpoint
        self.test_analyses_endpoint()
        
        # Test error handling
        self.test_error_handling()
        
        # Print summary
        logger.info("\n===== TEST SUMMARY =====")
        logger.info(f"Total tests: {self.test_results['total_tests']}")
        logger.info(f"Passed tests: {self.test_results['passed_tests']}")
        logger.info(f"Failed tests: {self.test_results['failed_tests']}")
        logger.info("=======================\n")
        
        return self.test_results

if __name__ == "__main__":
    tester = WebsiteAnalyzerTester()
    test_results = tester.run_all_tests()
    
    # Output results as JSON
    print(json.dumps(test_results, indent=2))