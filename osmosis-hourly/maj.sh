#! /bin/bash

. ../config

CHANGEFILE="$WORKDIR/change-`date +%F-%R`.osc.gz"

echo ""
echo "*** Get changes from server"
$OSMOSIS --read-replication-interval workingDirectory="$WORKDIR" --simplify-change --write-xml-change "$CHANGEFILE"

echo ""
echo "*** Insert data in postgresql"
$OSMOSIS --read-xml-change "$CHANGEFILE" --write-pgsql-change database="$DATABASE" user="$USER" password="$PASS"

echo "*** Create ways bounding box"
$PREFIX psql -f update-bbox.sql "$DATABASE"

echo ""
echo "*** Clean ways database"
$PREFIX psql "$DATABASE" -c "SELECT clean_bdd('$BOUNDING_BOX');"

echo "*** Create ways linestring"
$PREFIX psql -f update-linestring.sql "$DATABASE"
