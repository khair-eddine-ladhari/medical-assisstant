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

import pandas as pd


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



















"""add to the history"""

def save_to_history(symptoms, diseases, response):
    
    new_report = {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "symptoms": symptoms,
        "diseases_found": ", ".join([d["name"] for d in diseases]),
        "diagnosis": response
    }
    
    if os.path.exists("reports_history.csv"):
        df = pd.read_csv("reports_history.csv")
        df = pd.concat([df, pd.DataFrame([new_report])], ignore_index=True)
    else:
        df = pd.DataFrame([new_report])
    
    df.to_csv("reports_history.csv", index=False)
    print("✅ Report saved to history!")



"""return the history"""

def get_patient_history():
    if os.path.exists("reports_history.csv"):
        df = pd.read_csv("reports_history.csv")
        return df.to_string(index=False)
    return None












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














def doctor_consultation(input_symptoms, message):
    
    print("\n🏥 MediScan AI: Let me ask you some questions...\n")
    
    while True:
        # Ask AI if it needs more info or is ready to diagnose
        message.append({
            "role": "user",
            "content": f"""
            Based on the conversation so far about these symptoms: {input_symptoms}
            
            Do you have enough information to make a diagnosis?
            
            If YES → reply with exactly: "READY_TO_DIAGNOSE"
            If NO → ask the patient one specific follow-up question
            """
        })
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=message,
            temperature=0.7,
            max_tokens=200,
        )
        
        ai_response = response.choices[0].message.content
        message.append({"role": "assistant", "content": ai_response})
        
        # Check if AI is ready
        if "READY_TO_DIAGNOSE" in ai_response:
            print("\n🔍 I have enough information. Analyzing now...\n")
            break
        
        # AI needs more info → ask the question
        print(f"\n🤖 MediScan: {ai_response}\n")
        answer = input("You: ")
        message.append({"role": "user", "content": answer})













""" Function to calculate the number of tokens in the response and check if it exceeds the limit"""


def calculate_tokens(text):
    encoding = tk.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    num_tokens = len(tokens)
    return num_tokens <= 100





""" Main function to analyze symptoms, call the language model, and handle the response"""





@retry(stop=stop_after_attempt(3), wait=wait_random_exponential(min=10, max=10))
def analyze_symptoms(input_symptoms, message):

    try:

        if calculate_tokens(input_symptoms) == False:
            return "Response is too long, please shorten the input.", []

        if moderationfunc(input_symptoms) == False:
            return "Response is not safe, please try again.", []

        # Force AI to use the function
        message.append({
            "role": "user",
            "content": f"Based on everything we discussed, please now use the get_disease_info function to analyze my symptoms and provide a final diagnosis."
        })

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=message,
            temperature=0.7,
            max_tokens=1000,
            top_p=1,
            tools=function_definition,
            tool_choice="required",  # ← force function call!
            user=unique_id
        )

        print(f"Finish reason: {response.choices[0].finish_reason}")

        if response.choices[0].finish_reason == 'tool_calls':
            print("✅ AI called a function!")
            function_call = response.choices[0].message.tool_calls[0].function

            if function_call.name == "get_disease_info":
                disease_names = json.loads(function_call.arguments)["disease_names"]
                print(f"Diseases to search: {disease_names}")
                disease_data = get_disease_info(disease_names)

                if disease_data:
                    message.append(response.choices[0].message)
                    message.append({
                        "role": "tool",
                        "tool_call_id": response.choices[0].message.tool_calls[0].id,
                        "content": json.dumps(disease_data)
                    })

                    final_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=message,
                        temperature=0.7,
                        max_tokens=1000,
                    )

                    return final_response.choices[0].message.content, disease_data

                else:
                    return "No disease info found", []

        else:
            print("❌ AI didn't call function!")
            print(f"Reason: {response.choices[0].finish_reason}")
            print(f"AI said: {response.choices[0].message.content}")
            return response.choices[0].message.content, []

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise








def generate_pdf(symptoms, diseases, diagnosis):
    
    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Arial", "B", 20)
    pdf.cell(200, 15, "MEDISCAN AI - MEDICAL REPORT", ln=True, align="C")
    
    # Date
    pdf.set_font("Arial", "I", 10)
    pdf.cell(200, 10, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(5)
    
    # Line separator
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    # Symptoms
    pdf.set_font("Arial", "B", 13)
    pdf.cell(200, 10, "Symptoms Reported:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(190, 8, symptoms)
    pdf.ln(5)
    
    # Diseases found
    pdf.set_font("Arial", "B", 13)
    pdf.cell(200, 10, "Possible Conditions:", ln=True)
    pdf.set_font("Arial", size=11)
    for disease in diseases:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(200, 8, f"- {disease['name'].upper()}", ln=True)
        pdf.set_font("Arial", size=10)
        # Limit description to 300 chars
        description = disease['description'][:300] + "..."
        pdf.multi_cell(190, 7, description)
        pdf.ln(3)
    
    # Diagnosis
    pdf.ln(3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(200, 10, "AI Diagnosis:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(190, 8, diagnosis)
    pdf.ln(5)
    
    # Disclaimer
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("Arial", "I", 9)
    pdf.multi_cell(190, 7, 
        "DISCLAIMER: This report is generated by AI and is NOT a substitute "
        "for professional medical advice. Always consult a qualified doctor.")
    
    # Save
    filename = f"medical_report_{datetime.now().strftime('%d_%m_%Y_%H%M')}.pdf"
    pdf.output(filename)
    return filename





















history = get_patient_history()
if history:
    message.append({
        "role": "system",
        "content": f"""
This patient has visited before. Here are their last visits:
{history}

Use this history to:
- Identify recurring symptoms
- Check if conditions are worsening
- Provide more personalized diagnosis
        """
    })

# Get initial symptoms
input_symptoms = input("\nPlease enter your symptoms: ")
message.append({"role": "user", "content": input_symptoms})

# Doctor consultation
doctor_consultation(input_symptoms, message)

# Final diagnosis
print("\n🔍 Analyzing your complete symptoms...\n")
response, diseases = analyze_symptoms(input_symptoms, message)
print(f"\n🏥 MediScan: {response}")




filename = generate_pdf(input_symptoms, diseases, response)
print(f"\n📄 PDF Report saved: {filename}")





# Save to history
save_to_history(input_symptoms, diseases, response)