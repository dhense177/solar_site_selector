from typing import Annotated, Optional, List, Dict, Any, TypedDict
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, text, inspect
from prompts.text_to_sql_prompts import write_sql_template
import os
import dotenv
import re
from db_actions.db_utils import run_query
dotenv.load_dotenv()

# --- CONFIG ---
user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]
engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}")

llm = ChatOpenAI(model="gpt-4.1", temperature=0.2)

# --- STATE ---
class SQLState(TypedDict):
    """Shared memory and conversation state for multi-turn Text-to-SQL."""

    # Latest user input
    user_query: str
    expanded_query: Optional[str]
    sql_query: Optional[str]

    # Results
    results: Optional[Any]

    # Error tracking
    error: Optional[str]
    last_failed_sql: Optional[str]
    attempt: int  # Track number of repair attempts

    # Persistent multi-turn memory
    conversation: Annotated[List[Dict[str, str]], add_messages]

# --- FUNCTIONS ---
def get_all_tables_schema(_):
    """Get schema information for all tables in all schemas"""
    inspector = inspect(engine)
    # schemas = inspector.get_schema_names()
    schemas = ['parcels', 'geographic_features', 'infrastructure_features']
    
    all_tables_info = []
    
    for schema in schemas:
        tables = inspector.get_table_names(schema=schema)
        for table in tables:
            columns = inspector.get_columns(table, schema=schema)
            column_info = []
            for col in columns:
                col_str = f"  - {col['name']}: {col['type']}, comments: {col['comment']}"
                if col.get('nullable') is False:
                    col_str += " (NOT NULL)"
                column_info.append(col_str)
            
            table_info = f"Table: {schema}.{table}\nColumns:\n" + "\n".join(column_info)
            all_tables_info.append(table_info)
    
    return "\n\n".join(all_tables_info)

SCHEMA_TEXT = get_all_tables_schema("")

# --- HELPER FUNCTIONS ---
def clean_sql(sql: str) -> str:
    """Remove markdown code blocks and extract SQL from LLM response."""
    if not sql:
        return ""
    
    # Remove markdown code blocks
    sql = re.sub(r'```sql\n?', '', sql)
    sql = re.sub(r'```\n?', '', sql)
    sql = sql.strip()
    
    # Extract SQL if prefixed with "SQL:"
    if "SQL:" in sql or "sql:" in sql:
        parts = re.split(r'(?i)SQL:\s*', sql, maxsplit=1)
        if len(parts) > 1:
            sql = parts[1]
            # Remove explanation if present
            if "Explanation:" in sql or "explanation:" in sql:
                sql = re.split(r'(?i)Explanation:\s*', sql, maxsplit=1)[0]
    
    return sql.strip()


# def ensure_geometry_as_geojson(sql: str) -> str:
#     """Convert raw geometry to GeoJSON format."""
#     if not sql or 'ST_AsGeoJSON' in sql:
#         return sql
    
#     # Find table alias (default to pd)
#     alias_match = re.search(r'FROM\s+parcels\.parcel_details\s+(?:AS\s+)?(\w+)', sql, re.IGNORECASE)
#     alias = alias_match.group(1) if alias_match else 'pd'
#     geometry_col = f"{alias}.geometry"
    
#     # Replace raw geometry with GeoJSON
#     sql = re.sub(
#         rf'\b{re.escape(geometry_col)}\b',
#         f'ST_AsGeoJSON({geometry_col})::json as geometry',
#         sql,
#         flags=re.IGNORECASE
#     )
    
#     return sql

# --- NODES ---

def contextual_query_understanding(state: SQLState):
    """Rewrite user's query in context using conversation memory."""
    conversation = state.get("conversation", [])
    user_query = state.get("user_query", "")
    
    prompt = f"""
    You are a helpful assistant that interprets user questions about a parcel database.
    Use the prior conversation to make the current query self-contained.

    Conversation so far:
    {conversation}

    Latest query:
    {user_query}

    Rewrite the latest query so it can be executed independently.
    Return only the rewritten text.
    """
    rewritten = llm.invoke(prompt).content.strip()
    return {
        "expanded_query": rewritten,
        "conversation": [
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": rewritten},
        ],
    }


def generate_sql(state: SQLState):
    """Generate SQL from the natural language query."""
    expanded_query = state.get("expanded_query", "")
    
    prompt = ChatPromptTemplate.from_messages(
        [
            # "**CRITICAL**: ALWAYS include the 'ST_AsGeoJSON(geometry)::json as geometry' field from parcel_details database table in your SELECT clause."
            ("system", "You are a SQL expert with specialized knowledge in mapping natural language queries to database schema values."
            
            "Provide both the SQL query and a clear explanation of your reasoning."),
            ("human", write_sql_template),
        ]
    )
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"tables": SCHEMA_TEXT, "user_query": expanded_query})
    
    sql = clean_sql(response)
    # sql = ensure_geometry_as_geojson(sql)
    return {"sql_query": sql}


# def execute_sql(state: SQLState):
#     """Run SQL and capture success or failure."""
#     sql_query = state.get("sql_query", "")
#     try:
#         with engine.connect() as conn:
#             result = conn.execute(text(sql_query))
#             rows = result.fetchall()
#         return {"results": [dict(r._mapping) for r in rows], "error": None}
#     except Exception as e:
#         return {"error": str(e), "last_failed_sql": sql_query}
def execute_sql(state: SQLState):
    con = engine.connect()
    rows, error = run_query(state["sql_query"], con)
    con.close()
    
    # Convert RowMapping objects to plain dictionaries for serialization
    # This is necessary because the checkpointer needs to serialize the state
    # RowMapping objects from SQLAlchemy are not JSON/msgpack serializable
    if rows:
        serializable_rows = [dict(row) for row in rows]
        rows = serializable_rows
    
    return {"results": rows, "error": error}

def validate_sql(state: SQLState):
    """
    Validate SQL before accepting results:
    - Check syntax via EXPLAIN
    - Check non-empty results
    - Use LLM to confirm the results make sense
    """
    sql_query = state.get("sql_query", "")
    results = state.get("results")

    # 1️⃣ Check SQL syntax using EXPLAIN
    # try:
    #     with engine.connect() as conn:
    #         conn.execute(text(f"EXPLAIN {sql_query}"))
    # except Exception as e:
    #     return {"error": f"SQL syntax error: {e}", "last_failed_sql": sql_query}

    # 2️⃣ Check for empty results
    if not results or len(results) == 0:
        return {
            "error": "Query executed successfully but returned 0 results.",
            "last_failed_sql": sql_query,
        }

    # # 3️⃣ Validate alignment with user intent
    # # Use the first few rows to check correctness
    # preview = state.results[:3]
    # validation_prompt = f"""
    # The following SQL query was used to answer the user's request:

    # User request:
    # {state.user_query}

    # SQL:
    # {state.sql_query}

    # First few results:
    # {preview}

    # Determine whether the results seem relevant to the user's intent.
    # Reply with "VALID" if they match, or "INVALID" if they do not.
    # """

    # verdict = llm.invoke(validation_prompt).content.strip().upper()
    # if "INVALID" in verdict:
    #     return {"error": "Results appear misaligned with user intent.", "last_failed_sql": state.sql_query}

    # ✅ All good
    return {"error": None}


def repair_sql(state: SQLState):
    """If SQL failed or failed validation, ask the LLM to fix it."""
    error = state.get("error")
    if not error:
        return state

    last_failed_sql = state.get("last_failed_sql", "")
    attempt = state.get("attempt", 0)
    
    prompt = f"""
    The following SQL query failed validation.

    SQL:
    {last_failed_sql}

    Error or problem:
    {error}

    Please correct the SQL and return only the fixed statement.
    """
    response = llm.invoke(prompt).content.strip()
    fixed = clean_sql(response)
    # fixed = ensure_geometry_as_geojson(fixed)
    
    return {"sql_query": fixed, "error": None, "attempt": attempt + 1}


def display_results(state: SQLState):
    """Final display node."""
    error = state.get("error")
    results = state.get("results")
    
    if error:
        print("❌ Query failed:", error)
    elif results:
        print(f"✅ Returned {len(results)} results")
    else:
        print("No results found.")
    return state


# --- GRAPH CONSTRUCTION ---
graph = StateGraph(SQLState)

graph.add_node("contextual_query_understanding", contextual_query_understanding)
graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_sql", execute_sql)
graph.add_node("validate_sql", validate_sql)
graph.add_node("repair_sql", repair_sql)
graph.add_node("display_results", display_results)

graph.set_entry_point("contextual_query_understanding")

graph.add_edge("contextual_query_understanding", "generate_sql")
graph.add_edge("generate_sql", "execute_sql")
graph.add_edge("execute_sql", "validate_sql")

# Conditional routing: if validation fails → repair_sql (with attempt limit)
MAX_REPAIR_ATTEMPTS = 3

def route_after_validate(state: SQLState):
    """Route after validation: repair if error and under attempt limit, otherwise display results"""
    error = state.get("error")
    attempt = state.get("attempt", 0)
    
    if error and attempt < MAX_REPAIR_ATTEMPTS:
        return "repair_sql"
    else:
        return "display_results"

graph.add_conditional_edges(
    "validate_sql",
    route_after_validate,
    {
        "repair_sql": "repair_sql",
        "display_results": "display_results"
    }
)

graph.add_edge("repair_sql", "execute_sql")
graph.add_edge("display_results", END)

# Compile with MemorySaver for checkpointing (required for api_server.py)
memory = MemorySaver()
app = graph.compile(checkpointer=memory)


if __name__ == "__main__":
    from langchain_core.runnables import RunnableConfig
    
    state = {
        "user_query": "Find me all sites in Franklin county that are more than 20 acres.",
        "expanded_query": None,
        "sql_query": None,
        "results": None,
        "error": None,
        "last_failed_sql": None,
        "attempt": 0,
        "conversation": []
    }
    config = RunnableConfig(configurable={"thread_id": "test-thread"})
    result = app.invoke(state, config=config)
    # print(result)

    # state = {
    #     "user_query": "Actually, I want sites that are more than 30 acres.",
    #     "expanded_query": result['expanded_query'],
    #     "sql_query": result['sql_query'],
    #     "results": result['results'],
    #     "error": result['error'],
    #     "last_failed_sql": result['last_failed_sql'],
    #     "attempt": 0,
    #     "conversation": result['conversation']
    # }
    # result = app.invoke(state)
    # print(result)