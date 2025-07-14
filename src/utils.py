# src/utils.py

"""
Modulo contenente funzioni di utilità, come il visualizzatore Open3D
e strumenti di formattazione.
"""

import open3d as o3d
import numpy as np
import multiprocessing

def _visualizer_process_target(file_path):
    """
    Funzione target per il processo di visualizzazione.
    CARICA il file e AVVIA il visualizzatore.
    Questa funzione viene eseguita nel suo processo separato.
    """
    try:
        # Tutta la logica di caricamento è stata spostata qui,
        # all'interno del processo figlio.
        file_ext = file_path.lower().split('.')[-1]
        pcd = o3d.geometry.PointCloud()

        if file_ext == 'npy':
            numpy_array = np.load(file_path, allow_pickle=True)
            if not isinstance(numpy_array, np.ndarray) or numpy_array.ndim != 2:
                raise ValueError("Il file .npy non contiene un array 2D valido.")

            points = numpy_array[:, :3]
            pcd.points = o3d.utility.Vector3dVector(points)

            if numpy_array.shape[1] >= 6:
                colors = numpy_array[:, 3:6]
                if np.max(colors) > 1.0:
                    colors = colors / 255.0
                pcd.colors = o3d.utility.Vector3dVector(colors)

        elif file_ext == 'pcd':
            pcd = o3d.io.read_point_cloud(file_path)
        else:
            raise ValueError(f"Formato file non supportato: {file_ext}")

        if not pcd.has_points():
            raise ValueError("La nuvola di punti è vuota.")

        # Infine, visualizza i dati caricati
        o3d.visualization.draw_geometries([pcd])

    except Exception as e:
        # L'errore verrà stampato nella console del processo figlio
        print(f"[Processo Open3D] Errore durante la visualizzazione: {e}")


def start_open3d_process(file_path):
    """
    Crea e avvia un processo separato per il visualizzatore Open3D.
    Passiamo solo il 'file_path' (una semplice stringa), che è facilmente
    serializzabile ("pickleable").
    """
    process = multiprocessing.Process(target=_visualizer_process_target, args=(file_path,))
    process.start()


def format_hex_dump(data, length=16):
    """Formatta i dati binari in un formato hexdump leggibile."""
    res = []
    for i in range(0, len(data), length):
        chunk = data[i:i + length]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        text_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        res.append(f'{i:08X}  {hex_part:<{length * 3}}  |{text_part}|')
    return '\n'.join(res)