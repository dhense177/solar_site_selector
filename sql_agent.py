
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnablePassthrough
import dotenv
import os
import re
import time
from collections import Counter
from sqlalchemy import create_engine, inspect, text
from typing import TypedDict, Optional
from langchain_openai import ChatOpenAI
dotenv.load_dotenv()

user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]
engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

MAX_ATTEMPTS = 3

# Define the shared state for the graph
class SQLState(TypedDict):
    question: str
    schema: str
    sql: Optional[str]
    previous_sql: Optional[str]  # For tracking previous query when refining
    error: Optional[str]
    result: Optional[list]
    attempt: int
    validated_empty_ok: Optional[bool]  # Flag to indicate if empty results are validated as correct
    parcel_count: Optional[int]  # Total number of parcels in the database

def get_schema(table_name, schema_name):
    return inspect(engine).get_columns('parcel_details', schema='parcels')

def get_all_tables_schema(_):
    """Get schema information for all tables in all schemas"""
    inspector = inspect(engine)
    # schemas = inspector.get_schema_names()
    schemas = ['parcels','geographic_features']
    
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


def run_query(sql: str, con):
    try:
        print(f'Query being run: {sql} \n\n')
        return con.execute(text(sql)).mappings().all(), None
    except Exception as e:
        print("Error running query: ", str(e))
        return None, str(e)

def extract_conditional_filters(question: str):
    template = f"""
        You are a language-to-logic parser that extracts conditional filters from natural language site-selection queries.

        Your task is to read the user query and list each *distinct condition* exactly as it appears or is implied in the text.

        Each condition should represent one logical filter (for example, parcel size, location, zoning, exclusions, or proximity).

        ---

        ### Output format

        Return a JSON object with a single key `"conditions"`, whose value is a list of short, literal condition strings.

        Do **not** rewrite or interpret them as database fields.  
        Do **not** add metadata, operators, or inferred structure.  
        Just capture the constraints in plain text, as faithfully as possible.

        ---

        ### Example

        **User query:**
        "Find parcels larger than 10 acres in Worcester County, within 5 km of a substation, and not on wetlands."

        **Output:**
        
        "conditions": [
            "larger than 10 acres",
            "in Worcester County",
            "within 5 km of a substation",
            "not on wetlands"
        ]
        

        SQL Query:"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a language-to-logic parser that extracts conditional filters from natural language site-selection queries."),
            ("human", template),
        ]
    )
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"question": question})
    return response

def write_sql_query(state: SQLState):
    # Check if we're refining a previous query
    if state.get("previous_sql"):
        template = """Based on the available tables and their schemas below, MODIFY the previous SQL query according to the new requirement.

        Available tables and schemas:
        {tables}

        Previous SQL query:
        {previous_sql}

        New requirement: {question}

        Instructions:
        - Take the previous SQL query and modify it to incorporate the new requirement
        - Preserve the existing structure and logic, only add/modify what's needed for the new requirement
        - Use the full table name format: schema.table_name
        - You may need to add JOINs or WHERE clauses to satisfy the new requirement
        - Return ONLY the modified SQL query, no explanations or markdown formatting

        Modified SQL Query:"""
        
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a SQL expert. Modify the existing SQL query to incorporate the new requirement. "
                "Preserve the existing query structure and logic, only adding or modifying what's necessary. "
                "Return ONLY the modified SQL query - no prefix or suffix quotes, no markdown code blocks, no explanations, just the raw SQL query."),
                ("human", template),
            ]
        )
        tables = get_all_tables_schema("")
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "tables": tables, 
            "question": state["question"],
            "previous_sql": state["previous_sql"]
        })
    else:
        template = """Based on the available tables and their schemas below, write a SQL query that would answer the user's question.

        Available tables and schemas:
        {tables}

        Question: {question}

        Instructions:
        - Choose the appropriate table(s) to query based on the question
        - Use the full table name format: schema.table_name
        - You may need to JOIN multiple tables if the question requires it
        - When performing distance or area calculations, **ALWAYS** use the geometry_26986 column. Do not use the geometry column.
        - Return ONLY the SQL query, no explanations or markdown formatting

        SQL Query:"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a SQL expert. Given a question and available database tables, write a valid SQL query using PostgreSQL/PostGIS syntax. "
                "Choose the appropriate table(s) automatically based on what the question is asking. "
                "No pre-amble. Return ONLY the SQL query - no prefix or suffix quotes, no markdown code blocks, no explanations, just the raw SQL query."),
                ("human", template),
            ]
        )
        tables = get_all_tables_schema("")
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"tables": tables, "question": state["question"]})
    
    print(response)
    return {"sql": response, "attempt": state["attempt"] + 1}
    # return (
    #     RunnablePassthrough.assign(tables=get_all_tables_schema)
    #     | prompt
    #     | llm
    #     | StrOutputParser()
    # )

def execute_sql(state: SQLState):
    con = engine.connect()
    rows, error = run_query(state["sql"], con)
    con.close()
    return {"result": rows, "error": error}


def repair_sql(state: SQLState):
    # Get fresh schema information
    schema = get_all_tables_schema("")
    
    # Check if this is a duplicate issue or an error
    has_duplicates = False
    duplicate_info = ""
    if not state.get("error") and state.get("result"):
        results = state.get("result", [])
        if results and len(results) > 1:
            parcel_ids = [row.get('parcel_id') for row in results if row.get('parcel_id')]
            unique_count = len(set(parcel_ids)) if parcel_ids else 0
            if parcel_ids and len(parcel_ids) != unique_count:
                has_duplicates = True
                counts = Counter(parcel_ids)
                duplicate_ids = [pid for pid, count in counts.items() if count > 1]
                duplicate_info = f"The query returned {len(parcel_ids)} rows with only {unique_count} unique parcels. Found {len(duplicate_ids)} duplicate parcel_id(s)."
    
    if has_duplicates:
        template = """You are fixing a SQL query that returned duplicate parcel results. This usually means the query is missing DISTINCT or has incorrect JOINs causing duplicates.

Available tables and schemas:
{tables}

Original question: {question}

THE PROBLEM:
{duplicate_info}

THE SQL QUERY (this is what needs to be fixed):
{sql}

Instructions:
1. The query returns duplicate parcel_id values - this is always wrong
2. Add DISTINCT or DISTINCT ON (parcel_id) to eliminate duplicates
3. Check JOINs - they may be causing multiple matches per parcel
4. Make minimal changes - preserve the query logic but eliminate duplicates
5. Return the corrected SQL query only - no explanations, no markdown

CORRECTED SQL:"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a SQL repair assistant. Queries that return duplicate parcel_ids are incorrect. Fix by adding DISTINCT or correcting JOINs. Return only the SQL query."),
            ("human", template),
        ])
        
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "tables": schema,
            "question": state["question"],
            "duplicate_info": duplicate_info,
            "sql": state["sql"]
        })
    else:
        template = """You are fixing a SQL query that failed. The error message tells you exactly what's wrong. Read it carefully and fix ONLY what the error says is wrong.

Available tables and schemas:
{tables}

Original question: {question}

THE ERROR MESSAGE (this tells you what's broken):
{error}

THE FAILED SQL (this is what needs to be fixed):
{sql}

Instructions:
1. Read the error message - it tells you what function, column, or syntax doesn't exist
2. Remove or replace EXACTLY what the error says is wrong
3. Do NOT use the same problematic function again - if ST_Width doesn't exist, don't use ST_Width
4. Make minimal changes - only fix what the error points out
5. Return the corrected SQL query only - no explanations, no markdown

CORRECTED SQL:"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a SQL repair assistant. When an error message says something doesn't exist, you MUST remove it. Do NOT repeat the same mistake. Return only the SQL query."),
            ("human", template),
        ])
        
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({
            "tables": schema,
            "question": state["question"],
            "error": state["error"],
            "sql": state["sql"]
        })
    
    print(f"🔧 Repair attempt {state['attempt'] + 1}: {response}")
    return {"sql": response, "attempt": state["attempt"] + 1}


def validate_results(state: SQLState):
    """Validate if a query returning suspicious results (0 or too many) is correct, or generate a fixed query"""
    # Get fresh schema information
    schema = get_all_tables_schema("")
    
    result_count = len(state.get("result", []))
    parcel_count = state.get("parcel_count")
    
    # Determine the issue (duplicates should never reach here - they go to repair_sql)
    if result_count == 0:
        issue_description = "returned 0 results"
        issue_type = "zero"
    elif parcel_count and result_count > parcel_count:
        issue_description = f"returned {result_count} results, which is more than the total number of parcels in the database ({parcel_count}). This suggests the query may be incorrect (e.g., missing DISTINCT, incorrect JOINs causing duplicates)."
        issue_type = "too_many"
    else:
        # This shouldn't happen if routing is correct, but handle it gracefully
        return {"validated_empty_ok": True, "attempt": state["attempt"] + 1}
    
    template = """A SQL query executed successfully but {issue_description}. You need to determine if:
1. The query is syntactically correct
2. The query is the RIGHT query to answer the user's question

Available tables and schemas:
{tables}

Original question: {question}

The SQL query that {issue_description}:
{sql}

{further_context}

Instructions:
1. Check if the query syntax is correct
2. Check if the query logic correctly answers the user's question
3. If BOTH are correct, respond with "VALID: The query is correct and {issue_type} results is expected"
4. If either is wrong, respond with "FIX: " followed by the corrected SQL query

Your response (either "VALID: [explanation]" or "FIX: [corrected SQL]"):"""
    
    further_context = ""
    if issue_type == "too_many":
        further_context = f"Note: The total number of parcels in the database is {parcel_count}. If the query returns more rows than this, it likely has duplicate results from incorrect JOINs or missing DISTINCT clauses."
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a SQL validation assistant. Analyze if a query with suspicious results is correct. "
        "If the query is syntactically correct AND correctly answers the question, respond with 'VALID: [explanation]'. "
        "If there's an issue, respond with 'FIX: ' followed by the corrected SQL query only."),
        ("human", template),
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "tables": schema,
        "question": state["question"],
        "sql": state["sql"],
        "issue_description": issue_description,
        "issue_type": issue_type,
        "further_context": further_context,
        "parcel_count": parcel_count if parcel_count else "unknown"
    })
    
    print(f"🔍 Validation ({issue_description}): {response}")
    
    # Parse the response
    if response.strip().startswith("VALID:"):
        # Query is valid, results are acceptable
        print(f"✅ Query validated as correct - {issue_description} are acceptable")
        return {"validated_empty_ok": True, "attempt": state["attempt"] + 1}
    elif response.strip().startswith("FIX:"):
        # Query needs fixing, extract the new SQL
        new_sql = response.strip().replace("FIX:", "").strip()
        # Remove any markdown code blocks if present
        new_sql = re.sub(r'```sql\n?', '', new_sql)
        new_sql = re.sub(r'```\n?', '', new_sql)
        new_sql = new_sql.strip()
        print(f"🔧 Fixed query: {new_sql}")
        return {"sql": new_sql, "validated_empty_ok": False, "attempt": state["attempt"] + 1}
    else:
        # Unexpected response format, try to extract SQL or treat as valid
        print("⚠️  Unexpected validation response format, attempting to extract SQL...")
        if "SELECT" in response.upper() or "FROM" in response.upper():
            # Looks like SQL, use it
            new_sql = response.strip()
            new_sql = re.sub(r'```sql\n?', '', new_sql)
            new_sql = re.sub(r'```\n?', '', new_sql)
            new_sql = new_sql.strip()
            return {"sql": new_sql, "validated_empty_ok": False, "attempt": state["attempt"] + 1}
        else:
            # Assume it's valid if we can't parse it
            return {"validated_empty_ok": True, "attempt": state["attempt"] + 1}

 # --- Build the LangGraph workflow ---
workflow = StateGraph(SQLState)

workflow.add_node("generate_sql", write_sql_query)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("repair_sql", repair_sql)
workflow.add_node("validate_results", validate_results)

# Logic: generate → execute → (repair if error, or validate if empty, or end)
workflow.add_edge("generate_sql", "execute_sql")

def route_after_execute(state: SQLState):
    """Route after executing SQL: check for errors first, then duplicates, then suspicious results"""
    # If there's an error and we haven't exceeded attempts, repair
    if state.get("error") and state["attempt"] < MAX_ATTEMPTS:
        return "repair_sql"
    # If no error, check for duplicates - these should go to repair_sql
    elif (not state.get("error") and 
          state.get("result") is not None):
        results = state.get("result", [])
        result_count = len(results)
        
        # Check for duplicates - treat as error and send to repair
        has_duplicates = False
        if results and result_count > 1:
            parcel_ids = [row.get('parcel_id') for row in results if row.get('parcel_id')]
            has_duplicates = len(parcel_ids) != len(set(parcel_ids)) if parcel_ids else False
        
        if has_duplicates and state["attempt"] < MAX_ATTEMPTS:
            return "repair_sql"
        
        # If no duplicates, check for other suspicious results (0 results or too many)
        parcel_count = state.get("parcel_count")
        needs_validation = (
            result_count == 0 or 
            (parcel_count and result_count > parcel_count)
        )
        if (needs_validation and 
            not state.get("validated_empty_ok") and 
            state["attempt"] < MAX_ATTEMPTS):
            return "validate_results"
    # Otherwise, end
    return END

workflow.add_conditional_edges(
    "execute_sql",
    route_after_execute,
    {
        "repair_sql": "repair_sql",
        "validate_results": "validate_results",
        END: END
    },
)

workflow.add_edge("repair_sql", "execute_sql")

def route_after_validate(state: SQLState):
    """Route after validating empty results"""
    # If validation says it's OK, end
    if state.get("validated_empty_ok"):
        return END
    # Otherwise, we have a new SQL query to execute
    else:
        return "execute_sql"

workflow.add_conditional_edges(
    "validate_results",
    route_after_validate,
    {
        "execute_sql": "execute_sql",
        END: END
    },
)

# Set entrypoint
workflow.set_entry_point("generate_sql")

# Memory checkpoint (optional)
# memory = MemorySaver()

# Compile the app
# app = workflow.compile(checkpointer=memory)
app = workflow.compile()

if __name__ == "__main__":
    schema_text = get_all_tables_schema("")

    # Get total parcel count for validation
    query = "SELECT COUNT(*) as count FROM parcels.parcel_details"
    con = engine.connect()
    parcel_count_result, error = run_query(query, con)
    con.close()
    
    parcel_count = None
    if parcel_count_result and not error and len(parcel_count_result) > 0:
        # Extract count from result (result is a list of mappings)
        parcel_count = int(parcel_count_result[0].get('count', 0))
        print(f"Total parcels in database: {parcel_count}")
    
    # question = "Find me all sites in Milton, Massachusetts that are more than 20 acres."
    # sql_query = write_sql_query(llm).invoke({"question": question})
    # print(sql_query)
    # result, error = run_query(sql_query)
    # print(len(result))


    initial_state = {
        "question":"Exclude parcels within 250 feet of residential structures and within 500 feet of schools or hospitals.",
        "schema": schema_text,
        "sql": None,
        "previous_sql": None,
        "error": None,
        "result": None,
        "attempt": 0,
        "validated_empty_ok": False,
        "parcel_count": parcel_count,
    }
    start_time = time.time()
    final_state = app.invoke(initial_state)
    end_time = time.time()
    print(f"Time taken: {end_time - start_time} seconds")
    print(f"Number of rows: {len(final_state['result'])}")
    print(f"Number of unique parcels: {len(set([row['parcel_id'] for row in final_state['result']]))}")

    # question = "Find me all sites in Milton, Massachusetts that are more than 20 acres and at least 2km from any wetlands."
    # sql_query = write_sql_query(llm).invoke({"question": question})
    # print(sql_query)
    # result, error = run_query(sql_query)
    # print(len(result))


    # # Can we get the power lines as well and return them so they can be displayed on the map?
    # question = "Find me all sites in Milton, Massachusetts that are more than 20 acres and within 2km of any power line or substation."
    # sql_query = write_sql_query(llm).invoke({"question": question})
    # print(sql_query)
    # result, error = run_query(sql_query)
    # print(len(result))

    # Need to alter the projection for this calculation?
    # Need a loop
    # question = "Find me suitable parcels that are in Western Massachusetts and only include parcels that are at least 500 feet wide in both dimensions so I can fit rows"
    # sql_query = write_sql_query(llm).invoke({"question": question})
    # print(sql_query)
    # result, error = run_query(sql_query)
    # print(len(result))


    # --- Run the Graph ---
    # Example 1: Initial query
    # initial_state = {
    #     "question": "Find parcels within 1 km of a transmission line above 138 kV and within 2 km of a substation.",
    #     "schema": schema_text,
    #     "sql": None,
    #     "previous_sql": None,
    #     "error": None,
    #     "result": None,
    #     "attempt": 0,
    # }
    
    # Example 2: Refining the query to exclude wetlands
    # initial_state = {
    #     "question": "Exclude parcels that are within or intersect wetlands.",
    #     "schema": schema_text,
    #     "sql": None,
    #     "previous_sql": "SELECT DISTINCT ON (pd.parcel_id) pd.* FROM parcels.parcel_details pd JOIN geographic_features.infrastructure hv ON ST_DWithin(pd.geometry, hv.geometry, 1000) WHERE hv.voltage > 138000 JOIN geographic_features.infrastructure ss ON ST_DWithin(pd.geometry, ss.geometry, 2000) WHERE ss.class = 'substation' LIMIT 10;",
    #     "error": None,
    #     "result": None,
    #     "attempt": 0,
    # }
    
    # --- Run the Graph ---
    # Example 1: Initial query
    # initial_state = {
    #     "question": "Find parcels within 1 km of a transmission line above 138 kV and within 2 km of a substation.",
    #     "schema": schema_text,
    #     "sql": None,
    #     "previous_sql": None,
    #     "error": None,
    #     "result": None,
    #     "attempt": 0,
    # }

    # final_state = app.invoke(initial_state)
    
    # # Example 2: Refining the query to exclude wetlands
    # initial_state = {
    #     "question": "Exclude parcels that are less than 10 acres",
    #     "schema": schema_text,
    #     "sql": None,
    #     "previous_sql": final_state["sql"],
    #     "error": None,
    #     "result": None,
    #     "attempt": 0,
    # }

    # final_state = app.invoke(initial_state)

    # print("\n✅ Final SQL Query:\n", final_state["sql"])
    # print("\n📊 Query Result:\n", final_state["result"])
    # print("\n🧠 Attempts:", final_state["attempt"])



    # initial_state = {
    #     "question": "Show only vacant or agricultural parcels, not residential",
    #     "schema": schema_text,
    #     "sql": None,
    #     "previous_sql": None,
    #     "error": None,
    #     "result": None,
    #     "attempt": 0,
    # }

    # final_state = app.invoke(initial_state)

    # print("\n✅ Final SQL Query:\n", final_state["sql"])
    # print("\n📊 Query Result:\n", final_state["result"])
    # print("\n🧠 Attempts:", final_state["attempt"])