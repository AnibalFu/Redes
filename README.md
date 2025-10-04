# Redes

**A**: Application

**M**: Minimal

**C**: Client

**G**: Go-Back-N

**F**: File Transfer

## Integrantes

- [Infanti Franciso](https://github.com/FranInfanti)

- [Anibal Fu](https://github.com/anibalfu)

- [Weng Xu Marcos Tomás](https://github.com/wxmarcos)

- [Camila Figueroa](https://github.com/camilaFigueroaCillo)

- [Giuliana Pazos](https://github.com/giulianapazos)

## Inicialización

### Dependencias para Mininet

```bash
sudo apt install mininet
sudo apt install xterm   # Para visualizar terminales de cada host
```

### Ejecución de la topología

```bash
sudo -E python3 tests/net.py   # net.py es el archivo con la topología
```

Una vez inicializado Mininet, abre terminales en cada host (n es la cantidad de hosts):

```bash
xterm h1 h2 ... hn
```

> **Nota:** El host conectado al enlace con 10% packet loss debe ser el servidor.

---

### Iniciar el servidor

En la terminal del host servidor, ejecuta:

```bash
python3 src/start-server.py -H <IP_SERVIDOR> -p <PUERTO> -r <PROTOCOLO_RECUPERACION>
```

### Subir un archivo desde el cliente

En la terminal del host cliente, ejecuta:

```bash
python3 src/upload.py -H <IP_SERVIDOR> -p <PUERTO> -s <RUTA_ARCHIVO> -n <NOMBRE_ARCHIVO> -r <PROTOCOLO_RECUPERACION>
```

> Reemplaza `<IP_SERVIDOR>`, `<PUERTO>`, `<RUTA_ARCHIVO>`, `<NOMBRE_ARCHIVO>` y `<PROTOCOLO_RECUPERACION>` según corresponda.

Asegúrate de tener instaladas las dependencias necesarias y de ejecutar los comandos desde la raíz del proyecto.