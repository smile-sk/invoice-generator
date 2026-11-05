# Invoice Generator

Desktop app for Windows (PyQt6): keep price lists, build invoices, save to `.xlsx` and
open them in Excel for printing. The UI is in Ukrainian.

## Run (development)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build exe

```powershell
.\build.ps1
```

PyInstaller builds on Windows only. The result lands in `dist\InvoiceGenerator.exe`.
