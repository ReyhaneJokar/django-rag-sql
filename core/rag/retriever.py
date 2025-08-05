from langchain_community.vectorstores import Chroma
from sqlalchemy import inspect
from langchain.schema import Document

# extract tabel's metadata
def build_retriever(engine, embeddings, persist_directory: str = "chromadb"):
    inspector = inspect(engine)  #list of tabels and columns
    docs = []
    for table_name in inspector.get_table_names():
        cols = inspector.get_columns(table_name)
        schema = f"Table: {table_name}\nColumns:\n"
        for col in cols:
            schema += f" - {col['name']} ({col['type']})\n"
        docs.append(Document(page_content=schema, metadata={"table": table_name}))

    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    # print(f"📄 Number of extracted documents: {len(docs)}")
    # for i, doc in enumerate(docs[:5]):
    #     print(f"➡️ Document {i+1}:\n{doc.page_content}")

    return vector_store.as_retriever(search_kwargs={"k": 3})