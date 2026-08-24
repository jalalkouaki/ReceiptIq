# ReceiptIQ - Privacy-Focused Offline Desktop Expense Tracker

ReceiptIQ is a 100% offline desktop application designed for freelancers, small business owners, and privacy-conscious individuals. It combines local OCR text extraction, SQLCipher database encryption at rest, rule-based expense categorization, recurring subscription detection, electronics warranty tracking, customizable receipt generation, and tax report creation with zero internet or cloud dependencies.

---

## Key Features

- **100% Offline & Private**: Zero external API calls, zero CDNs, zero cloud telemetry. All computation, storage, and OCR run locally on your machine.
- **SQLCipher AES-256 Encryption**: All application data, receipts, user accounts, and configuration are securely stored in an encrypted SQLite database. Passphrases are kept in-memory only.
- **Tkinter GUI Launcher**: Standalone launcher to select custom database paths, log directories, server ports, theme preferences, and enter encryption keys.
- **Local OCR Engine**: Image preprocessing (PIL) + Tesseract OCR text extraction for PNG, JPG, JPEG, WEBP, and PDF receipts.
- **Receipt Generator Section**:
  - **Role-Based Store Configuration**: Administrators can edit and persist the default store name globally; regular users view it in read-only mode.
  - **Dynamic Article & Pricing Inputs**: Add, remove, and manage itemized line items with live subtotal, configurable tax rate, and total calculation.
  - **Interactive Live Preview**: Real-time thermal receipt visualization on-screen.
  - **PDF Export**: Generate and download authentic thermal-style sales receipts as PDF files via ReportLab.
- **Rule-Based Expense Categorization**: Automatic classification into Meals, Software & Subscriptions, Travel, Office Supplies, Utilities, Marketing, Groceries, or Other.
- **Warranty & Subscription Automation**: Auto-suggests warranty logging for electronics purchases and detects recurring vendors for subscription management.
- **Tax & Expense Reports**: Generate itemized CSV exports and PDF tax summary reports.
- **Desktop Notifications**: Cross-platform system notifications via `plyer`.

---

## Installation & System Prerequisites

### 1. System Dependencies

ReceiptIQ requires **Tesseract OCR** and **Poppler** (for PDF receipts):

- **Tesseract OCR (Windows)**:
  - Download the installer from the [UB-Mannheim Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki).
  - Install to `C:\Program Files\Tesseract-OCR` or add it to your system `PATH`.
  - Alternatively, set the environment variable:
    ```cmd
    set TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
    ```

- **Poppler for Windows (PDF conversion support)**:
  - Download Poppler binary release for Windows.
  - Extract and set the environment variable:
    ```cmd
    set POPPLER_PATH=C:\poppler\Library\bin
    ```

### 2. Install Python Dependencies

Make sure Python 3.11+ is installed. Then run:

```bash
pip install -r requirements.txt
```

---

## How to Run ReceiptIQ

Launch the desktop application using:

```bash
python main.py
```

### Default Accounts & Credentials
| **The Paraphrase for encryption** `ReceiptIQKey2026`
| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full admin control panel, store name configuration, user management, and system stats |
| **User** | `user` | `user123` | Standard expense tracking, OCR upload, receipt generation, and dashboard access |

### Launching Procedure
1. The **Tkinter Launcher** window will appear.
2. Select **Admin Login** or **User Login**.
3. Enter your database encryption passphrase when prompted (held in memory only).
4. Enter the username and password in the empty fields.
5. Upon successful authentication, the Tkinter launcher initializes the local Flask backend in a background thread and opens your default browser to:
   `http://localhost:5000/dashboard?token=<JWT_TOKEN>`

---

## Application Directory Structure

```text
receiptiq/
├── app.py                     # Flask application factory and route registrations
├── app_config.json            # Local configuration file (DB_PATH, STORAGE_PATH, LOGS_DIR, etc.)
├── auth.py                    # Password hashing (PBKDF2/bcrypt) and JWT token generation
├── config.py                  # Settings loader, environment variable resolution, and defaults
├── database.py                # SQLCipher database connection & session generator
├── logger.py                  # Rotating file logger (logs/receiptiq.log)
├── main.py                    # Application entry point (Tkinter GUI launcher)
├── models.py                  # SQLAlchemy ORM models (User, Receipt, ExpenseCategory, etc.)
├── notifier.py                # Desktop notifications dispatcher (Plyer)
├── ocr_engine.py              # Image preprocessing, Tesseract OCR, and regex parsers
├── seed.py                    # Initial database seeder for admin user and expense categories
├── routes/                    # Modular Flask blueprints
│   ├── admin_routes.py        # Admin panel, user management, system audit logs
│   ├── auth_routes.py         # Login, logout, password change
│   ├── category_routes.py     # Expense category endpoints
│   ├── generator_routes.py    # Receipt generator, store name config, and PDF creation
│   ├── inventory_routes.py    # Item inventory and low-stock alerts
│   ├── middleware.py          # JWT authentication and Admin role enforcement
│   ├── price_history_routes.py# Price tracking and vendor trend history
│   ├── receipt_routes.py      # Receipt upload, manual tagging, and pagination
│   ├── report_routes.py       # CSV and PDF tax summary export
│   ├── setting_routes.py      # Application settings update
│   ├── subscription_routes.py # Recurring subscriptions tracker
│   └── warranty_routes.py     # Warranty duration and expiry tracker
├── static/                    # Vendored CSS, JS, Chart.js, Bootstrap
├── templates/                 # Jinja2 HTML templates
├── data/                      # Encrypted SQLite database and receipt uploads
└── logs/                      # Application rotating logs
```

---

## Configuration & Environment Variables

ReceiptIQ dynamically loads settings from `app_config.json`, merged with environment variable overrides:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENCRYPTION_KEY` | *(Prompted in Launcher)* | Passphrase used by SQLCipher for AES-256 database encryption. |
| `DB_PATH` | `data/receiptiq.db` | Path to the encrypted SQLite database file. |
| `STORAGE_PATH` | `data/uploads` | Directory for uploaded receipt images and PDFs. |
| `LOGS_DIR` | `logs/` | Directory where rotating logs (`receiptiq.log`) are stored. |
| `STORE_NAME` | `ReceiptIQ Store` | Default business name used across the Receipt Generator. |
| `PORT` | `5000` | Local HTTP port for the web interface. |
| `SECRET_KEY` | `receiptiq-jwt-secret...` | Flask session and JWT signature secret key. |
| `DEFAULT_ADMIN_USER` | `admin` | Initial admin username generated on database seed. |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Initial admin password. |
| `OCR_LANGUAGE` | `eng` | Tesseract language code (e.g., `eng`, `deu`, `fra`). |
