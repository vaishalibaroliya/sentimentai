import pandas as pd

def get_summary(connection):
    df = pd.read_sql("SELECT * FROM comments", connection)

    summary = df['sentiment'].value_counts()
    total = len(df)

    positive = summary.get('Positive', 0)
    negative = summary.get('Negative', 0)
    neutral = summary.get('Neutral', 0)

    return {
        "total": int(total),
        "positive": int(positive),
        "negative": int(negative),
        "neutral": int(neutral),
        "positive_%": float((positive/total)*100),
        "negative_%": float((negative/total)*100),
        "neutral_%": float((neutral/total)*100)
    }