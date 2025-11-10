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

# --- DEBUG: Print all environment variables (without sensitive values) ---
print("=" * 80)
print("ENVIRONMENT VARIABLES DEBUG:")
print("=" * 80)
# List all environment variables that might be relevant
relevant_vars = [
    "DATABASE_URL", "SUPABASE_URL_SESSION", "SUPABASE_PWD",
    "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "DB_PORT",
    "PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGPORT",
    "OPENAI_API_KEY", "ALLOWED_ORIGINS"
]
for var in relevant_vars:
    value = os.getenv(var)
    if value:
        # Mask sensitive values
        if "PASSWORD" in var or "PWD" in var or "KEY" in var:
            print(f"{var}: {'*' * min(len(value), 20)}")
        elif "URL" in var or "HOST" in var:
            # Show URL but mask password if present
            if "@" in value:
                parts = value.split("@")
                if len(parts) == 2:
                    user_pass = parts[0].split("://")[-1]
                    if ":" in user_pass:
                        user, _ = user_pass.split(":", 1)
                        print(f"{var}: {value.split('://')[0]}://{user}:***@{parts[1]}")
                    else:
                        print(f"{var}: {value}")
                else:
                    print(f"{var}: {value}")
            else:
                print(f"{var}: {value}")
        else:
            print(f"{var}: {value}")
    else:
        print(f"{var}: NOT SET")
print("=" * 80)

# --- CONFIG ---
# Database connection setup
# Priority: 1) DATABASE_URL (Railway default), 2) SUPABASE_URL_SESSION, 3) DB_* variables, 4) PG* variables

# Check for DATABASE_URL first (Railway's default when you link a PostgreSQL service)
database_url = os.getenv("DATABASE_URL")
if database_url:
    print("Using DATABASE_URL connection string")
    # Railway's DATABASE_URL might be postgres://, convert to postgresql+psycopg2://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    engine = create_engine(database_url)
elif os.getenv("SUPABASE_URL_SESSION"):
    print("Using Supabase connection string")
    engine = create_engine(os.getenv("SUPABASE_URL_SESSION"))
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
    # Railway or other hosted database - support both DB_* and PG* variable names
    print("Using hosted database connection (Railway)")
    
    # Try DB_* variables first, then fall back to PG* variables (Railway default)
    user = os.getenv("DB_USER") or os.getenv("PGUSER")
    password = os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD")
    host = os.getenv("DB_HOST") or os.getenv("PGHOST")
    port = os.getenv("DB_PORT") or os.getenv("PGPORT", "5432")
    db_name = os.getenv("DB_NAME") or os.getenv("PGDATABASE")
    
    print(f"Host: {host}, User: {user}, Database: {db_name}, Port: {port}")
    print(f"Using variables: DB_*={'DB_USER' if os.getenv('DB_USER') else 'PGUSER'}")
    
    if not all([user, password, host, db_name]):
        missing = []
        if not user: missing.append("DB_USER or PGUSER")
        if not password: missing.append("DB_PASSWORD or PGPASSWORD")
        if not host: missing.append("DB_HOST or PGHOST")
        if not db_name: missing.append("DB_NAME or PGDATABASE")
        raise ValueError(
            f"Missing required database environment variables: {', '.join(missing)}. "
            "Need one of: DATABASE_URL, SUPABASE_URL_SESSION, or all of: DB_USER/PGUSER, DB_PASSWORD/PGPASSWORD, DB_HOST/PGHOST, DB_NAME/PGDATABASE"
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
    
    # Vague conditions tracking
    vague_conditions: Optional[List[Dict[str, str]]]  # List of vague conditions detected
    
    # Unmatched conditions tracking
    unmatched_conditions_warning: Optional[str]  # Warning message if conditions don't match database

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
    conversation = state.get("conversation", [])
    
    # Build conversation context string
    conversation_context = ""
    if conversation:
        conversation_parts = []
        for msg in conversation:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            elif hasattr(msg, 'type'):  # AIMessage or HumanMessage
                role = "assistant" if msg.type == "ai" else "user"
                content = msg.content if hasattr(msg, 'content') else str(msg)
            elif hasattr(msg, 'content'):  # Generic message object
                role = "assistant"  # Default to assistant if we can't determine
                content = msg.content
            else:
                continue  # Skip unknown message types
            
            conversation_parts.append(f"{role}: {content}")
        conversation_context = "\n".join(conversation_parts[-6:])  # Last 6 messages for context
    
    # Create enhanced prompt with conversation context
    if conversation_context:
        # Add conversation context to the template
        enhanced_template = f"""{topic_filter_template}

**IMPORTANT**: Consider the conversation context below. Follow-up questions, clarifications, or refinements to previous parcel queries are still relevant, even if they seem vague on their own.

Conversation context:
{conversation_context}
"""
        prompt = ChatPromptTemplate.from_messages(
            [("system", enhanced_template), ("human", "{{user_query}}")]
        )
    else:
        # No conversation context, use original template
        prompt = ChatPromptTemplate.from_messages(
            [("system", topic_filter_template), ("human", "{{user_query}}")]
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
    
    # Convert conversation messages to dicts if they're AIMessage objects
    conversation_str = ""
    if conversation:
        conversation_parts = []
        for msg in conversation:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
            elif hasattr(msg, 'type'):  # AIMessage or HumanMessage
                role = "assistant" if msg.type == "ai" else "user"
                content = msg.content if hasattr(msg, 'content') else str(msg)
            elif hasattr(msg, 'content'):  # Generic message object with content
                role = "assistant"  # Default to assistant if we can't determine
                content = msg.content
            else:
                role = "unknown"
                content = str(msg)
            conversation_parts.append(f"{role}: {content}")
        conversation_str = "\n".join(conversation_parts)
    
    prompt = f"""
    You are a helpful assistant that interprets user questions about a parcel database.
    Use the prior conversation to make the current query self-contained.

    Conversation so far:
    {conversation_str}

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
    user_query = state.get("user_query", "")
    
    prompt_template_str = """
    Analyze the following user query and identify ONLY truly vague or underspecified conditions.
    
    **CRITICAL RULES**:
    1. You must analyze the ACTUAL user query provided below: "{user_query}"
    2. Do NOT use example values. Only return vague conditions that actually exist in THIS user query.
    3. ONLY flag conditions that are genuinely vague - conditions with specific values (numbers, distances, feature types) are NOT vague.
    
    **What IS vague (flag these)**:
    - Geographic regions without specifics: "Western Massachusetts", "the coast", "rural areas"
    - Size descriptors without numbers: "large parcels", "small sites", "big enough"
    - Distance without specifics: "near", "close to", "far from" (without distance)
    - Time periods without specifics: "recent", "old", "new"
    - Ambiguous feature types: "infrastructure" (without specifying what type)
    
    **What is NOT vague (do NOT flag these)**:
    - Specific distances: "within 1 mile", "2km away", "500 meters"
    - Specific sizes: "over 20 acres", "at least 30 acres", "between 10 and 50 acres"
    - Specific feature types: "substations", "transmission lines", "wetlands"
    - Specific counties/towns: "Worcester county", "Boston", "Franklin county"
    - Specific values: "above $100,000", "capacity > 5MW"
    - Combinations of specific values: "within 1 mile of substations" (has distance AND feature type)
    
    Examples of vague conditions (for reference only - DO NOT use these, analyze the actual user query):
    - "Western Massachusetts" → vague (no specific counties)
    - "large parcels" → vague (no specific acreage)
    - "near a substation" → vague (no specific distance)
    
    Examples of CLEAR conditions (do NOT flag these):
    - "Within 1 mile of substations" → CLEAR (has distance and feature type)
    - "Parcels over 20 acres" → CLEAR (has specific size)
    - "In Worcester county" → CLEAR (has specific location)
    
    Schema information: {SCHEMA_TEXT}
    
    Respond ONLY as JSON in this format (only include vague conditions that actually exist in the user query):
    {{{{
      "vague_conditions": [
        {{{{
          "original": "<exact vague phrase from user query>",
          "suggested_replacement": "<concrete interpretation>",
          "reasoning": "<why you chose this interpretation>"
        }}}}
      ]
    }}}}
    
    If there are NO vague conditions in the user query, return:
    {{{{
      "vague_conditions": []
    }}}}
    """

    # Use ChatPromptTemplate for better prompt handling
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a SQL query analyzer. Analyze the ACTUAL user query for vague conditions. Do NOT use example values - only analyze the real user query provided."),
        ("human", prompt_template_str)
    ])
    
    parser = JsonOutputParser()
    chain = prompt_template | llm | parser
    
    try:
        result = chain.invoke({"SCHEMA_TEXT": SCHEMA_TEXT, "user_query": user_query})
        # JsonOutputParser should return a dict, but check if it's an AIMessage
        if hasattr(result, 'content'):
            # It's an AIMessage, parse the content
            import json
            data = json.loads(result.content)
        elif isinstance(result, dict):
            # It's already a dict
            data = result
        else:
            # Try to convert to dict
            data = dict(result) if hasattr(result, '__dict__') else {}
        vague_conditions = data.get("vague_conditions", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"Error parsing vague conditions with JsonOutputParser: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: try direct LLM call with manual JSON parsing
        try:
            # Format the prompt with actual values
            formatted_prompt = prompt_template_str.format(SCHEMA_TEXT=SCHEMA_TEXT, user_query=user_query)
            response = llm.invoke(formatted_prompt)
            # Extract content if it's an AIMessage
            if hasattr(response, 'content'):
                response_text = response.content.strip()
            else:
                response_text = str(response).strip()
            import json
            # Try to extract JSON from markdown if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            data = json.loads(response_text)
            vague_conditions = data.get("vague_conditions", []) if isinstance(data, dict) else []
        except Exception as e2:
            print(f"Error in fallback parsing: {e2}")
            import traceback
            traceback.print_exc()
            vague_conditions = []

    if not vague_conditions:
        # No vague items detected → proceed directly
        return {
            "conversation": [],
            "vague_conditions": []
        }

    # Build a confirmation message for user
    message_lines = ["I noticed a few vague parts of your query:"]
    for cond in vague_conditions:
        message_lines.append(
            f"- \"{cond['original']}\" → I interpreted as: {cond['suggested_replacement']}"
        )
    message_lines.append(
        "\nPlease confirm if this interpretation is correct, or provide more specific criteria."
    )
    clarification_message = "\n".join(message_lines)

    return {
        "conversation": [
            {"role": "assistant", "content": clarification_message}
        ],
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

def check_unmatched_conditions(state: SQLState):
    """
    Check if user's filtering conditions match what's available in the database.
    Warn user if they requested features that don't exist in the database.
    """
    user_query = state.get("user_query", "")
    expanded_query = state.get("expanded_query", "")
    sql_query = state.get("sql_query", "")
    results = state.get("results", [])
    
    check_prompt = f"""
    Analyze the user's query and identify any filtering conditions that request features NOT available in the database.
    
    User's original query: "{user_query}"
    Expanded query: "{expanded_query}"
    SQL query: "{sql_query}"
    
    Database schema (this shows all available features and their class values):
    {SCHEMA_TEXT}
    
    **IMPORTANT RULES**:
    1. Use the database schema above to determine what features are available. Look at the column comments which describe the available class values (e.g., "substation" or "power_line" for infrastructure, "wetland" or "forest" for land_cover, etc.).
    2. If the user asks for features that are semantically similar to available features (e.g., "power stations" → "substation", "power lines" → "power_line"), these are MATCHED and should NOT be flagged.
    3. Only flag features that have NO equivalent in the database schema (e.g., "hospitals", "schools", "buildings" when referring to specific building types that are not in the schema).
    4. If the user asks to exclude features that don't exist (e.g., "without hospitals"), this should be flagged as a warning.
    5. If results are empty or very few, and the user requested features that don't exist in the schema, this is likely the cause.
    
    **CRITICAL**: Keep all responses SHORT and SIMPLE. Do NOT mention database table names, column names, or any technical details. Just identify the requested feature name. The "reason" and "suggestion" fields will be ignored - only use "requested_feature".
    
    Respond ONLY as JSON in this format:
    {{{{
      "unmatched_conditions": [
        {{{{
          "requested_feature": "<exact feature requested by user - just the feature name>"
        }}}}
      ],
      "has_unmatched": true/false
    }}}}
    
    If all requested features match available features, return:
    {{{{
      "unmatched_conditions": [],
      "has_unmatched": false
    }}}}
    """
    
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a database schema analyzer. Check if user-requested features match what's available in the database. Only flag features that have NO equivalent in the database. Keep all responses SHORT and SIMPLE - no table names, no technical details."),
        ("human", check_prompt)
    ])
    
    parser = JsonOutputParser()
    chain = prompt_template | llm | parser
    
    try:
        result = chain.invoke({})
        # Handle both dict and AIMessage
        if hasattr(result, 'content'):
            import json
            data = json.loads(result.content)
        elif isinstance(result, dict):
            data = result
        else:
            data = dict(result) if hasattr(result, '__dict__') else {}
        
        has_unmatched = data.get("has_unmatched", False) if isinstance(data, dict) else False
        unmatched_conditions = data.get("unmatched_conditions", []) if isinstance(data, dict) else []
        
        if has_unmatched and unmatched_conditions:
            # Build short, simple warning message
            features = [cond['requested_feature'] for cond in unmatched_conditions]
            if len(features) == 1:
                warning_message = f"⚠️ Note: \"{features[0]}\" is not available in the database."
            else:
                features_str = ", ".join([f'"{f}"' for f in features[:-1]]) + f', and "{features[-1]}"'
                warning_message = f"⚠️ Note: {features_str} are not available in the database."
            
            return {
                "unmatched_conditions_warning": warning_message
            }
        
        return {"unmatched_conditions_warning": None}
        
    except Exception as e:
        print(f"Error checking unmatched conditions: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail the query if this check fails
        return {"unmatched_conditions_warning": None}

def validate_sql(state: SQLState):
    """
    Validate SQL before accepting results:
    - Check syntax via EXPLAIN
    - Check non-empty results
    - Check for unmatched conditions (features requested that don't exist in DB)
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

    # 2️⃣ Check for unmatched conditions (features requested that don't exist in DB)
    unmatched_check = check_unmatched_conditions(state)
    unmatched_warning = unmatched_check.get("unmatched_conditions_warning")

    # 3️⃣ Check for empty results
    if not results or len(results) == 0:
        # If there are unmatched conditions, include that in the error message
        if unmatched_warning:
            return {
                "error": f"Query executed successfully but returned 0 results. {unmatched_warning}",
                "last_failed_sql": sql_query,
                "unmatched_conditions_warning": unmatched_warning,
            }
        return {
            "error": "Query executed successfully but returned 0 results.",
            "last_failed_sql": sql_query,
        }
    
    # If we have results but unmatched conditions, include warning
    if unmatched_warning:
        return {
            "unmatched_conditions_warning": unmatched_warning
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
    vague_conditions = state.get("vague_conditions", [])
    topic_filter_message = state.get("topic_filter_message")
    unmatched_warning = state.get("unmatched_conditions_warning")
    
    # If topic filter failed, add the error message
    if topic_filter_message:
        # Check if message is already in conversation (handle both dict and AIMessage)
        message_exists = False
        if conversation:
            last_msg = conversation[-1]
            if isinstance(last_msg, dict):
                last_content = last_msg.get("content", "")
            elif hasattr(last_msg, 'content'):
                last_content = last_msg.content
            else:
                last_content = str(last_msg)
            message_exists = (last_content == topic_filter_message)
        
        if not message_exists:
            conversation.append({"role": "assistant", "content": topic_filter_message})
    
    # If vague conditions were detected, the message is already in conversation from resolve_vague_conditions
    # Just ensure it's there
    if vague_conditions and len(vague_conditions) > 0:
        # Check if the vague conditions message is already in conversation
        # Handle both dict and AIMessage objects
        vague_message_exists = False
        for msg in conversation:
            if isinstance(msg, dict):
                content = msg.get("content", "")
            elif hasattr(msg, 'content'):
                content = msg.content
            else:
                content = str(msg)
            if "vague parts of your query" in content:
                vague_message_exists = True
                break
        if not vague_message_exists:
            # Build the message (should already be there, but just in case)
            message_lines = ["I noticed a few vague parts of your query:"]
            for cond in vague_conditions:
                message_lines.append(
                    f"- \"{cond['original']}\" → I interpreted as: {cond['suggested_replacement']}"
                )
            message_lines.append(
                "\nPlease confirm if this interpretation is correct, or provide more specific criteria."
            )
            clarification_message = "\n".join(message_lines)
            conversation.append({"role": "assistant", "content": clarification_message})
    
    # If there's an error and it's not already in conversation, add it
    if error:
        # Check if error is already in conversation (handle both dict and AIMessage)
        error_exists = False
        if conversation:
            last_msg = conversation[-1]
            if isinstance(last_msg, dict):
                last_content = last_msg.get("content", "")
            elif hasattr(last_msg, 'content'):
                last_content = last_msg.content
            else:
                last_content = str(last_msg)
            error_exists = (last_content == error)
        
        if not error_exists:
            conversation.append({"role": "assistant", "content": error})
    
    # Don't add unmatched conditions warning to conversation - it will be added to summary in api_server.py
    # This prevents duplication
    
    if error:
        print("❌ Query failed:", error)
    elif results:
        print(f"✅ Returned {len(results)} results")
        if unmatched_warning:
            print(f"⚠️ Unmatched conditions warning: {unmatched_warning[:100]}...")
    elif vague_conditions:
        print(f"⚠️ Vague conditions detected: {len(vague_conditions)}")
    else:
        print("No results found.")
    
    return {"conversation": conversation}


# --- GRAPH CONSTRUCTION ---
graph = StateGraph(SQLState)

graph.add_node("topic_filter", topic_filter)
graph.add_node("resolve_vague_conditions", resolve_vague_conditions)
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
    # If topic is relevant, go to contextual_query_understanding first
    return "contextual_query_understanding"

graph.add_conditional_edges(
    "topic_filter",
    route_after_topic_filter,
    {
        "contextual_query_understanding": "contextual_query_understanding",
        "display_results": "display_results"
    }
)

# Direct edge: contextual_query_understanding → resolve_vague_conditions
graph.add_edge("contextual_query_understanding", "resolve_vague_conditions")

# Conditional routing after resolve_vague_conditions
def route_after_vague_conditions(state: SQLState):
    """Route after vague conditions: continue if none detected, ask user if detected."""
    vague_conditions = state.get("vague_conditions", [])
    
    # If vague conditions were detected, show them to the user and wait for confirmation
    if vague_conditions and len(vague_conditions) > 0:
        return "display_results"
    
    # No vague conditions detected, proceed to generate_sql
    return "generate_sql"

graph.add_conditional_edges(
    "resolve_vague_conditions",
    route_after_vague_conditions,
    {
        "generate_sql": "generate_sql",
        "display_results": "display_results"
    }
)
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
        "user_query": "Find me all sites in Franklin county that are more than 20 acres and are not close to wetlands.",
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

    vc = resolve_vague_conditions(result)
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