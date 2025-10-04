import time
import os
from colorama import Fore, Style, init
from tqdm import tqdm

init(autoreset=True) 

PACKET_RATE = 100  

class Logger:
    def __init__(self, verbose: bool = False, output_dir: str = 'logs'):
        self.verbose = verbose
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Logger inicializado. Modo 'verbose' está {'encendido' if self.verbose else 'apagadp'}.")

        # Datos para RTT
        self.x_data = []
        self.y_data = []
        self.rtt_list = []
        self.packets_sent = 0

        # Datos extra
        self.bytes_sent = 0
        self.start_time = None
        self.retransmissions = 0

        # Progreso
        self.progress_bar = None
        self.total_bytes = None

        # Carpeta para guardar resultados
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def log(self, message: str, quiet: bool = False):
        if self.verbose or quiet:
            print(message + '\n')
    
    def log_error(self, message: str):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}\n")

    def start_transfer(self, total_bytes: int = None, mode: str = "Upload"):
        """Marcar el inicio de la transferencia"""
        self.start_time = time.time()
        self.bytes_sent = 0
        self.retransmissions = 0
        self.total_bytes = total_bytes
        self.log(f"{Fore.GREEN}[START]{Style.RESET_ALL} Transferencia iniciada", True)

        if not self.verbose:
            self.progress_bar = tqdm(
                total=total_bytes,    
                unit="B",
                unit_scale=True,
                desc=mode,
                colour="green" if mode == "Upload" else "blue",
                leave=True
            )


    def add_bytes(self, nbytes: int, retransmission: bool = False):
        """Registrar bytes enviados y actualizar progreso"""
        self.bytes_sent += nbytes
        if retransmission:
            self.retransmissions += 1

        if self.progress_bar is not None:
            self.progress_bar.update(nbytes)

        if self.packets_sent % PACKET_RATE == 0:
            self.log(
                f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Bytes enviados: {self.bytes_sent}, "
                f"Retransmisiones: {self.retransmissions}"
            )

    def log_rtt(self, rtt: float):
        """Registrar un valor de RTT"""
        now = time.time()
        elapsed = now - self.start_time if self.start_time else 0
        self.rtt_list.append(rtt)
        self.packets_sent += 1

        if self.packets_sent % PACKET_RATE == 0:
            self.log(
                f"{Fore.MAGENTA}[RTT]{Style.RESET_ALL} Paquete {self.packets_sent}: "
                f"RTT={rtt*1000:.2f} ms, Tiempo transcurrido={elapsed:.2f} s"
            )

        if self.verbose:
            self.x_data.append(elapsed)
            self.y_data.append(rtt)

    def log_final(self, filename: str = 'metrics.txt'):
        """Guardar métricas y mostrar resultados finales"""
        if self.progress_bar is not None:
            self.progress_bar.close()

        self.log(f"{Fore.GREEN}[END]{Style.RESET_ALL} Transferencia finalizada", True)

        duration = time.time() - self.start_time if self.start_time else 0
        throughput = (self.bytes_sent / 1024) / duration if duration > 0 else 0
        rtt_avg = (sum(self.rtt_list)/len(self.rtt_list))*1000 if self.rtt_list else 0

        summary = (
            f"Duración: {duration:.2f} s\n"
            f"Bytes enviados: {self.bytes_sent}\n"
            f"Paquetes enviados: {self.packets_sent}\n"
            f"Throughput promedio: {throughput:.2f} KB/s\n"
            f"RTT promedio: {rtt_avg:.2f} ms\n"
            f"Retransmisiones: {self.retransmissions}\n"
        )

        self.log(f"{Fore.CYAN}[RESULTADOS FINALES]{Style.RESET_ALL}\n" + summary)

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w") as f:
            f.write(summary)
