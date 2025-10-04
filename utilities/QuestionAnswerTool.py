from langchain.chains import RetrievalQA
from langchain.globals import set_llm_cache
import logging
from flask import abort

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# set_llm_cache(InMemoryCache())
def generate_response(llm, retriever_data, prompt_template, query_text):
    try:
        logger.info('Generating response...')
        qa_interface2 = RetrievalQA.from_chain_type(llm=llm,
                                                    retriever=retriever_data,
                                                    chain_type_kwargs={"prompt": prompt_template},
                                                    return_source_documents=True)
        result = qa_interface2(query_text)['result']
        logger.info('Response generated successfully.')
        return result
    except Exception as e:
        logger.error(f'Error generating response: {str(e)}')
        return abort(500, {'error': f'Error generating response : {str(e)}'})


def generate_response_excel(llm, retriever_data, prompt_template, query_text,topic):
    try:
        logger.info('Generating response...')
 
        qa_interface2 = RetrievalQA.from_chain_type(llm=llm,
                                                    retriever=retriever_data,
                                                    chain_type_kwargs={"prompt": prompt_template},
                                                    return_source_documents=True)
        result = qa_interface2(query_text)['result']
        logger.info('Response generated successfully.')
        return result,query_text,topic
    except Exception as e:
        logger.error(f'Error generating response: {str(e)}')
        return abort(500, {'error': f'Error generating response : {str(e)}'})


def generate_response_tech(llm, retriever_data, prompt_template, query_text,system):
    try:
        logger.info('Generating response...')

        qa_interface2 = RetrievalQA.from_chain_type(llm=llm,
                                                    retriever=retriever_data,
                                                    chain_type_kwargs={"prompt": prompt_template},
                                                    return_source_documents=True)
        result = qa_interface2(query_text)['result']
        logger.info('Response generated successfully.')
        return system,result
    except Exception as e:
        logger.error(f'Error generating response: {str(e)}')
        return abort(500, {'error': f'Error generating response : {str(e)}'})
