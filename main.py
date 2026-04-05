import dns.resolver
import dns.reversename
import time
import threading
import statistics
import customtkinter as ctk
import os
from concurrent.futures import ThreadPoolExecutor

class DNSBenchPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DNS Performance Pro - Engineering Edition")
        self.geometry("1250x850")
        
        # Path Management (Directory cache/ below script)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_dir = os.path.join(self.base_dir, "cache")
        self.servers_file = os.path.join(self.cache_dir, "servers.txt")
        self.ensure_structure_exists()

        self.running = False
        self.rows_data = []
        self.sort_column = "avg"
        self.sort_reverse = False
        self.total_tasks = 0

        # Column Config: (Text, Key, Width)
        self.cols_config = [
            ("OWNER", "owner", 200), ("IP ADDRESS", "ip", 150), ("STATUS", "status", 100), 
            ("MIN", "min", 80), ("MAX", "max", 80), ("AVG", "avg", 80), 
            ("JITTER", "jitter", 80), ("RELIABILITY", "rel", 100)
        ]

        # Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        self.setup_main_panel()

    def ensure_structure_exists(self):
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        if not os.path.exists(self.servers_file):
            with open(self.servers_file, "w") as f:
                f.write("8.8.8.8\n1.1.1.1\n9.9.9.9\n208.67.222.222")

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="CONTROLS", font=("Roboto", 18, "bold")).pack(pady=20)
        
        self.btn_run = ctk.CTkButton(self.sidebar, text="START BENCHMARK", fg_color="#2ecc71", hover_color="#27ae60", command=self.start_benchmark)
        self.btn_run.pack(pady=10, padx=20, fill="x")

        self.btn_stop = ctk.CTkButton(self.sidebar, text="STOP BENCHMARK", fg_color="gray", state="disabled", command=self.stop_benchmark)
        self.btn_stop.pack(pady=10, padx=20, fill="x")

        self.btn_list = ctk.CTkButton(self.sidebar, text="MANAGE IPs", command=self.open_manage_window)
        self.btn_list.pack(pady=10, padx=20, fill="x")

        # Exit Button at the bottom
        self.btn_exit = ctk.CTkButton(self.sidebar, text="EXIT APP", fg_color="#34495e", command=self.quit)
        self.btn_exit.pack(side="bottom", pady=20, padx=20, fill="x")

        # Legend above Exit
        self.legend_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.legend_frame.pack(side="bottom", pady=10, padx=10, fill="x")
        self.add_legend_item("ONLINE", "Stable (>90%)", "#2ecc71")
        self.add_legend_item("UNSTABLE", "Unstable (<90%)", "#f39c12")
        self.add_legend_item("OFFLINE", "No Response", "#e74c3c")

    def add_legend_item(self, title, desc, color):
        lbl = ctk.CTkLabel(self.legend_frame, text=f"● {title}", text_color=color, font=("Roboto", 11, "bold"))
        lbl.pack(anchor="w", padx=10)
        ctk.CTkLabel(self.legend_frame, text=desc, font=("Roboto", 10)).pack(anchor="w", padx=20)

    def setup_main_panel(self):
        self.main_panel = ctk.CTkFrame(self)
        self.main_panel.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # Progress Section
        ctk.CTkLabel(self.main_panel, text="PROGRESS", font=("Roboto", 12, "bold")).pack(pady=(10, 0))
        self.progress_bar = ctk.CTkProgressBar(self.main_panel, width=600)
        self.progress_bar.pack(pady=(5, 20))
        self.progress_bar.set(0)

        # Interactive Header
        self.header_frame = ctk.CTkFrame(self.main_panel, fg_color="#2c3e50", height=45)
        self.header_frame.pack(fill="x", padx=10)
        self.header_buttons = {}
        for text, key, width in self.cols_config:
            btn = ctk.CTkButton(self.header_frame, text=text, width=width, height=35,
                                fg_color="transparent", hover_color="#34495e",
                                font=("Roboto", 11, "bold"), anchor="w",
                                command=lambda k=key: self.sort_by(k))
            btn.pack(side="left", padx=5)
            self.header_buttons[key] = btn

        self.results_scroll = ctk.CTkScrollableFrame(self.main_panel, fg_color="transparent")
        self.results_scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def get_dynamic_owner(self, ip):
        try:
            addr = dns.reversename.from_address(ip)
            ptr = dns.resolver.resolve(addr, "PTR")
            p = str(ptr[0]).split('.')
            return f"{p[-3].capitalize()} {p[-2].upper()}" if len(p) > 2 else str(ptr[0])
        except:
            return "Local Gateway" if ip.startswith(("192.168.", "10.", "172.")) else "Unknown ISP"

    def benchmark_worker(self, ip):
        if not self.running: return
        owner = self.get_dynamic_owner(ip)
        latencies, failures, iterations = [], 0, 50
        res = dns.resolver.Resolver()
        res.nameservers, res.timeout, res.lifetime = [ip], 2.0, 2.0

        for _ in range(iterations):
            if not self.running: break
            try:
                start = time.perf_counter()
                res.resolve("google.com", "A")
                latencies.append((time.perf_counter() - start) * 1000)
            except: failures += 1
            time.sleep(0.01)

        reliable = ((iterations - failures) / iterations) * 100
        v_avg = sum(latencies)/len(latencies) if latencies else 0
        v_min, v_max = (min(latencies), max(latencies)) if latencies else (0, 0)
        v_jitter = statistics.stdev(latencies) if len(latencies) > 1 else 0
        status = "OFFLINE" if not latencies else ("ONLINE" if reliable > 90 else "UNSTABLE")
        color = "#2ecc71" if status == "ONLINE" else ("#f39c12" if status == "UNSTABLE" else "#e74c3c")

        row = {"owner": owner, "ip": ip, "status": status, "color": color, "avg": v_avg, "min": v_min, "max": v_max, "jitter": v_jitter, "rel": reliable}
        self.after(0, lambda: self.on_task_complete(row))

    def on_task_complete(self, row):
        self.rows_data.append(row)
        self.refresh_table()
        self.progress_bar.set(len(self.rows_data) / self.total_tasks)
        if len(self.rows_data) == self.total_tasks: self.stop_benchmark()

    def refresh_table(self):
        for child in self.results_scroll.winfo_children(): child.destroy()
        sorted_list = sorted(self.rows_data, 
                             key=lambda x: (x[self.sort_column] == 0, x[self.sort_column]), 
                             reverse=self.sort_reverse)
        for r in sorted_list:
            row_frame = ctk.CTkFrame(self.results_scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            fields = [(r['owner'], 200), (r['ip'], 150), (r['status'], 100), (f"{r['min']:.1f}ms", 80), (f"{r['max']:.1f}ms", 80), (f"{r['avg']:.1f}ms", 80), (f"{r['jitter']:.1f}ms", 80), (f"{r['rel']:.0f}%", 100)]
            for text, width in fields:
                ctk.CTkLabel(row_frame, text=text, width=width, anchor="w", text_color=r['color'], font=("Courier New", 12)).pack(side="left", padx=5)

    def sort_by(self, key):
        if self.sort_column == key: self.sort_reverse = not self.sort_reverse
        else: self.sort_column, self.sort_reverse = key, False
        self.refresh_table()

    def start_benchmark(self):
        self.running = True
        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal", fg_color="#e74c3c")
        self.rows_data = []
        self.progress_bar.set(0) # Reset progress
        for child in self.results_scroll.winfo_children(): child.destroy()
        
        with open(self.servers_file, "r") as f:
            ips = list(set([l.strip() for l in f if l.strip()]))
        
        self.total_tasks = len(ips)
        if self.total_tasks == 0: return

        def run_pool():
            with ThreadPoolExecutor(max_workers=15) as executor:
                executor.map(self.benchmark_worker, ips)

        threading.Thread(target=run_pool, daemon=True).start()

    def stop_benchmark(self):
        self.running = False
        self.btn_stop.configure(state="disabled", fg_color="gray")
        self.btn_run.configure(state="normal")

    def open_manage_window(self):
        m_win = ctk.CTkToplevel(self)
        m_win.title("Manage IP List")
        m_win.geometry("450x550")
        m_win.attributes("-topmost", True)
        
        entry = ctk.CTkEntry(m_win, placeholder_text="New IP Address")
        entry.pack(pady=20, padx=20, fill="x")
        
        def add():
            ip = entry.get().strip()
            if ip:
                with open(self.servers_file, "a") as f: f.write(f"\n{ip}")
                entry.delete(0, 'end'); refresh()

        ctk.CTkButton(m_win, text="Add to List", command=add).pack()
        scroll = ctk.CTkScrollableFrame(m_win)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh():
            for child in scroll.winfo_children(): child.destroy()
            if os.path.exists(self.servers_file):
                with open(self.servers_file, "r") as f:
                    for line in f:
                        ip = line.strip()
                        if ip:
                            r = ctk.CTkFrame(scroll)
                            r.pack(fill="x", pady=2)
                            ctk.CTkLabel(r, text=ip).pack(side="left", padx=10)
                            ctk.CTkButton(r, text="Delete", width=60, fg_color="#c0392b", command=lambda x=ip: rm(x)).pack(side="right", padx=5)

        def rm(ip_val):
            with open(self.servers_file, "r") as f: lines = f.readlines()
            with open(self.servers_file, "w") as f:
                for l in lines:
                    if l.strip() != ip_val: f.write(l)
            refresh()
        refresh()

if __name__ == "__main__":
    app = DNSBenchPro()
    app.mainloop()
