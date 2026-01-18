import psycopg2

conn = psycopg2.connect(
    dbname='tradeagent',
    user='postgres',
    password='yasser',
    host='localhost'
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, numeric_precision, numeric_scale
    FROM information_schema.columns
    WHERE table_name = 'positions'
    ORDER BY ordinal_position
""")

print(f"\n{'='*80}")
print(f"POSITIONS TABLE SCHEMA:")
print(f"{'='*80}")
for row in cur.fetchall():
    col_name = row[0]
    data_type = row[1]
    precision = row[2] if row[2] else 'N/A'
    scale = row[3] if row[3] else 'N/A'
    print(f"{col_name:20s} | {data_type:15s} | Precision: {precision}, Scale: {scale}")
print(f"{'='*80}\n")

conn.close()
