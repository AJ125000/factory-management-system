import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
from datetime import timedelta
import json
import os
from typing import Dict, List, Tuple
import pandas as pd

class StoneFactoryPaymentSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("Kota Stone Factory - Payment Management System")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 600)
        
        # Initialize database
        self.init_database()
        
        # Create main interface
        self.create_widgets()
        
        # Load initial data
        self.load_workers()
        self.load_rates()
        
    def init_database(self):
        """Initialize SQLite database with required tables"""
        self.conn = sqlite3.connect('stone_factory.db')
        cursor = self.conn.cursor()
        
        # Workers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                worker_type TEXT NOT NULL,
                created_date DATE DEFAULT CURRENT_DATE
            )
        ''')
        
        # Production entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER,
                stone_length REAL NOT NULL,
                stone_width REAL NOT NULL,
                cuts INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                entry_date DATE DEFAULT CURRENT_DATE,
                FOREIGN KEY (worker_id) REFERENCES workers (id)
            )
        ''')
        
        # Rates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_rate_per_sqft REAL NOT NULL,
                operator_cut_amount REAL NOT NULL,
                loader_loading_rate REAL NOT NULL,
                loader_unloading_base_rate REAL NOT NULL,
                updated_date DATE DEFAULT CURRENT_DATE
            )
        ''')
        
        self.conn.commit()
        
    def create_widgets(self):
        """Create the main GUI interface"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_worker_management_tab()
        self.create_production_entry_tab()
        self.create_rates_management_tab()
        self.create_payment_calculation_tab()
        self.create_reports_tab()
        
    def create_worker_management_tab(self):
        """Create worker management interface"""
        worker_frame = ttk.Frame(self.notebook)
        self.notebook.add(worker_frame, text="Worker Management")
        
        # Add worker section
        add_frame = ttk.LabelFrame(worker_frame, text="Add New Worker", padding=10)
        add_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(add_frame, text="Worker Name:").grid(row=0, column=0, sticky='w', padx=5)
        self.worker_name_entry = ttk.Entry(add_frame, width=20)
        self.worker_name_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(add_frame, text="Worker Type:").grid(row=0, column=2, sticky='w', padx=5)
        self.worker_type_combo = ttk.Combobox(add_frame, values=["Machine Operator", "Loader"], width=15)
        self.worker_type_combo.grid(row=0, column=3, padx=5)
        
        ttk.Button(add_frame, text="Add Worker", command=self.add_worker).grid(row=0, column=4, padx=10)
        
        # Workers list
        list_frame = ttk.LabelFrame(worker_frame, text="Workers List", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for workers
        columns = ("ID", "Name", "Type", "Created Date")
        self.workers_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.workers_tree.heading(col, text=col)
            self.workers_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.workers_tree.yview)
        self.workers_tree.configure(yscrollcommand=scrollbar.set)
        
        self.workers_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Delete button
        ttk.Button(list_frame, text="Delete Selected Worker", 
                  command=self.delete_worker).pack(pady=5)
        
    def create_production_entry_tab(self):
        """Create production entry interface"""
        production_frame = ttk.Frame(self.notebook)
        self.notebook.add(production_frame, text="Production Entry")
        
        # Entry form
        entry_frame = ttk.LabelFrame(production_frame, text="Add Production Entry", padding=10)
        entry_frame.pack(fill='x', padx=10, pady=5)
        
        # Row 1
        ttk.Label(entry_frame, text="Worker:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.worker_combo = ttk.Combobox(entry_frame, width=20)
        self.worker_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(entry_frame, text="Stone Length (ft):").grid(row=0, column=2, sticky='w', padx=5, pady=2)
        self.length_entry = ttk.Entry(entry_frame, width=10)
        self.length_entry.grid(row=0, column=3, padx=5, pady=2)
        
        # Row 2
        ttk.Label(entry_frame, text="Stone Width (ft):").grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.width_entry = ttk.Entry(entry_frame, width=10)
        self.width_entry.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(entry_frame, text="Number of Cuts:").grid(row=1, column=2, sticky='w', padx=5, pady=2)
        self.cuts_entry = ttk.Entry(entry_frame, width=10)
        self.cuts_entry.grid(row=1, column=3, padx=5, pady=2)
        
        # Row 3
        ttk.Label(entry_frame, text="Quantity:").grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.quantity_entry = ttk.Entry(entry_frame, width=10)
        self.quantity_entry.grid(row=2, column=1, padx=5, pady=2)
        
        ttk.Button(entry_frame, text="Add Entry", command=self.add_production_entry).grid(row=2, column=3, padx=10, pady=5)
        
        # Entries list
        entries_frame = ttk.LabelFrame(production_frame, text="Production Entries", padding=10)
        entries_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for entries
        entry_columns = ("ID", "Worker", "Length", "Width", "Area", "Cuts", "Quantity", "Date")
        self.entries_tree = ttk.Treeview(entries_frame, columns=entry_columns, show='headings', height=12)
        
        for col in entry_columns:
            self.entries_tree.heading(col, text=col)
            self.entries_tree.column(col, width=100)
        
        entries_scrollbar = ttk.Scrollbar(entries_frame, orient='vertical', command=self.entries_tree.yview)
        self.entries_tree.configure(yscrollcommand=entries_scrollbar.set)
        
        self.entries_tree.pack(side='left', fill='both', expand=True)
        entries_scrollbar.pack(side='right', fill='y')
        
        # Control buttons
        button_frame = ttk.Frame(entries_frame)
        button_frame.pack(fill='x', pady=5)
        
        ttk.Button(button_frame, text="Delete Selected Entry", 
                  command=self.delete_production_entry).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", 
                  command=self.load_production_entries).pack(side='left', padx=5)
        
    def create_rates_management_tab(self):
        """Create rates management interface"""
        rates_frame = ttk.Frame(self.notebook)
        self.notebook.add(rates_frame, text="Rates Management")
        
        # Rates form
        rates_form = ttk.LabelFrame(rates_frame, text="Set Wage Rates", padding=20)
        rates_form.pack(fill='x', padx=10, pady=10)
        
        # Machine Operator Rates
        operator_frame = ttk.LabelFrame(rates_form, text="Machine Operator Rates", padding=10)
        operator_frame.pack(fill='x', pady=10)
        
        ttk.Label(operator_frame, text="Rate per sq ft:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.operator_rate_entry = ttk.Entry(operator_frame, width=15)
        self.operator_rate_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(operator_frame, text="Amount per cut:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.operator_cut_entry = ttk.Entry(operator_frame, width=15)
        self.operator_cut_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # Loader Rates
        loader_frame = ttk.LabelFrame(rates_form, text="Loader Rates", padding=10)
        loader_frame.pack(fill='x', pady=10)
        
        ttk.Label(loader_frame, text="Loading rate per sq ft:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.loader_loading_entry = ttk.Entry(loader_frame, width=15)
        self.loader_loading_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(loader_frame, text="Unloading base rate per sq ft:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.loader_unloading_entry = ttk.Entry(loader_frame, width=15)
        self.loader_unloading_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # Save button
        ttk.Button(rates_form, text="Save Rates", command=self.save_rates).pack(pady=10)
        
        # Current rates display
        current_frame = ttk.LabelFrame(rates_frame, text="Current Rates", padding=20)
        current_frame.pack(fill='x', padx=10, pady=10)
        
        self.rates_display = ttk.Label(current_frame, text="", font=('Arial', 10))
        self.rates_display.pack()
        
    def create_payment_calculation_tab(self):
        """Create payment calculation interface"""
        payment_frame = ttk.Frame(self.notebook)
        self.notebook.add(payment_frame, text="Payment Calculation")
        
        # Period selection
        period_frame = ttk.LabelFrame(payment_frame, text="Select Period", padding=10)
        period_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(period_frame, text="From Date:").grid(row=0, column=0, sticky='w', padx=5)
        self.from_date_entry = ttk.Entry(period_frame, width=12)
        self.from_date_entry.grid(row=0, column=1, padx=5)
        self.from_date_entry.insert(0, datetime.date.today().strftime('%Y-%m-%d'))
        
        ttk.Label(period_frame, text="To Date:").grid(row=0, column=2, sticky='w', padx=5)
        self.to_date_entry = ttk.Entry(period_frame, width=12)
        self.to_date_entry.grid(row=0, column=3, padx=5)
        self.to_date_entry.insert(0, datetime.date.today().strftime('%Y-%m-%d'))
        
        # Quick period buttons
        quick_frame = ttk.Frame(period_frame)
        quick_frame.grid(row=1, column=0, columnspan=4, pady=10)
        
        ttk.Button(quick_frame, text="Today", command=lambda: self.set_period('today')).pack(side='left', padx=2)
        ttk.Button(quick_frame, text="This Week", command=lambda: self.set_period('week')).pack(side='left', padx=2)
        ttk.Button(quick_frame, text="Half Month", command=lambda: self.set_period('half_month')).pack(side='left', padx=2)
        ttk.Button(quick_frame, text="This Month", command=lambda: self.set_period('month')).pack(side='left', padx=2)
        
        ttk.Button(period_frame, text="Calculate Payments", 
                  command=self.calculate_payments).grid(row=0, column=4, padx=10)
        
        # Payment results
        results_frame = ttk.LabelFrame(payment_frame, text="Payment Calculations", padding=10)
        results_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Treeview for payments
        payment_columns = ("Worker", "Type", "Total Area", "Total Cuts", "Calculated Payment", "Details")
        self.payments_tree = ttk.Treeview(results_frame, columns=payment_columns, show='headings', height=15)
        
        for col in payment_columns:
            self.payments_tree.heading(col, text=col)
            self.payments_tree.column(col, width=150)
        
        payment_scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=self.payments_tree.yview)
        self.payments_tree.configure(yscrollcommand=payment_scrollbar.set)
        
        self.payments_tree.pack(side='left', fill='both', expand=True)
        payment_scrollbar.pack(side='right', fill='y')
        
        # Export button
        ttk.Button(results_frame, text="Export to Excel", 
                  command=self.export_payments).pack(pady=5)
        
    def create_reports_tab(self):
        """Create reports interface"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="Reports")
        
        # Report type selection
        report_frame = ttk.LabelFrame(reports_frame, text="Generate Reports", padding=10)
        report_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(report_frame, text="Report Type:").grid(row=0, column=0, sticky='w', padx=5)
        self.report_type_combo = ttk.Combobox(report_frame, 
                                            values=["Worker Summary", "Daily Production", "Monthly Summary"], 
                                            width=20)
        self.report_type_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(report_frame, text="Generate Report", 
                  command=self.generate_report).grid(row=0, column=2, padx=10)
        
        # Report display
        report_display_frame = ttk.LabelFrame(reports_frame, text="Report", padding=10)
        report_display_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.report_text = tk.Text(report_display_frame, wrap='word', height=20)
        report_scrollbar = ttk.Scrollbar(report_display_frame, orient='vertical', command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scrollbar.set)
        
        self.report_text.pack(side='left', fill='both', expand=True)
        report_scrollbar.pack(side='right', fill='y')
        
    # Database operations
    def add_worker(self):
        """Add a new worker"""
        name = self.worker_name_entry.get().strip()
        worker_type = self.worker_type_combo.get()
        
        if not name or not worker_type:
            messagebox.showerror("Error", "Please fill all fields")
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO workers (name, worker_type) VALUES (?, ?)", 
                          (name, worker_type))
            self.conn.commit()
            
            self.worker_name_entry.delete(0, tk.END)
            self.worker_type_combo.set("")
            
            self.load_workers()
            messagebox.showinfo("Success", "Worker added successfully")
            
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Worker name already exists")
        except Exception as e:
            messagebox.showerror("Error", f"Error adding worker: {str(e)}")
    
    def delete_worker(self):
        """Delete selected worker"""
        selection = self.workers_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a worker to delete")
            return
        
        worker_id = self.workers_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this worker?"):
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
                self.conn.commit()
                
                self.load_workers()
                messagebox.showinfo("Success", "Worker deleted successfully")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error deleting worker: {str(e)}")
    
    def load_workers(self):
        """Load workers into the treeview and combo"""
        # Clear treeview
        for item in self.workers_tree.get_children():
            self.workers_tree.delete(item)
        
        # Load from database
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, worker_type, created_date FROM workers ORDER BY name")
        workers = cursor.fetchall()
        
        for worker in workers:
            self.workers_tree.insert("", "end", values=worker)
        
        # Update combo
        worker_names = [f"{worker[1]} ({worker[2]})" for worker in workers]
        self.worker_combo['values'] = worker_names
        
    def add_production_entry(self):
        """Add production entry"""
        try:
            worker_selection = self.worker_combo.get()
            length = float(self.length_entry.get())
            width = float(self.width_entry.get())
            cuts = int(self.cuts_entry.get())
            quantity = int(self.quantity_entry.get())
            
            if not worker_selection:
                messagebox.showerror("Error", "Please select a worker")
                return
            
            # Extract worker name
            worker_name = worker_selection.split(" (")[0]
            
            # Get worker ID
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM workers WHERE name = ?", (worker_name,))
            result = cursor.fetchone()
            
            if not result:
                messagebox.showerror("Error", "Worker not found")
                return
            
            worker_id = result[0]
            
            # Insert entry
            cursor.execute("""
                INSERT INTO production_entries 
                (worker_id, stone_length, stone_width, cuts, quantity) 
                VALUES (?, ?, ?, ?, ?)
            """, (worker_id, length, width, cuts, quantity))
            
            self.conn.commit()
            
            # Clear form
            self.length_entry.delete(0, tk.END)
            self.width_entry.delete(0, tk.END)
            self.cuts_entry.delete(0, tk.END)
            self.quantity_entry.delete(0, tk.END)
            
            self.load_production_entries()
            messagebox.showinfo("Success", "Production entry added successfully")
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Error adding entry: {str(e)}")
    
    def load_production_entries(self):
        """Load production entries"""
        # Clear treeview
        for item in self.entries_tree.get_children():
            self.entries_tree.delete(item)
        
        # Load from database
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT pe.id, w.name, pe.stone_length, pe.stone_width, 
                   pe.cuts, pe.quantity, pe.entry_date
            FROM production_entries pe
            JOIN workers w ON pe.worker_id = w.id
            ORDER BY pe.entry_date DESC, pe.id DESC
        """)
        
        entries = cursor.fetchall()
        
        for entry in entries:
            area = entry[2] * entry[3]  # length * width
            values = (entry[0], entry[1], entry[2], entry[3], f"{area:.2f}", 
                     entry[4], entry[5], entry[6])
            self.entries_tree.insert("", "end", values=values)
    
    def delete_production_entry(self):
        """Delete selected production entry"""
        selection = self.entries_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an entry to delete")
            return
        
        entry_id = self.entries_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this entry?"):
            try:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM production_entries WHERE id = ?", (entry_id,))
                self.conn.commit()
                
                self.load_production_entries()
                messagebox.showinfo("Success", "Entry deleted successfully")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error deleting entry: {str(e)}")
    
    def save_rates(self):
        """Save wage rates"""
        try:
            operator_rate = float(self.operator_rate_entry.get())
            operator_cut = float(self.operator_cut_entry.get())
            loader_loading = float(self.loader_loading_entry.get())
            loader_unloading = float(self.loader_unloading_entry.get())
            
            cursor = self.conn.cursor()
            
            # Check if rates exist
            cursor.execute("SELECT COUNT(*) FROM rates")
            count = cursor.fetchone()[0]
            
            if count > 0:
                cursor.execute("""
                    UPDATE rates SET 
                    operator_rate_per_sqft = ?, 
                    operator_cut_amount = ?,
                    loader_loading_rate = ?,
                    loader_unloading_base_rate = ?,
                    updated_date = CURRENT_DATE
                """, (operator_rate, operator_cut, loader_loading, loader_unloading))
            else:
                cursor.execute("""
                    INSERT INTO rates 
                    (operator_rate_per_sqft, operator_cut_amount, 
                     loader_loading_rate, loader_unloading_base_rate)
                    VALUES (?, ?, ?, ?)
                """, (operator_rate, operator_cut, loader_loading, loader_unloading))
            
            self.conn.commit()
            self.load_rates()
            messagebox.showinfo("Success", "Rates saved successfully")
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Error saving rates: {str(e)}")
    
    def load_rates(self):
        """Load current rates"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT operator_rate_per_sqft, operator_cut_amount,
                   loader_loading_rate, loader_unloading_base_rate
            FROM rates ORDER BY updated_date DESC LIMIT 1
        """)
        
        result = cursor.fetchone()
        
        if result:
            self.operator_rate_entry.delete(0, tk.END)
            self.operator_rate_entry.insert(0, str(result[0]))
            
            self.operator_cut_entry.delete(0, tk.END)
            self.operator_cut_entry.insert(0, str(result[1]))
            
            self.loader_loading_entry.delete(0, tk.END)
            self.loader_loading_entry.insert(0, str(result[2]))
            
            self.loader_unloading_entry.delete(0, tk.END)
            self.loader_unloading_entry.insert(0, str(result[3]))
            
            # Update display
            rates_text = f"""
Current Wage Rates:
• Machine Operator: ₹{result[0]}/sq ft + ₹{result[1]} per cut
• Loader Loading: ₹{result[2]}/sq ft
• Loader Unloading: ₹{result[3]}/sq ft (base rate)
            """
            self.rates_display.config(text=rates_text)
    
    def set_period(self, period):
        """Set date period for payment calculation"""
        today = datetime.date.today()
        
        if period == 'today':
            self.from_date_entry.delete(0, tk.END)
            self.from_date_entry.insert(0, today.strftime('%Y-%m-%d'))
            self.to_date_entry.delete(0, tk.END)
            self.to_date_entry.insert(0, today.strftime('%Y-%m-%d'))
            
        elif period == 'week':
            start_of_week = today - timedelta(days=today.weekday())
            self.from_date_entry.delete(0, tk.END)
            self.from_date_entry.insert(0, start_of_week.strftime('%Y-%m-%d'))
            self.to_date_entry.delete(0, tk.END)
            self.to_date_entry.insert(0, today.strftime('%Y-%m-%d'))
            
        elif period == 'half_month':
            if today.day <= 15:
                start_date = today.replace(day=1)
                end_date = today.replace(day=15)
            else:
                start_date = today.replace(day=16)
                end_date = today
            
            self.from_date_entry.delete(0, tk.END)
            self.from_date_entry.insert(0, start_date.strftime('%Y-%m-%d'))
            self.to_date_entry.delete(0, tk.END)
            self.to_date_entry.insert(0, end_date.strftime('%Y-%m-%d'))
            
        elif period == 'month':
            start_of_month = today.replace(day=1)
            self.from_date_entry.delete(0, tk.END)
            self.from_date_entry.insert(0, start_of_month.strftime('%Y-%m-%d'))
            self.to_date_entry.delete(0, tk.END)
            self.to_date_entry.insert(0, today.strftime('%Y-%m-%d'))
    
    def calculate_machine_operator_payment(self, area: float, cuts: int, quantity: int, rates: tuple) -> tuple:
        """Calculate machine operator payment"""
        operator_rate, operator_cut_amount = rates[0], rates[1]
        
        # For machine operator: area * (2^cuts) * quantity
        effective_area = 2* area * cuts * quantity
        payment = effective_area * operator_rate
        
        return payment, effective_area
    
    def calculate_loader_payment(self, area: float, cuts: int, quantity: int, rates: tuple) -> tuple:
        """Calculate loader payment (loading + unloading)"""
        loader_loading_rate, loader_unloading_base_rate = rates[2], rates[3]
        
        # Loading payment: simple area * quantity * loading_rate
        loading_payment = area * quantity * loader_loading_rate
        
        # Unloading payment: area * (1 + cuts) * quantity * unloading_rate
        unloading_effective_area = area * (1 + cuts) * quantity
        unloading_payment = unloading_effective_area * loader_unloading_base_rate
        
        total_payment = loading_payment + unloading_payment
        total_effective_area = (area * quantity) + unloading_effective_area
        
        return total_payment, total_effective_area, loading_payment, unloading_payment
    
    def calculate_payments(self):
        """Calculate payments for selected period"""
        try:
            from_date = self.from_date_entry.get()
            to_date = self.to_date_entry.get()
            
            # Validate dates
            datetime.datetime.strptime(from_date, '%Y-%m-%d')
            datetime.datetime.strptime(to_date, '%Y-%m-%d')
            
            # Get current rates
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT operator_rate_per_sqft, operator_cut_amount,
                       loader_loading_rate, loader_unloading_base_rate
                FROM rates ORDER BY updated_date DESC LIMIT 1
            """)
            
            rates = cursor.fetchone()
            if not rates:
                messagebox.showerror("Error", "Please set wage rates first")
                return
            
            # Clear previous results
            for item in self.payments_tree.get_children():
                self.payments_tree.delete(item)
            
            # Get production data for the period
            cursor.execute("""
                SELECT w.name, w.worker_type, pe.stone_length, pe.stone_width, 
                       pe.cuts, pe.quantity, pe.entry_date
                FROM production_entries pe
                JOIN workers w ON pe.worker_id = w.id
                WHERE pe.entry_date BETWEEN ? AND ?
                ORDER BY w.name, pe.entry_date
            """, (from_date, to_date))
            
            entries = cursor.fetchall()
            
            if not entries:
                messagebox.showinfo("Info", "No production entries found for the selected period")
                return
            
            # Group by worker
            worker_data = {}
            for entry in entries:
                worker_name, worker_type = entry[0], entry[1]
                length, width, cuts, quantity = entry[2], entry[3], entry[4], entry[5]
                area = length * width
                
                if worker_name not in worker_data:
                    worker_data[worker_name] = {
                        'type': worker_type,
                        'total_area': 0,
                        'total_cuts': 0,
                        'entries': []
                    }
                
                worker_data[worker_name]['total_area'] += area * quantity
                worker_data[worker_name]['total_cuts'] += cuts * quantity
                worker_data[worker_name]['entries'].append((area, cuts, quantity))
            
            # Calculate payments for each worker
            for worker_name, data in worker_data.items():
                total_payment = 0
                details = []
                
                for area, cuts, quantity in data['entries']:
                    if data['type'] == 'Machine Operator':
                        payment, effective_area = self.calculate_machine_operator_payment(
                            area, cuts, quantity, rates)
                        total_payment += payment
                        details.append(f"Area: {area:.2f} sq ft, Cuts: {cuts}, Qty: {quantity}, "
                                     f"Effective Area: {effective_area:.2f} sq ft, Payment: ₹{payment:.2f}")
                    
                    elif data['type'] == 'Loader':
                        payment, total_eff_area, loading_pay, unloading_pay = self.calculate_loader_payment(
                            area, cuts, quantity, rates)
                        total_payment += payment
                        details.append(f"Area: {area:.2f} sq ft, Cuts: {cuts}, Qty: {quantity}, "
                                     f"Loading: ₹{loading_pay:.2f}, Unloading: ₹{unloading_pay:.2f}")
                
                # Insert into treeview
                details_str = "; ".join(details[:2])  # Show first 2 entries
                if len(details) > 2:
                    details_str += f" ... ({len(details)} total entries)"
                
                self.payments_tree.insert("", "end", values=(
                    worker_name,
                    data['type'],
                    f"{data['total_area']:.2f}",
                    data['total_cuts'],
                    f"₹{total_payment:.2f}",
                    details_str
                ))
            
            messagebox.showinfo("Success", "Payments calculated successfully")
            
        except ValueError as e:
            messagebox.showerror("Error", "Please enter valid dates in YYYY-MM-DD format")
        except Exception as e:
            messagebox.showerror("Error", f"Error calculating payments: {str(e)}")
    
    def export_payments(self):
        """Export payment calculations to Excel"""
        try:
            if not self.payments_tree.get_children():
                messagebox.showwarning("Warning", "No payment data to export")
                return
            
            # Get data from treeview
            data = []
            for item in self.payments_tree.get_children():
                values = self.payments_tree.item(item)['values']
                data.append({
                    'Worker Name': values[0],
                    'Worker Type': values[1],
                    'Total Area (sq ft)': values[2],
                    'Total Cuts': values[3],
                    'Calculated Payment': values[4],
                    'Details': values[5]
                })
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="Save Payment Report"
            )
            
            if filename:
                df.to_excel(filename, index=False)
                messagebox.showinfo("Success", f"Payment report exported to {filename}")
                
        except ImportError:
            messagebox.showerror("Error", "pandas and openpyxl libraries are required for Excel export")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting data: {str(e)}")
    
    def generate_report(self):
        """Generate selected report"""
        report_type = self.report_type_combo.get()
        
        if not report_type:
            messagebox.showwarning("Warning", "Please select a report type")
            return
        
        try:
            cursor = self.conn.cursor()
            
            if report_type == "Worker Summary":
                cursor.execute("""
                    SELECT w.name, w.worker_type, COUNT(pe.id) as total_entries,
                           SUM(pe.stone_length * pe.stone_width * pe.quantity) as total_area,
                           SUM(pe.cuts * pe.quantity) as total_cuts
                    FROM workers w
                    LEFT JOIN production_entries pe ON w.id = pe.worker_id
                    GROUP BY w.id, w.name, w.worker_type
                    ORDER BY w.name
                """)
                
                results = cursor.fetchall()
                
                report_text = "WORKER SUMMARY REPORT\n"
                report_text += "=" * 50 + "\n\n"
                
                for result in results:
                    name, worker_type, entries, area, cuts = result
                    area = area or 0
                    cuts = cuts or 0
                    report_text += f"Worker: {name}\n"
                    report_text += f"Type: {worker_type}\n"
                    report_text += f"Total Entries: {entries}\n"
                    report_text += f"Total Area Processed: {area:.2f} sq ft\n"
                    report_text += f"Total Cuts Made: {cuts}\n"
                    report_text += "-" * 30 + "\n\n"
            
            elif report_type == "Daily Production":
                cursor.execute("""
                    SELECT pe.entry_date, 
                           COUNT(pe.id) as total_entries,
                           SUM(pe.stone_length * pe.stone_width * pe.quantity) as total_area,
                           SUM(pe.cuts * pe.quantity) as total_cuts
                    FROM production_entries pe
                    GROUP BY pe.entry_date
                    ORDER BY pe.entry_date DESC
                    LIMIT 30
                """)
                
                results = cursor.fetchall()
                
                report_text = "DAILY PRODUCTION REPORT (Last 30 Days)\n"
                report_text += "=" * 50 + "\n\n"
                
                for result in results:
                    date, entries, area, cuts = result
                    report_text += f"Date: {date}\n"
                    report_text += f"Total Entries: {entries}\n"
                    report_text += f"Total Area: {area:.2f} sq ft\n"
                    report_text += f"Total Cuts: {cuts}\n"
                    report_text += "-" * 30 + "\n\n"
            
            elif report_type == "Monthly Summary":
                cursor.execute("""
                    SELECT strftime('%Y-%m', pe.entry_date) as month,
                           COUNT(pe.id) as total_entries,
                           SUM(pe.stone_length * pe.stone_width * pe.quantity) as total_area,
                           SUM(pe.cuts * pe.quantity) as total_cuts
                    FROM production_entries pe
                    GROUP BY strftime('%Y-%m', pe.entry_date)
                    ORDER BY month DESC
                    LIMIT 12
                """)
                
                results = cursor.fetchall()
                
                report_text = "MONTHLY SUMMARY REPORT (Last 12 Months)\n"
                report_text += "=" * 50 + "\n\n"
                
                for result in results:
                    month, entries, area, cuts = result
                    report_text += f"Month: {month}\n"
                    report_text += f"Total Entries: {entries}\n"
                    report_text += f"Total Area: {area:.2f} sq ft\n"
                    report_text += f"Total Cuts: {cuts}\n"
                    report_text += "-" * 30 + "\n\n"
            
            # Display report
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, report_text)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error generating report: {str(e)}")
    
    def __del__(self):
        """Close database connection when app is destroyed"""
        if hasattr(self, 'conn'):
            self.conn.close()

def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = StoneFactoryPaymentSystem(root)
    
    # Load initial data
    app.load_production_entries()
    
    # Center window on screen
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 2
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()