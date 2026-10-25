import os
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from werkzeug.serving import make_server

from config import load_settings, save_settings
from database import init_db, check_db_encryption, get_db_session
from seed import seed_database
from models import User, Receipt
from auth import verify_password, create_jwt_token, hash_password
from logger import log_event


class FlaskServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=5000):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.app = app
        self.server = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        log_event("server", f"Starting localhost Flask server on {self.host}:{self.port}", level="INFO")
        self.server.serve_forever()

    def shutdown(self):
        log_event("server", "Stopping localhost Flask server", level="INFO")
        self.server.shutdown()


class ServerManager:
    _instance = None

    def __init__(self):
        self.server_thread = None
        self.is_running = False
        self.current_port = 5000

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ServerManager()
        return cls._instance

    def start_server(self, port=5000) -> bool:
        if self.is_running:
            return True

        os.environ["PORT"] = str(port)
        self.current_port = port

        try:
            from app import create_app
            flask_app = create_app()
            self.server_thread = FlaskServerThread(flask_app, host="127.0.0.1", port=port)
            self.server_thread.start()
            self.is_running = True
            time.sleep(0.5)  # Wait briefly for socket binding
            return True
        except Exception as e:
            log_event("server", f"Failed to start server on port {port}: {e}", level="CRITICAL")
            self.is_running = False
            return False

    def stop_server(self):
        if self.is_running and self.server_thread:
            try:
                self.server_thread.shutdown()
            except Exception as e:
                log_event("server", f"Error shutting down server: {e}", level="WARNING")
            self.is_running = False
            self.server_thread = None


class ReceiptIQLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("ReceiptIQ - Localhost Control & Authentication")
        self.root.geometry("480x420")
        self.root.resizable(False, False)

        self.cfg = load_settings()
        self.passphrase = os.environ.get("ENCRYPTION_KEY", "") or self.cfg.get("ENCRYPTION_KEY", "")
        # If passphrase is valid, initialize environment variable
        db_path = self.cfg.get("DB_PATH")
        if self.passphrase and check_db_encryption(db_path, self.passphrase):
            os.environ["ENCRYPTION_KEY"] = self.passphrase
        else:
            self.passphrase = ""

        self.server_mgr = ServerManager.get_instance()
        self.current_user = None
        self.jwt_token = None

        self._apply_style()
        self._show_main_menu()

    def _apply_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        is_dark = self.cfg.get('THEME') == 'dark'
        bg_color = '#1e1e2e' if is_dark else '#f8f9fa'
        fg_color = '#ffffff' if is_dark else '#212529'
        card_bg = '#252538' if is_dark else '#ffffff'
        border_c = '#3b3b58' if is_dark else '#dee2e6'
        accent_c = '#61afef' if is_dark else '#0d6efd'

        self.root.configure(bg=bg_color)
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color, font=('Segoe UI', 10))
        style.configure('Header.TLabel', background=bg_color, font=('Segoe UI', 16, 'bold'), foreground=accent_c)
        style.configure('TButton', font=('Segoe UI', 10), padding=6)
        style.configure('TLabelframe', background=bg_color, bordercolor=border_c)
        style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color, font=('Segoe UI', 10, 'bold'))
        style.configure('TCheckbutton', background=bg_color, foreground=fg_color, font=('Segoe UI', 9))
        
        # Treeview styling
        style.configure('Treeview', background=card_bg, foreground=fg_color, fieldbackground=card_bg, rowheight=26, font=('Segoe UI', 9), bordercolor=border_c)
        style.configure('Treeview.Heading', background=bg_color, foreground=fg_color, font=('Segoe UI', 10, 'bold'), bordercolor=border_c)
        style.map('Treeview', background=[('selected', accent_c)], foreground=[('selected', '#ffffff')])
        
        # Notebook styling
        style.configure('TNotebook', background=bg_color, bordercolor=border_c)
        style.configure('TNotebook.Tab', background=card_bg, foreground=fg_color, padding=[10, 5])
        style.map('TNotebook.Tab', background=[('selected', accent_c)], foreground=[('selected', '#ffffff')])

    def _clear_frame(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def _ensure_passphrase(self) -> bool:
        db_path = self.cfg.get("DB_PATH")

        # If already verified and valid, return True immediately
        if self.passphrase and check_db_encryption(db_path, self.passphrase):
            os.environ["ENCRYPTION_KEY"] = self.passphrase
            return True

        # Check if saved passphrase from config works
        cfg_key = self.cfg.get("ENCRYPTION_KEY", "")
        if cfg_key and check_db_encryption(db_path, cfg_key):
            self.passphrase = cfg_key
            os.environ["ENCRYPTION_KEY"] = cfg_key
            return True

        # Show dialog with inline validation
        dialog = tk.Toplevel(self.root)
        dialog.title("Database Encryption Passphrase")
        dialog.geometry("440x270")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Unlock Encrypted Database", font=("Segoe UI", 12, "bold")).pack(pady=(15, 4))
        ttk.Label(dialog, text="Please enter your SQLCipher database encryption passphrase.\n(Default: ReceiptIQKey2026)", font=("Segoe UI", 9), justify=tk.CENTER).pack(pady=(0, 8))

        lbl_error = ttk.Label(dialog, text="", font=("Segoe UI", 9, "bold"), foreground="#dc3545")
        lbl_error.pack(pady=(0, 4))

        entry = ttk.Entry(dialog, show="*", width=32, font=("Segoe UI", 10))
        if self.passphrase:
            entry.insert(0, self.passphrase)
        entry.pack(pady=4)
        entry.focus()

        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            entry.config(show="" if show_var.get() else "*")
        ttk.Checkbutton(dialog, text="Show Passphrase", variable=show_var, command=toggle_show).pack(pady=2)

        remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Remember passphrase on this device", variable=remember_var).pack(pady=4)

        result = {"success": False}

        def on_ok():
            val = entry.get().strip()
            if not val:
                lbl_error.config(text="Passphrase cannot be empty!")
                return

            if not check_db_encryption(db_path, val):
                lbl_error.config(text="Invalid passphrase! Could not decrypt database.")
                entry.selection_range(0, tk.END)
                entry.focus()
                return

            self.passphrase = val
            os.environ["ENCRYPTION_KEY"] = val
            if remember_var.get():
                save_settings({"ENCRYPTION_KEY": val})
                self.cfg = load_settings()

            result["success"] = True
            dialog.destroy()

        entry.bind("<Return>", lambda e: on_ok())

        btn_box = ttk.Frame(dialog)
        btn_box.pack(pady=12)
        ttk.Button(btn_box, text="Unlock Database", command=on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_box, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=6)

        self.root.wait_window(dialog)

        if not result["success"]:
            self.passphrase = ""
            return False

        return True

    def _show_main_menu(self):
        self._clear_frame()
        self.root.geometry("480x420")

        frame = ttk.Frame(self.root, padding="25 25 25 25")
        frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(frame, text="ReceiptIQ Control Center", style="Header.TLabel")
        header.pack(pady=(0, 5))

        subheader = ttk.Label(frame, text="Privacy-Focused Offline Expense Tracker")
        subheader.pack(pady=(0, 20))

        # Status badge
        srv_status = "RUNNING" if self.server_mgr.is_running else "STOPPED"
        status_color = "green" if self.server_mgr.is_running else "gray"
        lbl_srv = ttk.Label(frame, text=f"● Localhost Server: {srv_status}", font=("Segoe UI", 10, "bold"), foreground=status_color)
        lbl_srv.pack(pady=(0, 15))

        btn_admin = ttk.Button(frame, text="Admin Login & Control Panel", command=lambda: self.open_login_dialog(role="admin"))
        btn_admin.pack(fill=tk.X, pady=8)

        btn_user = ttk.Button(frame, text="User Login & Web Dashboard", command=lambda: self.open_login_dialog(role="user"))
        btn_user.pack(fill=tk.X, pady=8)

        btn_settings = ttk.Button(frame, text="Settings & Configuration", command=self.open_settings_dialog)
        btn_settings.pack(fill=tk.X, pady=8)

        btn_exit = ttk.Button(frame, text="Exit Application", command=self._on_close)
        btn_exit.pack(fill=tk.X, pady=8)

    def open_login_dialog(self, role: str):
        if not self._ensure_passphrase():
            return

        db_path = self.cfg.get("DB_PATH")
        try:
            engine, session_factory = init_db(db_path, self.passphrase)
            session = session_factory()
            seed_database(session)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize database:\n{e}\nPlease verify settings.")
            self.passphrase = ""
            return

        login_win = tk.Toplevel(self.root)
        login_win.title(f"{role.capitalize()} Login")
        login_win.geometry("400x290")
        login_win.transient(self.root)
        login_win.grab_set()

        ttk.Label(login_win, text=f"{role.capitalize()} Authentication", style="Header.TLabel").pack(pady=(15, 4))

        default_hint = "Default password: admin123" if role == "admin" else "Default password: user123"
        ttk.Label(login_win, text=f"Sign in with your account credentials.\n({default_hint})", font=("Segoe UI", 9), justify=tk.CENTER).pack(pady=(0, 8))

        lbl_login_err = ttk.Label(login_win, text="", font=("Segoe UI", 9, "bold"), foreground="#dc3545")
        lbl_login_err.pack(pady=(0, 4))

        form_frame = ttk.Frame(login_win)
        form_frame.pack(pady=4)

        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        user_entry = ttk.Entry(form_frame, width=25)
        user_entry.insert(0, "admin" if role == "admin" else "user")
        user_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        pass_entry = ttk.Entry(form_frame, show="*", width=25)
        pass_entry.grid(row=1, column=1, padx=5, pady=5)

        show_pwd_var = tk.BooleanVar(value=False)
        def toggle_pwd_show():
            pass_entry.config(show="" if show_pwd_var.get() else "*")
        ttk.Checkbutton(form_frame, text="Show Password", variable=show_pwd_var, command=toggle_pwd_show).grid(row=2, column=1, sticky="w", padx=5)

        pass_entry.focus()

        def do_login():
            uname = user_entry.get().strip()
            pwd = pass_entry.get().strip()

            user = session.query(User).filter_by(username=uname).first()
            if not user or not verify_password(pwd, user.password_hash):
                lbl_login_err.config(text=f"Invalid username or password!\n({default_hint})")
                pass_entry.selection_range(0, tk.END)
                pass_entry.focus()
                log_event("auth", f"Login failed for username '{uname}'", level="WARNING", user=uname)
                return

            if role == "admin" and user.role != "admin":
                lbl_login_err.config(text="Admin privileges required!")
                return

            self.jwt_token = create_jwt_token(user.id, user.username, user.role)
            self.current_user = user
            session.close()

            login_win.destroy()

            # Ensure server is running on login
            port = self.cfg.get("PORT", 5000)
            if not self.server_mgr.is_running:
                self.server_mgr.start_server(port)

            if role == "admin":
                self.show_admin_panel()
            else:
                self.show_user_panel()

        login_win.bind("<Return>", lambda e: do_login())

        btn_box = ttk.Frame(login_win)
        btn_box.pack(pady=12)
        ttk.Button(btn_box, text="Authenticate & Launch", command=do_login).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="Cancel", command=lambda: (session.close(), login_win.destroy())).pack(side=tk.LEFT, padx=5)

    def show_admin_panel(self):
        """Build and display the main persistent Admin Control Panel inside Tkinter."""
        self._clear_frame()
        self.root.geometry("820x620")
        self.root.title("ReceiptIQ - Admin Control Panel")

        # Top Control Bar
        top_bar = ttk.Frame(self.root, padding=10)
        top_bar.pack(fill=tk.X)

        lbl_user = ttk.Label(top_bar, text=f"Logged in as Admin: {self.current_user.username}", font=("Segoe UI", 11, "bold"))
        lbl_user.pack(side=tk.LEFT, padx=5)

        btn_logout = ttk.Button(top_bar, text="Logout to Menu", command=self._show_main_menu)
        btn_logout.pack(side=tk.RIGHT, padx=5)

        # Localhost Server Control Section
        srv_frame = ttk.LabelFrame(self.root, text="Localhost Server Control", padding=10)
        srv_frame.pack(fill=tk.X, padx=15, pady=5)

        self.lbl_srv_status = ttk.Label(srv_frame, text="Checking...", font=("Segoe UI", 10, "bold"))
        self.lbl_srv_status.grid(row=0, column=0, padx=10, sticky="w")

        btn_start_srv = ttk.Button(srv_frame, text="Start Server", command=self._start_server_action)
        btn_start_srv.grid(row=0, column=1, padx=5)

        btn_stop_srv = ttk.Button(srv_frame, text="Stop Server", command=self._stop_server_action)
        btn_stop_srv.grid(row=0, column=2, padx=5)

        btn_open_web = ttk.Button(srv_frame, text="Open Web App in Browser", command=self._open_browser_admin)
        btn_open_web.grid(row=0, column=3, padx=10)

        self._update_server_status_ui()

        # User management, system stats, and settings tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Tab 1: User Management
        users_tab = ttk.Frame(notebook, padding=10)
        notebook.add(users_tab, text="User Management")

        # User Table
        columns = ("id", "username", "role", "created_at", "last_login")
        self.tree_users = ttk.Treeview(users_tab, columns=columns, show="headings", height=10)
        self.tree_users.heading("id", text="ID")
        self.tree_users.column("id", width=50)
        self.tree_users.heading("username", text="Username")
        self.tree_users.column("username", width=150)
        self.tree_users.heading("role", text="Role")
        self.tree_users.column("role", width=100)
        self.tree_users.heading("created_at", text="Created At")
        self.tree_users.column("created_at", width=180)
        self.tree_users.heading("last_login", text="Last Login")
        self.tree_users.column("last_login", width=180)

        self.tree_users.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # User Actions Bar
        user_btn_frame = ttk.Frame(users_tab)
        user_btn_frame.pack(fill=tk.X)

        ttk.Button(user_btn_frame, text="+ Add User", command=self._dialog_add_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(user_btn_frame, text="- Delete Selected User", command=self._delete_selected_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(user_btn_frame, text="Refresh Users List", command=self._load_users_into_tree).pack(side=tk.LEFT, padx=5)

        self._load_users_into_tree()

        # Tab 2: System Statistics
        stats_tab = ttk.Frame(notebook, padding=15)
        notebook.add(stats_tab, text="System Statistics")

        self.lbl_stat_users = ttk.Label(stats_tab, text="Total System Users: --", font=("Segoe UI", 12))
        self.lbl_stat_users.pack(anchor="w", pady=10)

        self.lbl_stat_receipts = ttk.Label(stats_tab, text="Total Scanned Receipts: --", font=("Segoe UI", 12))
        self.lbl_stat_receipts.pack(anchor="w", pady=10)

        self.lbl_stat_expenses = ttk.Label(stats_tab, text="Total System Expenses: --", font=("Segoe UI", 12))
        self.lbl_stat_expenses.pack(anchor="w", pady=10)

        ttk.Button(stats_tab, text="Refresh Statistics", command=self._load_system_stats).pack(anchor="w", pady=15)
        self._load_system_stats()

        # Tab 3: Settings
        settings_tab = ttk.Frame(notebook, padding=15)
        notebook.add(settings_tab, text="Settings")

        ttk.Label(settings_tab, text="Database Path:").grid(row=0, column=0, sticky="w", pady=5)
        entry_db = ttk.Entry(settings_tab, width=45)
        entry_db.insert(0, self.cfg.get("DB_PATH"))
        entry_db.grid(row=0, column=1, pady=5, padx=5)

        ttk.Label(settings_tab, text="Logs Directory:").grid(row=1, column=0, sticky="w", pady=5)
        entry_logs = ttk.Entry(settings_tab, width=45)
        entry_logs.insert(0, self.cfg.get("LOGS_DIR"))
        entry_logs.grid(row=1, column=1, pady=5, padx=5)

        ttk.Label(settings_tab, text="Server Port:").grid(row=2, column=0, sticky="w", pady=5)
        entry_port = ttk.Entry(settings_tab, width=45)
        entry_port.insert(0, str(self.cfg.get("PORT", 5000)))
        entry_port.grid(row=2, column=1, pady=5, padx=5)

        ttk.Label(settings_tab, text="Encryption Passphrase:").grid(row=3, column=0, sticky="w", pady=5)
        entry_pass = ttk.Entry(settings_tab, show="*", width=45)
        current_pass = self.passphrase or self.cfg.get("ENCRYPTION_KEY", "")
        if current_pass:
            entry_pass.insert(0, current_pass)
        entry_pass.grid(row=3, column=1, pady=5, padx=5)

        show_admin_key_var = tk.BooleanVar(value=False)
        def toggle_admin_key_show():
            entry_pass.config(show="" if show_admin_key_var.get() else "*")
        ttk.Checkbutton(settings_tab, text="Show", variable=show_admin_key_var, command=toggle_admin_key_show).grid(row=3, column=2, padx=5, sticky="w")

        def save_admin_settings():
            new_pass = entry_pass.get().strip()
            self.passphrase = new_pass
            os.environ["ENCRYPTION_KEY"] = new_pass
            new_cfg = {
                "DB_PATH": entry_db.get().strip(),
                "LOGS_DIR": entry_logs.get().strip(),
                "PORT": int(entry_port.get().strip() or 5000),
                "ENCRYPTION_KEY": new_pass
            }
            save_settings(new_cfg)
            self.cfg = load_settings()
            messagebox.showinfo("Success", "Settings saved successfully!")

        ttk.Button(settings_tab, text="Save Configuration", command=save_admin_settings).grid(row=4, column=1, sticky="e", pady=15)

    def show_user_panel(self):
        """Display User status window keeping local server alive."""
        self._clear_frame()
        self.root.geometry("520x350")
        self.root.title("ReceiptIQ - Localhost Server Running")

        frame = ttk.Frame(self.root, padding=25)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Welcome, {self.current_user.username}!", style="Header.TLabel").pack(pady=(0, 5))
        ttk.Label(frame, text="Your ReceiptIQ local server is running.", font=("Segoe UI", 10)).pack(pady=(0, 15))

        port = self.cfg.get("PORT", 5000)
        self.lbl_user_srv = ttk.Label(frame, text=f"● Localhost Running at http://127.0.0.1:{port}", font=("Segoe UI", 11, "bold"), foreground="green")
        self.lbl_user_srv.pack(pady=10)

        btn_open = ttk.Button(frame, text="Open Web Dashboard in Browser", command=self._open_browser_user)
        btn_open.pack(fill=tk.X, pady=8)

        btn_stop = ttk.Button(frame, text="Stop Server & Logout", command=self._show_main_menu)
        btn_stop.pack(fill=tk.X, pady=8)

        # Open web browser automatically
        self._open_browser_user()

    def _start_server_action(self):
        port = self.cfg.get("PORT", 5000)
        if self.server_mgr.start_server(port):
            messagebox.showinfo("Server Started", f"Localhost server running on http://127.0.0.1:{port}")
        else:
            messagebox.showerror("Server Error", f"Failed to start server on port {port}")
        self._update_server_status_ui()

    def _stop_server_action(self):
        self.server_mgr.stop_server()
        messagebox.showinfo("Server Stopped", "Localhost server has been turned off.")
        self._update_server_status_ui()

    def _update_server_status_ui(self):
        port = self.cfg.get("PORT", 5000)
        if hasattr(self, 'lbl_srv_status'):
            if self.server_mgr.is_running:
                self.lbl_srv_status.config(text=f"● Server RUNNING (http://127.0.0.1:{port})", foreground="green")
            else:
                self.lbl_srv_status.config(text="● Server STOPPED", foreground="red")

    def _open_browser_admin(self):
        port = self.cfg.get("PORT", 5000)
        if not self.server_mgr.is_running:
            self._start_server_action()
        url = f"http://127.0.0.1:{port}/admin?token={self.jwt_token}"
        webbrowser.open(url)

    def _open_browser_user(self):
        port = self.cfg.get("PORT", 5000)
        if not self.server_mgr.is_running:
            self.server_mgr.start_server(port)
        url = f"http://127.0.0.1:{port}/dashboard?token={self.jwt_token}"
        webbrowser.open(url)

    def _load_users_into_tree(self):
        for row in self.tree_users.get_children():
            self.tree_users.delete(row)

        db = next(get_db_session())
        users = db.query(User).all()
        for u in users:
            self.tree_users.insert("", tk.END, values=(
                u.id, u.username, u.role,
                u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "N/A",
                u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never"
            ))

    def _dialog_add_user(self):
        win = tk.Toplevel(self.root)
        win.title("Add New User")
        win.geometry("360x260")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Create User Account", style="Header.TLabel").pack(pady=(15, 10))

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        e_user = ttk.Entry(frame, width=22)
        e_user.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        e_pass = ttk.Entry(frame, show="*", width=22)
        e_pass.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Role:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        cb_role = ttk.Combobox(frame, values=["user", "admin"], state="readonly", width=20)
        cb_role.set("user")
        cb_role.grid(row=2, column=1, padx=5, pady=5)

        def save_user():
            uname = e_user.get().strip()
            pwd = e_pass.get().strip()
            role = cb_role.get()

            if not uname or not pwd:
                messagebox.showerror("Error", "Username and password required!", parent=win)
                return

            db = next(get_db_session())
            existing = db.query(User).filter_by(username=uname).first()
            if existing:
                messagebox.showerror("Error", f"Username '{uname}' already exists!", parent=win)
                return

            new_u = User(username=uname, password_hash=hash_password(pwd), role=role)
            db.add(new_u)
            db.commit()
            messagebox.showinfo("Success", f"User '{uname}' created successfully!", parent=win)
            win.destroy()
            self._load_users_into_tree()

        ttk.Button(win, text="Create Account", command=save_user).pack(pady=15)

    def _delete_selected_user(self):
        selected = self.tree_users.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a user from the list to delete.")
            return

        item_values = self.tree_users.item(selected[0], "values")
        user_id = int(item_values[0])
        username = item_values[1]

        if user_id == self.current_user.id:
            messagebox.showerror("Denied", "You cannot delete your own logged-in admin account!")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{username}'?"):
            db = next(get_db_session())
            target = db.query(User).filter_by(id=user_id).first()
            if target:
                db.delete(target)
                db.commit()
                messagebox.showinfo("Deleted", f"User '{username}' deleted successfully.")
                self._load_users_into_tree()

    def _load_system_stats(self):
        db = next(get_db_session())
        total_users = db.query(User).count()
        total_receipts = db.query(Receipt).count()
        total_expenses = sum(r.total_amount for r in db.query(Receipt).all())

        self.lbl_stat_users.config(text=f"Total System Users: {total_users}")
        self.lbl_stat_receipts.config(text=f"Total Scanned Receipts: {total_receipts}")
        self.lbl_stat_expenses.config(text=f"Total System Expenses: ${total_expenses:,.2f}")

    def open_settings_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("ReceiptIQ Settings")
        win.geometry("540x480")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Application Settings", style="Header.TLabel").pack(pady=(15, 10))

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Database File Path:").grid(row=0, column=0, sticky="w", pady=5)
        db_entry = ttk.Entry(frame, width=32)
        db_entry.insert(0, self.cfg.get("DB_PATH"))
        db_entry.grid(row=0, column=1, pady=5, padx=5)

        def browse_db():
            path = filedialog.asksaveasfilename(title="Select Database File", filetypes=[("SQLite DB", "*.db"), ("All Files", "*.*")])
            if path:
                db_entry.delete(0, tk.END)
                db_entry.insert(0, path)

        ttk.Button(frame, text="Browse...", command=browse_db).grid(row=0, column=2, pady=5)

        ttk.Label(frame, text="Logs Directory:").grid(row=1, column=0, sticky="w", pady=5)
        log_entry = ttk.Entry(frame, width=32)
        log_entry.insert(0, self.cfg.get("LOGS_DIR"))
        log_entry.grid(row=1, column=1, pady=5, padx=5)

        def browse_log():
            path = filedialog.askdirectory(title="Select Logs Directory")
            if path:
                log_entry.delete(0, tk.END)
                log_entry.insert(0, path)

        ttk.Button(frame, text="Browse...", command=browse_log).grid(row=1, column=2, pady=5)

        ttk.Label(frame, text="Encryption Passphrase:").grid(row=2, column=0, sticky="w", pady=5)
        key_entry = ttk.Entry(frame, show="*", width=32)
        current_key = self.passphrase or self.cfg.get("ENCRYPTION_KEY", "")
        if current_key:
            key_entry.insert(0, current_key)
        key_entry.grid(row=2, column=1, pady=5, padx=5)

        key_btn_frame = ttk.Frame(frame)
        key_btn_frame.grid(row=2, column=2, pady=5, sticky="w")

        show_key_var = tk.BooleanVar(value=False)
        def toggle_key_show():
            key_entry.config(show="" if show_key_var.get() else "*")
        ttk.Checkbutton(key_btn_frame, text="Show", variable=show_key_var, command=toggle_key_show).pack(side=tk.LEFT, padx=2)

        def test_key_action():
            test_db = db_entry.get().strip()
            test_k = key_entry.get().strip()
            if not test_k:
                messagebox.showwarning("Passphrase Required", "Please enter a passphrase to test.", parent=win)
                return
            if check_db_encryption(test_db, test_k):
                messagebox.showinfo("Verification Succeeded", "Success! Passphrase correctly unlocks the database.", parent=win)
            else:
                messagebox.showerror("Verification Failed", "Failed! Passphrase does not unlock the database.", parent=win)

        ttk.Button(key_btn_frame, text="Verify", command=test_key_action).pack(side=tk.LEFT, padx=2)

        ttk.Label(frame, text="Server Port:").grid(row=3, column=0, sticky="w", pady=5)
        port_entry = ttk.Entry(frame, width=32)
        port_entry.insert(0, str(self.cfg.get("PORT", 5000)))
        port_entry.grid(row=3, column=1, pady=5, padx=5)

        ttk.Label(frame, text="UI Theme:").grid(row=4, column=0, sticky="w", pady=5)
        theme_combo = ttk.Combobox(frame, values=["dark", "light"], state="readonly", width=29)
        theme_combo.set(self.cfg.get("THEME", "dark"))
        theme_combo.grid(row=4, column=1, pady=5, padx=5)

        ttk.Label(frame, text="OCR Language:").grid(row=5, column=0, sticky="w", pady=5)
        ocr_entry = ttk.Entry(frame, width=32)
        ocr_entry.insert(0, self.cfg.get("OCR_LANGUAGE", "eng"))
        ocr_entry.grid(row=5, column=1, pady=5, padx=5)

        ollama_var = tk.BooleanVar(value=self.cfg.get("ENABLE_OLLAMA", False))
        ollama_check = ttk.Checkbutton(frame, text="Enable Local Ollama Integration", variable=ollama_var)
        ollama_check.grid(row=6, column=1, sticky="w", pady=5)

        def save_and_close():
            new_pass = key_entry.get().strip()
            self.passphrase = new_pass
            os.environ["ENCRYPTION_KEY"] = self.passphrase

            new_cfg = {
                "DB_PATH": db_entry.get().strip(),
                "LOGS_DIR": log_entry.get().strip(),
                "PORT": int(port_entry.get().strip() or 5000),
                "THEME": theme_combo.get(),
                "OCR_LANGUAGE": ocr_entry.get().strip(),
                "ENABLE_OLLAMA": ollama_var.get(),
                "ENCRYPTION_KEY": new_pass
            }
            save_settings(new_cfg)
            self.cfg = load_settings()
            self._apply_style()
            messagebox.showinfo("Success", "Settings saved successfully!", parent=win)
            win.destroy()

        ttk.Button(win, text="Save Settings", command=save_and_close).pack(pady=15)

    def _on_close(self):
        self.server_mgr.stop_server()
        self.root.destroy()


def start_launcher():
    root = tk.Tk()
    app = ReceiptIQLauncher(root)
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    root.mainloop()
