#!/usr/bin/env python3

import requests
import sys
import base64
import time
from datetime import datetime
from pathlib import Path
import json

class BillTranslationAPITester:
    def __init__(self, base_url="https://multilang-invoice-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def create_test_image_base64(self):
        """Create a simple test image with text-like content"""
        # Create a simple test image data (minimal JPEG header + data)
        # This is a minimal valid JPEG that should work for testing
        jpeg_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xaa\xff\xd9'
        return base64.b64encode(jpeg_data).decode('utf-8')

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            success = response.status_code == 200 and "Bill Translation API" in response.text
            self.log_test("API Root", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("API Root", False, str(e))
            return False

    def test_upload_bill(self):
        """Test bill upload"""
        try:
            # Create test file data
            test_image_data = b"fake_image_data_for_testing"
            
            files = {
                'file': ('test_bill.jpg', test_image_data, 'image/jpeg')
            }
            
            response = requests.post(f"{self.api_url}/bills/upload", files=files, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['id', 'filename', 'status', 'upload_date']
                has_all_fields = all(field in data for field in required_fields)
                
                if has_all_fields and data['status'] == 'uploaded':
                    self.log_test("Upload Bill", True, f"Bill ID: {data['id']}")
                    return data['id']
                else:
                    self.log_test("Upload Bill", False, f"Missing fields or wrong status: {data}")
                    return None
            else:
                self.log_test("Upload Bill", False, f"Status: {response.status_code}, Response: {response.text}")
                return None
                
        except Exception as e:
            self.log_test("Upload Bill", False, str(e))
            return None

    def test_translate_bill(self, bill_id):
        """Test bill translation"""
        if not bill_id:
            self.log_test("Translate Bill", False, "No bill ID provided")
            return False
            
        try:
            response = requests.post(f"{self.api_url}/bills/{bill_id}/translate", timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'translated' and data.get('translated_text'):
                    self.log_test("Translate Bill", True, f"Translation completed")
                    return True
                else:
                    self.log_test("Translate Bill", False, f"Translation failed or incomplete: {data}")
                    return False
            else:
                self.log_test("Translate Bill", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Translate Bill", False, str(e))
            return False

    def test_get_bills(self):
        """Test getting bills list"""
        try:
            response = requests.get(f"{self.api_url}/bills", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Get Bills List", True, f"Found {len(data)} bills")
                    return True
                else:
                    self.log_test("Get Bills List", False, "Response is not a list")
                    return False
            else:
                self.log_test("Get Bills List", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Bills List", False, str(e))
            return False

    def test_get_bill_details(self, bill_id):
        """Test getting single bill details"""
        if not bill_id:
            self.log_test("Get Bill Details", False, "No bill ID provided")
            return False
            
        try:
            response = requests.get(f"{self.api_url}/bills/{bill_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['id', 'filename', 'status']
                has_all_fields = all(field in data for field in required_fields)
                
                if has_all_fields:
                    self.log_test("Get Bill Details", True, f"Bill details retrieved")
                    return True
                else:
                    self.log_test("Get Bill Details", False, f"Missing required fields: {data}")
                    return False
            else:
                self.log_test("Get Bill Details", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Bill Details", False, str(e))
            return False

    def test_get_bill_image(self, bill_id):
        """Test getting bill original image"""
        if not bill_id:
            self.log_test("Get Bill Image", False, "No bill ID provided")
            return False
            
        try:
            response = requests.get(f"{self.api_url}/bills/{bill_id}/image", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'image_base64' in data:
                    self.log_test("Get Bill Image", True, "Image retrieved")
                    return True
                else:
                    self.log_test("Get Bill Image", False, "No image_base64 field")
                    return False
            else:
                self.log_test("Get Bill Image", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Get Bill Image", False, str(e))
            return False

    def test_generate_pdf(self, bill_id):
        """Test PDF generation"""
        if not bill_id:
            self.log_test("Generate PDF", False, "No bill ID provided")
            return False
            
        try:
            response = requests.get(f"{self.api_url}/bills/{bill_id}/pdf", timeout=30)
            
            if response.status_code == 200:
                # Check if response is PDF
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    self.log_test("Generate PDF", True, f"PDF generated, size: {len(response.content)} bytes")
                    return True
                else:
                    self.log_test("Generate PDF", False, f"Wrong content type: {content_type}")
                    return False
            else:
                self.log_test("Generate PDF", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Generate PDF", False, str(e))
            return False

    def run_full_test_suite(self):
        """Run complete test suite"""
        print("🚀 Starting Bill Translation API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 50)
        
        # Test API availability
        if not self.test_api_root():
            print("❌ API is not accessible. Stopping tests.")
            return False
        
        # Test upload
        bill_id = self.test_upload_bill()
        
        # Test bills list
        self.test_get_bills()
        
        if bill_id:
            # Test bill details
            self.test_get_bill_details(bill_id)
            
            # Test bill image
            self.test_get_bill_image(bill_id)
            
            # Test translation (this might take time)
            print("⏳ Testing translation (this may take 30-60 seconds)...")
            translation_success = self.test_translate_bill(bill_id)
            
            # Test PDF generation only if translation succeeded
            if translation_success:
                print("⏳ Testing PDF generation...")
                self.test_generate_pdf(bill_id)
            else:
                self.log_test("Generate PDF", False, "Skipped due to translation failure")
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return True
        else:
            print("⚠️  Some tests failed. Check details above.")
            return False

def main():
    tester = BillTranslationAPITester()
    success = tester.run_full_test_suite()
    
    # Save test results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": tester.tests_run,
        "passed_tests": tester.tests_passed,
        "success_rate": f"{(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "0%",
        "test_details": tester.test_results
    }
    
    # Write results to file
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())