from .llm_utils import load_llm
from .retriever import build_retriever
from .rag_pipeline import RAGPipeline

class interactive_loop:
    def __init__(self, engine):
        self.engine = engine
        self.llm = load_llm()
        self.embeddings = self.llm
        self.retriever = build_retriever(self.engine, self.embeddings)
        self.pipeline = RAGPipeline(self.llm, self.retriever, self.engine)

    def run(self):
        print("❓Ask question from system or type 'exit' for leave.")
        while True:
            q = input("> ")
            if q.lower() in ('exit', 'quit'):
                print("leaving the program👋")
                break
            try:
                sql, rows = self.pipeline.run(q)
                print(f"🔍 Generated SQL:\n{sql}")
                print("📊 Results:")
                for r in rows:
                    print(r)
            except Exception as e:
                print(f"❌ Error running the question: {e}")