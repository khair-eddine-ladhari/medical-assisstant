import os

from dotenv import load_dotenv
load_dotenv()

from groq import Groq

client = Groq(api_key=os.getenv("api_key_model"))
from fpdf import FPDF

import tiktoken as tk

import json

from datetime import datetime

import requests

from tenacity import (retry, stop_after_attempt, wait_random_exponential)


from openai import OpenAI
import uuid
unique_id =str(uuid.uuid4())



""" Define the system prompt and initial message"""

message = [
    {"role": "system", "content": """
You are MediScan AI, a professional medical assistant.

Your behavior:
- Analyze symptoms carefully and professionally
- Always use the get_disease_info function with MAXIMUM 3 diseases
- Never give a 100% certain diagnosis
- Always recommend seeing a doctor for Medium or High severity
- Only respond to medical symptom related inputs
- If the input is not about symptoms, reply: Sorry I can only analyze medical symptoms.
- Be clear, simple and empathetic in your analysis

Important:
- You are NOT a replacement for a real doctor
- Always prioritize patient safety
- For High severity symptoms, always say Go to emergency immediately
- ALWAYS call get_disease_info with exactly 2-3 disease names maximum
"""}
]


""" Define the function definition"""


function_definition = [
    {
        "type": "function",
        "function": {
            "name": "get_disease_info",
            "description": "Get medical information about a disease",
            "parameters": {
                "type": "object",
                "properties": {
                    "disease_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 2-3 simple disease names like flu, cold, migraine"
                    }
                },
                "required": ["disease_names"]
            }
        }
    }
]


""" Function to call the external medical API and fetch disease information based on the symptoms"""


def get_disease_info(disease_names):
    results = []
    
    for disease in disease_names:
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{disease.replace(' ', '_')}"
            headers = {"User-Agent": "MediScanAI/1.0"}
            response = requests.get(url, headers=headers)
            
            print(f"Searching: {disease} → Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "name": disease,
                    "description": data.get("extract", "No info found")
                })
                print(f"✅ Found: {disease}")
            else:
                print(f"❌ Not found: {disease}")
        except Exception as e:
            print(f"Error fetching {disease}: {e}")
    
    return results if results else [{"name": "unknown", "description": "No disease info found"}]
""" Function to call the moderation API to check if the response is safe or not"""



openai_client = OpenAI(api_key=os.getenv("api_key_moderation"))


@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=1, max=10))
def moderationfunc(message):
    return True

    

    moderation_response = openai_client.moderations.create(
        input=message
    )


    return not moderation_response.results[0].flagged











""" Function to calculate the number of tokens in the response and check if it exceeds the limit"""


def calculate_tokens(text):
    encoding = tk.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    num_tokens = len(tokens)
    return num_tokens <= 100





""" Main function to analyze symptoms, call the language model, and handle the response"""

@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=10, max=10))
def analyze_symptoms(input_symptoms,message):



    try:

        if (calculate_tokens(input_symptoms)==False):
            
            return "Response is too long, please shorten the input."
        
        if (moderationfunc(input_symptoms)==False):
            return "Response is not safe, please try again."


        response=client.chat.completions.create(
        model="llama-3.3-70b-versatile",

        messages=message,

        temperature=0.7,
        max_tokens=1000,
        top_p=1,


        tools=function_definition,
        tool_choice="auto",

        user=unique_id
        
 
        )   






        if response.choices[0].finish_reason == 'tool_calls':
            function_call = response.choices[0].message.tool_calls[0].function



    
            if function_call.name == "get_disease_info":
                disease_names = json.loads(function_call.arguments)["disease_names"]
                disease_data = get_disease_info(disease_names)
        
                if disease_data:

                    """add the function call response to the message"""

                    message.append(response.choices[0].message)

                    """add the disease data to the message"""
                    message.append({
                        "role": "tool",
                        "tool_call_id": response.choices[0].message.tool_calls[0].id,
                        "content": json.dumps(disease_data) 
                    })
                    """   'json.dumps(disease_data)'  to pass it as a string not as a dictionary"""
                    # Get final response from AI
                    final_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=message,
                        temperature=0.7,
                        max_tokens=1000,
                    
                    )
                    
                    return(final_response.choices[0].message.content) 
            
                else:
                    return("No disease info found")





        else:
            return response.choices[0].message.content
    
    
    

  
    except Exception as e:
        print(f"""Unexpected error: {e}""")
        raise








input_symptoms = input("Please enter your symptoms: ")

message.append({"role": "user", "content": input_symptoms})





response = analyze_symptoms(input_symptoms,message)

print(response)