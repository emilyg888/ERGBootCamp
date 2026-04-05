import duckdb

con = duckdb.connect("db/rowing.duckdb")
con.execute("SELECT 1").fetchall()

print("DuckDB connected ✅")