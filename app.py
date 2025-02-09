from typing import Optional, Literal
from pydantic import BaseModel, Field, validator
from groq import Groq
import requests
import json


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = 'h'

class Parm(BaseModel):
    """Information about a person."""
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
    searchInCountry: Literal["au", "ca", "fr", "uk", "us"] = Field(
        default="",
        description="Single country code (au, ca, fr, uk, us)."
    )

#         Any Section, Revision Date, Brand Name, Generic Name, Manufacturer, Label Title, Highlights, 
#         Abuse Section, Adverse Reactions, Boxed Warning Section, Clinical Pharmacology/Clinical Studies, 
#         Contraindications, Drug Interactions, Dosage & Administration, Dosage Form, 
#         Indications and Usage, Information For Patients/Caregivers , 
#         Overdosage, Preclinical Safet-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-y Data, Pregnancy & Lactation, Storage & Handling,
#         Warnings & Precautions, Medguide Section, PIL, CMI

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


def extract_information(user_query: str) -> Optional[Parm]:
    """Extract structured data from a user query using Groq's API."""
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
#     system_message = (
#     """You are an AI assistant specializing in extracting structured information from user queries. 
#     Your task is to return only a valid JSON object or a list of JSON objects when MULTIPLE conditions exist. 
#     The JSON must contain the following keys: 'param', 'condition', 'searchQuery', 'operators', and 'searchInCountry'.

#     RULES:
#     - 'param' must **strictly match** one of the predefined values:
#       ["Any Section", "Revision Date", "Brand Name", "Generic Name", "Manufacturer", "Label Title", 
#       "Highlights", "Abuse Section", "Adverse Reactions", "Boxed Warning Section", 
#       "Clinical Pharmacology/Clinical Studies", "Contraindications", "Drug Interactions", 
#       "Dosage & Administration", "Dosage Form", "Indications and Usage", 
#       "Information For Patients/Caregivers", "Overdosage", "Preclinical Safety Data", 
#       "Pregnancy & Lactation", "Storage & Handling", "Warnings & Precautions", 
#       "Medguide Section", "PIL", "CMI"].

#     - If the query **mentions a drug name**, set 'param' as `"Generic Name"`, unless context specifies otherwise.  
#     - 'condition' must be either 'contains' or 'not contains'.  
#     - 'searchQuery' should extract the **exact drug or term mentioned** in the query.  
#     - **'operators' should be determined based on user input text :**
#       - If the user explicitly states `"and"`, use `"operators": "and"`.  
#       - If the user explicitly states `"or"`, use `"operators": "or"`.  
#       - If there is only **one** condition, `"operators"` should be `null`.  
#       - **Only the last object in a multi-condition query should have `"operators": null"`.**  
#     - 'searchInCountry' should be **one of** ['au', 'ca', 'fr', 'uk', 'us'] if the searchInCountry is not present then "au,ca,fr,uk,us"  .

#     **If the query contains multiple distinct conditions with OR or AND in query, return an array of JSON objects.**  
#     Each condition must be connected with `"operators": "and"` or `"operators": "or"` depending on the query.  
#     The **last object must always have `"operators": null"`.**
#     **Output JSON only. Do not include explanations or additional text.**  
#     """
# )

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
      - If the user explicitly states `"or"`, use `"operators": "or"`.  
      - If there is only **one** condition, `"operators"` should be `null`.  
      - **Only the last object in a multi-condition query should have `"operators": null"`.**  
    - 'searchInCountry' should be **one of** ['au', 'ca', 'fr', 'uk', 'us'] if the searchInCountry is not present then "au,ca,fr,uk,us"  .

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
    
    response = requests.post(GROQ_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        try:
            response_data = response.json()            
            structured_data = response_data.get("choices", [{}])[0].get("message", {}).get("content", "{}").strip()
            return structured_data
        except:
            return "Please give more clear text"
    else:
        print(f"Groq API Error: {response.status_code} - {response.text}")
        return None
    
# Example usage
# user_query = "generic name for medicine whose title is ibuprofen or botox"
user_query = "generic name for ibuprofen in usa or botox in uk"
# user_query = "ibuprofen in france"
# user_query ="drugs for cancer in India"
# user_query = "generic name should not condtain for ibuprofen and botox "
# user_query = "Find me drug for cancer , post covid , pre covid in USA "

result = extract_information(user_query)
print(result)