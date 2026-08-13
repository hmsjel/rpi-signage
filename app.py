import os
import sqlite3
from datetime import datetime
import requests
import feedparser
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Sikr at uploads-mappen eksisterer lokalt
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('skaerm.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Tabel til planlagte billeder og videoer
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filnavn TEXT NOT NULL,
            start_dato TEXT,
            slut_dato TEXT
        )
    ''')
    # Tabel til dine egne rullende beskeder fra admin-panelet
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ticker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tekst TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Start med at bygge/tjekke databasen ved opstart
init_db()

# ==========================================
# RUTE 1: INFOSKÆRMEN (VISNING)
# ==========================================
@app.route('/')
def skaerm():
    idag = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    
    # 1. Hent aktive medier, der passer med dags dato
    aktive_medier = conn.execute('''
        SELECT filnavn FROM medier 
        WHERE start_dato <= ? AND slut_dato >= ?
    ''', (idag, idag)).fetchall()
    
    # 2. Hent dine egne beskeder fra admin-panelet
    lokale_nyheder = conn.execute('SELECT tekst FROM ticker').fetchall()
    conn.close()
    
    # Saml alle tekster til nyhedsbjælken i én fælles liste
    nyheds_liste = []
    for nyhed in lokale_nyheder:
        nyheds_liste.append(nyhed['tekst'])
        
    # 3. Hent de seneste live-nyheder fra din specifikke DR URL
    url = "https://www.dr.dk/nyheder/service/feeds/senestenyt"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        # RETTELSE: Vi bruger 'response.content' (rå bytes). 
        # Det løser XML-strukturen, som du sendte i dit eksempel.
        dr_feed = feedparser.parse(response.content)
        
        if dr_feed.entries:
            for entry in dr_feed.entries[:5]:
                nyheds_liste.append(f"++ DR NYHEDER: {entry.title} ++")
        else:
            print("Forbindelse oprettet til DR, men feedets bytes kunne ikke læses.")
            
    except Exception as e:
        print("Kunne ikke hente DR RSS på grund af netværksfejl:", e)
    
    return render_template('skaerm.html', medier=aktive_medier, nyheder=nyheds_liste)

# ==========================================
# RUTE 2: ADMIN PANEL (STYRING)
# ==========================================
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Hvis der sendes en nyhedstekst
        if 'nyhed_tekst' in request.form:
            tekst = request.form['nyhed_tekst']
            if tekst:
                conn.execute('INSERT INTO ticker (tekst) VALUES (?)', (tekst,))
                conn.commit()
                
        # Hvis der uploade en mediefil (billede/video)
        elif 'medie_fil' in request.files:
            fil = request.files['medie_fil']
            start = request.form['start_dato']
            slut = request.form['slut_dato']
            if fil and start and slut:
                filnavn = fil.filename
                fil.save(os.path.join(app.config['UPLOAD_FOLDER'], filnavn))
                conn.execute('INSERT INTO medier (filnavn, start_dato, slut_dato) VALUES (?, ?, ?)',
                             (filnavn, start, slut))
                conn.commit()
                
        return redirect(url_for('admin'))
            
    alle_medier = conn.execute('SELECT * FROM medier').fetchall()
    alle_nyheder = conn.execute('SELECT * FROM ticker').fetchall()
    conn.close()
    return render_template('admin.html', medier=alle_medier, nyheder=alle_nyheder)

# ==========================================
# RUTE 3: SLET MEDIE FRA FILMAPPE OG DATABASE
# ==========================================
@app.route('/slet/<int:id>')
def slet(id):
    conn = get_db_connection()
    medie = conn.execute('SELECT filnavn FROM medier WHERE id = ?', (id,)).fetchone()
    if medie:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], medie['filnavn']))
        except FileNotFoundError:
            pass
        conn.execute('DELETE FROM medier WHERE id = ?', (id,))
        conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# ==========================================
# RUTE 4: SLET NYHEDSTEKST FRA DATABASE
# ==========================================
@app.route('/slet-nyhed/<int:id>')
def slet_nyhed(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM ticker WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# Gør uploadede filer tilgængelige for HTML skærmen
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
