#!/bin/bash

# Usage: ./recreate_geographic_features.sh [--geo-only|--infra-only|--parcels-only]
# --geo-only: Recreate only geographic_features tables (preserves parcels) [default]
# --all: Recreate all tables

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
else
    export RECREATE_PARCELS=true
    export RECREATE_GEO_FEATURES=true
    export RECREATE_INFRA_FEATURES=true
fi

python db_actions/create_db.py
python db_actions/populate_tables.py

