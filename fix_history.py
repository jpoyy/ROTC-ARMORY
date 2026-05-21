import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE history ADD COLUMN field_changed TEXT")
except:
    pass

try:
    cursor.execute("ALTER TABLE history ADD COLUMN old_value TEXT")
except:
    pass

try:
    cursor.execute("ALTER TABLE history ADD COLUMN new_value TEXT")
except:
    pass

conn.commit()
conn.close()

print("History table updated successfully.")