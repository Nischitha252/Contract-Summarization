import os
from dotenv import load_dotenv
from azure.ai.translation.text import TextTranslationClient
from azure.ai.translation.text.models import InputTextItem
from azure.core.exceptions import HttpResponseError
from azure.core.credentials import AzureKeyCredential
import logging


load_dotenv()

key=os.environ.get("AZURE_TRANSLATOR_KEY")
endpoint=os.environ.get("AZURE_TRANSLATOR_ENDPOINT")
region=os.environ.get("AZURE_TRANSLATOR_REGION")

# credential = TranslatorCredential(key, region)
# text_translator = TextTranslationClient(endpoint=endpoint, credential=credential)

class Translator:
    def __init__(self):
        self.credential = AzureKeyCredential(key)
        self.text_translator = TextTranslationClient(endpoint=endpoint, credential=self.credential,region=region)
        self.logger = logging.getLogger('azure.core.pipeline.policies.http_logging_policy')
        self.logger.setLevel(logging.ERROR)

    def translate(self,input_text,language):
        try:
            source_language = "en"
            target_languages = [language]
            input_text_elements = [ InputTextItem(text = input_text) ]
            self.logger.info("Transalting text to target Language %s",language)
            response = self.text_translator.translate(body = input_text_elements, to_language = target_languages)
            translation = response[0] if response else None
            if translation:
                return translation.translations[0]["text"]
            else:
                return None
        
        except HttpResponseError as exception:
            self.logger.info(f"Error Code: {exception.status_code}")
            self.logger.info(f"Message: {exception.message}")
            return None