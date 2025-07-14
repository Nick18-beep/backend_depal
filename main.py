# main.py

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
import yaml
from tkinter import filedialog, messagebox
from collections import defaultdict
from PIL import Image

# Import locali dai moduli src
from src.config import API_BASE_URL
from src.ui_components import ToolTip, YamlEditorWindow
from src.utils import format_hex_dump, start_open3d_process


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Client di Generazione e Visualizzazione Scena")
        self.geometry("1050x750")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.temp_dir = tempfile.mkdtemp()
        atexit.register(self.cleanup)

        self._setup_main_layout()
        self._setup_ui_frames()
        
        self.status_label = ctk.CTkLabel(self, text="Pronto.", anchor="w")
        self.status_label.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="ew")

        self.load_available_files()

    def _setup_main_layout(self):
        self.grid_columnconfigure(0, weight=1, minsize=350)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

    def _setup_ui_frames(self):
        # Frame sinistro
        self.left_frame = ctk.CTkFrame(self, corner_radius=10)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.setup_generation_frame()
        self.setup_fetching_frame()

        # Frame destro
        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.setup_viewer_frame()

    def setup_generation_frame(self):
        """Crea il frame con le opzioni di generazione della scena."""
        gen_frame = ctk.CTkFrame(self.left_frame)
        gen_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        gen_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(gen_frame, text="Generazione Scena", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="w")

        self.generation_options = {
            "replicator": ctk.BooleanVar(value=True),
            "grip": ctk.BooleanVar(value=False),
            "pinza": ctk.BooleanVar(value=False)
        }
        
        for i, (name, var) in enumerate(self.generation_options.items(), 1):
            ctk.CTkCheckBox(gen_frame, text=name.replace("_", " ").title(), variable=var).grid(row=i, column=0, padx=10, pady=5, sticky="w")

        action_buttons_frame = ctk.CTkFrame(gen_frame, fg_color="transparent")
        action_buttons_frame.grid(row=len(self.generation_options) + 1, column=0, columnspan=2, pady=(10,5), sticky="ew")
        action_buttons_frame.grid_columnconfigure((0,1), weight=1)

        self.generate_button = ctk.CTkButton(action_buttons_frame, text="Genera Scena", command=self.start_generation_thread)
        self.generate_button.grid(row=0, column=0, padx=5, sticky="ew")
        self.regenerate_button = ctk.CTkButton(action_buttons_frame, text="Rigenera Dati", command=self.start_regeneration_thread)
        self.regenerate_button.grid(row=0, column=1, padx=5, sticky="ew")
        
        self.edit_config_button = ctk.CTkButton(gen_frame, text="Modifica Configurazione ⚙️", command=self.open_config_editor, fg_color="#34568B", hover_color="#597aa2")
        self.edit_config_button.grid(row=len(self.generation_options) + 2, column=0, columnspan=2, padx=10, pady=(5, 10), sticky="ew")

    def open_config_editor(self):
        """Apre la finestra dell'editor YAML."""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        if not os.path.exists(config_path):
            messagebox.showerror("Errore", f"File '{os.path.basename(config_path)}' non trovato.")
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not (hasattr(self, 'editor_window') and self.editor_window.winfo_exists()):
                self.editor_window = YamlEditorWindow(self, data, config_path)
            else:
                self.editor_window.focus()
        except Exception as e:
            messagebox.showerror("Errore Lettura YAML", f"Impossibile leggere il file config.yaml:\n{e}")

    def setup_fetching_frame(self):
        fetch_frame = ctk.CTkFrame(self.left_frame)
        fetch_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        fetch_frame.grid_rowconfigure(1, weight=1)
        fetch_frame.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(fetch_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=10, pady=(10,5), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header_frame, text="File sul Server", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w")
        refresh_button = ctk.CTkButton(header_frame, text="\u21BB", width=30, height=30, command=self.load_available_files, font=ctk.CTkFont(size=22), fg_color="transparent", hover_color=self.cget("fg_color"), text_color=("gray10", "gray90"))
        refresh_button.grid(row=0, column=1, sticky="e")

        self.file_tree_frame = ctk.CTkScrollableFrame(fetch_frame, label_text="")
        self.file_tree_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.checkboxes = {}

        bottom_frame = ctk.CTkFrame(fetch_frame)
        bottom_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        bottom_frame.grid_columnconfigure(1, weight=1)
        self.select_all_var = ctk.IntVar(value=0)
        self.select_all_checkbox = ctk.CTkCheckBox(bottom_frame, text="Tutti", variable=self.select_all_var, command=self.toggle_select_all, width=1)
        self.select_all_checkbox.grid(row=0, column=0, padx=(0,10), pady=5, sticky="w")
        self.get_files_button = ctk.CTkButton(bottom_frame, text="Fetch Dati Selezionati", command=self.start_get_files_thread)
        self.get_files_button.grid(row=0, column=1, sticky="ew")

    def setup_viewer_frame(self):
        # Vista lista risultati
        self.results_list_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.results_list_frame.grid(row=0, column=0, sticky="nsew")
        self.results_list_frame.grid_rowconfigure(1, weight=1)
        self.results_list_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.results_list_frame, text="Dati Recuperati", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.results_scroll_frame = ctk.CTkScrollableFrame(self.results_list_frame, label_text="")
        self.results_scroll_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        # Vista visualizzatore singolo file
        self.viewer_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.viewer_frame.grid_rowconfigure(1, weight=1)
        self.viewer_frame.grid_columnconfigure(0, weight=1)
        viewer_header = ctk.CTkFrame(self.viewer_frame, fg_color="transparent")
        viewer_header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.viewer_title = ctk.CTkLabel(viewer_header, text="Visualizzatore", font=ctk.CTkFont(size=18, weight="bold"))
        self.viewer_title.pack(side="left")
        ctk.CTkButton(viewer_header, text="← Indietro", width=100, command=self.show_results_list).pack(side="right")
        self.viewer_content_frame = ctk.CTkFrame(self.viewer_frame, fg_color="transparent")
        self.viewer_content_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        self.show_results_list() # Mostra la lista all'avvio

    def start_generation_thread(self):
        threading.Thread(target=self.generate_scene_logic, args=(False,), daemon=True).start()

    def start_regeneration_thread(self):
        threading.Thread(target=self.generate_scene_logic, args=(True,), daemon=True).start()

    def generate_scene_logic(self, is_regenerate=False):
        endpoint = "/regenerate_data" if is_regenerate else "/generate_scene"
        button = self.regenerate_button if is_regenerate else self.generate_button
        button_text = "Rigenera Dati" if is_regenerate else "Genera Scena"
        
        self.after(0, button.configure, {"state": "disabled", "text": "In corso..."})
        self.after(0, self.update_status, f"{'Rigenerazione' if is_regenerate else 'Generazione'} in corso...")
        
        selected_options = [name for name, var in self.generation_options.items() if var.get()]
        if not selected_options:
            self.after(0, self.update_status, "Errore: Selezionare almeno un'opzione.")
            self.after(0, button.configure, {"state": "normal", "text": button_text})
            return

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
            
            response.raise_for_status()
            self.after(0, self.update_status, "Operazione completata con successo.")
            self.after(0, self.load_available_files)
        except requests.exceptions.RequestException as e:
            self.after(0, self.update_status, f"Errore di connessione: {e}")
        finally:
            self.after(0, button.configure, {"state": "normal", "text": button_text})

    def start_get_files_thread(self):
        threading.Thread(target=self.get_all_files_logic, daemon=True).start()

    def get_all_files_logic(self):
        selected_files = [filename for filename, checkbox in self.checkboxes.items() if checkbox.get() == 1]
        if not selected_files:
            self.update_status("Nessun file selezionato.")
            return

        self.after(0, self.get_files_button.configure, {"state": "disabled", "text": "Recuperando..."})
        if len(selected_files) == 1:
            filename = selected_files[0]
            self.update_status(f"Recuperando file: {filename}...")
            try:
                details = self._fetch_file_details(filename)
                self.after(0, lambda: self.open_viewer_in_frame(filename, details))
                self.after(0, self.update_status, f"Visualizzazione di: {filename}")
            except requests.exceptions.RequestException as e:
                self.after(0, self.update_status, f"Errore nel recuperare {filename}: {e}")
                self.after(0, self.display_results, {"files": {}, "errors": {filename: str(e)}})
            finally:
                self.after(0, self.get_files_button.configure, {"state": "normal", "text": "Fetch Dati Selezionati"})
        else:
            self.update_status(f"Recupero di {len(selected_files)} file...")
            files_found, errors = {}, {}
            for i, filename in enumerate(selected_files, 1):
                self.update_status(f"Recuperando {i}/{len(selected_files)}: {filename}...")
                try:
                    files_found[filename] = self._fetch_file_details(filename)
                except requests.exceptions.RequestException as e:
                    errors[filename] = str(e)
                self.update_idletasks()
            
            self.after(0, self.display_results, {"files": files_found, "errors": errors})
            self.after(0, self.get_files_button.configure, {"state": "normal", "text": "Fetch Dati Selezionati"})
            final_message = f"Recuperati {len(files_found)} file." + (f" Falliti: {len(errors)}." if errors else "")
            self.after(0, self.update_status, final_message)

    def _fetch_file_details(self, filename):
        response = requests.get(f"{API_BASE_URL}/get_document/{filename}", timeout=30)
        response.raise_for_status()
        ext = filename.lower().split('.')[-1]
        mime_types = {'png': 'image/png', 'jpg': 'image/jpeg', 'txt': 'text/plain', 'json': 'application/json'}
        return {
            "data": base64.b64encode(response.content).decode('utf-8'),
            "mime_type": mime_types.get(ext, 'application/octet-stream')
        }

    def build_file_tree(self, file_paths):
        tree = lambda: defaultdict(tree)
        file_tree = tree()
        for path in file_paths:
            parts = path.split('/')
            node = file_tree
            for part in parts[:-1]:
                node = node[part]
            node[parts[-1]] = None
        return file_tree

    def populate_tree_view(self, parent_widget, tree, indent=0, current_path=""):
        sorted_items = sorted(tree.items(), key=lambda x: (isinstance(x[1], defaultdict), x[0]))
        for name, content in sorted_items:
            full_path = os.path.join(current_path, name).replace("\\", "/")
            is_folder = isinstance(content, defaultdict)
            item_frame = ctk.CTkFrame(parent_widget, fg_color="transparent")
            item_frame.pack(fill="x", anchor="w")
            if is_folder:
                self.create_folder_node(item_frame, name, content, indent, full_path)
            else:
                self.create_file_node(item_frame, name, indent, full_path)

    def create_folder_node(self, parent_frame, name, content, indent, full_path):
        row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        row_frame.pack(fill="x")
        children_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        
        toggle_button = ctk.CTkButton(row_frame, text="▶", width=25, fg_color="transparent", text_color=("gray10", "gray90"), command=lambda b=row_frame, cf=children_frame: self.toggle_folder(b, cf))
        toggle_button.pack(side="left", padx=(indent * 20, 5))
        
        folder_label = ctk.CTkLabel(row_frame, text=f"📁  {self.truncate_text(name)}", anchor="w")
        folder_label.pack(side="left", fill="x", expand=True)
        if len(name) > 40: ToolTip(folder_label, name)
        
        self.populate_tree_view(children_frame, content, indent + 1, full_path)
    
    def toggle_folder(self, button, children_frame):
        btn = button.winfo_children()[0] # Get the actual button widget
        if children_frame.winfo_viewable():
            children_frame.pack_forget()
            btn.configure(text="▶")
        else:
            children_frame.pack(fill="x", after=button)
            btn.configure(text="▼")

    def create_file_node(self, parent_frame, name, indent, full_path):
        checkbox = ctk.CTkCheckBox(parent_frame, text=f"  📄 {self.truncate_text(name)}")
        checkbox.pack(fill="x", padx=(indent * 20 + 30, 5), pady=2)
        if len(name) > 40: ToolTip(checkbox, name)
        self.checkboxes[full_path] = checkbox

    def truncate_text(self, text, max_len=40):
        return (text[:max_len-3] + "...") if len(text) > max_len else text

    def load_available_files(self):
        for widget in self.file_tree_frame.winfo_children(): widget.destroy()
        self.checkboxes.clear()
        self.select_all_var.set(0)
        self.update_status("Aggiornamento lista file...")
        try:
            response = requests.get(f"{API_BASE_URL}/list_files", timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "success":
                files = data.get("files", [])
                self.get_files_button.configure(state="normal")
                self.select_all_checkbox.configure(state="normal" if files else "disabled")
                if not files:
                    ctk.CTkLabel(self.file_tree_frame, text="Nessun file sul server.").pack(padx=10, pady=10)
                    self.update_status("Nessun file trovato sul server.")
                    return
                file_tree = self.build_file_tree(files)
                self.populate_tree_view(self.file_tree_frame, file_tree)
                self.update_status(f"Trovati {len(files)} file sul server.")
            else:
                raise requests.exceptions.RequestException(f"Errore API: {data.get('message')}")
        except requests.exceptions.RequestException as e:
            ctk.CTkLabel(self.file_tree_frame, text="❌ Server non raggiungibile.", text_color="gray50").pack(padx=10, pady=10)
            self.get_files_button.configure(state="disabled")
            self.select_all_checkbox.configure(state="disabled")
            self.update_status(f"Server non raggiungibile: {e}")

    def display_results(self, data):
        for widget in self.results_scroll_frame.winfo_children(): widget.destroy()
        files_found, errors = data.get("files", {}), data.get("errors", {})
        for filename, details in files_found.items():
            self.create_result_card(filename, details, success=True)
        for filename, message in errors.items():
            self.create_result_card(filename, {"message": str(message)}, success=False)
        self.show_results_list()

    def create_result_card(self, filename, details, success=True):
        card = ctk.CTkFrame(self.results_scroll_frame, corner_radius=6, border_width=1)
        card.pack(fill="x", padx=5, pady=5)
        card.configure(border_color=("#28a745" if success else "#dc3545"))
        
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", padx=10, pady=5, fill="x", expand=True)
        buttons_frame = ctk.CTkFrame(card, fg_color="transparent")
        buttons_frame.pack(side="right", padx=(0, 5), pady=5)

        if success:
            path_part, name_part = os.path.dirname(filename), os.path.basename(filename)
            if path_part:
                ctk.CTkLabel(info_frame, text=f"In: {self.truncate_text(path_part, 45)}", anchor="w", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray60").pack(fill="x")
            ctk.CTkLabel(info_frame, text=f"- {self.truncate_text(name_part, 50)}", anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x")
            ctk.CTkButton(buttons_frame, text="Visualizza", width=100, command=lambda f=filename, d=details: self.open_viewer_in_frame(f, d)).pack(side="right", padx=(5,0))
            ctk.CTkButton(buttons_frame, text="Salva", width=80, fg_color="#17a2b8", hover_color="#138496", command=lambda f=filename, d=details['data']: self.save_file_dialog(f, d)).pack(side="right")
        else:
            ctk.CTkLabel(info_frame, text=f"❌ {self.truncate_text(filename, 50)}", anchor="w", font=ctk.CTkFont(weight="bold")).pack(fill="x")
            ctk.CTkLabel(info_frame, text=details['message'], text_color="gray60", anchor="w").pack(fill="x")

    def open_viewer_in_frame(self, filename, details):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        self.viewer_title.configure(text=f"Visualizzatore: {self.truncate_text(filename, 50)}")
        if len(filename) > 50: ToolTip(self.viewer_title, filename)
        
        file_bytes = base64.b64decode(details['data'])
        temp_file_path = os.path.join(self.temp_dir, filename.replace("/", os.sep))
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        with open(temp_file_path, 'wb') as f: f.write(file_bytes)
        
        self.show_viewer()
        self.viewer_content_frame.update_idletasks()
        
        file_ext = filename.lower().split('.')[-1]
        mime_type = details.get('mime_type', 'application/octet-stream')

        if file_ext in ['npy', 'pcd']:
            self.display_message_in_viewer(f"Apertura visualizzatore 3D per '{filename}'...")
            start_open3d_process(temp_file_path)
        elif mime_type.startswith('image/'): self.display_image(temp_file_path)
        elif mime_type.startswith('text/') or 'json' in mime_type: self.display_text(temp_file_path)
        else: self.display_binary(temp_file_path)

    def display_image(self, image_path):
        try:
            pil_image = Image.open(image_path)
            container_width, container_height = self.viewer_content_frame.winfo_width() - 20, self.viewer_content_frame.winfo_height() - 20
            if container_width <= 1 or container_height <= 1:
                self.after(50, lambda: self.display_image(image_path))
                return
            
            image_copy = pil_image.copy()
            image_copy.thumbnail((container_width, container_height), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=image_copy, dark_image=image_copy, size=image_copy.size)
            ctk.CTkLabel(self.viewer_content_frame, text="", image=ctk_image).pack(padx=10, pady=10, expand=True)
        except Exception as e:
            self.display_message_in_viewer(f"Errore caricamento immagine:\n{e}")

    def create_textbox_viewer(self, file_path, is_binary=False):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        textbox = ctk.CTkTextbox(self.viewer_content_frame, font=("Consolas", 12), wrap="none")
        textbox.pack(expand=True, fill="both")
        
        content = ""
        if is_binary:
            with open(file_path, 'rb') as f:
                content = format_hex_dump(f.read())
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                try: content = json.dumps(json.loads(raw_content), indent=4) # Pretty-print JSON
                except (json.JSONDecodeError, TypeError): content = raw_content
            except Exception as e:
                content = f"Errore lettura file: {e}"
        
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

    def display_text(self, text_path): self.create_textbox_viewer(text_path)
    def display_binary(self, file_path): self.create_textbox_viewer(file_path, is_binary=True)
    def display_message_in_viewer(self, message):
        for widget in self.viewer_content_frame.winfo_children(): widget.destroy()
        ctk.CTkLabel(self.viewer_content_frame, text=message, font=ctk.CTkFont(size=14)).pack(padx=20, pady=20, expand=True)

    def toggle_select_all(self):
        is_checked = self.select_all_var.get()
        for checkbox in self.checkboxes.values():
            checkbox.select() if is_checked else checkbox.deselect()

    def show_viewer(self):
        self.results_list_frame.grid_forget()
        self.viewer_frame.grid(row=0, column=0, sticky="nsew")

    def show_results_list(self):
        self.viewer_frame.grid_forget()
        self.results_list_frame.grid(row=0, column=0, sticky="nsew")

    def save_file_dialog(self, filename, base64_data):
        try:
            file_bytes = base64.b64decode(base64_data)
            save_path = filedialog.asksaveasfilename(initialfile=os.path.basename(filename), title=f"Salva {filename}")
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(file_bytes)
                self.update_status(f"File '{os.path.basename(filename)}' salvato.")
        except Exception as e:
            self.update_status(f"Errore salvataggio: {e}")

    def update_status(self, message):
        self.status_label.configure(text=message)

    def cleanup(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"Directory temporanea {self.temp_dir} rimossa.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()