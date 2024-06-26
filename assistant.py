from typing import Optional

from phi.assistant import Assistant
from phi.knowledge import AssistantKnowledge
from phi.llm.groq import Groq
from phi.embedder.openai import OpenAIEmbedder
from phi.embedder.ollama import OllamaEmbedder
from phi.vectordb.pgvector import PgVector2
from phi.storage.assistant.postgres import PgAssistantStorage

db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"


def get_groq_assistant(
    llm_model: str = "llama3-70b-8192",
    embeddings_model: str = "text-embedding-3-large",
    user_id: Optional[str] = None,
    vector_table: Optional[str] = None,
    run_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Assistant:
    """Get a Groq RAG Assistant."""

    # Define the embedder based on the embeddings model
    embedder = (
        OllamaEmbedder(model=embeddings_model, dimensions=768)
        if embeddings_model == "nomic-embed-text"
        else OpenAIEmbedder(model=embeddings_model, dimensions=1536)
    )
    # Define the embeddings table based on the embeddings model
    # extra check for collection of tables/embedding models
    groq_rag_documents_openai= "crypto"

    if vector_table is not None:
        if vector_table !='':
            groq_rag_documents_openai = vector_table
    
    
    embeddings_table = (
        "groq_rag_documents_ollama" if embeddings_model == "nomic-embed-text" else groq_rag_documents_openai
    )

    return Assistant(
        name="groq_rag_assistant",
        run_id=run_id,
        user_id=user_id,
        llm=Groq(model=llm_model),
        storage=PgAssistantStorage(table_name="groq_rag_assistant", db_url=db_url),
        knowledge_base=AssistantKnowledge(
            vector_db=PgVector2(
                db_url=db_url,
                collection=embeddings_table,
                embedder=embedder,
            ),
            # 2 references are added to the prompt
            num_documents=2,
            
        ),
description="You are an AI assistant in Crypto and Finance called 'Finance and Crypto'. Your task is to answer questions using the provided information, focusing on clear explanations to crypto users in a professional and subtle manner.",
instructions=[
    "Restrict your answers to questions related to crypto ,blockchain and finance. Do not give advice to buy or sell coins or any other financial assets.",
    "Use the LLM's own knowledge combined with provided knowledge if available.",
    "Ensure answers are simple, coherent, and easy to understand.",
    "Focus on explaining terms and concepts in detail.",
    "Break down complex concepts into logical, sequential steps (chain of thought).",
    "Avoid using phrases like 'based on my knowledge' or 'depending on the information'.",
    "Do not start responses with greetings or repeat the user's question.",
    "Use examples and analogies to make complex concepts relatable.",
    "Maintain a supportive and encouraging tone."
],
        # This setting adds references from the knowledge_base to the user prompt
        add_references_to_prompt=True,
        # This setting tells the LLM to format messages in markdown
        markdown=True,
        # This setting adds chat history to the messages
        add_chat_history_to_messages=True,
        # This setting adds 4 previous messages from chat history to the messages
        num_history_messages=4,
        add_datetime_to_instructions=True,
        debug_mode=debug_mode,
    )

def get_research_assistant(
    model: str = "llama3-70b-8192",
    debug_mode: bool = True,
) -> Assistant:
    """Get a Groq Research Assistant."""

    return Assistant(
        name="groq_research_assistant",
        llm=Groq(model=model),
        description="You are a Senior NYT Editor tasked with writing a NYT cover story worthy report due tomorrow.",
        instructions=[
            "You will be provided with a topic and search results from junior researchers.",
            "Carefully read the results and generate a final - NYT cover story worthy report.",
            "Make your report engaging, informative, and well-structured.",
            "Your report should follow the format provided below."
            "Remember: you are writing for the New York Times, so the quality of the report is important.",
        ],
        add_to_system_prompt=dedent(
            """
        <report_format>
        ## Title

        - **Overview** Brief introduction of the topic.
        - **Importance** Why is this topic significant now?

        ### Section 1
        - **Detail 1**
        - **Detail 2**
        - **Detail 3**

        ### Section 2
        - **Detail 1**
        - **Detail 2**
        - **Detail 3**

        ### Section 3
        - **Detail 1**
        - **Detail 2**
        - **Detail 3**

        ## Conclusion
        - **Summary of report:** Recap of the key findings from the report.
        - **Implications:** What these findings mean for the future.

        ## References
        - [Reference 1](Link to Source)
        - [Reference 2](Link to Source)
        </report_format>
        """
        ),
        # This setting tells the LLM to format messages in markdown
        markdown=True,
        add_datetime_to_instructions=True,
        debug_mode=debug_mode,
    )
