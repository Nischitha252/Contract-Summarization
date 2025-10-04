from flask import Flask, render_template, request, jsonify,abort,session,send_from_directory
import os
from datetime import datetime,timedelta  
from flask_cors import CORS
import pandas as pd
import json
import uuid
import pickle
import logging
from dotenv import load_dotenv
import glob
import docx2txt
import subprocess
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
from io import BytesIO
import io

from langchain_openai import AzureChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, Docx2txtLoader, UnstructuredExcelLoader
import openai

from utilities.Document_Processing import BlobStorageProcessor,DocumentIntelligenceLoader,DocumentExtractor
from utilities.ConversationalQA import generate_resposne_conversation
from utilities.QuestionAnswerTool import generate_response
from utilities.Document_Loader import process_blob
from utilities.download_summary.Contracts import contract_answer_question
from utilities.Excel_Formatting import create_excel_with_formatting_local
from utilities.Azure_Translator import Translator

blobstorageprocessor=BlobStorageProcessor()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

app = Flask(__name__,static_folder='./frontend/build')
CORS(app)

epoch =1
i_loop = 0
blob_list=[]
text=''
guid4=uuid.uuid4()


openai.api_type =os.environ.get("AZURE_OPENAI_TYPE")
openai.api_base =os.environ.get('AZURE_OPENAI_ENDPOINT')  
openai.api_key = os.environ.get('AZURE_OPENAI_API_KEY')
openai.api_version = os.environ.get('AZURE_OPENAI_API_VERSION')

embedding_key=os.environ.get('AZURE_EMBEDDING_API_KEY')
Embedding_endpoint=os.environ.get('AZURE_EMBEDDING_OPENAI_ENDPOINT_')
emedding_api_version=os.environ.get('AZURE_OPENAI_API_VERSION_MGMT')

LLM_MODEL=os.environ.get('AZURE_OPENAI_GPT4_DEPLOYMENT_NAME')
EMBEDDINGS_MODEL=os.environ.get('AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT_NAME')

 
AZURE_BLOB_STORAGE_CONTAINER_NAME = os.environ.get('AZURE_BLOB_STORAGE_CONTAINER_NAME')
AZURE_DOWNLOAD_STORAGE_CONTAINER_NAME = os.environ.get("AZURE_DOWNLOAD_STORAGE_CONTAINER_NAME")
AZURE_VECTOR_STORAGE_CONTAINER_NAME =os.environ.get('AZURE_VECTOR_STORAGE_CONTAINER_NAME')
AZURE_BLOB_STORAGE_RR_CONTAINER_NAME=os.environ.get("AZURE_BLOB_STORAGE_RR_CONTAINER_NAME")

# def generate_embedding(split):
#     return embeddings.embed_documents([split])[0]

def generate_embedding(split):
    try:
        embedding = embeddings.embed_documents([split])[0]
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding for split: '{split[:50]}...' - Exception: {e}")
        return None

llm = AzureChatOpenAI(deployment_name=LLM_MODEL, openai_api_key=openai.api_key, openai_api_version=openai.api_version, azure_endpoint=openai.api_base,temperature=0.1)
embeddings = AzureOpenAIEmbeddings(azure_endpoint=Embedding_endpoint,api_key=embedding_key,
            azure_deployment=EMBEDDINGS_MODEL,
            openai_api_version=emedding_api_version
            )

# Save variables to app context
app.config['llm'] = llm
app.config['epoch'] = 1



# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:

        files = request.files.getlist('files')
        print('file')
        # container_name=request.form['container_name']
        if not files:
            logger.error('No files selected.')
            return jsonify({'error': 'No files selected'}),500

        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        folder_name = f"rfq_{timestamp}_{str(uuid.uuid4())}"
        for file in files: 
            blob_name = f"{folder_name}/{file.filename}"
            blob_list.append(blob_name)
            logger.info(f'Blob Name {blob_name}')
            logger.info(blob_list)
            print('this is the blob name')
            blobstorageprocessor.upload_blob( AZURE_BLOB_STORAGE_CONTAINER_NAME, blob_name, file)
            logger.info(f'File "{file.filename}" uploaded successfully.')

        # Assuming the same folder_name for all files, you can return it in the response
        return jsonify({'success': 'Files Uploaded Successfully', 'blob_name': folder_name})
    except Exception as e:
        logger.error(f'Error in upload route: {str(e)}')
        abort(500, str(e))


@app.route('/processfile', methods=['GET', 'POST'])
def process():
    retry_count = 0
    max_retries = 10  # Maximum number of retries allowed for embedding generation

    while retry_count < max_retries:
        try:
            logger.info('Processing files...')
            chat_history = []
            folder_name = request.json.get('blobName')
            container_client_folder = blobstorageprocessor.blob_service_client.get_container_client(AZURE_BLOB_STORAGE_CONTAINER_NAME)
            blob_list = container_client_folder.list_blobs(folder_name)

            # Check if blob_list is empty
            blob_list = list(blob_list)
            if not blob_list:
                logger.error("No blobs found in the specified folder.")
                return {'error': 'No blobs found'}, 400

            app.config['keywords'] = False
            app.config['Keyword_content'] = ""
            logger.info(f"Blob List: {blob_list}")

            def document_process_blob(blob):
                # Extract text from the blob using your existing helper
                return process_blob(blob, blobstorageprocessor, AZURE_BLOB_STORAGE_CONTAINER_NAME)

            # Process each blob concurrently and collect texts with file metadata
            all_texts = []
            with ThreadPoolExecutor() as executor:
                future_to_blob = {executor.submit(document_process_blob, blob): blob for blob in blob_list}
                for future in as_completed(future_to_blob):
                    blob = future_to_blob[future]
                    result = future.result()
                    if result:
                        # Prepend file metadata to the extracted text.
                        # You can later parse this metadata if needed.
                        file_text = f"[DOC_NAME: {blob.name}] {result}"
                        all_texts.append(file_text)
            
            if not all_texts:
                logger.error("No text extracted from any blobs.")
                return {'error': 'No text extracted from any blobs'}, 400

            # Initialize the text splitter
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=500)
            
            # Split texts into chunks for each file and preserve metadata.
            all_chunks = []
            for file_text in all_texts:
                splits = text_splitter.split_text(file_text)
                for i, chunk in enumerate(splits):
                    # Optionally, add additional metadata such as chunk index if needed.
                    # In this example, the file metadata is already in the chunk.
                    all_chunks.append(chunk)
            logger.info('Chunking completed successfully.')

            # Generate embeddings for all chunks concurrently.
            text_embedding_pairs = []
            with ThreadPoolExecutor() as executor:
                future_to_chunk = {executor.submit(generate_embedding, chunk): chunk for chunk in all_chunks}
                for future in as_completed(future_to_chunk):
                    chunk = future_to_chunk[future]
                    try:
                        embedding = future.result()
                        if embedding is not None:
                            text_embedding_pairs.append((chunk, embedding))
                        else:
                            logger.warning(f"Embedding generation returned None for chunk: {chunk[:50]}...")
                    except Exception as exc:
                        logger.error(f'Embedding generation failed for chunk: {chunk}, with exception: {exc}')

            # Check if embeddings were generated successfully
            if not text_embedding_pairs:
                logger.warning("No embeddings were generated; retrying the embedding process.")
                retry_count += 1
                if retry_count >= max_retries:
                    return {'error': f'Failed after {max_retries} attempts to generate embeddings.'}, 500
                continue  # Retry the loop

            # Create a combined FAISS vector store for all chunks.
            vectorstore = FAISS.from_embeddings(text_embedding_pairs, embeddings)
            logger.info('Vector Store has been created successfully.')
            timestamp = datetime.now().strftime("%Y%m%d%H%M")
            vector_store_name = f"rfq_vectorstore_{timestamp}_{str(uuid.uuid4())}"
            vectorstore_bytes = vectorstore.serialize_to_bytes()
            blobstorageprocessor.upload_blob(AZURE_VECTOR_STORAGE_CONTAINER_NAME, vector_store_name, vectorstore_bytes)
            logger.info('Processing completed successfully. Vector Store Name: %s', vector_store_name)

            return {'success': True,
                    'message': 'File processed successfully',
                    'vector_store_names': vector_store_name,
                    'chat_history': chat_history}

        except Exception as e:
            logger.error(f'Error processing file: {str(e)}')
            return {'error': f'Error processing file: {str(e)}'}, 500

@app.route('/process_input', methods=['POST'])
def process_input():
    try:
        logger.info('Processing user input...')
        vector_blob_name = request.json.get('vector_store_name')
        keywords=request.json.get("keyword")
        lang_selected=request.json.get('language')
        chat_history=request.json.get('chat_history')
        vector_download = blobstorageprocessor.download_blob(AZURE_VECTOR_STORAGE_CONTAINER_NAME, vector_blob_name)
        stream = vector_download.readall()
        retriever_store = FAISS.deserialize_from_bytes(embeddings=embeddings,serialized=stream)
        retriever = retriever_store.as_retriever(search_type="similarity", search_kwargs={"k": 5})
        logger.info("Retrieval is done successfully")
        # prompt_template = PromptTemplate(input_variables=['history','question'],template=data['ConversationalChat']['template'])
        user_input = request.json['user_input']
        logger.info("user_input " + user_input)
        prompt_template=''
        if keywords:
            # keyword_content = session.get("keywords")
            prompt_template = PromptTemplate.from_template(data['Chat']['template1'], partial_variables={'keywords': keywords})
        
        logger.info("prompttemplate" + str(prompt_template))

        generated_response = generate_resposne_conversation(llm, retriever, user_input,chat_history)
        # translated_generated_response=translator.translate(generated_response, lang_selected)
        logger.info(f'Response generated successfully: {generated_response}')
        return jsonify({'success': True, 'generated_response': generated_response})
    except Exception as e:
        logger.error(f'Error processing input: {str(e)}')
        return jsonify({'success': False, 'message': f'Error processing input: {str(e)}'}),500
    


@app.route('/contractExcel', methods=['GET','POST'])
def download_contract():
    # Retrieve the necessary data from the app context
    try:
        llm = app.config['llm']
        vector_blob_name = request.json.get('vectorStoreName') # Get vector store name from the request payload
        # lang_selected=request.json.get('language')
        lang_selected=request.json.get('language') 
        vector_download = blobstorageprocessor.download_blob(AZURE_VECTOR_STORAGE_CONTAINER_NAME,vector_blob_name)
        stream=vector_download.readall()
        retriever_store = FAISS.deserialize_from_bytes(embeddings=embeddings,serialized=stream)
        retriever_com = retriever_store.as_retriever(search_type="similarity", search_kwargs={"k": 10})
        result_df=contract_answer_question(llm,retriever_com,lang_selected)
        logger.info('printing variables',retriever_com,lang_selected)
        output=create_excel_with_formatting_local(result_df,lang_selected, sheet_name='Output')
        unique_id = str(uuid.uuid4())[:8]
        blob_name=f"Contact_Summary_{unique_id}.xlsx"
        blobstorageprocessor.upload_blob( AZURE_DOWNLOAD_STORAGE_CONTAINER_NAME, blob_name, output)

        return jsonify({'success': True, 'message': 'File generated and stored in Azure Blob Storage successfully', 'blob_name':blob_name})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error generating or storing Excel file: {str(e)}'}),500


if __name__ == '__main__':
    app.run()