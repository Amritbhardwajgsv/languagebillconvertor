from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType, ImageContent
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
from PIL import Image
import tempfile

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Get API key
API_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Define Models
class Bill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    original_language: str = "Unknown"
    status: str = "uploaded"  # uploaded, processing, translated, failed
    upload_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    original_image_base64: str = ""
    translated_text: str = ""
    error_message: Optional[str] = None

class BillCreate(BaseModel):
    filename: str
    original_image_base64: str

class BillResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str
    filename: str
    original_language: str
    status: str
    upload_date: str
    translated_text: str = ""
    error_message: Optional[str] = None

@api_router.get("/")
async def root():
    return {"message": "Bill Translation API"}

@api_router.post("/bills/upload", response_model=BillResponse)
async def upload_bill(file: UploadFile = File(...)):
    """Upload a bill image"""
    try:
        # Read file
        contents = await file.read()
        
        # Convert to base64
        base64_image = base64.b64encode(contents).decode('utf-8')
        
        # Determine mime type
        mime_type = file.content_type or 'image/jpeg'
        if mime_type not in ['image/jpeg', 'image/png', 'image/webp']:
            mime_type = 'image/jpeg'
        
        # Create bill record
        bill_dict = {
            "id": str(uuid.uuid4()),
            "filename": file.filename,
            "original_language": "Unknown",
            "status": "uploaded",
            "upload_date": datetime.now(timezone.utc).isoformat(),
            "original_image_base64": base64_image,
            "translated_text": "",
            "mime_type": mime_type
        }
        
        await db.bills.insert_one(bill_dict)
        
        return BillResponse(
            id=bill_dict["id"],
            filename=bill_dict["filename"],
            original_language=bill_dict["original_language"],
            status=bill_dict["status"],
            upload_date=bill_dict["upload_date"],
            translated_text=""
        )
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/bills/{bill_id}/translate", response_model=BillResponse)
async def translate_bill(bill_id: str):
    """Translate a bill using Gemini"""
    try:
        # Get bill from database
        bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        
        # Update status to processing
        await db.bills.update_one(
            {"id": bill_id},
            {"$set": {"status": "processing"}}
        )
        
        # Initialize Gemini chat
        chat = LlmChat(
            api_key=API_KEY,
            session_id=f"bill-{bill_id}",
            system_message="You are an expert at reading invoices and bills. Extract all information and structure it properly."
        ).with_model("gemini", "gemini-3-flash-preview")
        
        # Create image content from base64
        image_content = ImageContent(
            image_base64=bill["original_image_base64"]
        )
        
        # Create message with image - ask for structured JSON
        user_message = UserMessage(
            text="""Analyze this bill/invoice image and extract ALL information in the following JSON format:

{
  "language": "detected language (e.g., Hindi, Tamil, etc.)",
  "business_name": "store/business name",
  "business_address": "full address",
  "business_phone": "phone numbers",
  "bill_number": "invoice/bill number",
  "bill_date": "date on the bill",
  "customer_name": "customer name if present",
  "items": [
    {
      "sno": "serial number",
      "item_name": "item description in English",
      "quantity": "quantity with unit",
      "rate": "rate/price per unit",
      "amount": "total amount"
    }
  ],
  "subtotal": "subtotal if present",
  "tax": "tax amount if present",
  "total": "grand total",
  "notes": "any additional notes or terms"
}

IMPORTANT: 
- Translate ALL text to English
- If a field is not present in the bill, use empty string ""
- For items, extract as many rows as visible
- Preserve all numbers exactly as shown
- Return ONLY the JSON, no other text""",
            file_contents=[image_content]
        )
        
        # Get response from Gemini
        response = await chat.send_message(user_message)
        
        # Try to parse JSON from response
        import json
        import re
        
        # Extract JSON from response (handle cases where LLM adds extra text)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            bill_data = json.loads(json_match.group())
        else:
            # Fallback: store raw response
            bill_data = {"raw_translation": response}
        
        # Update bill in database with structured data
        await db.bills.update_one(
            {"id": bill_id},
            {
                "$set": {
                    "status": "translated",
                    "original_language": bill_data.get("language", "Unknown"),
                    "translated_text": response,
                    "structured_data": bill_data
                }
            }
        )
        
        # Get updated bill
        updated_bill = await db.bills.find_one({{"id": bill_id}}, {"_id": 0})
        
        return BillResponse(
            id=updated_bill["id"],
            filename=updated_bill["filename"],
            original_language=updated_bill["original_language"],
            status=updated_bill["status"],
            upload_date=updated_bill["upload_date"],
            translated_text=updated_bill["translated_text"]
        )
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        # Update status to failed
        await db.bills.update_one(
            {"id": bill_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(e)
                }
            }
        )
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bills/{bill_id}/pdf")
async def generate_pdf(bill_id: str):
    """Generate and download PDF of translated bill"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        import json
        
        # Get bill from database
        bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        
        if bill["status"] != "translated":
            raise HTTPException(status_code=400, detail="Bill not yet translated")
        
        # Get structured data
        structured_data = bill.get("structured_data", {})
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              rightMargin=50, leftMargin=50,
                              topMargin=50, bottomMargin=50)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Styles
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24,
                                     textColor=colors.HexColor('#002FA7'), alignment=TA_CENTER,
                                     spaceAfter=20, fontName='Helvetica-Bold')
        
        heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=12,
                                      textColor=colors.HexColor('#0A0A0A'), spaceAfter=8,
                                      fontName='Helvetica-Bold')
        
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10,
                                     textColor=colors.HexColor('#0A0A0A'), spaceAfter=4)
        
        # Title
        elements.append(Paragraph("INVOICE / BILL", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Business Info Section
        if structured_data.get("business_name"):
            elements.append(Paragraph(f"<b>{structured_data['business_name']}</b>", heading_style))
        if structured_data.get("business_address"):
            elements.append(Paragraph(structured_data["business_address"], normal_style))
        if structured_data.get("business_phone"):
            elements.append(Paragraph(f"Phone: {structured_data['business_phone']}", normal_style))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Bill Details Table
        details_data = []
        if structured_data.get("bill_number"):
            details_data.append(["Bill No:", structured_data["bill_number"]])
        if structured_data.get("bill_date"):
            details_data.append(["Date:", structured_data["bill_date"]])
        if structured_data.get("customer_name"):
            details_data.append(["Customer:", structured_data["customer_name"]])
        
        details_data.append(["Original Language:", bill.get("original_language", "Unknown")])
        details_data.append(["Translation Date:", bill["upload_date"][:10]])
        
        if details_data:
            details_table = Table(details_data, colWidths=[1.5*inch, 4*inch])
            details_table.setStyle(TableStyle([
                ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
                ('FONT', (1, 0), (1, -1), 'Helvetica', 9),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0A0A0A')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(details_table)
            elements.append(Spacer(1, 0.3*inch))
        
        # Items Table
        items = structured_data.get("items", [])
        if items:
            elements.append(Paragraph("ITEMS", heading_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Create table headers
            table_data = [["S.No", "Item Description", "Quantity", "Rate", "Amount"]]
            
            # Add item rows
            for item in items:
                row = [
                    item.get("sno", ""),
                    item.get("item_name", ""),
                    item.get("quantity", ""),
                    item.get("rate", ""),
                    item.get("amount", "")
                ]
                table_data.append(row)
            
            items_table = Table(table_data, colWidths=[0.6*inch, 2.5*inch, 1*inch, 1*inch, 1*inch])
            items_table.setStyle(TableStyle([
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#002FA7')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                
                # Body
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#0A0A0A')),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # S.No center
                ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Item left
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Numbers right
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                
                # Grid and colors
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5E5')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F7F7')]),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#002FA7')),
            ]))
            
            elements.append(items_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Totals Section
        totals_data = []
        if structured_data.get("subtotal"):
            totals_data.append(["Subtotal:", structured_data["subtotal"]])
        if structured_data.get("tax"):
            totals_data.append(["Tax:", structured_data["tax"]])
        if structured_data.get("total"):
            totals_data.append(["<b>Grand Total:</b>", f"<b>{structured_data['total']}</b>"])
        
        if totals_data:
            totals_table = Table(totals_data, colWidths=[4.5*inch, 1.5*inch])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -2), 'Helvetica', 10),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold', 11),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0A0A0A')),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#002FA7')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(totals_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Notes
        if structured_data.get("notes"):
            elements.append(Paragraph("<b>Notes:</b>", normal_style))
            elements.append(Paragraph(structured_data["notes"], normal_style))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_file.write(buffer.read())
        temp_file.close()
        
        return FileResponse(
            temp_file.name,
            media_type="application/pdf",
            filename=f"invoice_{bill['filename'].rsplit('.', 1)[0]}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/bills", response_model=List[BillResponse])
async def get_bills():
    """Get all bills"""
    bills = await db.bills.find({}, {"_id": 0, "original_image_base64": 0}).sort("upload_date", -1).to_list(1000)
    
    return [
        BillResponse(
            id=bill["id"],
            filename=bill["filename"],
            original_language=bill.get("original_language", "Unknown"),
            status=bill["status"],
            upload_date=bill["upload_date"],
            translated_text=bill.get("translated_text", ""),
            error_message=bill.get("error_message")
        )
        for bill in bills
    ]

@api_router.get("/bills/{bill_id}", response_model=BillResponse)
async def get_bill(bill_id: str):
    """Get single bill details"""
    bill = await db.bills.find_one({"id": bill_id}, {"_id": 0, "original_image_base64": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    return BillResponse(
        id=bill["id"],
        filename=bill["filename"],
        original_language=bill.get("original_language", "Unknown"),
        status=bill["status"],
        upload_date=bill["upload_date"],
        translated_text=bill.get("translated_text", ""),
        error_message=bill.get("error_message")
    )

@api_router.get("/bills/{bill_id}/image")
async def get_bill_image(bill_id: str):
    """Get original bill image"""
    bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    return {"image_base64": bill.get("original_image_base64", "")}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()