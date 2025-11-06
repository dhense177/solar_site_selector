
general_template = """

General Instructions:
- Choose the appropriate table(s) to query based on the question
- Use the full table name format: schema.table_name
- You may need to JOIN multiple tables if the question requires it
- When performing distance or area calculations, **ALWAYS** use the geometry_26986 column. Do not use the geometry column.
- Make sure that you convert units to the units for a feature which exist in the database. For example, if the user asks for parcels within 1 mile of a substation, you need to convert 1 mile to meters and use the geometry_26986 column to calculate the distance. 
- Unless specified in the query with 'or', use the AND operator to join filters.
- If user asks for parcels with a certain attribute linked to a numeric value (i.e. 12 acres) - assume that they are asking for parcels with that attribute value greater than or equal to the numeric value unless otherwise specified.

Mapping User Queries to Database Class Values:
- For categorical/enum columns (especially 'class'), you MUST match the user's terminology to a feature or feature value in the database listed in the column comments
- When the user mentions a feature type, search through the schema comments to find the matching class value
- The user may not use the exact same terminology as the database class values, so you need to use semantic understanding to map the user's query to the database class values.
- If unsure about a mapping, explain in your reasoning what value you chose and why

Output Instructions:
- **CRITICAL**: ALWAYS include the 'geometry' field from parcel_details database table in your SELECT clause
- **IMPORTANT**: Provide both the SQL query AND an explanation of your reasoning.
"""

write_sql_template = """

Based on the available tables and their schemas below, write a SQL query that would answer the user's question.

Available tables and schemas:
{tables}

Question: {user_query}

""" + general_template + """

Output format:
SQL: [your SQL query here]

Explanation: [your explanation of why you chose these tables/columns, how the query logic addresses the question, what filters/joins you used and why, and especially which class values you matched from the user query]
"""

