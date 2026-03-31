import sqlite3
import sqlite3
import pandas as pd

conn = sqlite3.connect("database.db")

# ================= USERS =================
df_users = pd.read_sql("SELECT id, name, email FROM users", conn)

print("\n" + "="*60)
print("👤 USERS TABLE")
print("="*60)

if df_users.empty:
    print("No users found ❌")
else:
    print(df_users.to_string(index=False))


# ================= COMMENTS =================
df_comments = pd.read_sql("""
    SELECT id, text, sentiment, confidence, source, created_at
    FROM comments
    ORDER BY created_at DESC
""", conn)

print("\n" + "="*60)
print("💬 COMMENTS TABLE (LATEST FIRST)")
print("="*60)

if df_comments.empty:
    print("No comments found ❌")
else:
    # text ko short kar (clean look)
    df_comments["text"] = df_comments["text"].apply(lambda x: x[:40] + "..." if len(x) > 40 else x)

    # confidence round
    df_comments["confidence"] = df_comments["confidence"].round(1)

    print(df_comments.to_string(index=False))


conn.close()