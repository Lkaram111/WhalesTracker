import os

import mysql.connector


def main():
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "3307"))
    user = os.environ.get("DB_USER", "whales")
    password = os.environ.get("DB_PASSWORD", "WhalesTracker135!")
    database = os.environ.get("DB_NAME", "whales")

    db = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        connection_timeout=5,
    )

    cursor = db.cursor()
    cursor.execute("SELECT 1")
    print(cursor.fetchone())
    cursor.close()
    db.close()


if __name__ == "__main__":
    main()
