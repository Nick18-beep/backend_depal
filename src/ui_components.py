# src/ui_components.py

"""
Modulo per le componenti dell'interfaccia utente (UI), come ToolTip
e la finestra di editor per i file YAML.
"""

import customtkinter as ctk
import os
import yaml
from tkinter import messagebox

class ToolTip(ctk.CTkToplevel):
    """Crea un tooltip che appare quando si passa il mouse su un widget."""
    def __init__(self, widget, text):
        super().__init__(widget)
        self.widget = widget
        self.text = text
        self.overrideredirect(True)

        # Rendi la finestra trasparente (specifico per Windows)
        if os.name == 'nt':
            self.transparent_color = '#abcdef'
            self.attributes("-transparentcolor", self.transparent_color)

        self.label = ctk.CTkLabel(
            self, text=self.text, corner_radius=5,
            fg_color=("#333333", "#CCCCCC"),
            text_color=("#FFFFFF", "#000000"),
            padx=8, pady=4, font=ctk.CTkFont(size=12)
        )
        self.label.pack()
        self.withdraw()  # Nascondi la finestra all'inizio

        # Associa gli eventi al widget
        self.widget.bind("<Enter>", self.show, add="+")
        self.widget.bind("<Leave>", self.hide, add="+")
        self.widget.bind("<Button-1>", self.hide, add="+")

    def show(self, event=None):
        """Mostra il tooltip vicino al widget."""
        self.deiconify()
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.geometry(f"+{x}+{y}")
        self.lift()

    def hide(self, event=None):
        """Nasconde il tooltip."""
        self.withdraw()


class YamlEditorWindow(ctk.CTkToplevel):
    """Una finestra per modificare un file YAML, con funzione di ricerca e scroll."""
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
        self._create_search_frame(main_frame)

        # Frame scrollabile per i parametri
        self.scrollable_frame = ctk.CTkScrollableFrame(main_frame, label_text="Parametri di Configurazione")
        self.scrollable_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        self.widgets = self._build_ui_recursive(self.scrollable_frame, self.yaml_data)

        # Pulsanti di azione
        self._create_action_buttons(main_frame)

    def _create_search_frame(self, parent):
        search_frame = ctk.CTkFrame(parent)
        search_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Cerca parametro...")
        self.search_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.search_entry.bind("<Return>", self._perform_search)

        ctk.CTkButton(search_frame, text="Cerca", width=100, command=self._perform_search).grid(row=0, column=1, padx=(0,5), pady=5)
        ctk.CTkButton(search_frame, text="Trova Succ.", width=100, command=lambda: self._perform_search(find_next=True)).grid(row=0, column=2, padx=(0,5), pady=5)
        self.search_status_label = ctk.CTkLabel(search_frame, text="", width=120)
        self.search_status_label.grid(row=0, column=3, padx=5, pady=5)

    def _create_action_buttons(self, parent):
        ctk.CTkButton(parent, text="Salva e Chiudi", command=self.save_and_close).grid(row=2, column=0, padx=(0, 5), pady=(5,0), sticky="ew")
        ctk.CTkButton(parent, text="Annulla", command=self.destroy, fg_color="gray50", hover_color="gray40").grid(row=2, column=1, padx=(5, 0), pady=(5,0), sticky="ew")

    def _build_ui_recursive(self, parent, data_node, indent=0):
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

    def scroll_to_widget(self, widget):
        """Scrolla la vista per rendere visibile il widget."""
        def _do_scroll():
            self.scrollable_frame.update_idletasks()
            try:
                content_height = self.scrollable_frame._parent_canvas.bbox("all")[3]
                if content_height <= 0: return
                widget_y = widget.master.winfo_y()
                scroll_fraction = max(0.0, widget_y / content_height - 0.05)
                self.scrollable_frame._parent_canvas.yview_moveto(scroll_fraction)
            except Exception as e:
                print(f"Non è stato possibile eseguire lo scroll: {e}")
        self.after(100, _do_scroll)

    def _rebuild_data_recursive(self, widget_node, original_data_node):
        if isinstance(widget_node, dict):
            return {key: self._rebuild_data_recursive(sub_widget, original_data_node[key]) for key, sub_widget in widget_node.items()}
        if isinstance(widget_node, list):
            return [self._rebuild_data_recursive(sub_widget, original_data_node[i]) for i, sub_widget in enumerate(widget_node)]
        
        value_str = widget_node.get()
        original_type = type(original_data_node)
        try:
            if original_type is bool: return value_str.lower() in ['true', '1', 't', 'y', 'yes']
            if original_data_node is None: return None if value_str.lower() == 'none' else value_str
            return original_type(value_str)
        except (ValueError, TypeError):
            return value_str

    def save_and_close(self):
        """Salva i dati modificati nel file YAML e chiude la finestra."""
        try:
            new_data = self._rebuild_data_recursive(self.widgets, self.yaml_data)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                yaml.dump(new_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            messagebox.showinfo("Successo", f"File '{os.path.basename(self.file_path)}' salvato correttamente.")
            if hasattr(self.master, 'update_status'):
                self.master.update_status(f"Configurazione '{os.path.basename(self.file_path)}' aggiornata.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Errore di Salvataggio", f"Impossibile salvare il file di configurazione:\n{e}")