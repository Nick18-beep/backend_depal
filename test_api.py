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
from tkinter import filedialog, messagebox
from collections import defaultdict

# --- NUOVO IMPORT ---
import yaml


from PIL import Image, ImageTk
import open3d as o3d
import numpy as np

# --- CONFIGURAZIONE ---
API_BASE_URL = "http://127.0.0.1:5000"

# --- CLASSE HELPER PER TOOLTIP ---
# (Nessuna modifica qui, lascio il codice collassato per brevità)
class ToolTip(ctk.CTkToplevel):
    """Crea un tooltip che appare quando si passa il mouse su un widget."""
    def __init__(self, widget, text):
        super().__init__(widget)
        self.widget = widget; self.text = text
        self.overrideredirect(True)
        if os.name == 'nt':
            self.transparent_color = '#abcdef'
            self.attributes("-transparentcolor", self.transparent_color)
        self.label = ctk.CTkLabel(self, text=self.text, corner_radius=5, fg_color=("#333333", "#CCCCCC"), text_color=("#FFFFFF", "#000000"), padx=8, pady=4, font=ctk.CTkFont(size=12))
        self.label.pack()
        self.withdraw()
        self.widget.bind("<Enter>", self.show, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")
        self.widget.bind("<Button-1>", self.hide, add="+")
    def show(self, event=None):
        self.deiconify(); x = self.widget.winfo_rootx() + 20; y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.geometry(f"+{x}+{y}"); self.lift()
    def hide(self, event=None):
        self.withdraw()

# --- FUNZIONE PER IL PROCESSO SEPARATO DI OPEN3D ---
# (Nessuna modifica qui, lascio il codice collassato per brevità)
def run_open3d_viewer(file_path):
    """Esegue il visualizzatore di Open3D in un processo separato."""
    try:
        file_ext = file_path.lower().split('.')[-1]
        pcd = o3d.geometry.PointCloud()
        if file_ext == 'npy':
            numpy_array = np.load(file_path, allow_pickle=True)
            if not isinstance(numpy_array, np.ndarray) or numpy_array.ndim != 2: raise ValueError("Il file .npy non contiene un array 2D valido.")
            points = numpy_array[:, :3]; pcd.points = o3d.utility.Vector3dVector(points)
            if numpy_array.shape[1] >= 6:
                colors = numpy_array[:, 3:6]
                if np.max(colors) > 1.0: colors = colors / 255.0
                pcd.colors = o3d.utility.Vector3dVector(colors)
        elif file_ext == 'pcd': pcd = o3d.io.read_point_cloud(file_path)
        else: raise ValueError(f"Formato file non supportato: {file_ext}")
        if not pcd.has_points(): raise ValueError("La nuvola di punti è vuota.")
        o3d.visualization.draw_geometries([pcd])
    except Exception as e: print(f"[Processo Open3D] Errore: {e}")

# --- NUOVA CLASSE PER L'EDITOR YAML ---

# Assicurati che questi import siano presenti all'inizio del tuo file




# --- CLASSE EDITOR YAML AGGIORNATA CON SCROLL FUNZIONANTE ---
# Assicurati che questi import siano presenti all'inizio del tuo file
from tkinter import filedialog, messagebox
import yaml

# --- CLASSE EDITOR YAML AGGIORNATA CON SCROLL ROBUSTO ---

class YamlEditorWindow(ctk.CTkToplevel):
    """Una finestra per modificare un file YAML, con funzione di ricerca e scroll robusto."""
    def __init__(self, master, yaml_data, file_path):
        super().__init__(master)
        self.transient(master)
        self.grab_set()
        self.title("Editor Configurazione YAML")
        self.geometry("800x700")

        self.yaml_data = yaml_data
        self.file_path = file_path
        self.widgets = {}
        
        self.search_map = []
        self.search_results = []
        self.current_search_index = -1
        self.last_highlighted_widget = None

        # Frame principale
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Frame per la ricerca
        search_frame = ctk.CTkFrame(main_frame)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)
        
        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Cerca parametro...")
        self.search_entry.grid(row=0, column=0, padx=(5,5), pady=5, sticky="ew")
        self.search_entry.bind("<Return>", self._perform_search)

        search_button = ctk.CTkButton(search_frame, text="Cerca", width=100, command=self._perform_search)
        search_button.grid(row=0, column=1, padx=(0,5), pady=5)
        
        find_next_button = ctk.CTkButton(search_frame, text="Trova Succ.", width=100, command=lambda: self._perform_search(find_next=True))
        find_next_button.grid(row=0, column=2, padx=(0,5), pady=5)
        
        self.search_status_label = ctk.CTkLabel(search_frame, text="", width=120)
        self.search_status_label.grid(row=0, column=3, padx=(5,5), pady=5)

        # Frame scrollabile
        self.scrollable_frame = ctk.CTkScrollableFrame(main_frame, label_text="Parametri di Configurazione")
        self.scrollable_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        
        self.widgets = self._build_ui_recursive(self.scrollable_frame, self.yaml_data)

        # Pulsanti Salva e Annulla
        save_button = ctk.CTkButton(main_frame, text="Salva e Chiudi", command=self.save_and_close)
        save_button.grid(row=2, column=0, padx=(0, 5), pady=(5,0), sticky="ew")
        cancel_button = ctk.CTkButton(main_frame, text="Annulla", command=self.destroy, fg_color="gray50", hover_color="gray40")
        cancel_button.grid(row=2, column=1, padx=(5, 0), pady=(5,0), sticky="ew")

    def _build_ui_recursive(self, parent, data_node, indent=0):
        # Questa funzione non è cambiata
        if isinstance(data_node, dict):
            widget_dict = {}
            for key, value in data_node.items():
                frame = ctk.CTkFrame(parent, fg_color="transparent")
                frame.pack(fill="x", anchor="w", padx=(indent * 20, 0))
                
                label = ctk.CTkLabel(frame, text=f"{key}:", font=ctk.CTkFont(weight="bold"))
                label.pack(side="top", anchor="w", pady=(5, 2))
                self.search_map.append(label)
                
                widget_dict[key] = self._build_ui_recursive(frame, value, indent + 1)
            return widget_dict
        elif isinstance(data_node, list):
            widget_list = []
            for i, item in enumerate(data_node):
                frame = ctk.CTkFrame(parent, fg_color="transparent")
                frame.pack(fill="x", anchor="w", padx=(indent * 20, 0))
                label = ctk.CTkLabel(frame, text=f"- Elemento {i}", text_color="gray60")
                label.pack(side="top", anchor="w", pady=(5, 0))
                widget_list.append(self._build_ui_recursive(frame, item, indent + 1))
            return widget_list
        else:
            entry = ctk.CTkEntry(parent, width=400)
            entry.pack(fill="x", expand=True, pady=(0, 5), padx=(indent * 10, 10))
            if data_node is not None:
                entry.insert(0, str(data_node))
            return entry
    
    def _perform_search(self, event=None, find_next=False):
        # Questa funzione non è cambiata
        query = self.search_entry.get().lower()
        if not query:
            return

        if self.last_highlighted_widget and self.last_highlighted_widget.winfo_exists():
            self.last_highlighted_widget.configure(fg_color="transparent")
        
        if not find_next or query != getattr(self, "_last_query", None):
            self.search_results = [w for w in self.search_map if query in w.cget("text").lower()]
            self.current_search_index = -1
            self.search_status_label.configure(text=f"Trovati: {len(self.search_results)}")
            self._last_query = query
        
        if not self.search_results:
            self.search_status_label.configure(text="Nessun risultato")
            return
            
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        target_widget = self.search_results[self.current_search_index]
        
        target_widget.configure(fg_color=("#F9E79F", "#6E6E6E"))
        self.last_highlighted_widget = target_widget
        
        self.scroll_to_widget(target_widget)
    
    # --- METODO DI SCORRIMENTO DEFINITIVO ---
    def scroll_to_widget(self, widget):
        """
        Scrolla la vista per rendere visibile il widget.
        Questo metodo è progettato per essere più robusto contro i problemi di timing.
        """
        def _do_scroll():
            # Forza l'aggiornamento di tutte le attività di geometria in sospeso
            self.scrollable_frame.update_idletasks()
            
            try:
                # Altezza totale del contenuto scrollabile
                content_height = self.scrollable_frame._parent_canvas.bbox("all")[3]
                if content_height <= 0: return

                # Posizione Y del frame contenitore del widget
                widget_y = widget.master.winfo_y()

                # Calcola la frazione di scroll
                scroll_fraction = widget_y / content_height
                
                # Applica un piccolo offset per non allineare il widget al bordo superiore
                scroll_fraction = max(0.0, scroll_fraction - 0.05)
                
                self.scrollable_frame._parent_canvas.yview_moveto(scroll_fraction)
            except Exception as e:
                print(f"Non è stato possibile eseguire lo scroll: {e}")

        # Esegui lo scroll dopo un breve ritardo per consentire alla GUI di aggiornarsi
        self.after(100, _do_scroll)


    def _rebuild_data_recursive(self, widget_node, original_data_node):
        # Questa funzione non è cambiata
        if isinstance(widget_node, dict):
            new_dict = {}
            for key, sub_widget in widget_node.items():
                new_dict[key] = self._rebuild_data_recursive(sub_widget, original_data_node[key])
            return new_dict
        elif isinstance(widget_node, list):
            new_list = []
            for i, sub_widget in enumerate(widget_node):
                new_list.append(self._rebuild_data_recursive(sub_widget, original_data_node[i]))
            return new_list
        else:
            value_str = widget_node.get()
            original_type = type(original_data_node)
            try:
                if original_type is bool: return value_str.lower() in ['true', '1', 't', 'y', 'yes']
                if original_data_node is None: return None if value_str.lower() == 'none' else value_str
                return original_type(value_str)
            except (ValueError, TypeError): return value_str

    def save_and_close(self):
        # Questa funzione non è cambiata
        try:
            new_data = self._rebuild_data_recursive(self.widgets, self.yaml_data)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                yaml.dump(new_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            messagebox.showinfo("Successo", f"File '{os.path.basename(self.file_path)}' salvato correttamente.")
            self.master.update_status(f"Configurazione '{os.path.basename(self.file_path)}' aggiornata.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Errore di Salvataggio", f"Impossibile salvare il file di configurazione:\n{e}")
            
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Client di Generazione e Visualizzazione Scena")
        self.geometry("1050x750")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.temp_dir = tempfile.mkdtemp()
        atexit.register(self.cleanup)

        self.grid_columnconfigure(0, weight=1, minsize=350)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self, corner_radius=10)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.setup_generation_frame()
        self.setup_fetching_frame()
        
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.setup_viewer_frame()

        self.status_label = ctk.CTkLabel(self, text="Pronto.", anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")

        self.load_available_files()

    # --- METODI DI SETUP DELL'INTERFACCIA ---

    def setup_generation_frame(self):
        """Crea il frame con le opzioni di generazione della scena."""
        gen_frame = ctk.CTkFrame(self.left_frame)
        gen_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        gen_frame.grid_columnconfigure(0, weight=1)
        
        title_label = ctk.CTkLabel(gen_frame, text="Generazione Scena", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")

        self.generation_options = {
            "replicator": ctk.BooleanVar(value=True),           
            "grip": ctk.BooleanVar(value=False),
            "pinza": ctk.BooleanVar(value=False)
        }
        
        row_counter = 1
        for name, var in self.generation_options.items():
            checkbox = ctk.CTkCheckBox(gen_frame, text=name.replace("_", " ").title(), variable=var)
            checkbox.grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            row_counter += 1

        # --- BOTTONE MODIFICATO E NUOVO BOTTONE ---
        # Frame per i pulsanti di azione
        action_buttons_frame = ctk.CTkFrame(gen_frame, fg_color="transparent")
        action_buttons_frame.grid(row=row_counter, column=0, columnspan=2, pady=(10,5), sticky="ew")
        action_buttons_frame.grid_columnconfigure((0,1), weight=1)

        self.generate_button = ctk.CTkButton(action_buttons_frame, text="Genera Scena", command=self.start_generation_thread)
        self.generate_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.regenerate_button = ctk.CTkButton(action_buttons_frame, text="Rigenera Dati", command=self.start_regeneration_thread)
        self.regenerate_button.grid(row=0, column=1, padx=5, sticky="ew")
        
        # Nuovo pulsante per l'editor di configurazione
        self.edit_config_button = ctk.CTkButton(
            gen_frame, 
            text="Modifica Configurazione ⚙️", 
            command=self.open_config_editor,
            fg_color="#34568B", hover_color="#597aa2"
        )
        self.edit_config_button.grid(row=row_counter + 1, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="ew")


    # --- NUOVO METODO PER APRIRE L'EDITOR ---
    def open_config_editor(self):
        """Apre la finestra dell'editor YAML."""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        
        if not os.path.exists(config_path):
            self.update_status(f"Errore: '{os.path.basename(config_path)}' non trovato.")
            messagebox.showerror("Errore", f"File '{os.path.basename(config_path)}' non trovato nella directory dello script.")
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Evita di aprire finestre multiple
            if hasattr(self, 'editor_window') and self.editor_window.winfo_exists():
                self.editor_window.focus()
            else:
                self.editor_window = YamlEditorWindow(self, data, config_path)

        except Exception as e:
            self.update_status("Errore di lettura del file YAML.")
            messagebox.showerror("Errore Lettura YAML", f"Impossibile leggere o analizzare il file config.yaml:\n{e}")


    # --- TUTTI GLI ALTRI METODI DELLA CLASSE APP RIMANGONO INVARIATI ---
    # (Lascio il codice collassato per brevità)
    def setup_fetching_frame(self):
        fetch_frame = ctk.CTkFrame(self.left_frame); fetch_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew"); fetch_frame.grid_rowconfigure(1, weight=1); fetch_frame.grid_columnconfigure(0, weight=1)
        header_frame = ctk.CTkFrame(fetch_frame, fg_color="transparent"); header_frame.grid(row=0, column=0, padx=10, pady=(10,5), sticky="ew"); header_frame.grid_columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(header_frame, text="File sul Server", font=ctk.CTkFont(size=18, weight="bold")); title_label.grid(row=0, column=0, sticky="w")
        refresh_button = ctk.CTkButton(header_frame, text=u"\u21BB", width=30, height=30, command=self.load_available_files, font=ctk.CTkFont(size=22), fg_color="transparent", hover_color=self.cget("fg_color"), text_color=("gray10", "gray90")); refresh_button.grid(row=0, column=1, sticky="e")
        self.file_tree_frame = ctk.CTkScrollableFrame(fetch_frame, label_text=""); self.file_tree_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew"); self.checkboxes = {}
        bottom_frame = ctk.CTkFrame(fetch_frame); bottom_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew"); bottom_frame.grid_columnconfigure(1, weight=1)
        self.select_all_var = ctk.IntVar(value=0); self.select_all_checkbox = ctk.CTkCheckBox(bottom_frame, text="Tutti", variable=self.select_all_var, command=self.toggle_select_all, width=1); self.select_all_checkbox.grid(row=0, column=0, padx=(0,10), pady=5, sticky="w")
        self.get_files_button = ctk.CTkButton(bottom_frame, text="Fetch Dati Selezionati", command=self.start_get_files_thread); self.get_files_button.grid(row=0, column=1, sticky="ew")
    def setup_viewer_frame(self):
        self.results_list_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent"); self.results_list_frame.grid(row=0, column=0, sticky="nsew"); self.results_list_frame.grid_rowconfigure(1, weight=1); self.results_list_frame.grid_columnconfigure(0, weight=1)
        results_label = ctk.CTkLabel(self.results_list_frame, text="Dati Recuperati", font=ctk.CTkFont(size=18, weight="bold")); results_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.results_scroll_frame = ctk.CTkScrollableFrame(self.results_list_frame, label_text=""); self.results_scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.viewer_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent"); self.viewer_frame.grid_rowconfigure(1, weight=1); self.viewer_frame.grid_columnconfigure(0, weight=1)
        viewer_header = ctk.CTkFrame(self.viewer_frame, fg_color="transparent"); viewer_header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.viewer_title = ctk.CTkLabel(viewer_header, text="Visualizzatore", font=ctk.CTkFont(size=18, weight="bold")); self.viewer_title.pack(side="left")
        back_button = ctk.CTkButton(viewer_header, text="← Indietro", width=100, command=self.show_results_list); back_button.pack(side="right")
        self.viewer_content_frame = ctk.CTkFrame(self.viewer_frame, fg_color="transparent"); self.viewer_content_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.show_results_list()
    def start_generation_thread(self): thread = threading.Thread(target=self.generate_scene_logic, args=(False,), daemon=True); thread.start()
    def start_regeneration_thread(self): thread = threading.Thread(target=self.generate_scene_logic, args=(True,), daemon=True); thread.start()
    def generate_scene_logic(self, is_regenerate=False):
        endpoint = "/regenerate_data" if is_regenerate else "/generate_scene"; button_text = "Rigenerazione..." if is_regenerate else "Generazione..."; success_text = "Dati rigenerati." if is_regenerate else "Scena generata."; button = self.regenerate_button if is_regenerate else self.generate_button
        self.after(0, button.configure, {"state": "disabled", "text": button_text}); self.after(0, self.update_status, f"{button_text} In corso...")
        selected_options = [name for name, var in self.generation_options.items() if var.get()]
        if not selected_options:
            self.after(0, self.update_status, "Errore: Selezionare almeno un'opzione."); self.after(0, button.configure, {"state": "normal", "text": "Rigenera Dati" if is_regenerate else "Genera Scena"}); return
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
            if not is_regenerate and os.path.exists(config_path):
                self.after(0, self.update_status, "Generazione con config.yaml...")
                payload = {'options': json.dumps(selected_options)}
                with open(config_path, 'rb') as config_file_obj:
                    files = {'config_file': ('config.yaml', config_file_obj, 'application/x-yaml')}
                    response = requests.post(f"{API_BASE_URL}{endpoint}", data=payload, files=files, timeout=60)
            else:
                if not is_regenerate: self.after(0, self.update_status, "Info: config.yaml non trovato, procedo senza.")
                response = requests.post(f"{API_BASE_URL}{endpoint}", json={"options": selected_options}, timeout=60)
            response.raise_for_status(); self.after(0, self.update_status, success_text); self.after(0, self.load_available_files)
        except requests.exceptions.RequestException as e: self.after(0, self.update_status, f"Errore di connessione: {e}")
        finally: self.after(0, button.configure, {"state": "normal", "text": "Rigenera Dati" if is_regenerate else "Genera Scena"})
    def start_get_files_thread(self): thread = threading.Thread(target=self.get_all_files_logic, daemon=True); thread.start()
    def get_all_files_logic(self):
        selected_files = [filename for filename, checkbox in self.checkboxes.items() if checkbox.get() == 1]
        if not selected_files: self.update_status("Nessun file selezionato."); return
        self.after(0, self.get_files_button.configure, {"state": "disabled", "text": "Recuperando..."})
        if len(selected_files) == 1:
            filename = selected_files[0]; self.update_status(f"Recuperando file: {filename}...")
            try:
                details = self._fetch_file_details(filename); self.after(0, lambda: self.open_viewer_in_frame(filename, details)); self.after(0, self.update_status, f"Visualizzazione di: {filename}")
            except requests.exceptions.RequestException as e: self.after(0, self.update_status, f"Errore nel recuperare {filename}: {e}"); self.after(0, self.display_results, {"files": {}, "errors": {filename: str(e)}})
            finally: self.after(0, self.get_files_button.configure, {"state": "normal", "text": "Fetch Dati Selezionati"})
        else:
            self.update_status(f"Recupero di {len(selected_files)} file..."); files_found, errors = {}, {}
            for i, filename in enumerate(selected_files):
                self.update_status(f"Recuperando {i+1}/{len(selected_files)}: {filename}...")
                try: files_found[filename] = self._fetch_file_details(filename)
                except requests.exceptions.RequestException as e: errors[filename] = str(e)
                self.update_idletasks()
            self.after(0, self.display_results, {"files": files_found, "errors": errors}); self.after(0, self.get_files_button.configure, {"state": "normal", "text": "Fetch Dati Selezionati"})
            final_message = f"Recuperati {len(files_found)} file.";
            if errors: final_message += f" Falliti: {len(errors)}."
            self.after(0, self.update_status, final_message)
    def _fetch_file_details(self, filename):
        file_url = f"{API_BASE_URL}/get_document/{filename}"; response = requests.get(file_url, timeout=30); response.raise_for_status()
        file_data_b64 = base64.b64encode(response.content).decode('utf-8'); ext = filename.lower().split('.')[-1]
        mime_types = {'png': 'image/png', 'jpg': 'image/jpeg', 'txt': 'text/plain', 'json': 'application/json'}; return {"data": file_data_b64, "mime_type": mime_types.get(ext, 'application/octet-stream')}
    def build_file_tree(self, file_paths):
        tree = lambda: defaultdict(tree); file_tree = tree()
        for path in file_paths:
            parts = path.split('/'); node = file_tree
            for part in parts[:-1]: node = node[part]
            node[parts[-1]] = None
        return file_tree
    def populate_tree_view(self, parent_widget, tree, indent=0):
        sorted_items = sorted(tree.items(), key=lambda x: (isinstance(x[1], defaultdict), x[0]))
        for name, content in sorted_items:
            is_folder = isinstance(content, defaultdict); item_frame = ctk.CTkFrame(parent_widget, fg_color="transparent"); item_frame.pack(fill="x", anchor="w")
            if is_folder: self.create_folder_node(item_frame, name, content, indent)
            else: self.create_file_node(item_frame, name, parent_widget.full_path, indent)
    def create_folder_node(self, parent_frame, name, content, indent):
        full_path = os.path.join(parent_frame.master.full_path, name) if hasattr(parent_frame.master, 'full_path') else name
        row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent"); row_frame.pack(fill="x"); row_frame.grid_columnconfigure(2, weight=1)
        children_frame = ctk.CTkFrame(parent_frame, fg_color="transparent"); children_frame.full_path = full_path
        toggle_button = ctk.CTkButton(row_frame, text="▶", width=25, fg_color="transparent", text_color=("gray10", "gray90")); toggle_button.configure(command=lambda b=toggle_button, cf=children_frame: self.toggle_folder(b, cf)); toggle_button.grid(row=0, column=0, padx=(indent * 20, 5))
        folder_label = ctk.CTkLabel(row_frame, text=f"📁  {self.truncate_text(name)}", anchor="w"); folder_label.grid(row=0, column=1, sticky="w")
        if len(name) > 40: ToolTip(folder_label, name)
        self.populate_tree_view(children_frame, content, indent + 1)
    def create_file_node(self, parent_frame, name, current_path, indent):
        full_path = os.path.join(current_path, name).replace("\\", "/"); checkbox = ctk.CTkCheckBox(parent_frame, text=f"   📄 {self.truncate_text(name)}")
        checkbox.pack(fill="x", padx=(indent * 20 + 25, 5), pady=2)
        if len(name) > 40: ToolTip(checkbox, name)
        self.checkboxes[full_path] = checkbox
    def toggle_folder(self, button, children_frame):
        if children_frame.winfo_viewable(): children_frame.pack_forget(); button.configure(text="▶")
        else: children_frame.pack(fill="x", after=button.master); button.configure(text="▼")
    def truncate_text(self, text, max_len=40): return (text[:max_len-3] + "...") if len(text) > max_len else text
    def load_available_files(self):
        for widget in self.file_tree_frame.winfo_children(): widget.destroy()
        self.checkboxes.clear(); self.select_all_var.set(0); self.update_status("Aggiornamento lista file...")
        try:
            response = requests.get(f"{API_BASE_URL}/list_files", timeout=5); response.raise_for_status(); data = response.json()
            if data.get("status") == "success":
                files = data.get("files", [])
                self.get_files_button.configure(state="normal"); self.select_all_checkbox.configure(state="normal")
                if not files:
                    ctk.CTkLabel(self.file_tree_frame, text="Nessun file sul server.").pack(padx=10, pady=10); self.select_all_checkbox.configure(state="disabled"); self.update_status("Nessun file trovato sul server."); return
                file_tree = self.build_file_tree(files); self.file_tree_frame.full_path = ""; self.populate_tree_view(self.file_tree_frame, file_tree); self.update_status(f"Trovati {len(files)} file sul server.")
            else: raise requests.exceptions.RequestException(f"Errore API: {data.get('message')}")
        except requests.exceptions.RequestException as e:
            ctk.CTkLabel(self.file_tree_frame, text=f"❌ Server non raggiungibile.\nClicca ⟳ per riprovare.", text_color="gray50").pack(padx=10, pady=10, expand=True)
            self.get_files_button.configure(state="disabled"); self.select_all_checkbox.configure(state="disabled"); self.update_status(f"Server non raggiungibile: {e}")
    def display_results(self, data):
        for widget in self.results_scroll_frame.winfo_children(): widget.destroy()
        files_found, errors = data.get("files", {}), data.get("errors", {});
        for filename, details in files_found.items(): self.create_result_card(filename, details, success=True)
        for filename, message in errors.items(): self.create_result_card(filename, {"message": str(message)}, success=False)
        self.show_results_list()
    def create_result_card(self, filename, details, success=True):
        card = ctk.CTkFrame(self.results_scroll_frame, corner_radius=6, border_width=1); card.pack(fill="x", padx=5, pady=5)
        border_color = ("#28a745", "#28a745") if success else ("#dc3545", "#dc3545"); card.configure(border_color=border_color)
        info_frame = ctk.CTkFrame(card, fg_color="transparent"); info_frame.pack(side="left", padx=10, pady=5, fill="x", expand=True)
        buttons_frame = ctk.CTkFrame(card, fg_color="transparent"); buttons_frame.pack(side="right", padx=(0, 5), pady=5, fill="y")
        if success:
            path_part = os.path.dirname(filename); name_part = os.path.basename(filename)
            if path_part:
                truncated_path = self.truncate_text(path_part, 45); path_label = ctk.CTkLabel(info_frame, text=f"[D] In: {truncated_path}", anchor="w", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray60"); path_label.pack(fill="x")
                if len(path_part) > 45: ToolTip(path_label, path_part)
            truncated_name = self.truncate_text(name_part, 50); file_label = ctk.CTkLabel(info_frame, text=f"  - {truncated_name}", anchor="w", font=ctk.CTkFont(weight="bold")); file_label.pack(fill="x")
            if len(name_part) > 50: ToolTip(file_label, name_part)
            view_btn = ctk.CTkButton(buttons_frame, text="Visualizza", width=100, command=lambda f=filename, d=details: self.open_viewer_in_frame(f, d)); view_btn.pack(side="right", padx=(5,0))
            save_btn = ctk.CTkButton(buttons_frame, text="Salva", width=80, fg_color="#17a2b8", hover_color="#138496", command=lambda f=filename, d=details['data']: self.save_file_dialog(f, d)); save_btn.pack(side="right")
        else:
            truncated_name = self.truncate_text(filename, 50); error_file_label = ctk.CTkLabel(info_frame, text=f"❌ {truncated_name}", anchor="w", font=ctk.CTkFont(weight="bold")); error_file_label.pack(fill="x")
            if len(filename) > 50: ToolTip(error_file_label, filename)
            error_msg_label = ctk.CTkLabel(info_frame, text=details['message'], text_color="gray60", anchor="w"); error_msg_label.pack(fill="x")
    def open_viewer_in_frame(self, filename, details):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        self.viewer_title.configure(text=f"Visualizzatore: {self.truncate_text(filename, 50)}")
        if len(filename) > 50: ToolTip(self.viewer_title, filename)
        file_bytes = base64.b64decode(details['data']); temp_file_path = os.path.join(self.temp_dir, filename.replace("/", os.sep)); os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        with open(temp_file_path, 'wb') as f: f.write(file_bytes)
        self.show_viewer(); self.viewer_content_frame.update_idletasks()
        file_ext = filename.lower().split('.')[-1]; mime_type = details.get('mime_type', 'application/octet-stream')
        if file_ext in ['npy', 'pcd']: self.display_message_in_viewer(f"Apertura visualizzatore 3D per '{filename}'..."); multiprocessing.Process(target=run_open3d_viewer, args=(temp_file_path,)).start()
        elif mime_type.startswith('image/'): self.display_image(temp_file_path)
        elif mime_type.startswith('text/') or 'json' in mime_type: self.display_text(temp_file_path)
        else: self.display_binary(temp_file_path)
    def display_image(self, image_path):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        try:
            pil_image = Image.open(image_path); container_width, container_height = self.viewer_content_frame.winfo_width() - 20, self.viewer_content_frame.winfo_height() - 20
            if container_width <= 1 or container_height <= 1: self.after(50, lambda: self.display_image(image_path)); return
            image_copy = pil_image.copy(); image_copy.thumbnail((container_width, container_height), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=image_copy, dark_image=image_copy, size=image_copy.size); image_label = ctk.CTkLabel(self.viewer_content_frame, text="", image=ctk_image); image_label.pack(padx=10, pady=10, expand=True)
        except Exception as e: self.display_message_in_viewer(f"Errore caricamento immagine:\n{e}")
    def create_textbox_viewer(self, file_path, is_binary=False):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        textbox = ctk.CTkTextbox(self.viewer_content_frame, font=("Consolas", 12), wrap="none"); textbox.pack(expand=True, fill="both")
        content = ""
        if is_binary:
            with open(file_path, 'rb') as f: content = self.format_hex_dump(f.read())
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f: raw_content = f.read()
                try: content = json.dumps(json.loads(raw_content), indent=4)
                except (json.JSONDecodeError, TypeError): content = raw_content
            except Exception as e: content = f"Errore lettura file: {e}"
        textbox.insert("1.0", content); textbox.configure(state="disabled")
    def display_text(self, text_path): self.create_textbox_viewer(text_path, is_binary=False)
    def display_binary(self, file_path): self.create_textbox_viewer(file_path, is_binary=True)
    def display_message_in_viewer(self, message):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        ctk.CTkLabel(self.viewer_content_frame, text=message, font=ctk.CTkFont(size=14)).pack(padx=20, pady=20, expand=True)
    def toggle_select_all(self):
        is_checked = self.select_all_var.get()
        for checkbox in self.checkboxes.values():
            if is_checked: checkbox.select()
            else: checkbox.deselect()
    def show_viewer(self): self.results_list_frame.grid_forget(); self.viewer_frame.grid(row=0, column=0, sticky="nsew")
    def show_results_list(self): self.viewer_frame.grid_forget(); self.results_list_frame.grid(row=0, column=0, sticky="nsew")
    def save_file_dialog(self, filename, base64_data):
        try:
            file_bytes = base64.b64decode(base64_data); save_path = filedialog.asksaveasfilename(initialfile=os.path.basename(filename), title=f"Salva {filename}")
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f: f.write(file_bytes)
                self.update_status(f"File '{os.path.basename(filename)}' salvato.")
        except Exception as e: self.update_status(f"Errore salvataggio: {e}")
    def update_status(self, message): self.status_label.configure(text=message)
    def cleanup(self):
        if os.path.isdir(self.temp_dir): shutil.rmtree(self.temp_dir); print(f"Directory temporanea {self.temp_dir} rimossa.")
    @staticmethod
    def format_hex_dump(data, length=16):
        res = [];
        for i in range(0, len(data), length):
            chunk = data[i:i+length]; hex_part = ' '.join(f'{b:02X}' for b in chunk); text_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            res.append(f'{i:08X}  {hex_part:<{length*3}}  |{text_part}|')
        return '\n'.join(res)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()