from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from requests.auth import HTTPBasicAuth
import urllib3
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.vectorstores import Chroma
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn
import time
import threading
import re

app = FastAPI()

# CouchDB connection parameters
COUCHDB_URL = 'https://192.168.57.185:5984'
COUCHDB_USERNAME = 'd_couchdb'
COUCHDB_PASSWORD = 'Welcome#2'
DATABASE_NAME = 'gowtham1'
GOOGLE_API_KEY = "AIzaSyAvgwBW-yBqVq3a1MjwaTDELT1inUyXSYc"

# Configure Google API
genai.configure(api_key=GOOGLE_API_KEY)

# Disable SSL warnings (not recommended for production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chroma database path
CHROMA_DB_PATH = "./chroma_db7"  # Path where Chroma stores the vector data

# Ensure the Chroma directory exists
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

# Pydantic models for requests
class QueryRequest(BaseModel):
    query: str

class AddEmployeeRequest(BaseModel):
    doc_id: str


employee_regex = r'employee_1_(\d+)'
additionalinfo_regex = r'additionalinfo_1_(\d+)'
leave_regex = r'leave_(\d+)'


# Fetch a specific document from CouchDB
def fetch_document(doc_id):
    try:
        response = requests.get(f"{COUCHDB_URL}/{DATABASE_NAME}/{doc_id}",
                                auth=HTTPBasicAuth(COUCHDB_USERNAME, COUCHDB_PASSWORD),
                                verify=False)
        response.raise_for_status()
        document = response.json()
        return document
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching document {doc_id}: {e}")

# Function to retrieve and combine employee data
def retrieve_and_combine_data(main_doc_id, additional_info_doc_id, leave_doc_id):
    # Fetching documents from CouchDB
    main_doc = fetch_document(main_doc_id)
    additional_info_doc = fetch_document(additional_info_doc_id)
    leave_doc = fetch_document(leave_doc_id)

    # Extract data from the main employee document (nested inside 'data')
    main_data = main_doc.get('data', {})  # Accessing the 'data' field
    employee_id = main_data.get('EmpID', 'N/A')  # Changed to "EmpID"
    first_name = main_data.get('FirstName', 'N/A')  # New field
    last_name = main_data.get('LastName', 'N/A')  # New field
    start_date = main_data.get('StartDate', 'N/A')  # New field
    manager = main_data.get('Manager', 'N/A')  # New field
    email = main_data.get('Email', 'N/A')  # New field
    employee_status = main_data.get('EmployeeStatus', 'N/A')  # New field
    employee_type = main_data.get('EmployeeType', 'N/A')  # New field
    pay_zone = main_data.get('PayZone', 'N/A')  # New field
    department_type = main_data.get('DepartmentType', 'N/A')  # New field
    division = main_data.get('Division', 'N/A')  # New field

    # Extract data from additional info document
    dob = additional_info_doc.get('DOB', 'N/A')  # New field
    state = additional_info_doc.get('State', 'N/A')  # New field
    gender_code = additional_info_doc.get('GenderCode', 'N/A')  # New field
    location_code = additional_info_doc.get('LocationCode', 'N/A')  # New field
    marital_desc = additional_info_doc.get('MaritalDesc', 'N/A')  # New field
    performance_score = additional_info_doc.get('Performance Score', 'N/A')  # New field
    current_employee_rating = additional_info_doc.get('Current Employee Rating', 'N/A')  # New field

    # Extract leave details
    leave_entries = leave_doc.get('leaves', [])
    leave_dates = [leave['date'] for leave in leave_entries]  # Keep the same for extracting leave dates

    # Combine all data into a single text string
    combined_text = (
        f"Employee ID: {employee_id}\n"
        f"First Name: {first_name}\n"
        f"Last Name: {last_name}\n"
        f"Start Date: {start_date}\n"
        f"Manager: {manager}\n"
        f"Email: {email}\n"
        f"Employee Status: {employee_status}\n"
        f"Employee Type: {employee_type}\n"
        f"Pay Zone: {pay_zone}\n"
        f"Department Type: {department_type}\n"
        f"Division: {division}\n"
        f"DOB: {dob}\n"
        f"State: {state}\n"
        f"Gender Code: {gender_code}\n"
        f"Location Code: {location_code}\n"
        f"Marital Status: {marital_desc}\n"
        f"Performance Score: {performance_score}\n"
        f"Current Employee Rating: {current_employee_rating}\n"
        f"Leave Dates: {', '.join(leave_dates)}"
    )
    return combined_text






# Dictionary to keep track of the last sequence for each document
last_sequences = {}

def add_employee_data_to_chroma(doc_id):
    try:
        # Fetch the updated employee document from CouchDB
        employee_doc = fetch_document(doc_id)
        additional_info_id = employee_doc.get("data", {}).get("additionalinfo_id", "")
        leave_id = f"leave_{additional_info_id.split('_')[-1]}"  # Extract only the numeric ID for leave

        if additional_info_id:
            # Fetch the additional info and leave documents
            additional_info_doc = fetch_document(f"additionalinfo_1_{additional_info_id.split('_')[-1]}")
            leave_doc = fetch_document(leave_id)

            # Check for changes in any of the three documents: employee, additional info, or leave
            has_employee_changed = has_document_changed(doc_id)
            has_additional_info_changed = has_document_changed(f"additionalinfo_1_{additional_info_id.split('_')[-1]}")
            has_leave_changed = has_document_changed(leave_id)

            # If any of the documents have changed, delete old embeddings and create new ones
            if has_employee_changed or has_additional_info_changed or has_leave_changed:
                # Delete old embeddings for employee, additional info, and leave documents
                delete_related_embeddings(doc_id, additional_info_id, leave_id)

                # Combine updated data for embeddings from all related documents
                employee_text = retrieve_and_combine_data(doc_id, f"additionalinfo_1_{additional_info_id.split('_')[-1]}", leave_id)

                # Generate the embedding using Google API
                embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
                chroma_db = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embeddings)

                # Add new embedding to Chroma
                chroma_db.add_texts([employee_text], metadatas=[{"doc_id": doc_id}], ids=[doc_id])
                chroma_db.persist()
                print(f"Updated document {doc_id} added to Chroma")

            else:
                print(f"No changes detected for {doc_id}, no update needed.")

    except Exception as e:
        print(f"Error updating Chroma for document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating Chroma for document {doc_id}: {e}")


# Function to check if the document has changed
def has_document_changed(doc_id):
    """ Check if the document has changed by comparing sequence numbers. """
    try:
        response = requests.get(f"{COUCHDB_URL}/{DATABASE_NAME}/{doc_id}",
                                auth=HTTPBasicAuth(COUCHDB_USERNAME, COUCHDB_PASSWORD),
                                verify=False)
        response.raise_for_status()
        current_seq = response.json().get('_rev')  # Assuming _rev is used as a version identifier

        if doc_id not in last_sequences or last_sequences[doc_id] != current_seq:
            last_sequences[doc_id] = current_seq
            return True
        return False
    except Exception as e:
        print(f"Error checking document change for {doc_id}: {e}")
        return False

# Monitor CouchDB _changes feed for real-time updates
def monitor_couchdb_changes():
    try:
        last_seq = None
        while True:
            params = {"since": last_seq} if last_seq else {}
            response = requests.get(f"{COUCHDB_URL}/{DATABASE_NAME}/_changes", 
                                    auth=HTTPBasicAuth(COUCHDB_USERNAME, COUCHDB_PASSWORD), 
                                    verify=False, params=params)
            response.raise_for_status()
            changes = response.json()

            # Process each change
            for change in changes.get("results", []):
                doc_id = change.get("id")

                # Check if the document has been deleted
                if change.get("deleted", False):
                    print(f"Document {doc_id} has been deleted. Skipping.")
                    continue  # Skip further processing for deleted documents

                try:
                    # Initialize the employee ID variable
                    employee_id = None

                    # Determine if we need to set doc_id to the corresponding employee_ ID
                    if re.match(additionalinfo_regex, doc_id) or re.match(leave_regex, doc_id):
                        # Extract the numeric part from the original document ID
                        match = re.search(r'_(\d+)$', doc_id)
                        if match:
                            employee_id = f"employee_1_{match.group(1)}"
                            print(f"Transformed document ID to employee ID: {employee_id}")

                    # Use the transformed employee_id if applicable
                    if employee_id:
                        # Attempt to fetch the employee document
                        add_employee_data_to_chroma(employee_id)
                    elif re.match(employee_regex, doc_id):
                        # If the original doc_id is an employee document
                        add_employee_data_to_chroma(doc_id)

                except HTTPException as e:
                    # Log the error without stopping the loop
                    print(f"Error processing document {doc_id}: {e}")

            # Update the last sequence number
            last_seq = changes.get("last_seq")

            # Sleep for a short time before checking for new changes
            time.sleep(5)

    except Exception as e:
        # This outer exception will catch errors in connection or main logic
        print(f"Error monitoring CouchDB changes: {e}")




# Function to delete related embeddings for employee, additional info, and leave documents
# Function to delete related embeddings for employee, additional info, and leave documents
def delete_related_embeddings(employee_id, additional_info_id, leave_id):
    try:
        chroma_db = Chroma(persist_directory=CHROMA_DB_PATH)

        # Collect ids to delete
        ids_to_delete = [employee_id, f"additionalinfo_{additional_info_id}", leave_id]

        # Perform deletion
        chroma_db.delete(ids=ids_to_delete)
        print(f"Old embeddings deleted for {employee_id}, additionalinfo_{additional_info_id}, and {leave_id}")
        
    except Exception as delete_err:
        print(f"Error deleting old embeddings: {delete_err}")


# Load Chroma vector store on app startup
@app.on_event("startup")
def load_chroma_db():
    """ Load Chroma vector store on app startup. """
    try:
        global chroma_db
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
        chroma_db = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embeddings)
        print("Chroma vector store loaded successfully on startup")
    except Exception as e:
        print(f"Error loading Chroma vector store: {e}")
        raise


# Dictionary to store conversation history, key will be user ID/session ID
conversation_history = {}


@app.post("/query")
async def query_chroma(request: QueryRequest):
    """ Query the Chroma database and include metadata in the response. """
    try:
        user_id = "some_user_id"  # Ideally, determined by session or user identifier

        # Initialize conversation history for a new user
        if user_id not in conversation_history:
            conversation_history[user_id] = []

        # Add the user's query to the conversation history
        conversation_history[user_id].append({"role": "user", "message": request.query})

        # Use the pre-loaded Chroma vector store as a retriever
        vector_index = chroma_db.as_retriever(search_kwargs={"k": 1000})

        # Query the vector store with LLM
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY)
        qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=vector_index, return_source_documents=True)

        # Perform the query
        result = qa_chain({"query": request.query})

        # Extract relevant metadata (e.g., `doc_id`) from source documents
        sources = []
        if result["source_documents"]:
            most_relevant_doc = result["source_documents"][0]
            doc_id = most_relevant_doc.metadata.get("doc_id", "Unknown")

            if "employee_" in doc_id:
                related_docs = [
                     doc_id,
                     doc_id.replace("employee_", "additionalinfo_"),
                     doc_id.replace("employee_", "leave_")
                ]
            elif "additionalinfo_" in doc_id:
                related_docs = [
                    doc_id.replace("additionalinfo_", "employee_"),
                    doc_id,
                    doc_id.replace("additionalinfo_", "leave_")
                ]
            elif "leave_" in doc_id:
                related_docs = [
                    doc_id.replace("leave_", "employee_"),
                    doc_id.replace("leave_", "additionalinfo_"),
                    doc_id
                ]
            else:
                related_docs = [doc_id]
            sources = [{"doc_id": related_doc} for related_doc in related_docs]




        # Add the response to the conversation history
        conversation_history[user_id].append({"role": "assistant", "message": result["result"]})

        # Return the query, answer, metadata, and conversation history
        return {
            "query": request.query,
            "answer": result["result"],
            "sources": sources,  # Include metadata like doc_id
            "conversation": conversation_history[user_id]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {e}")




# Endpoint to manually add employee data
@app.post("/add_employee")
async def add_employee(request: AddEmployeeRequest):
    """ Manually add or update an employee document. """
    add_employee_data_to_chroma(request.doc_id)
    return {"status": "Employee data added/updated in Chroma"}

# Start the CouchDB change monitoring in a separate thread
threading.Thread(target=monitor_couchdb_changes, daemon=True).start()

# Run the FastAPI application
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)