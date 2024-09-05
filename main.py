import os
from model import RAG

docs_dir = os.getenv('DOCS_DIR')

rag = RAG(
    docs_dir=docs_dir,
    n_retrievals=1, # Número de documentos retornados pela busca (int)  :   default=4
    chat_max_tokens=3097 # Número máximo de tokens que podem ser usados na memória do chat (int)  :   default=3097
)

print("Digite 'sair' para fechar o chat")
while True:
    question = str(input("Prompt: "))
    if question == "sair":
        break
    answer = rag.ask(question)
    print("Resposta:", answer)