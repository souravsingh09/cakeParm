# cakeParm
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, List
from dotenv import load_dotenv
from groq import Groq
import datetime
import uvicorn
import requests
import timeit
import asyncpg
import json
import re
import os

from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta

################ APP CREATION STARTED #################
app = FastAPI()

################ Load the environment variables ################
load_dotenv()

class Query(BaseModel):
    text : str


################ APP CREATION STARTED #################
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

################ CORS to allow specific origins ################
allowed_origins = os.getenv('ALLOWED_ORIGINS')


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Restrict to specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow specific HTTP methods
    allow_headers=["*"],  # Allow all headers
)
# Define your OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token",
             scopes={"me": "Read information about the current user.", "items": "Read items."})
# In-memory database for client_id and client_secret (you can use a real database)
fake_clients_db = {
   "client_id_1": {
       "client_secret": os.getenv("CLIENT_SECRET"),
       "scopes": ["read", "write"],
   }
}

# Secret key to encode the JWT token
SECRET_KEY = os.getenv("SECRET_KEY") 
ALGORITHM = os.getenv("ALGORITHM") 
ACCESS_TOKEN_EXPIRE_MINUTES = 30
class Token(BaseModel):
   access_token: str
   token_type: str

class TokenData(BaseModel):
   client_id: str | None = None
   scopes: list[str] = []

def verify_client(client_id: str, client_secret: str):
   client = fake_clients_db.get(client_id)
   if not client or client["client_secret"] != client_secret:
       return False
   return True

def create_access_token(data: dict, expires_delta: timedelta | None = None):
   to_encode = data.copy()
   if expires_delta:
       expire = datetime.utcnow() + expires_delta
   else:
       expire = datetime.utcnow() + timedelta(minutes=15)
   to_encode.update({"exp": expire})
   encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
   return encoded_jwt

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None):
    # Validate the "Accept" header
    accept_header = request.headers.get("accept", "")
    if accept_header not in ["application/json", "*/*","application/json, text/plain, */*"]:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Accept header must be application/json or */*"
        )

    client_id = form_data.username
    client_secret = form_data.password

    if not verify_client(client_id, client_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect client ID or client secret",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": client_id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_client(token: str = Depends(oauth2_scheme)):
   credentials_exception = HTTPException(
       status_code=status.HTTP_401_UNAUTHORIZED,
       detail="Could not validate credentials",
       headers={"WWW-Authenticate": "Bearer"},
   )
   try:
       payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
       client_id: str = payload.get("sub")
       if client_id is None:
           raise credentials_exception
       token_data = TokenData(client_id=client_id)
   except JWTError:
       raise credentials_exception
   return token_data

@app.post('/answer')
async def answer( data: Query , token: str = Depends(oauth2_scheme), request: Request = None):

    client = await get_current_client(token)
    
    data= data.dict()
    query_text = data['text']

    return {'response': f"hello {query_text}"} 

if __name__ == "__main__":
     uvicorn.run(app, host="0.0.0.0", port=8000)
