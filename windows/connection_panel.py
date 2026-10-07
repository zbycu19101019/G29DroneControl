"""ADB setup UI. Workers never touch Tk or SDL; results are queued to the UI."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
from tkinter import filedialog, ttk

from windows.adb_link import AdbLink


class ConnectionPanel:
    def __init__(self, owner, apk: Path):
        self.owner, self.apk = owner, apk
        self.window = tk.Toplevel(owner.root)
        self.window.title("PC ↔ ANDROID ↔ PILOT / DIAGNOSTYKA")
        self.window.geometry("800x650")
        self.window.configure(bg="#070c10")
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="adb")
        self.queue = Queue()
        self.closed = False
        self.busy = False
        self.serial = tk.StringVar()
        self.adb_path = tk.StringVar(value=owner.config.get("adbPath", ""))
        self.address = tk.StringVar()
        self.code = tk.StringVar()
        tk.Label(self.window, text="Połączenie z telefonem nie oznacza połączenia z dronem.\nMini 2 SE: brak oficjalnego wsparcia. Wariant DJI SDK służy tylko do odczytu.", bg="#070c10", fg="#ffb347", justify="left").pack(fill="x", padx=15, pady=12)
        row = tk.Frame(self.window); row.pack(fill="x", padx=15)
        tk.Label(row, text="adb.exe (puste = automatycznie)").pack(side="left")
        tk.Entry(row, textvariable=self.adb_path).pack(side="left", expand=True, fill="x")
        tk.Button(row, text="Wskaż", command=self.choose_adb).pack(side="right")
        row = tk.Frame(self.window); row.pack(fill="x", padx=15, pady=8)
        self.devices = ttk.Combobox(row, textvariable=self.serial, state="readonly")
        self.devices.pack(side="left", expand=True, fill="x")
        tk.Button(row, text="ODŚWIEŻ TELEFONY", command=self.refresh).pack(side="right")
        row = tk.Frame(self.window); row.pack(fill="x", padx=15, pady=5)
        for label, callback in (("1. ZAINSTALUJ APK", self.install), ("2. POŁĄCZ MOSTEK", self.connect), ("DIAGNOSTYKA USB / FLY", self.diagnostics)):
            tk.Button(row, text=label, command=callback).pack(side="left", padx=3)
        row = tk.Frame(self.window); row.pack(fill="x", padx=15, pady=5)
        tk.Button(row, text="OBRAZ DJI FLY (TYLKO PODGLĄD)", command=self.start_video).pack(side="left", padx=3)
        tk.Button(row, text="ZAMKNIJ WIDEO", command=self.owner.video.stop).pack(side="left", padx=3)
        tk.Button(row, text="DANE DJI SDK", command=self.owner.open_dji_panel).pack(side="left", padx=3)
        tk.Label(self.window, text="Podgląd ekranu telefonu w osobnym oknie. Otwórz DJI Fly i widok kamery.\nNie jest to osobny strumień SDK ani bezpieczny zamiennik bezpośredniej obserwacji drona.", bg="#070c10", fg="#91adb4", justify="left").pack(fill="x", padx=15)
        tk.Label(self.window, text="Pilot zajmuje USB? Android 11+: debugowanie bezprzewodowe.\nIP:PORT parowania i IP:PORT połączenia mogą być różne. Nie zapisujemy kodu.", bg="#070c10", fg="#91adb4", justify="left").pack(fill="x", padx=15, pady=8)
        row = tk.Frame(self.window); row.pack(fill="x", padx=15)
        tk.Label(row, text="IP:PORT").pack(side="left")
        tk.Entry(row, textvariable=self.address, width=24).pack(side="left")
        tk.Label(row, text="Kod").pack(side="left")
        tk.Entry(row, textvariable=self.code, width=9, show="•").pack(side="left")
        tk.Button(row, text="PARUJ", command=self.pair).pack(side="left")
        tk.Button(row, text="POŁĄCZ Wi-Fi", command=self.wifi).pack(side="left")
        self.text = tk.Text(self.window, bg="#05090c", fg="#00e6c1", font=("Consolas", 9), wrap="word")
        self.text.pack(fill="both", expand=True, padx=15, pady=12)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.after(100, self.poll)
        self.refresh()

    def choose_adb(self):
        path = filedialog.askopenfilename(parent=self.window, title="Wybierz adb.exe", filetypes=[("ADB", "adb.exe")])
        if path:
            self.adb_path.set(path)

    def report(self, message):
        self.text.insert("end", str(message) + "\n")
        if int(self.text.index("end-1c").split(".")[0]) > 600:
            self.text.delete("1.0", "100.0")
        self.text.see("end")

    def submit(self, operation, callback=None):
        if self.busy:
            self.report("Poczekaj na zakończenie bieżącej operacji ADB."); return
        try:
            adb = AdbLink(self.adb_path.get().strip())
        except (OSError, RuntimeError) as exc:
            self.report(exc); return
        self.owner.config["adbPath"] = adb.path
        self.busy = True
        self.report("ADB: operacja w toku…")
        def worker():
            try:
                self.queue.put((True, operation(adb), callback))
            except Exception as exc:
                self.queue.put((False, str(exc), None))
        self.pool.submit(worker)

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                success, result, callback = self.queue.get_nowait()
                self.busy = False
                if success and callback:
                    callback(result)
                else:
                    self.report(result)
        except Empty:
            pass
        self.window.after(100, self.poll)

    def refresh(self):
        def completed(devices):
            values = [f"{d['serial']} | {d['state']} | {d['description']}" for d in devices]
            self.devices.configure(values=values)
            if self.serial.get() not in values:
                self.serial.set(values[0] if values else "")
            self.report("\n".join(values) if values else "Brak telefonu w ADB. Włącz debugowanie i zaakceptuj autoryzację / sparuj Wi-Fi.")
        self.submit(lambda adb: adb.devices(), completed)

    def selected(self):
        parts = self.serial.get().split(" | ")
        if len(parts) < 2 or parts[1] != "device":
            self.report("Wybierz telefon w stanie device. unauthorized: zaakceptuj komunikat RSA na telefonie.")
            return ""
        return parts[0]

    def install(self):
        serial = self.selected()
        if serial:
            self.submit(lambda adb: adb.install(serial, self.apk))

    def start_video(self):
        serial = self.selected()
        if serial:
            self.submit(lambda adb: self.owner.video.start(adb.path, serial))

    def connect(self):
        serial = self.selected()
        if not serial:
            return
        self.owner.start_link()
        if self.owner.link is not None:
            port = int(self.owner.config["transportPort"])
            self.submit(lambda adb: adb.setup(serial, port))

    def diagnostics(self):
        serial = self.selected()
        if serial:
            self.submit(lambda adb: adb.diagnostics(serial))

    def pair(self):
        address, code = self.address.get().strip(), self.code.get().strip()
        self.code.set("")
        self.submit(lambda adb: adb.pair_wifi(address, code))

    def wifi(self):
        address = self.address.get().strip()
        self.submit(lambda adb: adb.connect_wifi(address))

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.window.destroy()
