from collections import defaultdict
from flask import Flask, request, jsonify ,Response, stream_with_context
import os

from phi.document import Document
from phi.document.reader.pdf import PDFReader
from phi.document.reader.website import WebsiteReader
from phi.document.reader.docx import DocxReader 
from phi.utils.log import logger
from typing import List
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path 

from phi.tools.tavily import TavilyTools

from assistant import get_groq_assistant , get_research_assistant 
import shutil
from flask_cors import CORS

app = Flask(__name__)
upload_folder = 'uploads'
os.makedirs(upload_folder, exist_ok=True)
ds=defaultdict(list)  
p_llm_model = "llama3-70b-8192"
p_embeddings_model = "text-embedding-3-large"

CORS(app) 

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:%(message)s'))

app.logger.addHandler(handler)

@app.route('/receive-file', methods=['POST'])
def receive_file():
    # Get Knowledge Base (KB) name from request parameter
    folder_name_param = request.form.get('kb_name')

    # Handle file uploads
    if 'file' in request.files:
        uploaded_files = request.files.getlist('file')
        rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,vector_table=folder_name_param) 
        for uploaded_file in uploaded_files:
            if uploaded_file.filename != '':
                file_path = os.path.join('uploads', uploaded_file.filename)
                uploaded_file.save(file_path)
                process_file(file_path,rag_assistant,folder_name_param,uploaded_file.filename)  # Process the file directly for the knowledge base

            else: logging.error(f"Error in processing file ")

    elif 'url' in request.form:
        url = request.form['url']
        rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,vector_table=folder_name_param) 
        process_url(url, rag_assistant, folder_name_param)
        
    return jsonify({'message': 'Files uploaded successfully', 'kb_name': folder_name_param}),200


def process_file(file_path,rag_assistant, user_id, file_name):
    file_extension = os.path.splitext(file_name)[-1].lower()
    file_processors = {
        '.pdf': process_file_pdf,
        '.docx': process_file_docx
    }
    
    processor = file_processors.get(file_extension)
    if processor:
        processor(file_path,rag_assistant, user_id,file_name)
    else:
        logging.error(f"No handler for file type: {file_extension}")



def process_file_pdf(file_path,rag_assistant,user_id,name):
    

    if rag_assistant :
    
        with open(file_path, 'rb') as file:
                reader = PDFReader(chunk_size=2000)
                rag_documents: List[Document] = reader.read(file_path)
                if rag_documents:
                    rag_assistant.knowledge_base.load_documents(rag_documents, upsert=True)
                    logging.info("PDF processed and loaded into the knowledge base")
                    ds[user_id].append(name)
                else:
                    logging.error("Could not read PDF in process_file")

def process_file_docx(file_path, rag_assistant,user_id,name):
   if rag_assistant :
        with open(file_path, 'rb') as file:
        
        
                reade = DocxReader()
                path_obj = Path(file_path)
                rag_document = reade.read(path_obj)
                if rag_document:
                    rag_assistant.knowledge_base.load_documents(rag_document, upsert=True)
                    logging.info("DOCX file processed and loaded into the knowledge base")
                else:
                    logging.error("Could not read DOCX file")

def process_url(input_url, rag_assistant, user_id):
     if rag_assistant :
        scraper = WebsiteReader(max_links=2, max_depth=1)
        web_documents = scraper.read(input_url)
        if web_documents:
            rag_assistant.knowledge_base.load_documents(web_documents, upsert=True)
            logging.info("URL processed and content loaded into the knowledge base")
        else:
            logging.error("Could not process URL")


@app.route('/listKB', methods=['GET'])
def list_kb():
    if request.is_json:
      data = request.get_json()
      id=data.get('kb_name')
      directory_path = 'uploads'
      files = list_files_in_folder(directory_path)
      if files:
          return jsonify({"kb_list": files, "kb_name":id}),200
      else:
          return jsonify({"kb_list": files, "kb_name":id,'message': 'The Knowledge Base does not exists.'}),200
    else:
         return jsonify({"error": "Missing parameters in request"}), 400
         
  
 
def list_files_in_folder(folder_path):
    file_list = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            print(file)
            file_list.append(file)
    return file_list

@app.route('/chat', methods=['POST'])
def rag_chat():  
    data = None
    user_prompt = None
    id=None

    if request.is_json:
          data = request.get_json()
          user_prompt = data.get('user_prompt')
          id=data.get('kb_name')
    
    def generate_responses():
        rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
        logging.info(f'chat user_id:{rag_assistant.user_id}')
        rag_assistant_run_ids: List[str] = rag_assistant.storage.get_all_run_ids(user_id=id) 
        if not rag_assistant_run_ids:    
          run_id=rag_assistant.create_run()
        else: run_id=rag_assistant_run_ids[0]
        rag_assistant=get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,run_id=run_id,user_id=id)
        # latest_news= TavilyTools().web_search_using_tavily(f'Provide today news on {user_prompt}')
        for delta in rag_assistant.run(user_prompt):
            yield delta

    return Response(stream_with_context(generate_responses()))
      

@app.route('/clear', methods=['POST'])
def clear_db():
    try:
         
        # Extract the 'user_prompt' from the JSON data
        data = request.get_json()
        id=data.get('kb_name')
        directory_path = upload_folder+"/"+id
        rag_assistant = get_groq_assistant(llm_model=p_llm_model, embeddings_model=p_embeddings_model,user_id=id)
        logging.info("Clearing KB : "+id)
        clear_status = rag_assistant.knowledge_base.vector_db.clear()
        if clear_status:
            try:
                shutil.rmtree(directory_path)
                logger.info(f"Directory '{directory_path}' deleted successfully.")
            except OSError as e:
                logger.info(f"Error deleting directory '{directory_path}': {e}")
        
        return jsonify({'message': 'Knowledge Base Cleared successfully.', 'kb_name': id,"kb_path":directory_path}),200
    except:
         return jsonify({'message': 'The Knowledge Base does not exists.', 'kb_name': id,"kb_path":directory_path}),404
         
    #return "Knowledge base cleared"
     

@app.route('/getreport', methods=['POST'])
def research():
    data = request.get_json()
    report_topic = data.get('topic')
    
    if  not report_topic:
        return jsonify({'error': 'Model and topic are required.'}), 400

    research_assistant = get_research_assistant(model="llama3-70b-8192")
    tavily_search_results = TavilyTools().web_search_using_tavily(report_topic)
    
    if not tavily_search_results:
        return jsonify({'error': 'Report generation failed due to no search results.'}), 500

    final_report = ""
    for delta in research_assistant.run(tavily_search_results):
        final_report += delta
    
    return jsonify({'report': final_report}) 


@app.route('/status', methods=['GET'])
def status_check():
    logging.info('Status check called')
    return jsonify({'status': 'API is up'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9000)
