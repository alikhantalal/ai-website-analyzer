#!/usr/bin/env python3
import requests
import json
import time
import os
import sys
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
API_BASE_URL = f"{BACKEND_URL}/api"

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
            response = self.session.get(f"{API_BASE_URL}")
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
            response = self.session.post(f"{API_BASE_URL}/analyze", json=payload)
            
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
                response = self.session.get(f"{API_BASE_URL}/progress/{session_id}")
                
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
            
            response = self.session.get(f"{API_BASE_URL}/result/{session_id}")
            
            if response.status_code != 200:
                self.log_test_result("Result Endpoint", False, f"Status code: {response.status_code}, Response: {response.text}")
                return None
            
            result_data = response.json()
            
            # Check for required fields in the result
            required_fields = [
                "session_id", "url", "overall_score", "performance_score", 
                "seo_score", "technical_score", "accessibility_score", 
                "schema_faq_score", "analysis_data", "ai_insights", 
                "schema_faq_analysis", "checkpoint_category"
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
                    "accessibility": result_data["accessibility_score"],
                    "schema_faq": result_data["schema_faq_score"]
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
            response = self.session.get(f"{API_BASE_URL}/analyses")
            
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
            response = self.session.post(f"{API_BASE_URL}/analyze", json=payload)
            empty_url_handled = response.status_code == 400
            
            # Test with invalid session ID
            invalid_session_response = self.session.get(f"{API_BASE_URL}/progress/invalid-session-id")
            invalid_session_handled = invalid_session_response.status_code == 404
            
            # Test with invalid result ID
            invalid_result_response = self.session.get(f"{API_BASE_URL}/result/invalid-result-id")
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
    
    def test_schema_faq_analysis(self, result_data):
        """Test schema and FAQ analysis from analysis results"""
        try:
            if not result_data or "schema_faq_analysis" not in result_data:
                self.log_test_result("Schema & FAQ Analysis", False, "No result data or schema_faq_analysis available")
                return False
            
            schema_faq_analysis = result_data["schema_faq_analysis"]
            
            # Check for required fields in schema_faq_analysis
            required_fields = ["score", "has_schema", "has_faq", "checkpoint_category", "category_label"]
            missing_fields = [field for field in required_fields if field not in schema_faq_analysis]
            
            if missing_fields:
                self.log_test_result("Schema & FAQ Analysis", False, f"Missing fields: {missing_fields}")
                return False
            
            # Check checkpoint category assignment
            valid_categories = ["both_schema_faq", "schema_only", "faq_only", "neither"]
            category_valid = schema_faq_analysis["checkpoint_category"] in valid_categories
            
            # Check consistency between has_schema/has_faq flags and checkpoint_category
            category_consistent = False
            if schema_faq_analysis["checkpoint_category"] == "both_schema_faq":
                category_consistent = schema_faq_analysis["has_schema"] and schema_faq_analysis["has_faq"]
            elif schema_faq_analysis["checkpoint_category"] == "schema_only":
                category_consistent = schema_faq_analysis["has_schema"] and not schema_faq_analysis["has_faq"]
            elif schema_faq_analysis["checkpoint_category"] == "faq_only":
                category_consistent = not schema_faq_analysis["has_schema"] and schema_faq_analysis["has_faq"]
            elif schema_faq_analysis["checkpoint_category"] == "neither":
                category_consistent = not schema_faq_analysis["has_schema"] and not schema_faq_analysis["has_faq"]
            
            # Check schema details if schema is detected
            schema_details_valid = True
            if schema_faq_analysis["has_schema"]:
                schema_details = schema_faq_analysis.get("schema_details", {})
                schema_details_valid = "json_ld_count" in schema_details and "microdata_count" in schema_details and "rdfa_count" in schema_details
            
            # Check FAQ details if FAQ is detected
            faq_details_valid = True
            if schema_faq_analysis["has_faq"]:
                faq_details = schema_faq_analysis.get("faq_details", {})
                faq_details_valid = "faq_indicators" in faq_details
            
            passed = (len(missing_fields) == 0 and category_valid and 
                     category_consistent and schema_details_valid and faq_details_valid)
            
            self.log_test_result("Schema & FAQ Analysis", passed, {
                "score": schema_faq_analysis["score"],
                "has_schema": schema_faq_analysis["has_schema"],
                "has_faq": schema_faq_analysis["has_faq"],
                "checkpoint_category": schema_faq_analysis["checkpoint_category"],
                "category_label": schema_faq_analysis["category_label"],
                "category_valid": category_valid,
                "category_consistent": category_consistent,
                "schema_details_valid": schema_details_valid,
                "faq_details_valid": faq_details_valid
            })
            
            return passed
        except Exception as e:
            self.log_test_result("Schema & FAQ Analysis", False, str(e))
            return False
    
    def test_pdf_export(self, session_id):
        """Test PDF export functionality"""
        try:
            if not session_id:
                self.log_test_result("PDF Export", False, "No session ID available")
                return False
            
            # Request PDF export
            response = self.session.get(f"{API_BASE_URL}/export/{session_id}?format=pdf", stream=True)
            
            if response.status_code != 200:
                self.log_test_result("PDF Export", False, f"Status code: {response.status_code}, Response: {response.text}")
                return False
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')
            
            is_pdf = content_type == 'application/pdf'
            has_filename = 'filename=' in content_disposition
            
            # Check file size (should be non-zero)
            content_length = int(response.headers.get('Content-Length', 0))
            has_content = content_length > 0
            
            if not has_content:
                # If Content-Length header is missing, check actual content
                content = response.content
                has_content = len(content) > 0
            
            passed = is_pdf and has_filename and has_content
            
            self.log_test_result("PDF Export", passed, {
                "content_type": content_type,
                "content_disposition": content_disposition,
                "is_pdf": is_pdf,
                "has_filename": has_filename,
                "has_content": has_content
            })
            
            return passed
        except Exception as e:
            self.log_test_result("PDF Export", False, str(e))
            return False
    
    def test_pdf_export_error_handling(self):
        """Test PDF export error handling with invalid session ID"""
        try:
            # Request PDF export with invalid session ID
            response = self.session.get(f"{API_BASE_URL}/export/invalid-session-id?format=pdf")
            
            # Should return 404 for invalid session ID
            invalid_session_handled = response.status_code == 404
            
            # Test with unsupported format
            format_response = self.session.get(f"{API_BASE_URL}/export/some-session-id?format=invalid")
            invalid_format_handled = format_response.status_code == 400
            
            passed = invalid_session_handled and invalid_format_handled
            
            self.log_test_result("PDF Export Error Handling", passed, {
                "invalid_session_handled": invalid_session_handled,
                "invalid_format_handled": invalid_format_handled
            })
            
            return passed
        except Exception as e:
            self.log_test_result("PDF Export Error Handling", False, str(e))
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