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
            system_message="You are an expert OCR and translation assistant. Extract text from bill images and translate them accurately to English while preserving the structure and formatting."
        ).with_model("gemini", "gemini-3-flash-preview")
        
        # Create image content from base64
        image_content = ImageContent(
            image_base64=bill["original_image_base64"]
        )
        
        # Create message with image
        user_message = UserMessage(
            text="""Please analyze this bill/invoice image and:
1. Identify the language used in the document
2. Extract ALL text from the image
3. Translate the entire content to English
4. Preserve the structure and formatting (headers, line items, totals, etc.)
5. Return the output in this exact format:

LANGUAGE: [detected language]

TRANSLATED BILL:
[translated content with preserved structure]
""",
            file_contents=[image_content]
        )
        
        # Get response from Gemini
        response = await chat.send_message(user_message)
        
        # Extract language from response
        language = "Unknown"
        if "LANGUAGE:" in response:
            language_line = response.split("\n")[0]
            language = language_line.replace("LANGUAGE:", "").strip()
        
        # Update bill in database
        await db.bills.update_one(
            {"id": bill_id},
            {
                "$set": {
                    "status": "translated",
                    "original_language": language,
                    "translated_text": response
                }
            }
        )
        
        # Get updated bill
        updated_bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
        
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
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        
        # Get bill from database
        bill = await db.bills.find_one({"id": bill_id}, {"_id": 0})
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        
        if bill["status"] != "translated":
            raise HTTPException(status_code=400, detail="Bill not yet translated")
        
        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                              rightMargin=50, leftMargin=50,
                              topMargin=50, bottomMargin=50)
        
        # Container for the 'flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#0A0A0A'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#002FA7'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#0A0A0A'),
            spaceAfter=6
        )
        
        # Add title
        elements.append(Paragraph("TRANSLATED INVOICE", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Add metadata table
        metadata = [
            ['Original File:', bill['filename']],
            ['Original Language:', bill['original_language']],
            ['Translation Date:', bill['upload_date'][:10]],
        ]
        
        meta_table = Table(metadata, colWidths=[2*inch, 4*inch])
        meta_table.setStyle(TableStyle([
            ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
            ('FONT', (1, 0), (1, -1), 'Helvetica', 9),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0A0A0A')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(meta_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Parse the translated text to extract bill structure
        text = bill["translated_text"]
        
        # Try to extract table data if present
        lines = text.split('\\n')
        
        # Look for table patterns
        table_data = []
        in_table = False
        header_info = []
        footer_info = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Skip language identifier
            if line.startswith('LANGUAGE:'):
                continue
            if line.startswith('TRANSLATED BILL:'):
                continue
                
            # Detect table headers (S.No, KG, ITEM, TOTAL, etc.)
            if 'S.No' in line or 'S NO' in line.upper() or ('ITEM' in line.upper() and 'TOTAL' in line.upper()):
                in_table = True
                # Clean up the header
                headers = [h.strip() for h in line.split('|') if h.strip()]
                if headers:
                    table_data.append(headers)
                continue
            
            # If we're in a table and line has pipe separators
            if in_table and '|' in line:
                # Check if it's a separator line (all dashes)
                if all(c in '-|: ' for c in line):
                    continue
                    
                row = [cell.strip() for cell in line.split('|') if cell.strip()]
                if row and any(cell for cell in row):  # If row has content
                    table_data.append(row)
            elif in_table and not '|' in line:
                # End of table
                in_table = False
                footer_info.append(line)
            elif not in_table and i < 10:  # Header info (first few lines)
                header_info.append(line)
            elif not in_table:
                footer_info.append(line)
        
        # Add header information
        if header_info:
            for info in header_info:
                if info and not info.startswith('*'):
                    elements.append(Paragraph(info, normal_style))
            elements.append(Spacer(1, 0.2*inch))
        
        # Add table if found
        if table_data and len(table_data) > 1:
            # Create the table
            bill_table = Table(table_data, repeatRows=1)
            bill_table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#002FA7')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Body styling
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#0A0A0A')),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E5E5')),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#002FA7')),
                
                # Alternate row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F7F7')]),
            ]))
            
            elements.append(bill_table)
            elements.append(Spacer(1, 0.2*inch))
        
        # Add footer information
        if footer_info:
            for info in footer_info:
                if info:
                    elements.append(Paragraph(info, normal_style))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_file.write(buffer.read())
        temp_file.close()
        
        # Return file
        return FileResponse(
            temp_file.name,
            media_type="application/pdf",
            filename=f"translated_{bill['filename'].rsplit('.', 1)[0]}.pdf"
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