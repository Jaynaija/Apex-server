"""
HC Apex Intelligence Server
Receives webhook data from TradingView HC Apex indicator
Stores trade data and generates performance reports
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import sqlite3
import json
from datetime import datetime
import os

app = FastAPI(title="HC Apex Intelligence Server")

DB_PATH = "apex_trades.db"

# ═══════════════════════════════════════════════════════════════
# DATABASE SETUP
# ═══════════════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            asset       TEXT,
            pair        TEXT,
            direction   TEXT,
            score       INTEGER,
            probability INTEGER,
            session     TEXT,
            regime      TEXT,
            structure   TEXT,
            smc         TEXT,
            inst_flow   TEXT,
            liquidity   TEXT,
            kill_zone   TEXT,
            macro       TEXT,
            mtf         TEXT,
            entry       REAL,
            sl          REAL,
            tp1         REAL,
            tp2         REAL,
            tp3         REAL,
            tp4         REAL,
            signal_type TEXT,
            raw         TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS trade_outcomes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            asset       TEXT,
            pair        TEXT,
            direction   TEXT,
            score       INTEGER,
            session     TEXT,
            regime      TEXT,
            inst_flow   TEXT,
            kill_zone   TEXT,
            structure   TEXT,
            outcome     TEXT,
            r_result    REAL,
            raw         TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ═══════════════════════════════════════════════════════════════
# WEBHOOK RECEIVER — SIGNALS
# ═══════════════════════════════════════════════════════════════
@app.post("/signal")
async def receive_signal(request: Request):
    """Receives entry signal alerts from TradingView"""
    try:
        body = await request.json()
    except:
        body = {}

    # Parse alert message if sent as plain text
    raw = json.dumps(body)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals 
        (timestamp, asset, pair, direction, score, probability, session, regime,
         structure, smc, inst_flow, liquidity, kill_zone, macro, mtf,
         entry, sl, tp1, tp2, tp3, tp4, signal_type, raw)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.utcnow().isoformat(),
        body.get("asset", ""),
        body.get("pair", ""),
        body.get("direction", ""),
        body.get("score", 0),
        body.get("probability", 0),
        body.get("session", ""),
        body.get("regime", ""),
        body.get("structure", ""),
        body.get("smc", ""),
        body.get("inst_flow", ""),
        body.get("liquidity", ""),
        body.get("kill_zone", ""),
        body.get("macro", ""),
        body.get("mtf", ""),
        body.get("entry", 0),
        body.get("sl", 0),
        body.get("tp1", 0),
        body.get("tp2", 0),
        body.get("tp3", 0),
        body.get("tp4", 0),
        body.get("signal_type", ""),
        raw
    ))
    conn.commit()
    conn.close()
    return {"status": "signal logged", "timestamp": datetime.utcnow().isoformat()}

# ═══════════════════════════════════════════════════════════════
# WEBHOOK RECEIVER — TRADE OUTCOMES
# ═══════════════════════════════════════════════════════════════
@app.post("/outcome")
async def receive_outcome(request: Request):
    """Receives trade close alerts (TP hits, SL hits) from TradingView"""
    try:
        body = await request.json()
    except:
        body = {}

    raw = json.dumps(body)

    # Calculate R result from outcome type
    outcome = body.get("outcome", "")
    r_map = {
        "TP1": 1.0,
        "TP2": 2.0,
        "TP3": 3.0,
        "TP4": 4.0,
        "SL":  -1.0
    }
    r_result = r_map.get(outcome, 0.0)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO trade_outcomes
        (timestamp, asset, pair, direction, score, session, regime,
         inst_flow, kill_zone, structure, outcome, r_result, raw)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.utcnow().isoformat(),
        body.get("asset", ""),
        body.get("pair", ""),
        body.get("direction", ""),
        body.get("score", 0),
        body.get("session", ""),
        body.get("regime", ""),
        body.get("inst_flow", ""),
        body.get("kill_zone", ""),
        body.get("structure", ""),
        outcome,
        r_result,
        raw
    ))
    conn.commit()
    conn.close()
    return {"status": "outcome logged", "r_result": r_result}

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE REPORT
# ═══════════════════════════════════════════════════════════════
@app.get("/report", response_class=HTMLResponse)
async def get_report():
    """Full HTML performance report"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Overall stats
    c.execute("SELECT COUNT(*) FROM trade_outcomes")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM trade_outcomes WHERE r_result > 0")
    wins = c.fetchone()[0]

    c.execute("SELECT AVG(r_result) FROM trade_outcomes")
    avg_r = c.fetchone()[0] or 0

    c.execute("SELECT SUM(r_result) FROM trade_outcomes WHERE r_result > 0")
    gross_win = c.fetchone()[0] or 0

    c.execute("SELECT SUM(ABS(r_result)) FROM trade_outcomes WHERE r_result < 0")
    gross_loss = c.fetchone()[0] or 1

    pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else 0
    wr = round((wins / total * 100), 1) if total > 0 else 0

    # By session
    c.execute("""
        SELECT session, COUNT(*) as trades,
               SUM(CASE WHEN r_result > 0 THEN 1 ELSE 0 END) as wins,
               AVG(r_result) as avg_r
        FROM trade_outcomes GROUP BY session ORDER BY avg_r DESC
    """)
    session_rows = c.fetchall()

    # By score
    c.execute("""
        SELECT score, COUNT(*) as trades,
               SUM(CASE WHEN r_result > 0 THEN 1 ELSE 0 END) as wins,
               AVG(r_result) as avg_r
        FROM trade_outcomes GROUP BY score ORDER BY score DESC
    """)
    score_rows = c.fetchall()

    # By regime
    c.execute("""
        SELECT regime, COUNT(*) as trades,
               SUM(CASE WHEN r_result > 0 THEN 1 ELSE 0 END) as wins,
               AVG(r_result) as avg_r
        FROM trade_outcomes GROUP BY regime ORDER BY avg_r DESC
    """)
    regime_rows = c.fetchall()

    # By kill zone
    c.execute("""
        SELECT kill_zone, COUNT(*) as trades,
               SUM(CASE WHEN r_result > 0 THEN 1 ELSE 0 END) as wins,
               AVG(r_result) as avg_r
        FROM trade_outcomes GROUP BY kill_zone ORDER BY avg_r DESC
    """)
    kz_rows = c.fetchall()

    # By inst flow
    c.execute("""
        SELECT inst_flow, COUNT(*) as trades,
               SUM(CASE WHEN r_result > 0 THEN 1 ELSE 0 END) as wins,
               AVG(r_result) as avg_r
        FROM trade_outcomes GROUP BY inst_flow ORDER BY avg_r DESC
    """)
    inst_rows = c.fetchall()

    # Recent trades
    c.execute("""
        SELECT timestamp, pair, direction, score, session, regime,
               kill_zone, inst_flow, outcome, r_result
        FROM trade_outcomes ORDER BY timestamp DESC LIMIT 20
    """)
    recent = c.fetchall()

    # Total signals fired
    c.execute("SELECT COUNT(*) FROM signals")
    total_signals = c.fetchone()[0]

    conn.close()

    def table_rows(rows, headers):
        h = "".join(f"<th>{h}</th>" for h in headers)
        body = ""
        for r in rows:
            cells = ""
            for i, cell in enumerate(r):
                val = cell if cell is not None else "-"
                if isinstance(val, float):
                    color = "#00c853" if val > 0 else "#ff1744" if val < 0 else "#fff"
                    cells += f'<td style="color:{color}">{round(val,2)}</td>'
                else:
                    cells += f"<td>{val}</td>"
            body += f"<tr>{cells}</tr>"
        return f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>HC Apex Performance Report</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body {{ background:#0a0a14; color:#e0e0ff; font-family:monospace; padding:20px; }}
            h1 {{ color:#7c4dff; }} h2 {{ color:#00c853; margin-top:30px; }}
            .stats {{ display:flex; gap:20px; flex-wrap:wrap; margin:20px 0; }}
            .card {{ background:#12122a; border:1px solid #2a2a4a; border-radius:8px; padding:15px 25px; min-width:140px; }}
            .card .val {{ font-size:2em; font-weight:bold; }}
            .card .lbl {{ color:#888; font-size:0.8em; }}
            .green {{ color:#00c853; }} .red {{ color:#ff1744; }} .yellow {{ color:#ffd600; }}
            table {{ width:100%; border-collapse:collapse; margin:10px 0 25px; }}
            th {{ background:#1a1a3a; color:#7c4dff; padding:8px; text-align:left; }}
            td {{ padding:7px 8px; border-bottom:1px solid #1a1a2a; }}
            tr:hover {{ background:#12122a; }}
            .badge {{ padding:2px 8px; border-radius:4px; font-size:0.8em; }}
        </style>
    </head>
    <body>
        <h1>⚡ HC Apex Intelligence Report</h1>
        <p style="color:#555">Auto-refreshes every 30s &nbsp;|&nbsp; Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>

        <div class="stats">
            <div class="card"><div class="val {'green' if wr>=55 else 'red'}">{wr}%</div><div class="lbl">WIN RATE</div></div>
            <div class="card"><div class="val {'green' if avg_r>0 else 'red'}">{round(avg_r,2)}R</div><div class="lbl">AVG R</div></div>
            <div class="card"><div class="val {'green' if pf>=1.5 else 'yellow' if pf>=1 else 'red'}">{pf}</div><div class="lbl">PROFIT FACTOR</div></div>
            <div class="card"><div class="val">{total}</div><div class="lbl">CLOSED TRADES</div></div>
            <div class="card"><div class="val">{wins}</div><div class="lbl">WINS</div></div>
            <div class="card"><div class="val">{total-wins}</div><div class="lbl">LOSSES</div></div>
            <div class="card"><div class="val yellow">{total_signals}</div><div class="lbl">SIGNALS FIRED</div></div>
        </div>

        <h2>📅 By Session</h2>
        {table_rows(session_rows, ["Session","Trades","Wins","Avg R"])}

        <h2>🎯 By Score</h2>
        {table_rows(score_rows, ["Score","Trades","Wins","Avg R"])}

        <h2>⚡ By Regime</h2>
        {table_rows(regime_rows, ["Regime","Trades","Wins","Avg R"])}

        <h2>🕐 By Kill Zone</h2>
        {table_rows(kz_rows, ["Kill Zone","Trades","Wins","Avg R"])}

        <h2>🏦 By Inst Flow</h2>
        {table_rows(inst_rows, ["Inst Flow","Trades","Wins","Avg R"])}

        <h2>📋 Last 20 Trades</h2>
        {table_rows(recent, ["Time","Pair","Dir","Score","Session","Regime","KZ","Inst","Outcome","R"])}
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/")
async def root():
    return {"status": "HC Apex Server running", "endpoints": ["/signal", "/outcome", "/report"]}
