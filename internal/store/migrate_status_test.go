// SPDX-License-Identifier: Apache-2.0

package store

import (
	"context"
	"testing"
)

// MigrationStatus is what `aicc doctor` runs against a live deployment, so the
// property that matters most is that asking changes nothing — above all on a
// database nobody has migrated, where goose's own readers would create the
// version table.

func statusStore(t *testing.T) *Store {
	t.Helper()
	st, err := Open(context.Background(), scratchDB(t), 2)
	if err != nil {
		t.Fatalf("open store: %v", err)
	}
	t.Cleanup(st.Close)
	return st
}

func versionTableExists(t *testing.T, st *Store) bool {
	t.Helper()
	var exists bool
	if err := st.Pool.QueryRow(context.Background(),
		`SELECT to_regclass('goose_db_version') IS NOT NULL`).Scan(&exists); err != nil {
		t.Fatalf("look for goose_db_version: %v", err)
	}
	return exists
}

func TestAnUnmigratedDatabaseIsPendingAndLeftUntouched(t *testing.T) {
	st := statusStore(t)

	state, err := st.MigrationStatus(context.Background())
	if err != nil {
		t.Fatalf("migration status: %v", err)
	}
	if state.DBVersion != 0 || !state.HasPending || state.LatestVersion == 0 {
		t.Fatalf("want 0/<latest> pending, got %+v", state)
	}
	if versionTableExists(t, st) {
		t.Fatal("asking for the status created goose_db_version")
	}
}

func TestAMigratedDatabaseIsCurrent(t *testing.T) {
	st := statusStore(t)
	ctx := context.Background()
	if err := st.Migrate(ctx); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	state, err := st.MigrationStatus(ctx)
	if err != nil {
		t.Fatalf("migration status: %v", err)
	}
	if state.HasPending || state.DBVersion != state.LatestVersion || state.DBVersion == 0 {
		t.Fatalf("want current and nothing pending, got %+v", state)
	}
}

// A database a newer binary migrated is ahead of this one. That is not
// pending — there is nothing this binary could apply — and the version says
// by how much.
func TestADatabaseANewerBinaryMigratedIsAheadNotPending(t *testing.T) {
	st := statusStore(t)
	ctx := context.Background()
	if err := st.Migrate(ctx); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	if _, err := st.Pool.Exec(ctx,
		`INSERT INTO goose_db_version (version_id, is_applied) VALUES (99999, true)`); err != nil {
		t.Fatalf("record a future migration: %v", err)
	}

	state, err := st.MigrationStatus(ctx)
	if err != nil {
		t.Fatalf("migration status: %v", err)
	}
	if state.HasPending || state.DBVersion != 99999 || state.LatestVersion >= state.DBVersion {
		t.Fatalf("want ahead and nothing pending, got %+v", state)
	}
}
