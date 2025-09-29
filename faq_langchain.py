import os
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA

# Lade knowledge.md
with open("docs/knowledge.md", "r", encoding="utf-8") as f:
    faq_content = f.read()

# Splitte FAQ in sinnvolle Chunks
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
faq_chunks = splitter.split_text(faq_content)

# Embeddings erzeugen
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.from_texts(faq_chunks, embeddings)

# Prompt für individuelle, gemischte Antwort
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=(
        "Du bist ein kompetenter Support-Agent. Nutze das folgende FAQ-Wissen, um eine individuelle, situationsbezogene Antwort zu geben. "
        "Kombiniere relevante Informationen aus den FAQs und formuliere eine eigene, hilfreiche Antwort. Antworte immer auf Deutsch.\n"
        "FAQ-Wissen:\n{context}\n\nFrage: {question}\nAntwort:"
    )
)

llm = OpenAI(temperature=0.2, openai_api_key=os.environ.get("OPENAI_API_KEY"))

qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore.as_retriever(),
    return_source_documents=True,
    chain_type_kwargs={"prompt": prompt}
)

def faq_answer(question):
    result = qa({"query": question})
    return result["result"].strip()

# Relevanzprüfung: Nutzt FAISS similarity_search_with_score.
# Hinweis: Bei FAISS in LangChain ist ein KLEINERER Score in der Regel besser (Distanz).
# Der Default-Threshold 0.6 ist konservativ; je kleiner desto strenger.
def faq_is_relevant(question: str, threshold: float = 0.6):
    try:
        docs = vectorstore.similarity_search_with_score(question, k=1)
        if not docs:
            return False, None, None
        doc, score = docs[0]
        is_rel = score is not None and score <= threshold
        return is_rel, doc.page_content if doc else None, score
    except Exception:
        return False, None, None

if __name__ == "__main__":
    frage = input("Deine Frage: ")
    print(faq_answer(frage))
