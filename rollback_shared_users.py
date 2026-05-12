"""
Rollback: restore the original SAT integer-based users table.

Restores:
  users          → INTEGER pk, username, email, password columns (original schema)
  test_sessions.user_id       → INTEGER
  drill_sessions.user_id      → INTEGER
  drill_set_progress.user_id  → INTEGER
  text_highlights.user_id     → INTEGER
"""

import psycopg2
from psycopg2.extras import execute_values

DB_URL = (
    "postgresql://sat_practice_user:r8ljaxqJVYW0DFVRh7HgRof9noIEDcsz"
    "@dpg-d3ie486mcj7s73964f80-a.singapore-postgres.render.com/sat_practice"
)

# Tables that have a user_id FK referencing users.id
FK_TABLES = [
    ("test_sessions",      "test_sessions_user_id_fkey"),
    ("drill_sessions",     "drill_sessions_user_id_fkey"),
    ("drill_set_progress", "drill_set_progress_user_id_fkey"),
    ("text_highlights",    "text_highlights_user_id_fkey"),
]


def rollback():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False

    try:
        cur = conn.cursor()

        # 1. Read current UUID users, assign sequential integer IDs
        cur.execute(
            "SELECT id, username, email, password_hash FROM users ORDER BY created_at"
        )
        uuid_users = cur.fetchall()
        # uuid → new integer id (1-based, matching original order)
        uuid_to_int: dict[str, int] = {
            row[0]: idx for idx, row in enumerate(uuid_users, start=1)
        }
        print(f"Found {len(uuid_users)} users. UUID → integer mapping:")
        for uuid_id, int_id in uuid_to_int.items():
            user = next(r for r in uuid_users if r[0] == uuid_id)
            print(f"  {int_id:3d}  {user[2]:40s}  ({uuid_id[:8]}…)")

        # 2. Drop all FK constraints pointing at users.id
        for table, constraint in FK_TABLES:
            cur.execute(
                f"ALTER TABLE {table} DROP CONSTRAINT {constraint}"
            )
        print("\nDropped FK constraints.")

        # 3. Rename current users table out of the way
        cur.execute("ALTER TABLE users RENAME TO users_uuid_backup")

        # 4. Recreate original users table with INTEGER primary key
        cur.execute("""
            CREATE TABLE users (
                id       SERIAL        PRIMARY KEY,
                username VARCHAR(80)   NOT NULL UNIQUE,
                email    VARCHAR(120)  NOT NULL UNIQUE,
                password VARCHAR(120)  NOT NULL
            )
        """)

        # 5. Insert users with their assigned integer IDs
        #    Use setval to keep the sequence in sync after manual inserts
        rows = [
            (uuid_to_int[row[0]], row[1], row[2], row[3])
            for row in uuid_users
        ]
        execute_values(
            cur,
            "INSERT INTO users (id, username, email, password) VALUES %s",
            rows,
        )
        # Advance the sequence past the highest ID we inserted
        max_id = max(uuid_to_int.values())
        cur.execute(f"SELECT setval('users_id_seq', {max_id})")
        print(f"Inserted {len(rows)} users into restored users table.")

        # 6. For each FK table: add integer column, fill from mapping, swap
        for table, constraint in FK_TABLES:
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN user_id_int INTEGER"
            )
            # Fill using a join against the backup table
            cur.execute(f"""
                UPDATE {table} t
                SET user_id_int = m.new_int
                FROM (
                    SELECT id AS uuid_id,
                           ROW_NUMBER() OVER (ORDER BY created_at) AS new_int
                    FROM users_uuid_backup
                ) m
                WHERE t.user_id = m.uuid_id
            """)
            cur.execute(f"ALTER TABLE {table} DROP COLUMN user_id")
            cur.execute(
                f"ALTER TABLE {table} RENAME COLUMN user_id_int TO user_id"
            )
            cur.execute(
                f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL"
            )
            cur.execute(f"""
                ALTER TABLE {table}
                    ADD CONSTRAINT {constraint}
                    FOREIGN KEY (user_id) REFERENCES users(id)
            """)
            print(f"  ✓ {table}.user_id restored to INTEGER.")

        # 7. Drop UUID backup table
        cur.execute("DROP TABLE users_uuid_backup")

        conn.commit()
        print("\nRollback complete. ✓  SAT app should be working again.")

    except Exception as exc:
        conn.rollback()
        print(f"\nRollback FAILED — database unchanged.\nError: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rollback()
