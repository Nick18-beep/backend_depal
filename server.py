import os
import base64
import mimetypes
import subprocess
import psutil  # Unica dipendenza necessaria per la gestione dei processi
from flask import Flask, request, jsonify

# Trova il percorso assoluto della directory in cui si trova questo script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Definisci la cartella dei documenti
DOCUMENTS_FOLDER = os.path.join(BASE_DIR, 'documents')

# Inizializza l'applicazione Flask
app = Flask(__name__)

# Definisci il percorso del file che conterrà il PID della simulazione
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'simulation.pid')

def get_simulation_status():
    """
    Controlla lo stato della simulazione basandosi sul PID file.
    Restituisce un dizionario con lo stato.
    """
    if not os.path.exists(PID_FILE):
        return {"status": "not_running", "message": "Nessuna simulazione attiva."}
    
    with open(PID_FILE, 'r') as f:
        try:
            pid = int(f.read())
        except (ValueError, TypeError):
            os.remove(PID_FILE)
            return {"status": "not_running", "message": "File PID corrotto e rimosso."}

    if psutil.pid_exists(pid):
        return {"status": "running", "message": f"Simulazione in esecuzione con PID: {pid}"}
    else:
        return {"status": "finished", "message": f"Simulazione (PID: {pid}) completata. Pronta per il recupero dei file."}

# --- ENDPOINT DI CONTROLLO ---

@app.route('/start_simulation', methods=['POST'])
def start_simulation():
    """Avvia la simulazione solo se non ce n'è già una attiva o completata."""
    status_info = get_simulation_status()
    
    if status_info['status'] in ['running', 'finished']:
        print(f"⚠️ Tentativo di avvio fallito. Stato attuale: {status_info['status']}")
        return jsonify(status_info), 409

    print("🚀 Richiesta ricevuta per avviare la simulazione...")
    command = [
        r"C:\isaacsim\python.bat",
        r"C:\Users\cm03696\Desktop\depal project\main.py",
        "--enable", "isaacsim.robot_setup.grasp_editor", "--use-grip"
    ]
    
    try:
        process = subprocess.Popen(command)
        with open(PID_FILE, 'w') as f:
            f.write(str(process.pid))
        
        message = f"Simulazione avviata (PID: {process.pid}). Controlla /simulation_status per aggiornamenti."
        print(f"✅ {message}")
        return jsonify({"status": "starting", "message": message}), 202
        
    except Exception as e:
        print(f"⚠️ ERRORE: Impossibile avviare la simulazione: {e}")
        return jsonify({"status": "error", "message": f"Errore del server: {e}"}), 500

@app.route('/simulation_status', methods=['GET'])
def simulation_status():
    """Restituisce lo stato attuale della simulazione."""
    status_info = get_simulation_status()
    return jsonify(status_info), 200

@app.route('/clear_simulation', methods=['POST'])
def clear_simulation():
    """Pulisce lo stato della simulazione (rimuove il PID file) per permettere un nuovo avvio."""
    status_info = get_simulation_status()
    if status_info['status'] == 'running':
        return jsonify({"status": "error", "message": "Impossibile pulire: la simulazione è ancora in esecuzione."}), 400
    
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
        message = "Stato simulazione resettato. È possibile avviarne una nuova."
        print(f"🧹 {message}")
        return jsonify({"status": "cleared", "message": message}), 200
    else:
        return jsonify({"status": "not_running", "message": "Nessuna simulazione da pulire."}), 200


# --- ENDPOINT PER GESTIONE FILE (invariati) ---

@app.route('/list_files', methods=['GET'])
def list_files():
    # ... (codice invariato)
    available_files = []
    if not os.path.isdir(DOCUMENTS_FOLDER):
        return jsonify({"status": "error", "message": "La cartella 'documents' non esiste sul server."}), 500
    try:
        available_files = [f for f in os.listdir(DOCUMENTS_FOLDER) if os.path.isfile(os.path.join(DOCUMENTS_FOLDER, f))]
        return jsonify({"status": "success", "files": available_files}), 200
    except Exception as e:
        print(f"⚠️ Errore durante la lettura della cartella 'documents': {e}")
        return jsonify({"status": "error", "message": "Errore interno del server durante l'accesso ai file."}), 500

@app.route('/get_documents', methods=['POST'])
def get_documents():
    # ... (codice invariato)
    try:
        data = request.get_json()
        if not data or 'documents' not in data:
            return jsonify({"status": "error", "message": "Richiesta malformata."}), 400
        filenames = data['documents']
        if not isinstance(filenames, list):
            return jsonify({"status": "error", "message": "La chiave 'documents' deve contenere una lista."}), 400
    except Exception:
        return jsonify({"status": "error", "message": "Corpo della richiesta non è un JSON valido."}), 400
    response_payload = { "status": "success", "files": {}, "errors": {} }
    found_any_files = False
    for filename in filenames:
        if not isinstance(filename, str) or "/" in filename or "\\" in filename:
            response_payload["errors"][filename] = "Nome file non valido."
            continue
        file_path = os.path.join(DOCUMENTS_FOLDER, filename)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                    base64_encoded_data = base64.b64encode(file_bytes).decode('utf-8')
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if mime_type is None:
                        mime_type = 'application/octet-stream'
                    response_payload["files"][filename] = {"mime_type": mime_type, "data": base64_encoded_data}
                    found_any_files = True
            except Exception as e:
                print(f"⚠️ Errore durante la lettura del file '{filename}': {e}")
                response_payload["errors"][filename] = "Errore interno durante la lettura del file."
        else:
            response_payload["errors"][filename] = "File non trovato."
    if response_payload["errors"]:
        response_payload["status"] = "partial_success" if found_any_files else "error"
    return jsonify(response_payload), 200

# --- AVVIO APPLICAZIONE ---

if __name__ == '__main__':
    if not os.path.isdir(DOCUMENTS_FOLDER):
        print("*" * 60)
        print(f"ATTENZIONE: Creazione della cartella 'documents' in '{BASE_DIR}'")
        os.makedirs(DOCUMENTS_FOLDER)
        print("Assicurati di metterci dentro i tuoi file.")
        print("*" * 60)
        
    app.run(host='0.0.0.0', port=5002, debug=False)