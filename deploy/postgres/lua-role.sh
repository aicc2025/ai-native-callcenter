#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
#
# Creates the confined role FreeSWITCH reads the luacc views with, once the
# application has created them.
#
# Role creation deliberately lives outside the migrations (deploy/sql/
# lua_role.sql explains why), which leaves a gap in an automated stack: the
# grants need the views, the views arrive when the application migrates, and
# the switch needs the role before it answers its first registration. This
# waits for the first, does the second, and lets compose hold back the third.
#
# The luacc schema existing does not mean the migrations are over: the schema
# is created by an early one, and later ones replace views in it. A GRANT that
# runs while a migration is replacing a view fails with "tuple concurrently
# deleted", which on a fresh start is the common case, not a rare one. So
# this waits until the recorded schema version has stopped moving, runs
# lua_role.sql, and then checks the result: every relation in luacc must be
# readable by aicc_lua. On an error, or a relation left without its grant, it
# waits for the version to settle again and repeats. lua_role.sql is
# idempotent, so a repeat is safe. Views created after a successful run are
# covered twice over: by the default privileges lua_role.sql sets on the
# schema, and by the migrations themselves, which grant to aicc_lua whenever
# the role exists.
set -eu

: "${LUA_PASSWORD:?set the database password the switch reads with}"

q() {
    psql -h postgres -U aicc -d aicc -tAc "$1" 2>/dev/null
}

echo "lua-role: waiting for the application to create the luacc views"
attempt=0
until q "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'luacc'" | grep -q 1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 120 ]; then
        echo "lua-role: the luacc views never appeared; is the application healthy?" >&2
        exit 1
    fi
    sleep 2
done

# settle waits until goose's recorded version is the same on three reads two
# seconds apart, which a migration run in progress does not survive.
settle() {
    last=""
    same=0
    polls=0
    while [ "$same" -lt 2 ] && [ "$polls" -lt 60 ]; do
        now=$(q "SELECT coalesce(max(version_id), 0) FROM goose_db_version WHERE is_applied" || true)
        if [ -n "$now" ] && [ "$now" = "$last" ]; then
            same=$((same + 1))
        else
            same=0
        fi
        last=$now
        polls=$((polls + 1))
        sleep 2
    done
    echo "lua-role: schema version ${last:-unknown}"
}

ungranted() {
    q "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
       WHERE n.nspname = 'luacc' AND c.relkind IN ('r', 'v', 'm')
         AND NOT has_table_privilege('aicc_lua', c.oid, 'SELECT')"
}

attempt=1
while :; do
    settle
    if psql -h postgres -U aicc -d aicc -v ON_ERROR_STOP=1 \
        -v lua_password="'${LUA_PASSWORD}'" -f /lua_role.sql &&
        [ "$(ungranted)" = "0" ]; then
        break
    fi
    if [ "$attempt" -ge 10 ]; then
        echo "lua-role: could not grant aicc_lua the luacc views after $attempt attempts" >&2
        exit 1
    fi
    echo "lua-role: attempt $attempt did not complete; retrying"
    attempt=$((attempt + 1))
    sleep "$attempt"
done

echo "lua-role: aicc_lua may read the luacc views"
