"""Read-only operational summary; never print contacts or credentials."""
import sqlite3
from pathlib import Path
p = Path('/data/leads.sqlite3')
if not p.exists():
    print('No leads recorded yet.')
else:
    with sqlite3.connect('file:/data/leads.sqlite3?mode=ro', uri=True) as db:
        for state, count in db.execute('SELECT state, COUNT(*) FROM leads GROUP BY state'):
            print(state + ':', count)
