import os
import base64
import mimetypes
from flask import Flask, request, jsonify

# Trova il percorso assoluto della directory in cui si trova questo script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Definisci la cartella dei documenti
DOCUMENTS_FOLDER = os.path.join(BASE_DIR, 'documents')

# Inizializza l'applicazione Flask
app = Flask(__name__)


# --- NUOVO ENDPOINT PER L'INTERFACCIA GRAFICA ---
@app.route('/list_files', methods=['GET'])
def list_files():
    """
    Restituisce una lista JSON dei file disponibili nella cartella 'documents'.
    Questo endpoint è usato dall'interfaccia grafica per popolare la lista di selezione.
    """
    available_files = []
    if not os.path.isdir(DOCUMENTS_FOLDER):
        return jsonify({"status": "error", "message": "La cartella 'documents' non esiste sul server."}), 500
    
    try:
        # Lista solo i file, ignorando le sottocartelle
        available_files = [f for f in os.listdir(DOCUMENTS_FOLDER) if os.path.isfile(os.path.join(DOCUMENTS_FOLDER, f))]
        return jsonify({"status": "success", "files": available_files}), 200
    except Exception as e:
        print(f"⚠️ Errore durante la lettura della cartella 'documents': {e}")
        return jsonify({"status": "error", "message": "Errore interno del server durante l'accesso ai file."}), 500


@app.route('/get_documents', methods=['POST'])
def get_documents():
    """
    Questo endpoint riceve una richiesta POST con un JSON contenente
    una lista di nomi di file. Restituisce un JSON con i file
    richiesti codificati in Base64. (Logica invariata)
    """
    # 1. Valida la richiesta in arrivo
    try:
        data = request.get_json()
        if not data or 'documents' not in data:
            return jsonify({"status": "error", "message": "Richiesta malformata."}), 400
        filenames = data['documents']
        if not isinstance(filenames, list):
            return jsonify({"status": "error", "message": "La chiave 'documents' deve contenere una lista."}), 400
    except Exception:
        return jsonify({"status": "error", "message": "Corpo della richiesta non è un JSON valido."}), 400

    # 2. Prepara la risposta
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


if __name__ == '__main__':
    if not os.path.isdir(DOCUMENTS_FOLDER):
        print("*" * 60)
        print(f"ATTENZIONE: Creazione della cartella 'documents' in '{BASE_DIR}'")
        os.makedirs(DOCUMENTS_FOLDER)
        print("Assicurati di metterci dentro i tuoi file.")
        print("*" * 60)
        
    app.run(host='0.0.0.0', port=5002, debug=False) # debug=False è raccomandato per non avere doppio output