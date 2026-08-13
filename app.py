import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('skaerm.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Eksisterende medietabel
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filnavn TEXT NOT NULL,
            start_dato TEXT,
            slut_dato TEXT
        )
    ''')
    # NY TABEL: Til nyhedsteksterne
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ticker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tekst TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# RUTE 1: Infoskærmen (Henter nu både aktive medier og nyheder)
@app.route('/')
def skaerm():
    idag = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    
    aktive_medier = conn.execute('''
        SELECT filnavn FROM medier 
        WHERE start_dato <= ? AND slut_dato >= ?
    ''', (idag, idag)).fetchall()
    
    nyheder = conn.execute('SELECT tekst FROM ticker').fetchall()
    conn.close()
    
    return render_template('skaerm.html', medier=aktive_medier, nyheder=nyheder)

# RUTE 2: Admin panel (Håndterer både medier og nyhedstekster)
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Tjek om det er en nyhedstekst der sendes
        if 'nyhed_tekst' in request.form:
            tekst = request.form['nyhed_tekst']
            if tekst:
                conn.execute('INSERT INTO ticker (tekst) VALUES (?)', (tekst,))
                conn.commit()
        # Ellers er det en mediefil
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

# RUTE 3: Slet medie
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

# RUTE 4: Slet nyhedstekst
@app.route('/slet-nyhed/<int:id>')
def slet_nyhed(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM ticker WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
