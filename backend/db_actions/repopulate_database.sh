#!/bin/bash

# Usage: ./repopulate_database.sh [--geo-only|--infra-only|--parcels-only] [--local|--hosted]
# Example: ./repopulate_database.sh --geo-only --local

# arg 1: --geo-only, --infra-only, --parcels-only, --all-features
# --geo-only: Recreate only geographic_features tables (preserves parcels)
# --infra-only: Recreate only infrastructure_features tables (preserves parcels)
# --parcels-only: Recreate only parcels tables (preserves geographic_features and infrastructure_features)
# --all-features: Recreate all tables (preserves parcels)
# If no argument is provided, all tables will be recreated.

# arg 2: --local, --hosted
# --local: Use local database
# --hosted: Use hosted database
# If no argument is provided, local database will be used.

if [ "$1" == "--geo-only" ]; then
    export RECREATE_GEO_FEATURES=true
    export RECREATE_PARCELS=false
    export RECREATE_INFRA_FEATURES=false
elif [ "$1" == "--infra-only" ]; then
    export RECREATE_INFRA_FEATURES=true
    export RECREATE_PARCELS=false
    export RECREATE_GEO_FEATURES=false
elif [ "$1" == "--parcels-only" ]; then
    export RECREATE_PARCELS=true
    export RECREATE_GEO_FEATURES=false
    export RECREATE_INFRA_FEATURES=false
elif [ "$1" == "--all-features" ]; then
    export RECREATE_PARCELS=true
    export RECREATE_GEO_FEATURES=true
    export RECREATE_INFRA_FEATURES=true
else
    export RECREATE_PARCELS=true
    export RECREATE_GEO_FEATURES=true
    export RECREATE_INFRA_FEATURES=true
fi

if [ "$2" == "--local" ]; then
    export DB_HOST=local
else
    export DB_HOST=hosted
fi

python db_actions/create_db.py
python db_actions/populate_tables.py

