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

# Standard queries - All information available in database
STANDARD = [
    # {
    #     "question":
    #         "Find parcels over 20 acres in Franklin county",
    #     "sql":"""
    #         SELECT *
    #         FROM parcels.parcel_details
    #         WHERE area_acres > 20
    #         AND county_name = 'FRANKLIN'
    #         """
    # },
    # {
    #     "question":
    #         "Find parcels within 1 km of a transmission line above 138 kV and within 2 km of a substation.",
    #     "sql":"""
    #         SELECT 
    #             DISTINCT ON (pd.parcel_id) pd.*,
    #             ST_Distance(
    #             pd.geometry_26986,
    #             hv.geometry_26986) AS distance_to_transmission_line,
    #             ST_Distance(
    #             pd.geometry_26986,
    #             ss.geometry_26986) AS distance_to_substation
    #         FROM parcels.parcel_details AS pd
    #         JOIN infrastructure_features.infrastructure AS hv
    #         ON hv.voltage > 138000
    #         AND hv.class = 'power_line'
    #         AND ST_DWithin(
    #             pd.geometry_26986,
    #             hv.geometry_26986,
    #             1000
    #             )
    #         JOIN infrastructure_features.infrastructure AS ss
    #         ON ss.class = 'substation'
    #         AND ST_DWithin(
    #             pd.geometry_26986,
    #             ss.geometry_26986,
    #             2000
    #             )
    #         """
    # },
    {
        "user_query":
            "Find me sites for a 2-megawatt ground-mount or freestanding solar system that requires about 12 acres of land and sells power back to the electricity grid such that a majority of electricity produced is not consumed on site",
        "sql_correct":"""
            SELECT *
            FROM parcels.parcel_details
            WHERE area_acres >= 12
            AND ground_mounted_capacity_kw >= 2000
            """
    },
    # {
    #     "query":
    #         "Show only vacant or agricultural parcels, not residential",
    #     "sql":"""
    #         SELECT *
    #         FROM parcels.parcel_details
    #         WHERE land_use = 'vacant' OR land_use = 'agricultural'
    #         """
    # }
]




# intermediate queries - information available in database

INTERMEDIATE = [
    {
        # "query":
        #     "Only include parcels that are at least 500 feet wide in both dimensions so I can fit rows",
        # "sql":"""
        #     SELECT *
        #     FROM parcels.parcel_details
        #     WHERE width >= 500
        #     """
    },
    {
        "question":
            "I'm looking for 20+ acre parcels in Western Mass, within 2 miles of a substation, no wetlands, and not residentially zoned.",
            # mostly flat,
        "sql":"""
            SELECT DISTINCT pd.parcel_id, pd.full_address, pd.area_acres
            FROM parcels.parcel_details pd
            JOIN geographic_features.land_use lu ON ST_Intersects(pd.geometry_26986, lu.geometry_26986) AND lu.class != 'residential'
            JOIN geographic_features.land_cover lc ON ST_Intersects(pd.geometry_26986, lc.geometry_26986) AND lc.class != 'wetland'
            JOIN geographic_features.flood_zones fz ON ST_DWithin(pd.geometry_26986, fz.geometry_26986, 3218.69) -- 2 miles in meters
            WHERE pd.area_acres > 20
            AND pd.county_name IN ('HAMPDEN', 'HAMPSHIRE', 'BERKSHIRE');
            """
    },
    {
        "question":
            "Give me large contiguous land (30 acres or more) west of Worcester that's within half a mile of three-phase lines and not in floodplain or NHESP habitat.",
        "sql":"""
            SELECT *
            FROM parcels.parcel_details
            WHERE area_acres >= 30
            """
    }
]

VAGUE = [
    {
        "question":
            "Find me all sites in Southwest Massachusetts that are more than 20 acres.",
        "sql":"""
            SELECT * 
            FROM parcels.parcel_details 
            WHERE area_acres > 20 
            AND county_name IN ('HAMPDEN', 'HAMPSHIRE', 'BERKSHIRE');
            """
    }
]

UNRELATED = [
    {
        "question":
            "What is the current temperature in Boston?",
        "sql": None
    }
]

MULTI_TURN = [
    {
        "thread_id": "test-session-1",
        "question1":
            "Find parcels over 20 acres in Franklin county",
        "sql1":"""
            SELECT * 
            FROM parcels.parcel_details 
            WHERE area_acres > 20 
            AND county_name = 'FRANKLIN';
            """,
        "question2":
            "actually I want parcels greater than 30 acres",
        "sql2":"""
            SELECT * 
            FROM parcels.parcel_details 
            WHERE area_acres > 30 
            AND county_name = 'FRANKLIN';
            """
    }

]

if __name__ == "__main__":
    schema_text = get_all_tables_schema("")

    for query in STANDARD:
        config = RunnableConfig(configurable={"thread_id": random.randint(1,100000)})
        # start_time = time.time()
        query['schema'] = schema_text
        query['attempt'] = 0
        # Use invoke_app helper function with a thread_id for checkpointing
        results_dict = app.invoke(query, config=config)

        len_results = len(results_dict['results'])

        ground_truth, error = run_query(query['sql'], con)
        len_ground_truth = len(ground_truth)

        assert len_results == len_ground_truth, "Number of rows in results and ground truth do not match"

    #     # end_time = time.time()
    #     # print(f"Time taken: {end_time - start_time} seconds")
    #     # print(f"Number of rows: {len(rows)}")


    # for query in MULTI_TURN:
    #     query['schema'] = schema_text
    #     query['attempt'] = 0

    #     query['question'] = query['question1']
    #     query['sql'] = query['sql1']
    #     results_dict1 = invoke_app(query, thread_id=query['thread_id'])
    #     len_results = len(results_dict1['result'])
    #     ground_truth, error = run_query(query['sql1'], con)
    #     len_ground_truth = len(ground_truth)
    #     assert len_results == len_ground_truth, "Number of rows in results and ground truth do not match"
        
    #     query['question'] = query['question2']
    #     query['sql'] = query['sql2']
    #     results_dict2 = invoke_app(query, thread_id=query['thread_id'])
    #     len_results = len(results_dict2['result'])
    #     ground_truth, error = run_query(query['sql2'], con)
    #     len_ground_truth = len(ground_truth)
    #     assert len_results == len_ground_truth, "Number of rows in results and ground truth do not match"


"""
# Vague query - need to make assumptions and/or ask for clarification from user

# Missing information in database
"I'm looking for a 75 MW solar site in southern Massachusetts with at least 150 contiguous acres, <5° slope, within 5 km of a 230 kV line, not zoned residential and no known endangered species nearby."

"Find parcels over 15 acres with average slope under 5%"

"Give me parcels where less than 5% of the area is wetlands or surface water."

# "Exclude parcels that are already developed — no buildings, no parking lots, no existing industrial footprint"


# "Show parcels that have at least 15 buildable acres after subtracting wetlands, buffers, and required setbacks"

# "Prioritize parcels near substations with recent upgrades or open queue capacity."


"Exclude heavily forested parcels with dense canopy unless tree clearing is under 10 acres."

"Exclude parcels at elevation above 1,500 ft due to snow loading and access cost."

"Filter out parcels in municipalities with strict tree-clearing bylaws or solar moratoriums."

"Find parcels within 0.5 miles of an existing public road, not private drive"

# "Exclude sites that require crossing wetlands or streams to bring in equipment."

"Exclude parcels within 250 feet of residential structures and within 500 feet of schools or hospitals."


"Show only parcels with road access and a single private owner, not town-owned."

"I want brownfields and capped landfills that are already disturbed and are close to distribution infrastructure."


# Advanced queries

# Multiple queries back to back?

"Find me all sites in Plymouth county, Massachusetts that are more than 20 acres and at least 2km from any wetlands."

"Avoid sites in wildlife corridors, conservation easements, or wetlands."
"""
#####

# query = """
# SELECT DISTINCT ON (pd.parcel_id) pd.*
# FROM parcels.parcel_details AS pd
# JOIN infrastructure_features.infrastructure AS hv
#   ON hv.voltage > 138000
#  AND ST_DWithin(
#        pd.geometry_26986,
#        hv.geometry_26986,
#        1000
#      )
# JOIN infrastructure_features.infrastructure AS ss
#   ON ss.class = 'substation'
#  AND ST_DWithin(
#        pd.geometry_26986,
#        ss.geometry_26986,
#        2000
#      );
# """

# # Check indexes
# query = """SELECT
# schemaname,
# tablename,
# indexname,
# indexdef
# FROM
# pg_indexes
# ORDER BY
# schemaname, tablename;"""

#####

# Tests
# q1 = {"question": "Find parcels over 20 acres in Franklin county away from wetlands"}
# q2 = "Show flat land parcels over 15 acres in Worcester county",
# q3 = "Find parcels with southern exposure in Berkshire county",
# q4 = "Search for 25+ acre parcels near grid infrastructure in Hampshire county"

# q1['schema'] = schema_text
# q1['attempt'] = 0
# results_dict = sql_agent_app.invoke(query)

#####

# Testing follow-up queries
# q1 = {"question": "Find parcels over 20 acres in Franklin county"}
# q2 = {"question": "actually I want parcels greater than 30 acres"}

# q1['schema'] = schema_text
# q1['attempt'] = 0
# # Use invoke_app helper function with a thread_id for checkpointing
# results_dict = invoke_app(q1, thread_id="test-session-1")

# q2['schema'] = schema_text
# q2['attempt'] = 0
# Use the same thread_id to maintain conversation state
# results_dict = invoke_app(q2, thread_id="test-session-1")
