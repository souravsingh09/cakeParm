# # if __name__ == "__main__":
# #     uvicorn.run(app, host="0.0.0.0", port=8000)


from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
import uvicorn
from io import BytesIO
from xhtml2pdf import pisa
from scrapy.selector import Selector
import re

################ APP CREATION STARTED #################

app = FastAPI()

pdf_options = {
    "page-size": "A4",
    "encoding": "UTF-8",
}

# CORS to allow specific origins
allowed_origins = [ 
    "https://dev.druglabels.in",
    "http://localhost:3000"  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict to specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow specific HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define a Pydantic model for input validation
class HTMLContent(BaseModel):
    html: str

@app.post("/generate-pdf")
async def generate_pdf(html: str = Body(..., media_type="text/html")):
    # Create a BytesIO object to store the PDF output
    pdf_output = BytesIO()

    # Extract only the body content
    bodyresponse = Selector(text=html)
    html = bodyresponse.xpath('//body').get()
    # Regex to remove colspan
    html = re.sub(r'\s*colspan="\d+"', '', html)
    # Regex to remove rowspan
    html = re.sub(r'\s*rowspan="\d+"', '', html)
    print('===========', len(html))

    # Convert the HTML content to a PDF
    pisa_status = pisa.CreatePDF(html, dest=pdf_output, encoding='utf-8')

    # Check if PDF generation was successful
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="An error occurred while generating the PDF")

    # Retrieve the PDF data from the buffer
    pdf_output.seek(0)  # Reset the buffer position to the beginning
    pdf_data = pdf_output.getvalue()

    # Return the PDF as a downloadable response
    return Response(content=pdf_data, media_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=generated.pdf"
    })



