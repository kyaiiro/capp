import psycopg, bcrypt
from psycopg.rows import dict_row

class dbAccess():
    def __init__(self, DB_PASS, DB_IP):
        self.dbpass = DB_PASS
        self.dbip = DB_IP
        self.conn = f"dbname=capp user=postgres password={self.dbpass} host={self.dbip}"

    def write_message(self, user_id, message):
        with psycopg.connect(self.conn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (user_id, content) VALUES (%s, %s)",
                    (user_id, message)
                )

    async def create_new_user(self, username, password, pfp):
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

        with psycopg.connect(self.conn) as conn:
            with conn.cursor() as cur:
                # We must provide password_hash since it's NOT NULL
                cur.execute(
                    """
                    INSERT INTO users (username, password_hash, pfp) 
                    VALUES (%s, %s, %s) 
                    RETURNING id
                    """,
                    (username, hashed_password.decode('utf-8'), pfp)
                )
                new_id = cur.fetchone()[0]
                return new_id
    
    async def login(self, conn_string, username, input_password):
        async with await psycopg.AsyncConnection.connect(conn_string) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT password_hash, id FROM users WHERE username = %s", 
                    (username,)
                )
                result = await cur.fetchone()

                if not result:
                    return "no"
                stored_hash = result['password_hash'].encode('utf-8')
                uid = result["id"]
                user_input_bytes = input_password.encode('utf-8')

                # bcrypt.checkpw returns True if they match
                if bcrypt.checkpw(user_input_bytes, stored_hash):
                    return f"yes {uid}"
                else:
                    return "no"
            
    async def get_all_users_json(self, conn_string):
        async with await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT id, username, pfp FROM users")
                users = await cur.fetchall()
                
                # Convert list to dict: {id: {"username": username, "pfp": pfp}, ...}
                return {user['id']: {"id": user["id"], "username": user['username'], "pfp": user['pfp']} for user in users}
            
    async def detFlag(self, conn_string, my_user_id):
        my_channel = f"user_unread_{my_user_id}"
        async with await psycopg.AsyncConnection.connect(conn_string, autocommit=True) as conn:
            await conn.execute(f"LISTEN {my_channel}")
            
            async for notify in conn.notifies():
                return True 

    async def getUnread(self, conn_string, my_user_id):
        async with await psycopg.AsyncConnection.connect(conn_string) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT unread_count FROM user_notifications WHERE user_id = %s", 
                    (my_user_id,)
                )
                res = await cur.fetchone()
                count = res['unread_count'] if res else 0
                return count

    async def lowerFlag(self, conn_string, my_user_id):
        async with await psycopg.AsyncConnection.connect(conn_string, autocommit=True) as conn:
            await conn.execute(
                "UPDATE user_notifications SET unread_count = 0 WHERE user_id = %s", 
                (my_user_id,)
            )
            return True

    async def getMsg(self, conn_string, amount: int):
        async with await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                # We join with users to get the name, and sort by ID/Time descending
                await cur.execute("""
                    SELECT u.username, m.content, m.created_at, u.id
                    FROM messages m
                    JOIN users u ON m.user_id = u.id
                    ORDER BY m.id DESC 
                    LIMIT %s
                """, (amount,))
                
                rows = await cur.fetchall()
                
                # Formatting timestamps so JSON likes them
                for row in rows:
                    if row['created_at']:
                        row['created_at'] = row['created_at'].isoformat()
                
                return rows
            
    async def msgCount(self, conn_string):
        async with await psycopg.AsyncConnection.connect(conn_string, row_factory=dict_row) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM messages")
                result = await cur.fetchone()
                return result['count']
    
    import asyncio
import psycopg

async def check_server_status(main_dsn, backup_dsn):
    try:
        async with await psycopg.AsyncConnection.connect(main_dsn, timeout=4) as conn:
            return 1
    except Exception:
        try:
            async with await psycopg.AsyncConnection.connect(backup_dsn, timeout=4) as conn:
                return 2
        except Exception:
            return "noServer"

#def