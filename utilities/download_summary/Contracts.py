import os
import pandas as pd 
from flask import jsonify
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import logging
import concurrent.futures

from ..prompt_tools.contract_questions import contract_terms,analytics_ques_list, download_ques_list
from ..prompt_tools.templates import con_template
from ..QuestionAnswerTool import generate_response_excel
from ..Azure_Translator import Translator
import re

load_dotenv('.../.env')
AZURE_DOWNLOAD_STORAGE_CONTAINER_NAME = os.environ.get("AZURE_DOWNLOAD_STORAGE_CONTAINER_NAME")
AZURE_VECTOR_STORAGE_CONTAINER_NAME =os.environ.get('AZURE_VECTOR_STORAGE_CONTAINER_NAME')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
translator = Translator()


# def process_term_query_pair(term, query_actual, query_display, llm, retriever_com, new_prompt_template, language):
#     """Function to process a single term-query pair with detailed and simplified queries."""
#     try:
#         # Generate response using the actual (detailed) query
#         generated_response, _, _ = generate_response_excel(llm, retriever_com, new_prompt_template, query_actual, term)
        
#         # Translate the display query (simplified query) for readability in the output
#         translated_query = translator.translate(query_display, language)
#         translated_generated_response = translator.translate(generated_response, language)
        
#         return term, translated_query, translated_generated_response.strip().lower()
#     except Exception as exc:
#         # Handle errors gracefully
#         return term, query_display, "Error in response generation"   

def process_term_query_pair(term, query, llm, retriever_com, new_prompt_template, language):
    """Function to process a single term-query pair."""
    try:
        generated_response, _, _ = generate_response_excel(llm, retriever_com, new_prompt_template, query, term)
        translated_query = translator.translate(query, language)
        translated_generated_response = translator.translate(generated_response, language)
        return term, translated_query, translated_generated_response.strip().lower()
    except Exception as exc:
        return term, query, "Error in response generation"


# def process_term_query_pair(term, query, llm, retriever_com, new_prompt_template, language):
#     """Function to process a single term-query pair."""
#     try:
#         generated_response, _, _ = generate_response_excel(llm, retriever_com, new_prompt_template, query, term)
#         translated_query = translator.translate(query, language)
#         translated_generated_response = translator.translate(generated_response, language)
#         return term, translated_query, translated_generated_response.strip().lower()
#     except Exception as exc:
#         return term, query, "Error in response generation"




# def contract_answer_question(llm, retriever_com, language):
#     try:
#         # List of predefined contract terms and corresponding prompts        
#         new_prompt_template = PromptTemplate.from_template(con_template)

#         # Ensure lists have the same length
#         if len(contract_terms) != len(analytics_ques_list) or len(analytics_ques_list) != len(analytics_ques_list_actual):
#             logger.error("Length mismatch between contract_terms, analytics_ques_list, and analytics_ques_list_actual.")
#             return jsonify({'success': False, 'message': 'Error: Length mismatch between terms and prompts.'})

#         # Use ThreadPoolExecutor for controlled parallel processing
#         with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#             # Schedule tasks for each term-query pair
#             future_to_pair = {
#                 executor.submit(
#                     process_term_query_pair, term, query_actual, query_display, llm, retriever_com, new_prompt_template, language
#                 ): (term, query_display)
#                 for term, query_actual, query_display in zip(contract_terms, analytics_ques_list_actual, analytics_ques_list)
#             }

#             result_dict = {"Contract Terms": [], "Query": [], "AI Response": []}
#             for future in concurrent.futures.as_completed(future_to_pair):
#                 try:
#                     term, query_display = future_to_pair[future]
#                     response = future.result()
#                     _, _, ai_generated_response = response

#                     result_dict['Contract Terms'].append(term)
#                     result_dict['Query'].append(query_display.replace("Do not include introductory statements highlight the key points.", "").strip())
#                     result_dict['AI Response'].append(ai_generated_response)
#                 except Exception as e:
#                     logger.error(f"Error processing term-query pair: {e}")


#         # Create a DataFrame from the result dictionary
#         df = pd.DataFrame(result_dict)
#         df.index = df.index + 1
#         df = df.reset_index()
#         df.rename(columns={"index": "Serial No"}, inplace=True)

#         return df if not df.empty else jsonify({'success': False, 'message': 'Error generating data: Result dictionary is empty.'})

#     except Exception as e:
#         logger.error(f"Error occurred: {e}")
#         return jsonify({'success': False, 'message': f'Error occurred: {str(e)}'})
    

def contract_answer_question(llm, retriever_com, language):
    try:
        # List of predefined contract terms and corresponding prompts        

        # Retrieve the necessary data from the app context
        new_prompt_template = PromptTemplate.from_template(con_template)

        # Use ThreadPoolExecutor for controlled parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Schedule tasks for each term-query pair
            future_to_pair = {
                executor.submit(process_term_query_pair, term, query, llm, retriever_com, new_prompt_template, language): (term, query)
                for term, query in zip(contract_terms, analytics_ques_list)
            }

            result_dict = {"Contract Terms": [], "Query": [], "AI Response": []}
            for future in concurrent.futures.as_completed(future_to_pair):
                try:
                    term, query, response = future.result()
                    # formatted_response = bold_keywords(response, query)
                    phrases_to_remove=[
                        "Do not include introductory statements highlight the key points.",
                        "Include specific details with exact page numbers.If references span multiple sections, consolidate the information.Do not include introductory statements highlight the key points.",
                        "If the prerequisites or related procedures reference other clauses, sections, or paragraphs explicitly mention these references and consolidate the details into a clear and comprehensive summary.Do not include introductory statements highlight the key points.",
                        "If the retention-related conditions or procedures reference other clauses, sections, or paragraphs, explicitly mention these references and consolidate the details into a clear and comprehensive summary.Do not include introductory statements highlight the key points.",
                        "If the provisions reference other clauses, sections, or paragraphs elsewhere in the document (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a cohesive summary.Do not include introductory statements highlight the key points",
                        "Extract the details of the governing law explicitly mentioned in the document, including the country or jurisdiction.",
                        "Include specific details with exact page numbers and clause/section/paragraph IDs. If references span multiple sections, consolidate the information.",
                        "Provide exact page numbers and clause/section/paragraph IDs in your response. If the prerequisites or related procedures reference other clauses, sections, or paragraphs (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a clear and comprehensive summary.",
                        "Provide exact page numbers and clause/section/paragraph IDs in your response. If the retention-related conditions or procedures reference other clauses, sections, or paragraphs (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a clear and comprehensive summary.",
                        "Include exact page numbers and clause/section/paragraph IDs in your response. If the provisions reference other clauses, sections, or paragraphs elsewhere in the document (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a cohesive summary. Do not include introductory statements highlight the key points",
                        "Extract the details of the governing law explicitly mentioned in the document, including the country or jurisdiction. If referenced in other clauses, annexures, or paragraphs, include those cross-references with exact page numbers and clause/section/paragraph IDs. Present the information concisely, highlighting only key points. If the governing law details span multiple sections, consolidate all relevant information.",
                        "Summarize the requirements, deadlines, and procedures for any performance security (e.g., letter of credit, parent company guarantee, bond, or other guarantees) that ABB must provide under the contract.Include specific details with exact page numbers and clause/section/paragraph IDs. If references span multiple sections, consolidate the information.Do not include introductory statements highlight the key points.",
                        "Include conditions, reasons, and procedures specified for the contractor's right to terminate, along with exact page numbers and clause/section/paragraph IDs.If the provisions refer to other clauses, sections, or paragraphs elsewhere in the document (e.g., annexures or cross-references), explicitly mention these references in the response.Consolidate details from multiple sections into a cohesive summary.Do not include introductory statements highlight the key points.",
                        "Summarize:*Specific prerequisites or conditions that must be fulfilled before work commencement, including details of any Notice to Proceed or Purchase Order requirements.* Timeframes or deadlines for fulfilling these prerequisites. Provide exact page numbers and clause/section/paragraph IDs in your response. If the prerequisites or related procedures reference other clauses, sections, or paragraphs (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a clear and comprehensive summary.Do not include introductory statements highlight the key points.",
                        "Summarize:*The specific conditions under which retention money can be withheld from payments due to the contractor.*The procedures and conditions for the release of the retention money, including timelines or milestones specifying when the retention money, or part thereof, must be paid back to the contractor. Provide exact page numbers and clause/section/paragraph IDs in your response. If the retention-related conditions or procedures reference other clauses, sections, or paragraphs (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a clear and comprehensive summary.Do not include introductory statements highlight the key points.",
                        "Include exact page numbers and clause/section/paragraph IDs in your response. If the provisions reference other clauses, sections, or paragraphs elsewhere in the document (e.g., annexures or cross-references), explicitly mention these references and consolidate the details into a cohesive summary.Do not include introductory statements highlight the key points",
                        "Include specific details with exact page numbers and clause/section/paragraph IDs. If references span multiple sections, consolidate the information.Do not include introductory statements highlight the key points."]
                    

                    result_dict['Contract Terms'].append(term)
                    for phrase in phrases_to_remove:
                          query = query.replace(phrase, "").strip()
                    result_dict['Query'].append(query)
                    #result_dict['Query'].append(query.replace("Do not include introductory statements highlight the key points.", "").strip())
                    result_dict['AI Response'].append(response)
                except Exception as e:
                    logger.error(f"Error processing term-query pair: {e}")


        # Create a DataFrame from the result dictionary
        df = pd.DataFrame(result_dict)
        df.index = df.index + 1
        df = df.reset_index()
        df.rename(columns={"index": "Serial No"}, inplace=True)

        return df if not df.empty else jsonify({'success': False, 'message': 'Error generating data: Result dictionary is empty.'})

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return jsonify({'success': False, 'message': f'Error occurred: {str(e)}'})

