from typing import Annotated, Optional, List, Dict, Any, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import create_engine, text, inspect
from prompts.text_to_sql_prompts import write_sql_template, topic_filter_template
import os
import dotenv
import re
from db_actions.db_utils import run_query
dotenv.load_dotenv()

# --- CONFIG ---
# Database connection setup
# Priority: 1) SUPABASE_URL_SESSION, 2) DB_* variables (local or hosted)

supabase_connection_string = os.getenv("SUPABASE_URL_SESSION")
if supabase_connection_string:
    print("Using Supabase connection string")
    engine = create_engine(supabase_connection_string)
elif os.getenv("DB_HOST") == "local":
    # Local development
    print("Using local database connection")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    if not all([user, password, db_name]):
        raise ValueError("Missing required local database environment variables: DB_USER, DB_PASSWORD, DB_NAME")
    engine = create_engine(f"postgresql+psycopg2://{user}:{password}@localhost:5432/{db_name}")
else:
    # Railway or other hosted database - use standard DB_* environment variables
    print("Using hosted database connection (Railway)")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")
    
    print(f"DB_HOST: {host}, DB_USER: {user}, DB_NAME: {db_name}, DB_PORT: {port}")
    
    if not all([user, password, host, db_name]):
        missing = []
        if not user: missing.append("DB_USER")
        if not password: missing.append("DB_PASSWORD")
        if not host: missing.append("DB_HOST")
        if not db_name: missing.append("DB_NAME")
        raise ValueError(
            f"Missing required database environment variables: {', '.join(missing)}. "
            "Need either SUPABASE_URL_SESSION or all of: DB_USER, DB_PASSWORD, DB_HOST, DB_NAME"
        )
    
    connection_string = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
    print(f"Creating engine with connection string: postgresql+psycopg2://{user}:***@{host}:{port}/{db_name}")
    engine = create_engine(connection_string)

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
    relevant_query_topic: Optional[bool]
    topic_filter_message: Optional[str]  # Error message if topic filter fails
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

# --- NODES ---
def topic_filter(state: SQLState):
    """Filter the user's query to ensure it is related to solar site selection."""
    user_query = state.get("user_query", "")
    prompt = ChatPromptTemplate.from_messages(
        [("system", topic_filter_template), ("human", "{user_query}")]
    )
    chain = prompt | llm | JsonOutputParser()
    data = chain.invoke({"user_query": user_query})
    
    is_relevant = data.get("solar_query", False)
    
    if not is_relevant:
        error_message = data.get("message", "I can only assist with land parcel search and filtering for solar site selection.")
        return {
            "relevant_query_topic": False,
            "topic_filter_message": error_message,
            "error": error_message
        }
    
    return {"relevant_query_topic": True}

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

def resolve_vague_conditions(state: SQLState):
    """
    Detect vague or underspecified conditions in the user's query.
    Attempt to infer reasonable replacements using schema + geography context.
    Ask user to confirm or refine.
    """

    prompt = """
    The user provided the following query:

    "{user_query}"

    Identify any vague or underspecified conditions (e.g., "Western Massachusetts", "large parcels", "near a substation").
    For each vague condition:
      1. Propose the most likely concrete interpretation based on the schema and common domain sense.
      2. Return your best guess in the form of a structured list of suggested replacements.

    Schema information:
    {schema}

    Respond ONLY as JSON in this format:
    {{
      "vague_conditions": [
        {{
          "original": "Western Massachusetts",
          "suggested_replacement": "counties IN ('BERKSHIRE', 'FRANKLIN', 'HAMPSHIRE', 'HAMPDEN')",
          "reasoning": "These are the four westernmost counties in MA"
        }}
      ]
    }}
    """

    response = llm.invoke(prompt).content.strip()

    # Try to parse JSON safely
    import json
    try:
        data = json.loads(response)
        vague_conditions = data.get("vague_conditions", [])
    except Exception:
        vague_conditions = []

    if not vague_conditions:
        # No vague items detected → proceed directly
        return {"conversation": [{"role": "assistant", "content": "No vague conditions detected."}]}

    # Build a confirmation message for user
    message_lines = ["I noticed a few vague parts of your query:"]
    for cond in vague_conditions:
        message_lines.append(
            f"- \"{cond['original']}\" → I interpreted as: {cond['suggested_replacement']}"
        )
    message_lines.append(
        "\nIs this what you had in mind? You can confirm or clarify any of these."
    )
    clarification_message = "\n".join(message_lines)

    return {
        "conversation": [
            {"role": "assistant", "content": clarification_message}
        ],
        # Optionally store for later refinement
        "vague_conditions": vague_conditions,
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
    conversation = state.get("conversation", [])
    
    # If there's an error and it's not already in conversation, add it
    if error and (not conversation or conversation[-1].get("content") != error):
        conversation.append({"role": "assistant", "content": error})
    
    if error:
        print("❌ Query failed:", error)
    elif results:
        print(f"✅ Returned {len(results)} results")
    else:
        print("No results found.")
    
    return {"conversation": conversation}


# --- GRAPH CONSTRUCTION ---
graph = StateGraph(SQLState)

# graph.add_node("resolve_vague_conditions", resolve_vague_conditions)
graph.add_node("topic_filter", topic_filter)
graph.add_node("contextual_query_understanding", contextual_query_understanding)
graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_sql", execute_sql)
graph.add_node("validate_sql", validate_sql)
graph.add_node("repair_sql", repair_sql)
graph.add_node("display_results", display_results)

graph.set_entry_point("topic_filter")

# Conditional routing after topic filter
def route_after_topic_filter(state: SQLState):
    """Route after topic filter: continue if relevant, error if not."""
    # Check if topic filter failed - look for the error message we set
    # Also check the boolean flag
    if state.get("relevant_query_topic") is False:
        return "display_results"
    return "contextual_query_understanding"

graph.add_conditional_edges(
    "topic_filter",
    route_after_topic_filter,
    {
        "contextual_query_understanding": "contextual_query_understanding",
        "display_results": "display_results"
    }
)

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