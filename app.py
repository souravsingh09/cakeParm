from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from groq import Groq
import datetime
import uvicorn
import requests
import timeit
import asyncpg
import json
import re
import os

################ APP CREATION STARTED #################
app = FastAPI()

################ APP CREATION STARTED #################
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

################ CORS to allow specific origins ################
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

################ Pydantic model for input validation ################
class UserContent(BaseModel):
    user_query : str

################ Pydantic model for output validation ################
class Parm(BaseModel):
    param: Optional[str] = Field(
        default=None,
        description="Information user wants to look for. Must be from the allowed list."
    )
    condition: Literal["contains", "not contains"] = Field(
        default="contains",
        description="Whether the user wants the term to be included or excluded."
    )
    searchQuery: Optional[str] = Field(
        default="",
        description="Query term such as medicine name, condition, etc."
    )
    operators: Literal["and", "or", ""] = Field(
        default="",
        description="Logical operator (if any) from the user query."
    )
    searchInCountry: Literal["au", "ca", "fr", "uk", "us","eu"] = Field(
        default="",
        description="Single country code (au, ca, fr, uk, us, eu)."
    )

    @validator("param", pre=True)
    def normalize_param(cls, value):
        """Ensure param value matches the allowed list (case-insensitive)."""
        allowed_values = {
            "anysection": "Any Section",
            "revisiondate": "Revision Date",
            "brandname": "Brand Name",
            "generic name": "Generic Name",
            "manufacturer": "Manufacturer",
            "labeltitle": "Label Title",
            "highlights": "Highlights",
            "abusesection": "Abuse Section",
            "adversereactions": "Adverse Reactions",
            "boxedwarningsection": "Boxed Warning Section",
            "clinicalpharmacology/clinicalstudies": "Clinical Pharmacology/Clinical Studies",
            "contraindications": "Contraindications",
            "druginteractions": "Drug Interactions",
            "dosage&administration": "Dosage & Administration",
            "dosageform": "Dosage Form",
            "indicationsandusage": "Indications and Usage",
            "informationforpatients/caregivers": "Information For Patients/Caregivers",
            "overdosage": "Overdosage",
            "preclinicalsafetydata": "Preclinical Safety Data",
            "pregnancy&lactation": "Pregnancy & Lactation",
            "storage&handling": "Storage & Handling",
            "warnings&precautions": "Warnings & Precautions",
            "medguidesection": "Medguide Section",
            "pil": "PIL",
            "cmi": "CMI",
        }
        
        if value is None:
            return None
        
        normalized_value = value.replace(" ", "").lower()
        if normalized_value in allowed_values:
            return allowed_values[normalized_value]

        raise ValueError(f"Invalid param value: {value}. Must be one of {list(allowed_values.values())}")

    @validator("operators", pre=True)
    def normalize_operators(cls, value):
        """Ensure operators is a string."""
        if isinstance(value, list) and not value:
            return ""  # Convert empty list to an empty string
        return value

async def insert_row (user_query, structured_data, reqStatusCode , responseTime, dateCreated):
    try: 
        conn = await asyncpg.connect(
            database = os.getenv('database'),
            user     = os.getenv('user'),
            password = os.getenv('password'),
            host     = os.getenv('host'),,
            port     = 5432
        )

        sql = """INSERT INTO "userQueryAI" ("userQuery", "aiResponse", "statusCode", "responseTime", "dateCreated" ) VALUES ($1, $2, $3, $4, $5)"""
        await conn.execute(sql, user_query, structured_data, reqStatusCode, str(responseTime), dateCreated )
        await conn.close()
        print("Row inserted successfully!")

    except Exception as e:
        print(f"Error inserting row: {e}")  
        return {"error": str(e)}


@app.post("/generate-parm")
async def generate_parm(user_query: str) -> Optional[Parm]:

    system_message = (
    """You are an AI assistant specializing in extracting structured information from user queries. 
    Your task is to return only a valid JSON object or a list of JSON objects when multiple conditions exist. 
    The JSON must contain the following keys: 'param', 'condition', 'searchQuery', 'operators', and 'searchInCountry'.
    RULES:
    - 'param' must **strictly match** one of the predefined values:
      ["Any Section", "Revision Date", "Brand Name", "Generic Name", "Manufacturer", "Label Title", 
      "Highlights", "Abuse Section", "Adverse Reactions", "Boxed Warning Section", 
      "Clinical Pharmacology/Clinical Studies", "Contraindications", "Drug Interactions", 
      "Dosage & Administration", "Dosage Form", "Indications and Usage", 
      "Information For Patients/Caregivers", "Overdosage", "Preclinical Safety Data", 
      "Pregnancy & Lactation", "Storage & Handling", "Warnings & Precautions", 
      "Medguide Section", "PIL", "CMI"].
    - If the query **mentions a drug name**, set 'param' as `"Generic Name"`, unless context specifies otherwise.  
    - 'condition' must be either 'contains' or 'not contains'.  
    - 'searchQuery' should extract the **exact drug or term mentioned** in the query.  
    - **'operators' should be determined based on user input text :**
      - If the user explicitly states `"and"`, use `"operators": "and"`.  
       - If the user explicitly states `"or"` or uses ',' , use `"operators": "or"`.  
      - If there is only **one** condition, `"operators"` should be `null`.  
      - **Only the last object in a multi-condition query should have `"operators": null"`.**  
    - 'searchInCountry' should be **one of** ['au', 'ca', 'fr', 'uk', 'us', 'eu'] if the searchInCountry is not present then "au,ca,fr,uk,us,eu".

    **If the query contains multiple distinct conditions with OR or AND, return an array of JSON objects.**  
    Each condition must be connected with `"operators": "and"` or `"operators": "or"` depending on the query.  
    The **last object must always have `"operators": null"`.**
    **Output JSON only. Do not include explanations or additional text.**  
    """
    )
 
    payload = {
        "model": "deepseek-r1-distill-llama-70b",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_query}
        ]
    }
    
    start = timeit.default_timer()
    response = requests.post(GROQ_API_URL, headers=headers, json=payload)
    dateCreated = datetime.datetime.now()

    if response.status_code == 200:
        try:
            response_data = response.json()           
            structured_data = response_data.get("choices", [{}])[0].get("message", {}).get("content", "{}").strip()    
            structured_data = re.sub(r"<think>.*?</think>", "", structured_data , flags=re.DOTALL).strip()
            
            match = re.search(r"(\[.*\]|\{.*\})", structured_data, re.DOTALL)
            if match:
                structured_data = match.group(0).strip()

            # Parse string JSON into Python dict
            structured_data = json.dumps(structured_data)

            end = timeit.default_timer()

            ########### Some Variable to be set ##############
            responseTime = end - start
            reqStatusCode = response.status_code

            ########### insert row in PGADMIN ###########
            await insert_row(user_query, structured_data, reqStatusCode, responseTime, dateCreated)
            return Response(content=structured_data, media_type="application/json")

        except:
            return "Please give more clear text"
    else:
        print(f"Groq API Error: {response.status_code} - {response.text}")
        return None
