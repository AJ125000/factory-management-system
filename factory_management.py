###############################################################################
# Kota Stone Factory – Payment Management System
# Version : 1.1  •  Last updated: June 2025
#
# Key changes
#   • Removed operator_cut_amount
#   • Added entry_date input
#   • Soft‑delete workers (is_active flag)
###############################################################################
import tkinter as tk
from ttkthemes import ThemedTk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
from datetime import timedelta
from typing import Dict, List, Tuple
import pandas as pd
import os, shutil
###############################################################################
class StoneFactoryPaymentSystem:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Kota Stone Factory – Payment Management System")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)

        self.init_database()          # ── DB & schema (auto‑upgrade)
        self.create_widgets()         # ── Build GUI
        self.load_workers()           # ── Populate widgets
        self.load_rates()

    # ─────────────────────────────────────────────────────────────────────── DB
    def init_database(self):
        """Create (or migrate) the SQLite database and tables."""
        self.conn = sqlite3.connect("stone_factory.db")
        self.conn.execute("PRAGMA foreign_keys = ON")  # keep referential safety
        cur = self.conn.cursor()

        # ── workers ──────────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workers(
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL UNIQUE,
                worker_type  TEXT    NOT NULL,             -- 'Machine Operator' | 'Loader'
                created_date DATE    DEFAULT CURRENT_DATE,
                is_active    INTEGER DEFAULT 1             -- 1 = active, 0 = left/archived
            )
        """)

        # ── production_entries ───────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS production_entries(
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id     INTEGER,
                stone_length  REAL    NOT NULL,
                stone_width   REAL    NOT NULL,
                cuts          INTEGER NOT NULL,
                quantity      INTEGER NOT NULL,
                entry_date    DATE    NOT NULL DEFAULT CURRENT_DATE,
                FOREIGN KEY (worker_id) REFERENCES workers(id) ON DELETE RESTRICT
            )
        """)

        # ── rates ────────────────────────────────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rates(
                id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_rate_per_sqft     REAL NOT NULL,
                loader_loading_rate        REAL NOT NULL,
                loader_unloading_base_rate REAL NOT NULL,
                updated_date               DATE DEFAULT CURRENT_DATE
            )
        """)

        # ─────────────────────────── schema‑upgrade for legacy DBs ───────
        # 1. Drop old operator_cut_amount column if still present
        cur.execute("PRAGMA table_info(rates)")
        rate_cols = [row[1] for row in cur.fetchall()]
        if "operator_cut_amount" in rate_cols:
            cur.executescript("""
                ALTER TABLE rates RENAME TO rates_old;
                CREATE TABLE rates(
                    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                    operator_rate_per_sqft     REAL NOT NULL,
                    loader_loading_rate        REAL NOT NULL,
                    loader_unloading_base_rate REAL NOT NULL,
                    updated_date               DATE DEFAULT CURRENT_DATE
                );
                INSERT INTO rates(id, operator_rate_per_sqft,
                                  loader_loading_rate, loader_unloading_base_rate,
                                  updated_date)
                SELECT id, operator_rate_per_sqft,
                       loader_loading_rate, loader_unloading_base_rate,
                       updated_date
                FROM rates_old;
                DROP TABLE rates_old;
            """)

        # 2. Add is_active if DB pre‑dates the flag
        cur.execute("PRAGMA table_info(workers)")
        worker_cols = [row[1] for row in cur.fetchall()]
        if "is_active" not in worker_cols:
            cur.execute("ALTER TABLE workers ADD COLUMN is_active INTEGER DEFAULT 1")

        self.conn.commit()

    # ────────────────────────────────────────────────────────────── GUI setup
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.create_worker_management_tab()
        self.create_production_entry_tab()
        self.create_rates_management_tab()
        self.create_payment_calculation_tab()
        self.create_reports_tab()

    # ───────────────────────────────────────────────────────── worker tab ──
    def create_worker_management_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Worker Management")

        add = ttk.LabelFrame(frame, text="Add New Worker", padding=10)
        add.pack(fill="x", padx=10, pady=5)

        ttk.Label(add, text="Worker Name:").grid(row=0, column=0, padx=5, sticky="w")
        self.worker_name_entry = ttk.Entry(add, width=25)
        self.worker_name_entry.grid(row=0, column=1, padx=5)

        ttk.Label(add, text="Worker Type:").grid(row=0, column=2, padx=5, sticky="w")
        self.worker_type_combo = ttk.Combobox(add, width=18,
                                              values=["Machine Operator", "Loader"])
        self.worker_type_combo.grid(row=0, column=3, padx=5)

        ttk.Button(add, text="Add Worker", command=self.add_worker).grid(row=0, column=4, padx=10)

        # Worker list
        list_frame = ttk.LabelFrame(frame, text="Workers (List – active only)", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("ID", "Name", "Type", "Created", "Active?")
        self.workers_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=15)
        for col in cols:
            self.workers_tree.heading(col, text=col)
            self.workers_tree.column(col, width=140)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.workers_tree.yview)
        self.workers_tree.configure(yscrollcommand=sb.set)
        self.workers_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        ttk.Button(list_frame, text="Archive (soft‑delete) Selected Worker",
                   command=self.archive_worker).pack(pady=5)

    # ───────────────────────────────────────────── production‑entry tab ──
    def create_production_entry_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Production Entry")

        entry = ttk.LabelFrame(frame, text="Add Production Entry", padding=10)
        entry.pack(fill="x", padx=10, pady=5)

        ttk.Label(entry, text="Worker:").grid(row=0, column=0, padx=5, sticky="w")
        self.worker_combo = ttk.Combobox(entry, width=25)
        self.worker_combo.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(entry, text="Stone Length (ft):").grid(row=0, column=2, padx=5, sticky="w")
        self.length_entry = ttk.Entry(entry, width=10)
        self.length_entry.grid(row=0, column=3, padx=5)

        ttk.Label(entry, text="Stone Width (ft):").grid(row=1, column=0, padx=5, sticky="w")
        self.width_entry = ttk.Entry(entry, width=10)
        self.width_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(entry, text="Cuts:").grid(row=1, column=2, padx=5, sticky="w")
        self.cuts_entry = ttk.Entry(entry, width=10)
        self.cuts_entry.grid(row=1, column=3, padx=5)

        ttk.Label(entry, text="Quantity:").grid(row=2, column=0, padx=5, sticky="w")
        self.quantity_entry = ttk.Entry(entry, width=10)
        self.quantity_entry.grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(entry, text="Entry Date (YYYY‑MM‑DD):").grid(row=2, column=2, padx=5, sticky="w")
        self.date_entry = ttk.Entry(entry, width=12)
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        self.date_entry.insert(0, today_str)
        self.date_entry.grid(row=2, column=3, padx=5)

        ttk.Button(entry, text="Add Entry", command=self.add_production_entry)\
            .grid(row=3, column=3, padx=10, pady=5)

        # ---- list of entries ----
        list_f = ttk.LabelFrame(frame, text="Production Entries", padding=10)
        list_f.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("ID", "Worker", "Length", "Width", "Area", "Cuts",
                "Qty", "Date")
        self.entries_tree = ttk.Treeview(list_f, columns=cols, show="headings", height=12)
        for c in cols:
            self.entries_tree.heading(c, text=c)
            self.entries_tree.column(c, width=100)
        sb_e = ttk.Scrollbar(list_f, orient="vertical", command=self.entries_tree.yview)
        self.entries_tree.configure(yscrollcommand=sb_e.set)
        self.entries_tree.pack(side="left", fill="both", expand=True)
        sb_e.pack(side="right", fill="y")

        btn_f = ttk.Frame(list_f)
        btn_f.pack(fill="x", pady=5)
        ttk.Button(btn_f, text="Delete Selected Entry", command=self.delete_production_entry)\
            .pack(side="left", padx=5)
        ttk.Button(btn_f, text="Refresh", command=self.load_production_entries)\
            .pack(side="left", padx=5)

    # ───────────────────────────────────────────────────────── rates tab ──
    def create_rates_management_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Rates Management")

        frm = ttk.LabelFrame(frame, text="Set Wage Rates", padding=20)
        frm.pack(fill="x", padx=10, pady=10)

        op_fr = ttk.LabelFrame(frm, text="Machine Operator", padding=10)
        op_fr.pack(fill="x", pady=8)
        ttk.Label(op_fr, text="Rate per sq ft (₹):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.operator_rate_entry = ttk.Entry(op_fr, width=15)
        self.operator_rate_entry.grid(row=0, column=1, padx=5, pady=5)

        ld_fr = ttk.LabelFrame(frm, text="Loader", padding=10)
        ld_fr.pack(fill="x", pady=8)
        ttk.Label(ld_fr, text="Loading rate per sq ft (₹):").grid(row=0, column=0, padx=5, sticky="w")
        self.loader_loading_entry = ttk.Entry(ld_fr, width=15)
        self.loader_loading_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(ld_fr, text="Unloading base rate per sq ft (₹):")\
            .grid(row=0, column=2, padx=5, sticky="w")
        self.loader_unloading_entry = ttk.Entry(ld_fr, width=15)
        self.loader_unloading_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(frm, text="Save Rates", command=self.save_rates).pack(pady=10)

        cur_fr = ttk.LabelFrame(frame, text="Current Rates", padding=20)
        cur_fr.pack(fill="x", padx=10, pady=10)
        self.rates_display = ttk.Label(cur_fr, text="", font=("Arial", 10))
        self.rates_display.pack()

    # ───────────────────────────────────────────── payment‑calc tab ──
    def create_payment_calculation_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Payment Calculation")

        # date period
        period = ttk.LabelFrame(frame, text="Select Period", padding=10)
        period.pack(fill="x", padx=10, pady=5)

        ttk.Label(period, text="From Date:").grid(row=0, column=0, padx=5, sticky="w")
        self.from_date_entry = ttk.Entry(period, width=12)
        ttk.Label(period, text="To Date:").grid(row=0, column=2, padx=5, sticky="w")
        self.to_date_entry = ttk.Entry(period, width=12)

        today_str = datetime.date.today().strftime("%Y-%m-%d")
        self.from_date_entry.insert(0, today_str)
        self.to_date_entry.insert(0, today_str)

        self.from_date_entry.grid(row=0, column=1, padx=5)
        self.to_date_entry.grid(row=0, column=3, padx=5)

        qf = ttk.Frame(period)
        qf.grid(row=1, column=0, columnspan=4, pady=8)
        ttk.Button(qf, text="Today", command=lambda: self.set_period("today")).pack(side="left", padx=2)
        ttk.Button(qf, text="This Week", command=lambda: self.set_period("week")).pack(side="left", padx=2)
        ttk.Button(qf, text="Half Month", command=lambda: self.set_period("half_month")).pack(side="left", padx=2)
        ttk.Button(qf, text="This Month", command=lambda: self.set_period("month")).pack(side="left", padx=2)

        ttk.Button(period, text="Calculate Payments", command=self.calculate_payments)\
            .grid(row=0, column=4, padx=10)

        # result list
        res_f = ttk.LabelFrame(frame, text="Payment Calculations", padding=10)
        res_f.pack(fill="both", expand=True, padx=10, pady=5)
        cols = ("Worker", "Type", "Total Area (sq ft)", "Total Cuts",
                "Calculated Payment", "Details")
        self.payments_tree = ttk.Treeview(res_f, columns=cols, show="headings", height=15)
        for c in cols:
            self.payments_tree.heading(c, text=c)
            self.payments_tree.column(c, width=160)
        sb_p = ttk.Scrollbar(res_f, orient="vertical", command=self.payments_tree.yview)
        self.payments_tree.configure(yscrollcommand=sb_p.set)
        self.payments_tree.pack(side="left", fill="both", expand=True)
        sb_p.pack(side="right", fill="y")

        ttk.Button(res_f, text="Export to Excel", command=self.export_payments).pack(pady=5)

    # ───────────────────────────────────────────────────────── reports tab ──
    def create_reports_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Reports")

        rep_frame = ttk.LabelFrame(frame, text="Generate Reports", padding=10)
        rep_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(rep_frame, text="Report Type:").grid(row=0, column=0, padx=5, sticky="w")
        self.report_type_combo = ttk.Combobox(rep_frame, width=22,
                                              values=["Worker Summary", "Daily Production", "Monthly Summary"])
        self.report_type_combo.grid(row=0, column=1, padx=5)
        ttk.Button(rep_frame, text="Generate Report", command=self.generate_report)\
            .grid(row=0, column=2, padx=10)

        disp = ttk.LabelFrame(frame, text="Report", padding=10)
        disp.pack(fill="both", expand=True, padx=10, pady=5)
        self.report_text = tk.Text(disp, wrap="word", height=20)
        sb_r = ttk.Scrollbar(disp, orient="vertical", command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=sb_r.set)
        self.report_text.pack(side="left", fill="both", expand=True)
        sb_r.pack(side="right", fill="y")

    # ─────────────────────────────────────────── worker operations ──
    def add_worker(self):
        name = self.worker_name_entry.get().strip()
        wtype = self.worker_type_combo.get()
        if not name or not wtype:
            messagebox.showerror("Error", "Please fill all fields")
            return
        try:
            self.conn.execute(
                "INSERT INTO workers(name, worker_type) VALUES(?,?)",
                (name, wtype)
            )
            self.conn.commit()
            self.worker_name_entry.delete(0, tk.END)
            self.worker_type_combo.set("")
            self.load_workers()
            messagebox.showinfo("Success", "Worker added")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Worker name already exists")
        except Exception as exc:
            messagebox.showerror("Error", f"Error adding worker: {exc}")

    def archive_worker(self):
        sel = self.workers_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a worker to archive")
            return
        wid = self.workers_tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm",
                               "This will mark the worker as inactive but KEEP all past data.\nContinue?"):
            self.conn.execute("UPDATE workers SET is_active=0 WHERE id=?", (wid,))
            self.conn.commit()
            self.load_workers()

    def load_workers(self):
        self.workers_tree.delete(*self.workers_tree.get_children())
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, name, worker_type, created_date,
                   CASE WHEN is_active=1 THEN 'Yes' ELSE 'No' END AS active
            FROM workers
            ORDER BY name
        """)
        all_rows = cur.fetchall()
        for row in all_rows:
            self.workers_tree.insert("", "end", values=row)

        # worker dropdown shows only active workers
        cur.execute("SELECT name, worker_type FROM workers WHERE is_active=1 ORDER BY name")
        vals = [f"{n} ({t})" for n, t in cur.fetchall()]
        self.worker_combo["values"] = vals

    # ────────────────────────────────── production‑entry operations ──
    def add_production_entry(self):
        try:
            worker_sel = self.worker_combo.get()
            length = float(self.length_entry.get())
            width = float(self.width_entry.get())
            cuts = int(self.cuts_entry.get())
            qty = int(self.quantity_entry.get())
            entry_date = self.date_entry.get().strip()

            if not worker_sel:
                messagebox.showerror("Error", "Select a worker")
                return
            # validate date
            try:
                datetime.datetime.strptime(entry_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format (YYYY‑MM‑DD)")
                return

            worker_name = worker_sel.split(" (")[0]
            cur = self.conn.cursor()
            cur.execute("SELECT id FROM workers WHERE name=?", (worker_name,))
            row = cur.fetchone()
            if not row:
                messagebox.showerror("Error", "Worker not found")
                return
            wid = row[0]

            cur.execute("""
                INSERT INTO production_entries(
                    worker_id, stone_length, stone_width,
                    cuts, quantity, entry_date
                )
                VALUES(?,?,?,?,?,?)
            """, (wid, length, width, cuts, qty, entry_date))
            self.conn.commit()

            # clear form
            self.length_entry.delete(0, tk.END)
            self.width_entry.delete(0, tk.END)
            self.cuts_entry.delete(0, tk.END)
            self.quantity_entry.delete(0, tk.END)
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

            self.load_production_entries()
            messagebox.showinfo("Success", "Entry added")
        except ValueError:
            messagebox.showerror("Error", "Enter numeric values for length/width/cuts/qty")
        except Exception as exc:
            messagebox.showerror("Error", f"Error adding entry: {exc}")

    def load_production_entries(self):
        self.entries_tree.delete(*self.entries_tree.get_children())
        cur = self.conn.cursor()
        cur.execute("""
            SELECT pe.id, w.name, pe.stone_length, pe.stone_width,
                   pe.cuts, pe.quantity, pe.entry_date
            FROM production_entries pe
            JOIN workers w ON pe.worker_id = w.id
            ORDER BY pe.entry_date DESC, pe.id DESC
        """)
        rows = cur.fetchall()
        for rid, name, L, W, cuts, qty, d in rows:
            area = L * W
            self.entries_tree.insert("", "end",
                values=(rid, name, L, W, f"{area:.2f}", cuts, qty, d))

    def delete_production_entry(self):
        sel = self.entries_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select an entry to delete")
            return
        eid = self.entries_tree.item(sel[0])["values"][0]
        if messagebox.askyesno("Confirm", "Delete this production entry?"):
            self.conn.execute("DELETE FROM production_entries WHERE id=?", (eid,))
            self.conn.commit()
            self.load_production_entries()

    # ───────────────────────────────────────────── rates operations ──
    def save_rates(self):
        try:
            op_rate = float(self.operator_rate_entry.get())
            ld_rate = float(self.loader_loading_entry.get())
            un_rate = float(self.loader_unloading_entry.get())

            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(*) FROM rates")
            if cur.fetchone()[0]:
                cur.execute("""
                    UPDATE rates SET
                        operator_rate_per_sqft=?,
                        loader_loading_rate=?,
                        loader_unloading_base_rate=?,
                        updated_date=CURRENT_DATE
                """, (op_rate, ld_rate, un_rate))
            else:
                cur.execute("""
                    INSERT INTO rates(operator_rate_per_sqft,
                                      loader_loading_rate,
                                      loader_unloading_base_rate)
                    VALUES(?,?,?)
                """, (op_rate, ld_rate, un_rate))
            self.conn.commit()
            self.load_rates()
            messagebox.showinfo("Success", "Rates saved")
        except ValueError:
            messagebox.showerror("Error", "Enter numeric values")
        except Exception as exc:
            messagebox.showerror("Error", f"Error saving rates: {exc}")

    def load_rates(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT operator_rate_per_sqft,
                   loader_loading_rate,
                   loader_unloading_base_rate
            FROM rates ORDER BY updated_date DESC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            op, ld, un = row
            # pre‑fill fields
            self.operator_rate_entry.delete(0, tk.END)
            self.operator_rate_entry.insert(0, str(op))
            self.loader_loading_entry.delete(0, tk.END)
            self.loader_loading_entry.insert(0, str(ld))
            self.loader_unloading_entry.delete(0, tk.END)
            self.loader_unloading_entry.insert(0, str(un))

            self.rates_display.config(
                text=f"Current Rates (₹):\n"
                     f"• Operator: {op}/sq ft\n"
                     f"• Loader Loading: {ld}/sq ft\n"
                     f"• Loader Unloading: {un}/sq ft"
            )
    # ────────────────────────────────────────────────── helper: periods ──
    def set_period(self, key: str):
        today = datetime.date.today()
        if key == "today":
            start = end = today
        elif key == "week":
            start = today - timedelta(days=today.weekday())
            end = today
        elif key == "half_month":
            if today.day <= 15:
                start = today.replace(day=1)
                end = today.replace(day=15)
            else:
                start = today.replace(day=16)
                end = today
        elif key == "month":
            start = today.replace(day=1)
            end = today
        else:
            return
        self.from_date_entry.delete(0, tk.END); self.from_date_entry.insert(0, start)
        self.to_date_entry.delete(0, tk.END);   self.to_date_entry.insert(0, end)

    # ─────────────────────────────────────────── payment calculation ──
    @staticmethod
    def _operator_payment(area, cuts, qty, rate):
        effective_area = 2 * area * cuts * qty    # same formula, no per‑cut extra
        return effective_area * rate, effective_area

    @staticmethod
    def _loader_payment(area, cuts, qty, ld_rate, un_rate):
        loading = area * qty * ld_rate
        un_eff_area = area * (1 + cuts) * qty
        unloading = un_eff_area * un_rate
        total = loading + unloading
        return total, area*qty + un_eff_area, loading, unloading

    def calculate_payments(self):
        try:
            from_d = self.from_date_entry.get().strip()
            to_d = self.to_date_entry.get().strip()
            # validate
            datetime.datetime.strptime(from_d, "%Y-%m-%d")
            datetime.datetime.strptime(to_d, "%Y-%m-%d")
            cur = self.conn.cursor()
            cur.execute("""
                SELECT operator_rate_per_sqft,
                       loader_loading_rate,
                       loader_unloading_base_rate
                FROM rates ORDER BY updated_date DESC LIMIT 1
            """)
            rates = cur.fetchone()
            if not rates:
                messagebox.showerror("Error", "Set wage rates first")
                return
            op_rate, ld_rate, un_rate = rates

            self.payments_tree.delete(*self.payments_tree.get_children())

            cur.execute("""
                SELECT w.name, w.worker_type,
                       pe.stone_length, pe.stone_width,
                       pe.cuts, pe.quantity
                FROM production_entries pe
                JOIN workers w ON pe.worker_id = w.id
                WHERE pe.entry_date BETWEEN ? AND ?
                ORDER BY w.name
            """, (from_d, to_d))
            rows = cur.fetchall()
            if not rows:
                messagebox.showinfo("Info", "No entries in the selected period")
                return

            # group by worker
            workers: Dict[str, Dict] = {}
            for name, wtype, L, W, cuts, qty in rows:
                area = L * W
                if name not in workers:
                    workers[name] = {
                        "type": wtype, "area": 0.0, "cuts": 0, "entries": []
                    }
                workers[name]["area"] += area * qty
                workers[name]["cuts"] += cuts * qty
                workers[name]["entries"].append((area, cuts, qty))

            for name, data in workers.items():
                total_pay = 0.0
                details = []
                for area, cuts, qty in data["entries"]:
                    if data["type"] == "Machine Operator":
                        pay, eff_area = self._operator_payment(area, cuts, qty, op_rate)
                        total_pay += pay
                        details.append(f"{area:.2f} sq ft ×{qty}, cuts={cuts} ⇒ ₹{pay:.2f}")
                    else:  # Loader
                        pay, _, ld, un = self._loader_payment(area, cuts, qty, ld_rate, un_rate)
                        total_pay += pay
                        details.append(f"{area:.2f}×{qty}, cuts={cuts} "
                                       f"(load ₹{ld:.0f}+unload ₹{un:.0f})")

                det_str = "; ".join(details[:2]) + \
                          (f" … ({len(details)} entries)" if len(details) > 2 else "")
                self.payments_tree.insert("", "end",
                    values=(name, data["type"],
                            f"{data['area']:.2f}", data["cuts"],
                            f"₹{total_pay:.2f}", det_str))
            messagebox.showinfo("Success", "Payments calculated")
        except Exception as exc:
            messagebox.showerror("Error", f"Payment calc error: {exc}")

    # ─────────────────────────────────────────── export → Excel ──
    def export_payments(self):
        if not self.payments_tree.get_children():
            messagebox.showwarning("Warning", "No data to export")
            return
        data = []
        for item in self.payments_tree.get_children():
            vals = self.payments_tree.item(item)["values"]
            data.append({
                "Worker": vals[0],
                "Type": vals[1],
                "Total Area (sq ft)": vals[2],
                "Total Cuts": vals[3],
                "Payment": vals[4],
                "Details": vals[5],
            })
        df = pd.DataFrame(data)
        fn = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            title="Save payment report"
        )
        if fn:
            try:
                df.to_excel(fn, index=False)
                messagebox.showinfo("Success", f"Saved to {fn}")
            except Exception as exc:
                messagebox.showerror("Error", f"Export failed: {exc}")

    # ─────────────────────────────────────────── reports ──
    def generate_report(self):
        rtype = self.report_type_combo.get()
        if not rtype:
            messagebox.showwarning("Warning", "Select a report type")
            return
        cur = self.conn.cursor()
        try:
            if rtype == "Worker Summary":
                cur.execute("""
                    SELECT w.name, w.worker_type,
                           COUNT(pe.id),
                           COALESCE(SUM(pe.stone_length*pe.stone_width*pe.quantity),0),
                           COALESCE(SUM(pe.cuts*pe.quantity),0)
                    FROM workers w
                    LEFT JOIN production_entries pe ON w.id=pe.worker_id
                    GROUP BY w.id
                    ORDER BY w.name
                """)
                rows = cur.fetchall()
                rep = ["WORKER SUMMARY", "="*60]
                for n,t,e,a,c in rows:
                    rep.append(f"{n} ({t}) — entries:{e}, area:{a:.2f} sq ft, cuts:{c}")
            elif rtype == "Daily Production":
                cur.execute("""
                    SELECT entry_date,
                           COUNT(id),
                           SUM(stone_length*stone_width*quantity),
                           SUM(cuts*quantity)
                    FROM production_entries
                    GROUP BY entry_date
                    ORDER BY entry_date DESC LIMIT 30
                """)
                rows = cur.fetchall()
                rep = ["DAILY PRODUCTION (Last 30 days)", "="*60]
                for d,e,a,c in rows:
                    rep.append(f"{d}: entries={e}, area={a:.2f} sq ft, cuts={c}")
            else:  # Monthly Summary
                cur.execute("""
                    SELECT strftime('%Y-%m', entry_date) AS m,
                           COUNT(id),
                           SUM(stone_length*stone_width*quantity),
                           SUM(cuts*quantity)
                    FROM production_entries
                    GROUP BY m ORDER BY m DESC LIMIT 12
                """)
                rows = cur.fetchall()
                rep = ["MONTHLY SUMMARY (Last 12 months)", "="*60]
                for m,e,a,c in rows:
                    rep.append(f"{m}: entries={e}, area={a:.2f} sq ft, cuts={c}")
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", "\n".join(rep))
        except Exception as exc:
            messagebox.showerror("Error", f"Report error: {exc}")

    # ────────────────────────────────────────────── backup database ──
    def backup_database(src_path="stone_factory.db", backup_dir="backups"):
        # ensure backup folder exists
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(backup_dir, f"stone_factory_{timestamp}.db")
        # copy the live database
        shutil.copy2(src_path, dst)
        print(f"Database backed up to {dst}")    

    # ───────────────────────────────────────────── cleanup ──
    def __del__(self):
        try:
            # before closing connection, make a timestamped backup
            self.backup_database()
            self.conn.close()
        except Exception:
            pass

# ────────────────────────────────────────────────────── main loop ──
def main():
    root = ThemedTk(theme="adapta")

    root.iconbitmap("output_icon.ico")
    app = StoneFactoryPaymentSystem(root)
    app.load_production_entries()

    # center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 2
    root.geometry(f"+{x}+{y}")
    root.mainloop()

if __name__ == "__main__":
    main()
