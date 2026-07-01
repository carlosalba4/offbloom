import sqlite3
con = sqlite3.connect("offbloom.db")
tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print(tablas)