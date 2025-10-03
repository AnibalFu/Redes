#import matplotlib.pyplot as plt
import time
import os

PACKET_RATE = 100  # Log every 100 packets

class Logger:
    def __init__(self, verbose: bool = False, output_dir: str = 'logs'):
        self.verbose = verbose
        print(f"[INFO] Logger initialized. Verbose mode is {'on' if self.verbose else 'off'}.")

        # Datos para RTT
        self.x_data = []
        self.y_data = []
        self.rtt_list = []        # Nueva lista de RTT
        self.packets_sent = 0     # Contador de paquetes

        # Datos para métricas extra
        self.bytes_sent = 0
        self.start_time = None
        self.retransmissions = 0

        # Carpeta para guardar resultados
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        #if self.verbose:
            # Para gráfico de Throughput
            #self.fig, (self.ax_rtt, self.ax_tp) = plt.subplots(2, 1, figsize=(8, 6))
            
            #self.fig, self.ax_rtt = plt.subplots(figsize=(8, 4))
            #self.line_rtt, = self.ax_rtt.plot([], [], label="RTT")
            #self.ax_rtt.set_xlabel("Tiempo (s)")
            #self.ax_rtt.set_ylabel("RTT (ms)")
            #self.ax_rtt.set_title("RTT en tiempo real")
            
            # Gráfico de Throughput (opcional)
            #self.line_tp, = self.ax_tp.plot([], [], label="Throughput")
            #self.ax_tp.set_xlabel("Tiempo (s)")
            #self.ax_tp.set_ylabel("KB/s")
            #self.ax_tp.set_title("Throughput en tiempo real")
            #plt.tight_layout()

    def log(self, message: str, quiet: bool = False):
        if self.verbose or quiet:
            print(message)

    def start_transfer(self):
        """Marcar el inicio de la transferencia"""
        self.start_time = time.time()
        self.bytes_sent = 0
        self.retransmissions = 0
        self.log("Transferencia iniciada")

    def add_bytes(self, nbytes: int, retransmission: bool = False):
        self.bytes_sent += nbytes
        if retransmission:
            self.retransmissions += 1
        if self.packets_sent % PACKET_RATE == 0:  
            self.log(f"[INFO] Bytes enviados: {self.bytes_sent}, Retransmisiones: {self.retransmissions}")


    def log_rtt(self, rtt: float):
        """Registrar un valor de RTT"""
        now = time.time()
        elapsed = now - self.start_time if self.start_time else 0
        self.rtt_list.append(rtt)
        self.packets_sent += 1
        if self.packets_sent % PACKET_RATE == 0:
            self.log(f"[RTT] Paquete {self.packets_sent}: RTT={rtt*1000:.2f} ms, Tiempo transcurrido={elapsed:.2f} s")
        if self.verbose:
            self.x_data.append(elapsed)
            self.y_data.append(rtt)

    def log_final(self, filename: str = 'metrics.txt'):
        """Guardar métricas y mostrar resultados finales"""
        
        duration = time.time() - self.start_time if self.start_time else 0
        throughput = (self.bytes_sent / 1024) / duration if duration > 0 else 0
        rtt_avg = (sum(self.rtt_list)/len(self.rtt_list))*1000 if self.rtt_list else 0  # ms

        summary = (
            f"Duración: {duration:.2f} s\n"
            f"Bytes enviados: {self.bytes_sent}\n"
            f"Paquetes enviados: {self.packets_sent}\n"
            f"Throughput promedio: {throughput:.2f} KB/s\n"
            f"RTT promedio: {rtt_avg:.2f} ms\n"
            f"Retransmisiones: {self.retransmissions}\n"
        )

        self.log("Resultados finales:\n" + summary)

        # Guardar métricas en archivo
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w") as f:
            f.write(summary)

        #if self.verbose:
            #self.line_rtt.set_xdata(self.x_data)
            #self.line_rtt.set_ydata(self.y_data)
            #self.ax_rtt.relim()
            #self.ax_rtt.autoscale_view()
            #plt.draw()
            #plt.pause(10)
