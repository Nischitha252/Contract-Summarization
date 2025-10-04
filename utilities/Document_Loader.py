import logging
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
import requests
import subprocess
import docx2txt2
import pandas as pd
from io import BytesIO
import os
from flask import abort
import io
from tempfile import NamedTemporaryFile
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, ContentFormat, AnalyzeResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCAI_ENDPOINT = os.environ.get('AZURE_DOCUMENTAI_ENDPOINT')
DOCAI_KEY = os.environ.get('AZURE_DOCUMENTAI_KEY')

def process_blob(blob,blobstorageprocessor,AZURE_BLOB_STORAGE_CONTAINER_NAME):
    blob_name = blob.name
    blob_url = blobstorageprocessor.get_blob_sas_url(AZURE_BLOB_STORAGE_CONTAINER_NAME, blob_name)
    
    if not any(blob_name.lower().endswith(ext) for ext in [".pdf", ".docx", ".doc", ".xlsx", ".csv",".xls"]):
        logger.warning(f"Unsupported file format: {blob_name}")
        return abort(500, {'error': 'Unsupported File format'})
    
    try:
        if blob_name.endswith((".pdf", ".PDF")):
            logger.info('PDF File is being Processed')
            
            # Download the blob content using requests
            response = requests.get(blob_url)
            response.raise_for_status()  # Ensure we have a valid file
            file_content = response.content
            
            # Create a temporary file with a proper .pdf suffix and a safe name
            with NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
                temp_pdf.write(file_content)
                temp_pdf_path = temp_pdf.name  # This is a safe file path without query params

            try:
                # Use PyPDFLoader with the temporary file path
                pdf_loader = PyPDFLoader(temp_pdf_path)
                pdf = pdf_loader.load()

                # Check if pages are empty (e.g., for scanned PDFs)
                all_pages_empty = all(not doc.page_content.strip() for doc in pdf)
                if all_pages_empty:
                    logger.warning(f"PyPDFLoader returned empty pages for {blob_name}. Using Azure Document Intelligence...")

                    document_intelligence_client = DocumentIntelligenceClient(
                        endpoint=os.environ.get('AZURE_DOCUMENTAI_ENDPOINT'),
                        credential=AzureKeyCredential(os.environ.get('AZURE_DOCUMENTAI_KEY'))
                    )

                    # Analyze the document using Azure Document Intelligence
                    poller = document_intelligence_client.begin_analyze_document(
                        "prebuilt-layout",
                        AnalyzeDocumentRequest(url_source=blob_url)
                    )
                    result = poller.result()

                    # Extract text from the analysis result
                    extracted_text = ""
                    for page in result.pages:
                        for line in page.lines:
                            extracted_text += line.content + "\n"

                    logger.info(f"Processed scanned PDF with Azure Document AI for {blob_name}")
                    return extracted_text

                # Process normally if content exists
                total_pages = len(pdf)
                result = ""
                file_name = os.path.basename(blob_name)
                for page_idx, doc in enumerate(pdf):
                    physical_page_number = page_idx + 1  # Physical page numbering
                    result += (
                        f"[Metadata: [Source file: {file_name}]; [Page No: {physical_page_number}],\n"
                        f"[Content: [{doc.page_content}]]] \n"
                    )
                result = f"The document \"{file_name}\" has {total_pages} pages.\n" + result
                return result

            finally:
                # Always clean up the temporary file
                os.remove(temp_pdf_path)

        

        
        elif blob_name.endswith((".docx")):
            logger.info('DOCX File is being Processed')
            docx_loader = Docx2txtLoader(blob_url)
            docx = docx_loader.load()
            result = ""
            file_name = blob_name.split('/')[-1]
            for doc in docx:
                content_with_metadata = f"[Metadata: [Source file : {file_name}]],\n[content: [{doc.page_content}]]] \n"
                result += content_with_metadata
            return result
        
        elif blob_name.endswith(".doc"):
            # Create a temporary directory
            logger.info('DOC File is being Processed')
            response = requests.get(blob_url)

            # Use io.BytesIO instead of writing to a local file
            doc_content = io.BytesIO(response.content)

            # Create a temporary file for the conversion process
            with NamedTemporaryFile(suffix='.doc', delete=False) as temp_doc:
                temp_doc.write(doc_content.getvalue())
                temp_doc_path = temp_doc.name

            # Convert DOC to DOCX using LibreOffice
            output_dir = os.path.dirname(temp_doc_path)
            subprocess.call(['lowriter', '--headless', '--convert-to', 'docx', '--outdir', output_dir, temp_doc_path])


            # The converted file will have the same name but with .docx extension
            temp_docx_path = temp_doc_path.replace('.doc', '.docx')

            # Read the DOCX file
            doc_text = docx2txt2.extract_text(temp_docx_path)

            # Extract text from the DOCX
            # doc_text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])

            os.remove(temp_doc_path)
            os.remove(temp_docx_path)
            return doc_text
        
        elif blob_name.endswith((".xlsx",".xls")):
            logger.info('Excel File is being Processed')
            response = requests.get(blob_url)
            response.raise_for_status()  # Raise an exception for non-200 status codes

            # Load the Excel content using pandas
            excel_content = BytesIO(response.content)
            excel_df = pd.read_excel(excel_content, sheet_name=None)  # Load all sheets into a dictionary
            file_name = blob_name.split('/')[-1]
            # Combine all sheets into a single string
            all_sheets_content = ""
            for sheet_name, df in excel_df.items():
                all_sheets_content += f"Sheet: {sheet_name}\n"
                all_sheets_content += df.to_csv(index=False)  # Convert the DataFrame to CSV format without the index
            final_excel_output = f"[Metadata: [Source file : {file_name}],\n[content: [{all_sheets_content}]]] \n"
            return final_excel_output
        
        elif blob_name.endswith((".csv")):
            logger.info('CSV File is being Processed')
            response = requests.get(blob_url)
            response.raise_for_status()  # Raise an exception for non-200 status codes

            # Load the CSV content using pandas
            csv_content = BytesIO(response.content)
            csv_df = pd.read_csv(csv_content)
            file_name = blob_name.split('/')[-1]
            # Convert the DataFrame to CSV format without the index
            csv_data = csv_df.to_csv(index=False)
            final_csv_data = f"[Metadata: [Source file : {file_name}],\n[content: [{csv_data}]]] \n"
            return final_csv_data
    
    except Exception as e:
        logger.error(f"Error processing {blob_name}: {str(e)}")
        return None