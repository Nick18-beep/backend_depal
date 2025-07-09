import customtkinter as ctk
import requests
import threading
import base64
import os
import io
import tempfile
import shutil
import atexit
import multiprocessing
import json

from PIL import Image, ImageTk
import open3d as o3d
import numpy as np

# --- CONFIGURAZIONE ---
API_BASE_URL = "http://127.0.0.1:5002"

def run_open3d_viewer(file_path):
    try:
        file_ext = file_path.lower().split('.')[-1]
        pcd = o3d.geometry.PointCloud()
        if file_ext == 'npy':
            numpy_array = np.load(file_path)
            if not isinstance(numpy_array, np.ndarray) or numpy_array.ndim != 2: raise ValueError("Il file .npy non contiene un array 2D valido.")
            points = numpy_array[:, :3]
            pcd.points = o3d.utility.Vector3dVector(points)
            if numpy_array.shape[1] >= 6:
                colors = numpy_array[:, 3:6]
                if np.max(colors) > 1.0: colors = colors / 255.0
                pcd.colors = o3d.utility.Vector3dVector(colors)
        elif file_ext == 'pcd':
            pcd = o3d.io.read_point_cloud(file_path)
        else:
            raise ValueError(f"Formato file non supportato: {file_ext}")
        if not pcd.has_points(): raise ValueError("La nuvola di punti è vuota.")
        o3d.visualization.draw_geometries([pcd])
    except Exception as e:
        print(f"[Processo Open3D] Errore: {e}")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Client Documenti con Visualizzatore Integrato")
        self.geometry("950x700")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.temp_dir = tempfile.mkdtemp()
        atexit.register(self.cleanup)

        self.grid_columnconfigure(0, weight=1, minsize=300)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self, corner_radius=10)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.left_frame.grid_rowconfigure(0, weight=0)
        self.left_frame.grid_rowconfigure(1, weight=0) # --- MODIFICA: Riga per "seleziona tutti"
        self.left_frame.grid_rowconfigure(2, weight=1) # --- MODIFICA: Riga per la lista file (si espande)
        self.left_frame.grid_rowconfigure(3, weight=0) # --- MODIFICA: Riga per il pulsante
        self.left_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1) # Permette al titolo di espandersi

        title_label = ctk.CTkLabel(header_frame, text="File Disponibili", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        # --- MODIFICA: Pulsante di ricarica migliorato ---
        # Usa un'icona unicode più pulita e uno stile moderno (senza sfondo/bordi)
        refresh_button = ctk.CTkButton(
            header_frame, 
            text=u"\u21BB", # Simbolo di ricarica (freccia circolare)
            width=30, 
            height=30,
            command=self.load_available_files,
            font=ctk.CTkFont(size=22),
            fg_color="transparent",
            hover_color=self.cget("fg_color"), # Usa il colore di sfondo del frame per l'hover
            text_color=("gray10", "gray90")
        )
        refresh_button.grid(row=0, column=1, padx=(10, 0), sticky="e")
        
        # --- AGGIUNTA: Checkbox "Seleziona Tutti" ---
        select_all_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        select_all_frame.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="w")
        
        self.select_all_var = ctk.IntVar(value=0)
        self.select_all_checkbox = ctk.CTkCheckBox(
            select_all_frame, 
            text="Seleziona/Deseleziona tutti", 
            variable=self.select_all_var,
            command=self.toggle_select_all
        )
        self.select_all_checkbox.pack(anchor="w")

        # --- NOTA: La gestione delle barre di scorrimento è già automatica ---
        # CTkScrollableFrame mostra le barre solo se il contenuto eccede lo spazio.
        # Il comportamento richiesto è quindi quello predefinito.
        self.file_selection_frame = ctk.CTkScrollableFrame(self.left_frame, label_text="")
        self.file_selection_frame.grid(row=2, column=0, padx=20, pady=5, sticky="nsew")
        self.checkboxes = {}
        
        self.get_files_button = ctk.CTkButton(self.left_frame, text="Recupera File Selezionati", command=self.start_get_files_thread)
        self.get_files_button.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        # --- Sezione destra (invariata) ---
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.results_list_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.results_list_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.results_list_frame.grid_rowconfigure(1, weight=1)
        self.results_list_frame.grid_columnconfigure(0, weight=1)

        results_label = ctk.CTkLabel(self.results_list_frame, text="Risultati", font=ctk.CTkFont(size=18, weight="bold"))
        results_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.results_scroll_frame = ctk.CTkScrollableFrame(self.results_list_frame, label_text="")
        self.results_scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        self.viewer_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.viewer_frame.grid_rowconfigure(1, weight=1)
        self.viewer_frame.grid_columnconfigure(0, weight=1)

        viewer_header = ctk.CTkFrame(self.viewer_frame, fg_color="transparent")
        viewer_header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.viewer_title = ctk.CTkLabel(viewer_header, text="Visualizzatore", font=ctk.CTkFont(size=18, weight="bold"))
        self.viewer_title.pack(side="left")
        back_button = ctk.CTkButton(viewer_header, text="← Indietro", width=100, command=self.show_results_list)
        back_button.pack(side="right")

        self.viewer_content_frame = ctk.CTkFrame(self.viewer_frame, fg_color="transparent")
        self.viewer_content_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        self.load_available_files()

    # --- AGGIUNTA: Funzione per gestire la checkbox "Seleziona Tutti" ---
    def toggle_select_all(self):
        """ Seleziona o deseleziona tutte le checkbox dei file. """
        is_checked = self.select_all_var.get()
        for checkbox in self.checkboxes.values():
            if is_checked:
                checkbox.select()
            else:
                checkbox.deselect()

    def load_available_files(self):
        for widget in self.file_selection_frame.winfo_children(): widget.destroy()
        self.checkboxes.clear()
        # --- AGGIUNTA: Resetta la checkbox "Seleziona Tutti" quando si ricarica la lista ---
        self.select_all_var.set(0)
        try:
            response = requests.get(f"{API_BASE_URL}/list_files", timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "success":
                self.get_files_button.configure(state="normal")
                self.select_all_checkbox.configure(state="normal")
                files = data.get("files", [])
                if not files:
                    label = ctk.CTkLabel(self.file_selection_frame, text="Nessun file sul server.")
                    label.pack(padx=10, pady=10)
                    self.select_all_checkbox.configure(state="disabled") # Disabilita se non ci sono file
                    return
                for filename in files:
                    checkbox = ctk.CTkCheckBox(self.file_selection_frame, text=filename)
                    checkbox.pack(padx=10, pady=5, anchor="w")
                    self.checkboxes[filename] = checkbox
            else:
                raise requests.exceptions.RequestException(f"Errore API: {data.get('message')}")
        except requests.exceptions.RequestException as e:
            error_label = ctk.CTkLabel(self.file_selection_frame, text=f"❌ Server non raggiungibile.\nClicca ⟳ per riprovare.", text_color="gray50", wraplength=250)
            error_label.pack(padx=10, pady=10, expand=True)
            self.get_files_button.configure(state="disabled")
            self.select_all_checkbox.configure(state="disabled")

    def create_textbox_viewer(self, file_path, is_binary=False):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        scrollable_frame = ctk.CTkScrollableFrame(self.viewer_content_frame, label_text="")
        scrollable_frame.pack(expand=True, fill="both")
        textbox = ctk.CTkTextbox(scrollable_frame, font=("Consolas", 12), wrap="none")
        textbox.pack(expand=True, fill="both")
        content = ""
        if is_binary:
            with open(file_path, 'rb') as f: content = self.format_hex_dump(f.read())
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f: raw_content = f.read()
                try:
                    json_data = json.loads(raw_content)
                    content = json.dumps(json_data, indent=4)
                except json.JSONDecodeError:
                    content = raw_content
            except Exception as e:
                content = f"Errore durante la lettura del file: {e}"
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

    def cleanup(self):
        if os.path.isdir(self.temp_dir): shutil.rmtree(self.temp_dir)
    def show_viewer(self):
        self.results_list_frame.grid_forget()
        self.viewer_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
    def show_results_list(self):
        self.viewer_frame.grid_forget()
        self.results_list_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
    def open_viewer_in_frame(self, filename, details):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        self.viewer_title.configure(text=f"Visualizzatore: {filename}")
        mime_type = details.get('mime_type', 'application/octet-stream')
        file_bytes = base64.b64decode(details['data'])
        temp_file_path = os.path.join(self.temp_dir, filename)
        with open(temp_file_path, 'wb') as f: f.write(file_bytes)
        self.show_viewer()
        self.viewer_content_frame.update_idletasks()
        file_ext = filename.lower().split('.')[-1]
        if file_ext in ['npy', 'pcd']:
            self.display_message_in_viewer(f"Apertura visualizzatore 3D per '{filename}'...")
            pcd_process = multiprocessing.Process(target=run_open3d_viewer, args=(temp_file_path,))
            pcd_process.start()
        elif mime_type.startswith('image/'):
            self.display_image(temp_file_path)
        elif mime_type.startswith('text/') or mime_type == 'application/json' or file_ext == 'json':
            self.display_text(temp_file_path)
        else:
            self.display_binary(temp_file_path)
    def display_image(self, image_path):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        try:
            pil_image = Image.open(image_path)
            # Dare un po' di margine per non far toccare l'immagine ai bordi
            container_width = self.viewer_content_frame.winfo_width() - 20
            container_height = self.viewer_content_frame.winfo_height() - 20
            
            # Assicurarsi che le dimensioni non siano zero (può accadere all'avvio)
            if container_width <= 0 or container_height <= 0:
                self.after(50, lambda: self.display_image(image_path)) # Riprova tra 50ms
                return
                
            image_copy = pil_image.copy()
            image_copy.thumbnail((container_width, container_height), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=image_copy, dark_image=image_copy, size=image_copy.size)
            image_label = ctk.CTkLabel(self.viewer_content_frame, text="", image=ctk_image)
            image_label.pack(padx=10, pady=10, expand=True)
        except Exception as e:
            self.display_message_in_viewer(f"Errore caricamento immagine:\n{e}")
    def display_text(self, text_path): self.create_textbox_viewer(text_path, is_binary=False)
    def display_binary(self, file_path): self.create_textbox_viewer(file_path, is_binary=True)
    def display_message_in_viewer(self, message):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        msg_label = ctk.CTkLabel(self.viewer_content_frame, text=message, font=ctk.CTkFont(size=14))
        msg_label.pack(padx=20, pady=20, expand=True)
    def create_result_card(self, filename, details, success=True):
        card = ctk.CTkFrame(self.results_scroll_frame, corner_radius=6, border_width=1)
        card.pack(fill="x", padx=5, pady=5)
        label_text = f"✅ {filename}" if success else f"❌ {filename}"
        border_color = ("#28a745", "#28a745") if success else ("#dc3545", "#dc3545")
        card.configure(border_color=border_color)
        label = ctk.CTkLabel(card, text=label_text, font=ctk.CTkFont(weight="bold"))
        label.pack(side="left", padx=10, pady=10)
        if success:
            save_btn = ctk.CTkButton(card, text="Salva", width=80, command=lambda f=filename, d=details['data']: self.save_file_dialog(f, d))
            save_btn.pack(side="right", padx=10, pady=5)
            view_btn = ctk.CTkButton(card, text="Visualizza", width=100, fg_color="#343a40", hover_color="#555c64", command=lambda f=filename, d=details: self.open_viewer_in_frame(f, d))
            view_btn.pack(side="right", padx=(0, 5), pady=5)
        else:
            error_label = ctk.CTkLabel(card, text=details['message'], text_color="gray60")
            error_label.pack(side="right", padx=10)
    def display_results(self, data):
        for widget in self.results_scroll_frame.winfo_children(): widget.destroy()
        files_found = data.get("files", {})
        errors = data.get("errors", {})
        for filename, details in files_found.items(): self.create_result_card(filename, details, success=True)
        for filename, message in errors.items(): self.create_result_card(filename, {"message": message}, success=False)
        self.show_results_list()
    def save_file_dialog(self, filename, base64_data):
        try:
            file_bytes = base64.b64decode(base64_data)
            save_path = ctk.filedialog.asksaveasfilename(initialfile=filename, title=f"Salva {filename}")
            if save_path:
                with open(save_path, 'wb') as f: f.write(file_bytes)
        except Exception as e: print(f"Errore durante il salvataggio di {filename}: {e}")
    def start_get_files_thread(self):
        thread = threading.Thread(target=self.get_files_logic, daemon=True)
        thread.start()
    def get_files_logic(self):
        selected_files = [filename for filename, checkbox in self.checkboxes.items() if checkbox.get() == 1]
        if not selected_files: return
        self.after(0, self.get_files_button.configure, {"state": "disabled", "text": "Caricamento..."})
        try:
            payload = {"documents": selected_files}
            response = requests.post(f"{API_BASE_URL}/get_documents", json=payload, timeout=20)
            response.raise_for_status()
            self.after(0, self.display_results, response.json())
        except requests.exceptions.RequestException as e:
            # Mostra un errore più visibile all'utente
            self.after(0, self.display_results, {"errors": {"Errore di Connessione": str(e)}})
        finally:
            self.after(0, self.get_files_button.configure, {"state": "normal", "text": "Recupera File Selezionati"})
    @staticmethod
    def format_hex_dump(data, length=16):
        res = []
        for i in range(0, len(data), length):
            chunk = data[i:i+length]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            text_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            res.append(f'{i:08X}  {hex_part:<{length*3}}  |{text_part}|')
        return '\n'.join(res)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()