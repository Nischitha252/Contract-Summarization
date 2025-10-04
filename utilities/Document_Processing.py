import os
import base64
import logging
import io
import concurrent.futures
import pandas as pd
from openai import AzureOpenAI
from pdf2image import convert_from_path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dotenv import load_dotenv
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from utilities.prompt_tools.rrprompt import rr_prompt_template

load_dotenv('./.env')

AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_BLOB_STORAGE_CONNECTION_STRING')
AZURE_BLOB_STORAGE_ACCOUNT_NAME=os.environ.get("AZURE_BLOB_STORAGE_ACCOUNT_NAME")
AZURE_BLOB_STORAGE_ACCOUNT_KEY=os.environ.get("AZURE_BLOB_STORAGE_ACCOUNT_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCAI_ENDPOINT = os.environ.get('AZURE_DOCUMENTAI_ENDPOINT')
DOCAI_KEY = os.environ.get('AZURE_DOCUMENTAI_KEY')

class BlobStorageProcessor:
    def __init__(self):
        self.blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

    def upload_blob(self,container_name,blob_name, data):
        container_client = self.blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(data,overwrite=True)
        logger.info(container_name,blob_name,)

    def get_blob_sas_url(self, container_name,blob_name):
        sas_token = generate_blob_sas(
            account_name=AZURE_BLOB_STORAGE_ACCOUNT_NAME,
            container_name=container_name,
            blob_name=blob_name,
            account_key=AZURE_BLOB_STORAGE_ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        return "https://"+AZURE_BLOB_STORAGE_ACCOUNT_NAME+".blob.core.windows.net/"+container_name+"/"+blob_name+"?"+sas_token
    
    def download_blob(self,container_name,blob_name):
        self.container_client = self.blob_service_client.get_container_client(container_name)
        self.blob_client = self.container_client.get_blob_client(blob_name)
        return self.blob_client.download_blob()
    
class DocumentIntelligenceLoader:
    def __init__(self):
        self.document_analysis_client = DocumentAnalysisClient(DOCAI_ENDPOINT, AzureKeyCredential(DOCAI_KEY))

    def analyze_document_pdf(self, blob_sas_url):
        poller = self.document_analysis_client.begin_analyze_document_from_url(model_id="prebuilt-layout",document_url=blob_sas_url)
        result = poller.result()
        return result
    
    def analyze_document_word(self, blob_sas_url):
        poller = self.document_analysis_client.begin_analyze_document_from_url(model_id="prebuilt-read",document_url=blob_sas_url)
        result = poller.result()
        return result
    
class DocumentExtractor:
    def __init__(self, api_key, api_version, azure_endpoint, azure_deployment):
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint,
            azure_deployment=azure_deployment
        )
        self.prompt_template = rr_prompt_template
    
    def local_image_to_data_url(self, image):
        logger.info("Save the Image")
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        base64_encoded_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
        logger.info('inside local_image_to_data_url the image is  ',image)
        return f"data:image/png;base64,{base64_encoded_data}"

    def gpt4o_imagefile(self, image, prompt):
        try:
            logger.info("Reading the image through GPT-4o")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.prompt_template},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": self.local_image_to_data_url(image)},
                            },
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return "skip"

    def process_image(self, image, prompt):
        return self.gpt4o_imagefile(image, prompt)
    
    def process_pdf(self, pdf_path, prompt):
        # poppler_path = r'C:\\Program Files\\poppler-24.02.0\\Library\\bin'  # Correct path with raw string
        images = convert_from_path(pdf_path, 500)
        results = []
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.process_image, image, prompt) for image in images]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                logger.info(f'Processing result: {result[:100]}')  # Log part of the result for debugging
                results.append(result)
        
        return results

    def remove_skip_strings(self, results):
        return [result for result in results if result.lower() != 'skip']
    
    @staticmethod
    def json_list_to_excel(data_list, file_name='output.xlsx'):
        processed_data = []
        
        for entry in data_list:
            section = entry.get('section', '')
            question = entry.get('question', '')
            answer = entry.get('answer', '')
            
            if isinstance(answer, dict):
                customer_answer = answer.get('Customer', '')
                our_bid_answer = answer.get('Our bid', '')
            else:
                customer_answer = answer
                our_bid_answer = ''
            
            score = ''
            
            processed_data.append({
                'section': section,
                'question': question,
                'customer_answer': customer_answer,
                'our_bid_answer': our_bid_answer,
                'score': score,
                'page': entry.get('page', '')  # Ensure 'page' is handled properly
            })
        
        df = pd.DataFrame(processed_data)
        df = df.sort_values(by='page').drop(columns='page')
        
        with pd.ExcelWriter(file_name, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            worksheet = writer.sheets['Sheet1']
            column_widths = [30, 80, 30, 30, 20]
            for i, width in enumerate(column_widths):
                worksheet.set_column(i, i, width)
        return processed_data