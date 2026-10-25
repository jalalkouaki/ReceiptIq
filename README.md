# ReceiptIQ - Privacy-Focused Offline Desktop Expense Tracker

ReceiptIQ is a 100% offline desktop application designed for freelancers, small business owners, and privacy-conscious individuals. It combines local OCR text extraction, SQLCipher database encryption at rest, rule-based expense categorization, recurring subscription detection, electronics warranty tracking, customizable receipt generation, and tax report creation with zero internet or cloud dependencies.

---

## Key Features

- **100% Offline & Private**: Zero external API calls, zero CDNs, zero cloud telemetry. All computation, storage, and OCR run locally on your machine.
- **SQLCipher AES-256 Encryption**: All application data, receipts, user accounts, and configuration are securely stored in an encrypted SQLite database.
- **Smart Passphrase & Key Management**:
  - Pre-configured with database encryption passphrase (`ReceiptIQKey2026`).
  - Passphrase is automatically remembered and editable in Settings.
  - Interactive **"Verify"** button inside Settings to test database decryption on demand.
  - In-dialog passphrase validation with clear error feedback and zero lockout loops.
- **Tkinter GUI Control Center & Launcher**:
  - Persistent localhost server controls (Start / Stop Server, live status indicators).
  - Built-in Admin Control Panel with User Management (`Treeview`), live System Statistics, and configurable settings.
  - Enter / Return key support on all login dialogs with **"Show Password"** visibility toggles.
  - Automatic browser launch directly into authenticated dashboards.
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
- **Portable & Privacy-Protected**:
  - Fully relative path architecture (`data/receiptiq.db`, `data/uploads`, `logs/`).
  - No personal local operating system usernames or sensitive machine paths are stored or logged.

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

### Credentials & Security Reference

ReceiptIQ implements two layers of security:

1. **Database Encryption Passphrase (SQLCipher AES-256)**:
   - **Default Key**: `ReceiptIQKey2026`
   - Unlocks the encrypted database file `data/receiptiq.db`.
   - Pre-configured in `app_config.json` and remembered automatically.
   - Can be modified or tested at any time via **Settings & Configuration** using the **"Verify"** button.


| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | Full admin control panel, store name configuration, user management, and system stats |
| **User** | `user` | `user123` | Standard expense tracking, OCR upload, receipt generation, and dashboard access |

### Launching Procedure
1. Run `python main.py`. The **ReceiptIQ Control Center** window appears.
2. The encrypted database unlocks automatically using the saved passphrase (`ReceiptIQKey2026`).
3. Click **Admin Login & Control Panel** (or **User Login & Web Dashboard**).
4. The username is pre-filled. Enter your password (e.g. `admin123` or `user123`) and press **Enter** (or click **Authenticate & Launch**).
5. The local server starts and automatically opens your web browser to the authenticated dashboard:
   - Admin Panel: `http://127.0.0.1:5000/admin?token=<JWT_TOKEN>`
   - User Dashboard: `http://127.0.0.1:5000/dashboard?token=<JWT_TOKEN>`

---

## GUI & Privacy Fixes Applied

The application has been refined with the following fixes:

1. **Database Unlock & Passphrase Resolution**:
   - Fixed the confusion between account passwords and the database encryption key.
   - The database encryption passphrase (`ReceiptIQKey2026`) is now persisted in `app_config.json` and automatically loaded at startup.
   - When entering or testing a passphrase, validation is performed directly inside the unlock modal. If a mistyped passphrase is entered, the modal stays open with an inline error (`"Invalid passphrase! Could not decrypt database."`) so you can retry without entering an endless error loop.
   - Invalid passphrases are never cached in memory, preventing the recurring popup `"failed to unlock database please verify passphrase in settings"` from firing on every button click.

2. **Settings Persistence & Key Verification**:
   - Resolved the issue where the passphrase field was blank in Settings. `config.py` now retains and persists `ENCRYPTION_KEY` when settings are saved.
   - Added a **"Show"** password visibility toggle and an interactive **"Verify"** button directly next to the Encryption Passphrase field in Settings to test database decryption before saving.

3. **Login Usability Improvements**:
   - Login dialogs now pre-fill the username (`admin` or `user`) and place direct focus into the password box.
   - Added password visibility toggles (`Show Password`) to prevent login typos.
   - Added `<Return>` / Enter key bindings to submit login forms instantly.

4. **Privacy Protection & Portability**:
   - Cleaned all hardcoded Windows absolute user paths (`C:/Users/...`) from `app_config.json`, replacing them with portable relative paths (`data/receiptiq.db`, `data/uploads`, `logs`).
   - Sanitized historical application logs in `logs/receiptiq.log` to remove local machine user profile directory references.
   - Retained author name and email in the root `LICENSE` file as well as the dedicated `licence/LICENSE.txt` file.

5. **Safe Database Resource Management**:
   - Wrapped SQLCipher connection checks in `try...finally` blocks to ensure SQLite database connection handles are closed even when decryption fails, preventing database file locks on Windows.

6. **Comprehensive Theme Contrast & Visibility (Dark & Light Mode)**:
   - **Disabled & Readonly Inputs**: Fixed white-on-white text in light mode (e.g. read-only Store Name for standard users, Database/Logs paths in Settings).
   - **Modal Close Buttons**: Fixed `.btn-close` icons that were black on dark modal backgrounds in dark mode.
   - **Navbar Text & Mobile Toggler**: Fixed user profile text and toggler icons disappearing in light theme.
   - **Interactive Chart Theme Sync**: Chart.js labels, grid lines, and legends now dynamically adapt their colors when switching themes.
   - **Alerts & Badges**: Polished alert contrast in dark mode and high-contrast badge text for bright categories (Meals/Utilities).

---

## Application Directory Structure

```text
receiptiq/
├── app.py                     # Flask application factory and route registrations
├── app_config.json            # Portable local configuration file (DB_PATH, STORAGE_PATH, etc.)
├── auth.py                    # Password hashing (PBKDF2/Werkzeug) and JWT token generation
├── config.py                  # Settings loader, relative path resolution, and persistence
├── database.py                # SQLCipher database engine, session generator, and encryption tester
├── LICENSE                    # MIT License with author attribution
├── licence/                   # Dedicated license directory
│   └── LICENSE.txt            # License text copy
├── logger.py                  # Rotating file logger (logs/receiptiq.log)
├── main.py                    # Application entry point (Tkinter GUI launcher)
├── models.py                  # SQLAlchemy ORM models (User, Receipt, ExpenseCategory, etc.)
├── notifier.py                # Desktop notifications dispatcher (Plyer)
├── ocr_engine.py              # Image preprocessing, Tesseract OCR, and regex parsers
├── seed.py                    # Initial database seeder for admin/user accounts & categories
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
├── static/                    # Vendored CSS, JS, Chart.js, Bootstrap (Zero CDN)
├── templates/                 # Jinja2 HTML templates
├── data/                      # Encrypted SQLite database and receipt uploads
│   ├── receiptiq.db           # SQLCipher AES-256 encrypted database
│   └── uploads/               # Uploaded receipt images/PDFs
└── logs/                      # Application rotating logs
    └── receiptiq.log          # Sanitized application log
```

---

## Configuration & Settings

ReceiptIQ loads settings from `app_config.json`, merged with environment variable overrides:

| Setting Key | Default Value | Description |
| :--- | :--- | :--- |
| `ENCRYPTION_KEY` | `ReceiptIQKey2026` | SQLCipher AES-256 database passphrase. |
| `DB_PATH` | `data/receiptiq.db` | Relative or absolute path to the encrypted database. |
| `STORAGE_PATH` | `data/uploads` | Directory for uploaded receipt images and PDFs. |
| `LOGS_DIR` | `logs` | Directory where rotating logs (`receiptiq.log`) are stored. |
| `STORE_NAME` | `ReceiptIQ Store` | Default store name used across the Receipt Generator. |
| `PORT` | `5000` | Local HTTP port for the web interface. |
| `SECRET_KEY` | `receiptiq-jwt-secret...` | Flask session and JWT signature secret key. |
| `DEFAULT_ADMIN_USER` | `admin` | Initial admin username generated on database seed. |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | Initial admin password. |
| `OCR_LANGUAGE` | `eng` | Tesseract language code (e.g., `eng`, `deu`, `fra`). |
| `ENABLE_OLLAMA` | `false` | Optional local Ollama service integration toggle. |

---

## License

MIT License. Copyright (c) 2026 Jalal Kouaki (<jalalkouaki@outlook.com>). See [`LICENSE`](LICENSE) and [`licence/LICENSE.txt`](licence/LICENSE.txt) for details.
