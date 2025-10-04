from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
# from langchain_core.chat_history import BaseChatMessageHistory
# from langchain_community.chat_message_histories import ChatMessageHistory
# from langchain.memory import ConversationBufferMemory
# from langchain_core.runnables.history import RunnableWithMessageHistory

from langchain.memory import ConversationBufferMemory
from langchain.chains.conversational_retrieval.base import ConversationalRetrievalChain
import logging
from flask import abort


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

store={}

# def get_session_history(session_id: str) -> BaseChatMessageHistory:
#     if session_id not in store:
#         store[session_id] = ChatMessageHistory()
#     return store[session_id]
def generate_resposne_conversation(llm,retriever_data,query_text,chat_history):
     try:
        contextualize_q_system_prompt = (
         "Given a chat history and the latest user question "
         "which might reference context in the chat history, "
         "formulate a standalone question which can be understood "
         "without the chat history. Do NOT answer the question, "
         "just reformulate it if needed and otherwise return it as is."
      )
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
         [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
         ]
      )
        
        system_prompt = (
         "You are an assistant for question-answering tasks. "
         "Use the following pieces of retrieved context to answer "
         "the question. If you don't know the answer, say that you "
         "don't know. Highlight the keywords and numbers or values with '**'. \n For Example:\n **Daily LD Amount*\n* **Daily Drawing LD Amount**\n"
         "Give the answer in sentences or bullet points instead of a paragraph."
         "Also mention the document name and page number where the information."
         "\n\n"
         "{context}"
         "Answer: ...  \n\n **Source Document: ...** \n  **Page No: ...  **"
      )
        qa_prompt = ChatPromptTemplate.from_messages(
         [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
         ]
      )
      #   memory = ConversationBufferMemory(memory_key="chat_history",output_key="answer", 
      #                           return_messages=True)
      #   retriever=retriever_data
      #   qa = ConversationalRetrievalChain.from_llm(
      #   llm,
      #   retriever=retriever,
      #   memory=memory,return_source_documents=True,
      #   combine_docs_chain_kwargs={"prompt": PROMPT}
      #   )
        logger.info('Generating response...')
        history_aware_retriever=create_history_aware_retriever(llm, retriever_data, contextualize_q_prompt)
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        rag_chain =create_retrieval_chain(history_aware_retriever,question_answer_chain)
        # conversational_rag_chain = RunnableWithMessageHistory(
        #        rag_chain,
        #        get_session_history,
        #        input_messages_key="input",
        #        history_messages_key="chat_history",
        #        output_messages_key="answer",
        #     )
        # response=conversational_rag_chain.invoke({"chat_history": [], "input": query_text, "answer": })
        # logger.info('Response generated successfully.')
        
        response = rag_chain.invoke({"chat_history":chat_history,"input":query_text})['answer']
        chat_history.extend([HumanMessage(content=query_text),AIMessage(content=response),])
      #   print (response['answer'])
      #   response=qa.invoke({"question": query_text})['answer']
      #   print(response['source_documents'])

        return response
     except Exception as e:
        logger.error(f'Error generating response: {str(e)}')
        return abort(500, {'error': f'Error generating response : {str(e)}'})
