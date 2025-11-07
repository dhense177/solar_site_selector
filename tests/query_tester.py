from sql_agent import run_query
from sqlalchemy import create_engine
import dotenv
import os
import time
import random
from langchain_core.runnables import RunnableConfig
from sql_agent import app  # Use the helper function instead
from db_actions.db_utils import run_query
from sql_agent import get_all_tables_schema
dotenv.load_dotenv()
user, password, host, port, db_name = os.environ["DB_USER"], os.environ["DB_PASSWORD"], "localhost", "5432", os.environ["DB_NAME"]

engine = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}")

con = engine.connect()

schema_text = get_all_tables_schema("")



q1 = {"user_query": "What is the weather today in New York?"}

q1['schema'] = schema_text
q1['attempt'] = 0
config = RunnableConfig(configurable={"thread_id": random.randint(1,100000)})
# Use invoke_app helper function with a thread_id for checkpointing
results_dict1 = app.invoke(q1, config=config)


# # Testing follow-up queries
# q1 = {"question": "Find parcels over 20 acres in Franklin county"}
# q2 = {"question": "actually I want parcels greater than 30 acres"}

# q1['schema'] = schema_text
# q1['attempt'] = 0
# # Use invoke_app helper function with a thread_id for checkpointing
# results_dict1 = invoke_app(q1, thread_id="test-session-1")

# q2['schema'] = schema_text
# q2['attempt'] = 0
# # Use the same thread_id to maintain conversation state
# results_dict2 = invoke_app(q2, thread_id="test-session-1")