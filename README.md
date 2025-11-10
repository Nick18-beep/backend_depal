# Backend Depal

Desktop client built with CustomTkinter to generate scenes, tweak YAML configs, and visualize point clouds via Open3D. The project is fully managed through a Conda environment so you can reproduce the same setup on Windows, macOS, or Linux.

## Requirements
- Anaconda, Miniconda, or Mambaforge with `conda` on the PATH (`conda --version`).
- Python-compatible GPU drivers if you plan to render heavy Open3D workloads.
- Internet access the first time you create or update the environment.

## Quick start
1. **Create the environment**
   ```bash
   conda env create -f environment.yml
   ```
2. **Activate it**
   ```bash
   conda activate backend-depal
   ```
3. **Run the GUI**
   ```bash
   python main.py
   ```
   The CustomTkinter window should appear, letting you generate data, edit `config.yaml`, and launch the Open3D viewer.

## Useful commands
- Update dependencies to match `environment.yml`:
  ```bash
  conda env update -f environment.yml --prune
  ```
- Remove the environment when you no longer need it:
  ```bash
  conda remove --name backend-depal --all
  ```

## Troubleshooting
- **DLL or display errors on Linux:** install the system Tk packages (`sudo apt install python3-tk`) and ensure you have an X/Wayland session.
- **Slow installs:** add `mamba` to your Conda stack or set `conda config --set channel_priority strict` for faster solves.
- **Open3D crashes:** confirm GPU drivers are up to date; fall back to CPU rendering by disabling GPU backends in Open3D if needed.
