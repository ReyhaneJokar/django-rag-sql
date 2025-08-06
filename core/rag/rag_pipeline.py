from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from sqlalchemy import text


def clean_sql_output(sql_text: str) -> str:
    """
    Remove markdown code block markers from the SQL query.
    """
    return sql_text.replace("```sql", "").replace("```", "").strip()


class RAGPipeline:
    def __init__(self, llm, retriever, engine):
        self.llm = llm
        self.retriever = retriever
        self.engine = engine
        
        self.prompt_tmpl = PromptTemplate.from_template(
            """Schema:
                {context}

                Note:
                - Do not reference any non-existent columns.

                Generate a SQL query for the following question:
                {question}

                Only output the SQL."""
        )
        
    def run(self, question: str):
        docs = self.retriever.invoke(question)
        context = "\n".join([d.page_content for d in docs])
        prompt = self.prompt_tmpl.format(
            context=context,
            question=question
        )
        sql = self.llm.generate(prompt)
        sql = clean_sql_output(sql) 

        # run query on database
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = result.fetchall()
        return sql, rows