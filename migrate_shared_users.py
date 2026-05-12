"""
One-time migration: create a shared `users` table used by both the SAT and
IELTS platforms.

What this does:
  1. Reads all 21 existing SAT users from the old `users` table.
  2. Generates a UUID for each one.
  3. Creates a new `users` table with the unified schema.
  4. Inserts the SAT users into it.
  5. Adds a `user_uuid` column to `test_sessions`, fills it, then swaps it
     in place of the old integer `user_id` column.
  6. Drops the old `users` table.

Everything runs inside a single transaction — if anything fails the database
is rolled back to its original state.

Usage:
    pip install psycopg2-binary
    python migrate_shared_users.py          # dry-run (prints SQL, no changes)
    python migrate_shared_users.py --apply  # applies changes to the database
"""

import sys
import uuid
import psycopg2
from psycopg2.extras import execute_values

DB_URL = (
    "postgresql://sat_practice_user:r8ljaxqJVYW0DFVRh7HgRof9noIEDcsz"
    "@dpg-d3ie486mcj7s73964f80-a.singapore-postgres.render.com/sat_practice"
)

DRY_RUN = "--apply" not in sys.argv


def migrate():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False

    try:
        cur = conn.cursor()

        # ── 1. Read existing SAT users ──────────────────────────────────────
        cur.execute("SELECT id, username, email, password FROM users ORDER BY id")
        sat_users = cur.fetchall()
        print(f"Found {len(sat_users)} existing SAT users.\n")

        # ── 2. Build old-int-id → new-UUID mapping ──────────────────────────
        id_map: dict[int, str] = {row[0]: str(uuid.uuid4()) for row in sat_users}

        print("ID mapping (old integer → new UUID):")
        for old_id, new_uuid in id_map.items():
            row = next(r for r in sat_users if r[0] == old_id)
            print(f"  user {old_id:3d}  {row[2]:35s}  →  {new_uuid}")

        if DRY_RUN:
            print("\n[DRY RUN] No changes made. Re-run with --apply to execute.")
            return

        print("\nApplying migration…")

        # ── 3. Drop FK so we can safely rename the users table ─────────────
        cur.execute(
            "ALTER TABLE test_sessions DROP CONSTRAINT test_sessions_user_id_fkey"
        )

        # ── 4. Rename old users table out of the way ────────────────────────
        cur.execute("ALTER TABLE users RENAME TO sat_users_old")

        # ── 5. Create the new unified users table ───────────────────────────
        cur.execute("""
            CREATE TABLE users (
                id            VARCHAR(36)    PRIMARY KEY,
                email         VARCHAR(255)   UNIQUE NOT NULL,
                name          VARCHAR(255)   NOT NULL,
                username      VARCHAR(80)    UNIQUE,
                password_hash VARCHAR(255)   NOT NULL,
                role          VARCHAR(20)    NOT NULL DEFAULT 'STUDENT',
                target_score  NUMERIC(5, 1),
                created_at    TIMESTAMP      NOT NULL DEFAULT NOW()
            )
        """)

        # ── 6. Insert SAT users with their new UUIDs ─────────────────────────
        # name  → use username as display name (SAT had no separate name field)
        # password_hash → copy the existing bcrypt hash from `password` column
        rows = [
            (
                id_map[row[0]],   # id (UUID)
                row[2],           # email
                row[1],           # name  (= username, best we have)
                row[1],           # username
                row[3],           # password_hash (already bcrypt)
                "STUDENT",        # role
            )
            for row in sat_users
        ]
        execute_values(
            cur,
            "INSERT INTO users (id, email, name, username, password_hash, role) VALUES %s",
            rows,
        )
        print(f"  ✓ Inserted {len(rows)} users into new shared users table.")

        # ── 7. Add UUID column to test_sessions, fill from mapping ──────────
        cur.execute("ALTER TABLE test_sessions ADD COLUMN user_uuid VARCHAR(36)")
        for old_id, new_uuid in id_map.items():
            cur.execute(
                "UPDATE test_sessions SET user_uuid = %s WHERE user_id = %s",
                (new_uuid, old_id),
            )
        print("  ✓ Filled user_uuid in test_sessions.")

        # ── 8. Swap columns: drop old integer user_id, rename user_uuid ─────
        cur.execute("ALTER TABLE test_sessions DROP COLUMN user_id")
        cur.execute("ALTER TABLE test_sessions RENAME COLUMN user_uuid TO user_id")
        cur.execute("ALTER TABLE test_sessions ALTER COLUMN user_id SET NOT NULL")
        cur.execute("""
            ALTER TABLE test_sessions
                ADD CONSTRAINT test_sessions_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id)
        """)
        print("  ✓ Swapped test_sessions.user_id to UUID with FK restored.")

        # ── 9. Drop old SAT users table ──────────────────────────────────────
        cur.execute("DROP TABLE sat_users_old")
        print("  ✓ Dropped sat_users_old.")

        conn.commit()
        print("\nMigration complete. ✓")

    except Exception as exc:
        conn.rollback()
        print(f"\nMigration FAILED — database rolled back.\nError: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
