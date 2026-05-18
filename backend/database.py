import aiosqlite

DB_PATH = "jobs.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress TEXT,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def create_job(id: str, created_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO jobs (id, status, created_at) VALUES (?, 'pending', ?)",
            (id, created_at),
        )
        await db.commit()


async def update_job(id: str, **fields):
    if not fields:
        return
    assignments = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)
        await db.commit()


async def get_job(id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE id = ?", (id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def list_jobs() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
