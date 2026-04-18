#!/usr/bin/env python3

import requests
import sys
import base64
import time
from datetime import datetime
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
import io

class BillTranslationAPITesterWithRealImage:
    def __init__(self, base_url="https://hindi-to-english-25.preview.emergentagent.com"):
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

    def create_hindi_bill_image(self):
        """Create a simple bill image with Hindi text"""
        try:
            # Create a white image
            width, height = 400, 600
            image = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(image)
            
            # Try to use a default font
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            # Add some text that looks like a bill
            y_pos = 50
            
            # Header
            draw.text((50, y_pos), "बिल / BILL", fill='black', font=font)
            y_pos += 40
            
            # Shop details
            draw.text((50, y_pos), "दुकान का नाम: राम स्टोर", fill='black', font=font)
            y_pos += 30
            draw.text((50, y_pos), "Shop Name: Ram Store", fill='black', font=font)
            y_pos += 30
            
            # Items
            draw.text((50, y_pos), "वस्तुएं / Items:", fill='black', font=font)
            y_pos += 30
            draw.text((50, y_pos), "चावल - 50 रुपये", fill='black', font=font)
            y_pos += 25
            draw.text((50, y_pos), "Rice - 50 Rupees", fill='black', font=font)
            y_pos += 25
            draw.text((50, y_pos), "दाल - 30 रुपये", fill='black', font=font)
            y_pos += 25
            draw.text((50, y_pos), "Lentils - 30 Rupees", fill='black', font=font)
            y_pos += 40
            
            # Total
            draw.text((50, y_pos), "कुल राशि / Total: 80 रुपये", fill='black', font=font)
            y_pos += 30
            draw.text((50, y_pos), "Total: 80 Rupees", fill='black', font=font)
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=95)
            buffer.seek(0)
            
            return base64.b64encode(buffer.read()).decode('utf-8')
            
        except Exception as e:
            print(f"Error creating image: {e}")
            # Fallback to a minimal valid JPEG
            minimal_jpeg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x64\x00\x64\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\xf7\xfa(\xa2\x80\x0f\xff\xd9'
            return base64.b64encode(minimal_jpeg).decode('utf-8')

    def test_full_translation_workflow(self):
        """Test complete workflow: upload -> translate -> PDF"""
        try:
            print("🔄 Testing complete translation workflow...")
            
            # Create test image
            image_base64 = self.create_hindi_bill_image()
            
            # Step 1: Upload
            image_data = base64.b64decode(image_base64)
            files = {
                'file': ('hindi_bill.jpg', image_data, 'image/jpeg')
            }
            
            upload_response = requests.post(f"{self.api_url}/bills/upload", files=files, timeout=30)
            
            if upload_response.status_code != 200:
                self.log_test("Full Workflow - Upload", False, f"Upload failed: {upload_response.status_code}")
                return False
            
            bill_data = upload_response.json()
            bill_id = bill_data['id']
            print(f"✅ Upload successful, Bill ID: {bill_id}")
            
            # Step 2: Translate
            print("⏳ Starting translation (may take 30-60 seconds)...")
            translate_response = requests.post(f"{self.api_url}/bills/{bill_id}/translate", timeout=120)
            
            if translate_response.status_code != 200:
                self.log_test("Full Workflow - Translation", False, f"Translation failed: {translate_response.status_code}, {translate_response.text}")
                return False
            
            translation_data = translate_response.json()
            if translation_data.get('status') != 'translated':
                self.log_test("Full Workflow - Translation", False, f"Translation status not 'translated': {translation_data}")
                return False
            
            print(f"✅ Translation successful")
            print(f"📝 Translated text preview: {translation_data.get('translated_text', '')[:200]}...")
            
            # Step 3: Generate PDF
            pdf_response = requests.get(f"{self.api_url}/bills/{bill_id}/pdf", timeout=30)
            
            if pdf_response.status_code != 200:
                self.log_test("Full Workflow - PDF", False, f"PDF generation failed: {pdf_response.status_code}")
                return False
            
            # Check if it's actually a PDF
            content_type = pdf_response.headers.get('content-type', '')
            if 'application/pdf' not in content_type:
                self.log_test("Full Workflow - PDF", False, f"Wrong content type: {content_type}")
                return False
            
            print(f"✅ PDF generated successfully, size: {len(pdf_response.content)} bytes")
            
            self.log_test("Full Translation Workflow", True, f"Complete workflow successful for bill {bill_id}")
            return True
            
        except Exception as e:
            self.log_test("Full Translation Workflow", False, str(e))
            return False

    def run_integration_test(self):
        """Run integration test with real image"""
        print("🚀 Starting Bill Translation Integration Test")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test the full workflow
        success = self.test_full_translation_workflow()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Integration Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if success:
            print("🎉 Integration test passed!")
            return True
        else:
            print("⚠️ Integration test failed. Check details above.")
            return False

def main():
    tester = BillTranslationAPITesterWithRealImage()
    success = tester.run_integration_test()
    
    # Save test results
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": tester.tests_run,
        "passed_tests": tester.tests_passed,
        "success_rate": f"{(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "0%",
        "test_details": tester.test_results
    }
    
    # Write results to file
    with open('/app/integration_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())