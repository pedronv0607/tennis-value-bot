import sqlite3
conn = sqlite3.connect('tennis_value_bot.db')
conn.execute("CREATE TABLE IF NOT EXISTS bankroll (fecha TEXT PRIMARY KEY, cantidad REAL)")
conn.execute("INSERT OR REPLACE INTO bankroll VALUES ('2026-05-19', 20.0)")
conn.commit()
conn.close()
print('Bankroll actualizado a 20 euros')