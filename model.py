import os
from dotenv import load_dotenv
load_dotenv()

from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langchain.memory import ConversationTokenBufferMemory
from langchain_core.prompts import MessagesPlaceholder
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.vectorstores import Milvus
from milvus import default_server as milvus_server

openai_key=os.getenv('OPENAI_KEY')
gemini_key=os.getenv('GEMINII_KEY')
model = "gemini-1.5-pro"
# model = "gpt-3.5-turbo"

class RAG():
        def __init__(self,
                     docs_dir: str,
                     n_retrievals: int = 4,
                     chat_max_tokens: int = 3097,
                     model_name = model):
                
                self.__model = self.__set_llm_model(model_name)
                self.__docs_list = self.__get_docs_list(docs_dir)
                self.__retriever = self.__set_retriever(k=n_retrievals)
                self.__chat_history = self.__set_chat_history(max_token_limit=chat_max_tokens)

        # define o LLM (gpt-3.5-turbo || gemini-1.5-pro)
        def __set_llm_model(self, model_name = model):
                if "gpt" in model_name:
                        temperature: float = 0.7
                        return ChatOpenAI(model_name=model_name, temperature=temperature, api_key=openai_key)
                temperature: float = 0
                return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, api_key=gemini_key)

        # carrega os documentos
        # para ler arquivos de outros tipos, deve-se utilizar
        # loaders específicos. Ex.: PDFLoader, DocxLoader
        def __get_docs_list(self, docs_dir: str) -> list:
                print("Carregando documentos...")
                loader = DirectoryLoader(docs_dir,
                                        recursive=True,
                                        show_progress=True,
                                        use_multithreading=True,
                                        max_concurrency=4)
                docs_list = loader.load_and_split()
        
                return docs_list

        # retorna os documentos
        def __set_retriever(self, k: int = 4, llm: str = "gem"):
                # Milvus Vector Store
                embeddings = OpenAIEmbeddings() if llm == "gpt" else GoogleGenerativeAIEmbeddings(model="models/embedding-001")
                milvus_server.start()
                vector_store = Milvus.from_documents(
                        self.__docs_list,
                        embedding=embeddings,
                        connection_args={"host": os.getenv("MILVUS_HOST"), "port": os.getenv("MILVUS_PORT")},
                        collection_name="personal_documents",
                )

                # Self-Querying Retriever
                metadata_field_info = [
                        AttributeInfo(
                        name="source",
                        description="O caminho de diretórios onde se encontra o documento",
                        type="string",
                        ),
                ]

                document_content_description = "Documentos pessoais"

                _retriever = SelfQueryRetriever.from_llm(
                        self.__model,
                        vector_store,
                        document_content_description,
                        metadata_field_info,
                        search_kwargs={"k": k}
                )

                return _retriever

        # mantém contexto do chat (562 limite da api do Gemini)
        def __set_chat_history(self, max_token_limit: int = 562):
                return ConversationTokenBufferMemory(llm=self.__model, max_token_limit=max_token_limit, return_messages=True)

        # recebe prompt e retorna resposta
        def ask(self, question: str) -> str:
                prompt = ChatPromptTemplate.from_messages([
                        ("system", "Você é um assistente responsável por responder perguntas sobre documentos. Responda a pergunta do usuário com um nível de detalhes razoável e baseando-se no(s) seguinte(s) documento(s) de contexto:\n\n{context}"),
                        MessagesPlaceholder(variable_name="chat_history"),
                        ("user", "{input}"),
                ])

                output_parser = StrOutputParser()
                chain = prompt | self.__model | output_parser
                answer = chain.invoke({
                        "input": question,
                        "chat_history": self.__chat_history.load_memory_variables({})['history'],
                        "context": self.__retriever.invoke(question)
                })

                # Atualização do histórico de conversa
                self.__chat_history.save_context({"input": question}, {"output": answer})

                return answer