#IMPORTACIONES Y CONFIGURACIÓN
import json                         # Para leer y escribir los archivos .nota
import re                           # Para buscar links dentro del texto
import webbrowser                   # Para abrir los links en el navegador
import os                           # Para armar la ruta del archivo
import tkinter as tk                # La librería que dibuja las ventanas
from tkinter import messagebox      # Para las ventanitas de preguntas y errores
from tkinter import filedialog      # Para las ventanas de "Guardar como" y "Abrir"
import sys                          # Para cerrar esta copia si ya hay otra abierta
import socket                       # Para que una segunda copia de la app le avise a la primera
import threading                    # Para escuchar el atajo de teclado sin congelar las notas
import queue                        # Para pasar avisos desde esos "hilos" a las notas de forma segura
import ctypes                       # Para usar funciones de Windows (el atajo de teclado)
import ctypes.wintypes              # Tipos de datos de Windows que necesita ctypes

# Colores que aparecen en el menú de colores.
# Para agregar un color, solo súmalo a esta lista.
COLORES = ["#fff475", "#ccff90", "#a7ffeb", "#aecbfa", "#f8bbd0", "#ffd180", "#e6c9a8"]

# Texto gris que aparece en el título cuando está vacío
AVISO_TITULO = "Escribe un título..."

# Cómo reconocer un link: algo que empieza con http://, https:// o www.
# y sigue hasta el próximo espacio o salto de línea
PATRON_LINK = re.compile(r"(https?://\S+|www\.\S+)")

# Las notas guardadas con el botón Guardar usan la extensión .nota (por dentro es JSON)
EXTENSION = ".nota"
TIPOS_ARCHIVO = [("Nota adhesiva", "*.nota"), ("Todos los archivos", "*.*")]

# Atajo de teclado para crear una nota desde cualquier parte: Ctrl + Alt + N
# Para cambiar la letra, cambia "N" por otra (siempre en mayúscula)
TECLA_RAPIDA = "N"

# Puerto interno que usa la app para saber si ya hay una copia abierta
PUERTO_INTERNO = 47231



#FUNCIÓN DE AYUDA
def oscurecer(color_hex, factor=0.85):
    """Recibe un color como '#fff475' y devuelve uno un poco más oscuro.
    Se usa para que la barra de arriba se note distinta del papel."""
    # Un color '#RRGGBB' tiene 3 partes: rojo, verde y azul.
    # Cada parte se convierte a número (0 a 255) y se multiplica por 0.85
    r = int(int(color_hex[1:3], 16) * factor)
    g = int(int(color_hex[3:5], 16) * factor)
    b = int(int(color_hex[5:7], 16) * factor)
    # Se vuelve a juntar en formato '#RRGGBB'
    return f"#{r:02x}{g:02x}{b:02x}"




# Cada vez que hacemos clic al + aparece una nota nueva en pantalla.
# Está dividida en bloques:
#   a) __init__        -> arma la nota (ventana, barra, título, texto, esquina)
#   b) Colores         -> aplicar_color, abrir_colores, elegir_color, cerrar_colores
#   c) Título y texto  -> poner_aviso, quitar_aviso, leer_titulo, leer_texto
#   d) Minimizar       -> minimizar, restaurar, alternar_minimizar, mostrar_contenido
#   e) Mover           -> empezar_mover, mover
#   f) Cambiar tamaño  -> empezar_redimensionar, redimensionar
#   g) Borrar          -> borrar
#   h) Links           -> marcar_links, abrir_link
#   i) Guardar archivo -> guardar_en_archivo, avisar, limpiar_aviso_barra, esta_vacia, cargar_contenido
# ---------------------------------------------------------------------
class Nota:

    #Arma la nota
    # "app"   = la App que la controla (para pedirle crear notas, abrir archivos o salir)
    # "datos" = la info guardada de la nota (título, texto, color, posición, tamaño)
    def __init__(self, app, datos):
        self.app = app
        # Si la nota no tiene color guardado, usa el primero (amarillo)
        self.color = datos.get("color", COLORES[0])
        self.menu_colores = None   # La ventanita de colores (None = cerrada)
        self.minimizada = False
        # Dónde se guardó esta nota con Guardar (None = nunca se ha guardado)
        self.ruta = datos.get("ruta")

        # Posición y tamaño. Los guardamos nosotros mismos para tenerlos
        # siempre a mano (aunque la nota esté minimizada).
        self.ancho = datos.get("ancho", 260)
        self.alto = datos.get("alto", 240)
        self.x = datos.get("x", 100)
        self.y = datos.get("y", 100)

        # -- La ventana --
        self.ventana = tk.Toplevel(app.raiz)
        self.ventana.overrideredirect(True)        # Quita el borde y la barra de Windows
        self.ventana.attributes("-topmost", True)  # Siempre encima de las otras ventanas
        self.ventana.geometry(f"{self.ancho}x{self.alto}+{self.x}+{self.y}")  # "ANCHOxALTO+X+Y"

        # -- La barra de arriba (de aquí se agarra para mover) --
        self.barra = tk.Frame(self.ventana, height=28)
        self.barra.pack(fill="x")  # Ocupa todo el ancho

        # Botones: Abrir, Guardar, + y ● a la izquierda; ✕ y — a la derecha
        # Abrir se lo pide a la App, porque abrir puede crear una nota nueva
        # (le pasa esta nota para que, si está vacía, la use en vez de crear otra)
        self.btn_abrir = self.crear_boton("Abrir", lambda: app.abrir_nota_guardada(self))
        self.btn_abrir.pack(side="left")
        self.btn_guardar = self.crear_boton("Guardar", self.guardar_en_archivo)
        self.btn_guardar.pack(side="left")
        self.btn_nueva = self.crear_boton("+", app.nueva_nota)   # Nueva nota: lo hace la App
        self.btn_nueva.pack(side="left")
        self.btn_color = self.crear_boton("●", self.abrir_colores)
        self.btn_color.pack(side="left")
        self.btn_borrar = self.crear_boton("✕", self.borrar)
        self.btn_borrar.pack(side="right")
        self.btn_minimizar = self.crear_boton("—", self.alternar_minimizar)
        self.btn_minimizar.pack(side="right")

        # Etiqueta en el medio de la barra: muestra el título cuando está minimizada
        self.etiqueta = tk.Label(self.barra, text="", anchor="w",
                                 font=("Segoe UI", 10, "bold"))
        self.etiqueta.pack(side="left", fill="x", expand=True)

        # -- El título (va arriba, antes del texto) --
        self.titulo = tk.Entry(self.ventana, bd=0, font=("Segoe UI", 12, "bold"),
                               highlightthickness=0)
        self.titulo.insert(0, datos.get("titulo", ""))  # Pone el título guardado
        self.hay_aviso = False  # True cuando se está mostrando el texto gris

        # Al entrar al título se quita el aviso gris; al salir, vuelve si está vacío
        self.titulo.bind("<FocusIn>", self.quitar_aviso)
        self.titulo.bind("<FocusOut>", self.poner_aviso)
        self.titulo.bind("<Button-1>", lambda e: self.titulo.focus_force())
        # Al presionar Enter en el título, pasa a escribir el texto de la nota
        self.titulo.bind("<Return>", lambda e: self.texto.focus_set())

        # Línea delgada que separa el título del texto
        self.linea = tk.Frame(self.ventana, height=1)

        # -- La zona donde se escribe --
        self.texto = tk.Text(self.ventana, wrap="word", bd=0, font=("Segoe UI", 11),
                             padx=8, pady=6, undo=True, highlightthickness=0)
        self.texto.insert("1.0", datos.get("texto", ""))  # Pone el texto guardado
        # Cada vez que sueltas una tecla: revisa los links
        self.texto.bind("<KeyRelease>", self.al_escribir)

        #Links se ven azules y subrayados, y se abren con un clic 
        self.texto.tag_config("link", foreground="#1a5fb4", underline=True)
        self.texto.tag_bind("link", "<Enter>", lambda e: self.texto.config(cursor="hand2"))
        self.texto.tag_bind("link", "<Leave>", lambda e: self.texto.config(cursor="xterm"))
        self.texto.tag_bind("link", "<Button-1>", self.abrir_link)
        self.marcar_links()  # Marca los links que ya venían guardados
        # Al hacer clic en el texto, la nota toma el foco (para poder escribir)
        self.texto.bind("<Button-1>", lambda e: self.texto.focus_force())

        #La esquina ◢ para cambiar el tamaño
        self.esquina = tk.Label(self.ventana, text="◢", cursor="size_nw_se")

        #Pone en la nota el título, la línea, el texto y la esquina (en ese orden)
        self.mostrar_contenido()

        #Conectar el mouse con las acciones
        # Mover: se puede agarrar la barra o la etiqueta del medio
        for parte in (self.barra, self.etiqueta):
            parte.bind("<ButtonPress-1>", self.empezar_mover)
            parte.bind("<B1-Motion>", self.mover)

        #Cambiar tamaño: apretar, arrastrar y soltar la esquina
        self.esquina.bind("<ButtonPress-1>", self.empezar_redimensionar)
        self.esquina.bind("<B1-Motion>", self.redimensionar)

        # -- Menú de clic derecho en la barra --
        menu = tk.Menu(self.ventana, tearoff=0)
        menu.add_command(label="Nueva nota", command=app.nueva_nota)
        menu.add_command(label="Salir", command=lambda: app.confirmar_salir(self.ventana))
        for parte in (self.barra, self.etiqueta):
            parte.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        #Pinta todo con el color de la nota
        self.aplicar_color()
        #Si la nota no tiene título, muestra el aviso gris
        self.poner_aviso()

    def crear_boton(self, simbolo, accion):
        #Crea un botón plano para la barra. Así no repetimos el mismo código en cada botón
        #Los símbolos (+, ●, ✕, —) usan un ancho fijo; las palabras (Abrir, Guardar) el que necesiten
        ancho = 2 if len(simbolo) == 1 else 0
        #highlightthickness=0 asegura que no aparezca un borde gris alrededor de los botones
        return tk.Button(self.barra, text=simbolo, command=accion, bd=0, highlightthickness=0,
                         relief="flat", font=("Segoe UI", 10), width=ancho, padx=6, cursor="hand2")

    #Colores
    def aplicar_color(self):
        #Pinta cada parte de la nota: el papel con el color y la barra más oscura
        barra = oscurecer(self.color)
        self.ventana.config(bg=self.color)
        self.titulo.config(bg=self.color, insertbackground="#333")  # insertbackground = color del cursor
        self.texto.config(bg=self.color, insertbackground="#333")
        self.linea.config(bg=barra)
        self.esquina.config(bg=self.color, fg=barra)
        self.barra.config(bg=barra)
        self.etiqueta.config(bg=barra)
        for boton in (self.btn_nueva, self.btn_color, self.btn_guardar, self.btn_abrir,
                      self.btn_borrar, self.btn_minimizar):
            boton.config(bg=barra, activebackground=self.color)

    def abrir_colores(self):
        #Abre una ventanita debajo del botón ● con un cuadrado por cada color
        # Si ya estaba abierta, el mismo botón la cierra
        if self.menu_colores:
            self.cerrar_colores()
            return

        self.menu_colores = tk.Toplevel(self.ventana)
        self.menu_colores.overrideredirect(True)
        self.menu_colores.attributes("-topmost", True)
        self.menu_colores.config(bg="#ffffff", padx=4, pady=4)

        for color in COLORES:
            # El color que tiene la nota ahora se marca con un borde
            borde = 2 if color == self.color else 0
            cuadro = tk.Frame(self.menu_colores, bg=color, width=22, height=22,
                              cursor="hand2", highlightthickness=borde,
                              highlightbackground="#333")
            cuadro.pack(side="left", padx=2)
            # "c=color" guarda el color de ESTE cuadro para cuando se haga clic
            cuadro.bind("<Button-1>", lambda e, c=color: self.elegir_color(c))

        # La pone justo debajo del botón ●
        x = self.btn_color.winfo_rootx()
        y = self.btn_color.winfo_rooty() + self.btn_color.winfo_height()
        self.menu_colores.geometry(f"+{x}+{y}")

        # Se cierra si haces clic en otro lado o presionas Esc
        self.menu_colores.bind("<FocusOut>", lambda e: self.cerrar_colores())
        self.menu_colores.bind("<Escape>", lambda e: self.cerrar_colores())
        self.menu_colores.focus_force()

    def elegir_color(self, color):
        #Cambia el color de la nota al que se eligió en el menú
        self.color = color
        self.aplicar_color()
        self.cerrar_colores()

    def cerrar_colores(self):
        #Cierra la ventanita de colores (si está abierta)
        if self.menu_colores:
            self.menu_colores.destroy()
            self.menu_colores = None

    #Titulo
    def poner_aviso(self, evento=None):
        #Si el título está vacío, muestra 'Escribe un título...' en gris
        if not self.titulo.get():
            self.titulo.insert(0, AVISO_TITULO)
            self.titulo.config(fg="#888")
            self.hay_aviso = True

    def quitar_aviso(self, evento=None):
        #Al hacer clic en el título, borra el texto gris para escribir
        if self.hay_aviso:
            self.titulo.delete(0, "end")
            self.titulo.config(fg="#222")
            self.hay_aviso = False

    def leer_titulo(self):
        #Devuelve el título real (vacío si solo está el aviso gris)
        return "" if self.hay_aviso else self.titulo.get()

    def leer_texto(self):
        #Devuelve todo el texto de la nota ("end-1c" = sin el salto de línea final)
        return self.texto.get("1.0", "end-1c")

    #Minimizar
    #la nota se enrolla y queda solo la barra con el título.
    def alternar_minimizar(self):
        #El botón - minimiza si ya está minimizada la vuelve a abrir
        if self.minimizada:
            self.restaurar()
        else:
            self.minimizar()

    def minimizar(self):
        self.cerrar_colores()
        #Esconde todo menos la barra
        self.titulo.pack_forget()
        self.linea.pack_forget()
        self.texto.pack_forget()
        self.esquina.place_forget()
        #Muestra el título en la barra y cambia el botón a ▢ (abrir)
        self.etiqueta.config(text=self.leer_titulo() or "Sin título")
        self.btn_minimizar.config(text="▢")
        #Achica la ventana al alto de la barra
        alto_barra = self.barra.winfo_reqheight()
        self.ventana.geometry(f"{self.ancho}x{alto_barra}")
        self.minimizada = True

    def restaurar(self):
        # Vuelve a mostrar todo, en el mismo orden de antes
        self.mostrar_contenido()
        self.etiqueta.config(text="")
        self.btn_minimizar.config(text="—")
        # Recupera su tamaño normal
        self.ventana.geometry(f"{self.ancho}x{self.alto}")
        self.minimizada = False

    def mostrar_contenido(self):
        #Muestra el título, la línea, el texto y la esquina debajo de la barra
        #Se usa al armar la nota y al restaurarla, así los márgenes están en un solo lugar
        self.titulo.pack(fill="x", padx=8, pady=(6, 0))
        self.linea.pack(fill="x", padx=8, pady=(2, 0))
        self.texto.pack(fill="both", expand=True)          # Ocupa todo el espacio que queda
        self.esquina.place(relx=1, rely=1, anchor="se")    # Pegada abajo a la derecha

    #Mover la nota
    def empezar_mover(self, evento):
        #Al apretar la barra: recuerda en qué punto de la nota la agarraste
        self.cerrar_colores()
        self.dx = evento.x_root - self.x
        self.dy = evento.y_root - self.y

    def mover(self, evento):
        #Mientras arrastras: mueve la nota siguiendo al mouse
        self.x = evento.x_root - self.dx
        self.y = evento.y_root - self.dy
        self.ventana.geometry(f"+{self.x}+{self.y}")

    #Cambiar tamaño
    def empezar_redimensionar(self, evento):
        #Al apretar la esquina: recuerda dónde estaba el mouse y el tamaño inicial
        self.inicio_x = evento.x_root
        self.inicio_y = evento.y_root
        self.inicio_ancho = self.ancho
        self.inicio_alto = self.alto

    def redimensionar(self, evento):
        #Mientras arrastras: tamaño inicial + lo que se movió el mouse max() evita que la nota quede más chica que 180x150
        self.ancho = max(180, self.inicio_ancho + evento.x_root - self.inicio_x)
        self.alto = max(150, self.inicio_alto + evento.y_root - self.inicio_y)
        self.ventana.geometry(f"{self.ancho}x{self.alto}")

    #Borrar
    def borrar(self):
        #Borra la nota. Si tiene título o texto, primero pregunta
        self.cerrar_colores()
        if not self.esta_vacia():
            if not messagebox.askyesno("Notas-adhesivas", "¿Salir de Notas-adhesivas?", parent=self.ventana):
                return  # Dijiste que no: no hace nada
        self.app.notas.remove(self)  # La saca de la lista de la App
        self.ventana.destroy()       # Cierra su ventana
        #Aunque sea la última nota, la app sigue abierta en segundo plano
        #para que el atajo de teclado pueda crear otra (Salir la cierra del todo)

    #Links
    def al_escribir(self, evento=None):
        #Se llama cada vez que sueltas una tecla (también al pegar con Ctrl+V)
        self.marcar_links()

    def marcar_links(self):
        #Busca los links en el texto y los pinta azules y subrayados
        #Primero quita las marcas viejas
        self.texto.tag_remove("link", "1.0", "end")
        contenido = self.leer_texto()

        for encontrado in PATRON_LINK.finditer(contenido):
            # Quita signos que suelen quedar pegados al final, como "." o ")"
            link = encontrado.group().rstrip(".,;:!?)")
            # "1.0+25c" significa: desde el inicio del texto, avanza 25 letras
            inicio = f"1.0+{encontrado.start()}c"
            fin = f"1.0+{encontrado.start() + len(link)}c"
            self.texto.tag_add("link", inicio, fin)

    def abrir_link(self, evento):
        #Abre en el navegador el link donde hiciste clic
        #Posición exacta del clic dentro del texto
        posicion = self.texto.index(f"@{evento.x},{evento.y}")
        #Busca el link que contiene esa posición (su inicio y su fin)
        rango = self.texto.tag_prevrange("link", f"{posicion}+1c")
        if not rango:
            return
        link = self.texto.get(rango[0], rango[1])
        #Si empieza con "www." le falta el "https://" para que el navegador lo entienda
        if link.startswith("www."):
            link = "https://" + link
        webbrowser.open(link)
        return "break"  #Evita que el clic además mueva el cursor

    #Guardar un archivo
    def guardar_en_archivo(self):
        #Guarda esta nota en un archivo nota la primera vez pregunta dónde; las siguientes guarda directo en el mismo lugar
        self.cerrar_colores()

        #No deja guardar si la nota no tiene título
        if not self.leer_titulo().strip():
            messagebox.showwarning("Notas-adhesivas", "Escribe un título antes de guardar la nota.",
                                   parent=self.ventana)
            if self.minimizada:
                self.restaurar()  # Para que se vea el título y puedas escribirlo
            self.titulo.focus_force()  # Deja el cursor en el título
            return

        #Si nunca se ha guardado (o la carpeta ya no existe), pregunta dónde
        if not self.ruta or not os.path.isdir(os.path.dirname(self.ruta)):
            #Usa el título como nombre del archivo, quitando signos que Windows no acepta
            nombre = re.sub(r'[<>:"/\\|?*]', "", self.leer_titulo()).strip() or "nota"
            ruta = filedialog.asksaveasfilename(
                parent=self.ventana, title="Guardar nota",
                initialfile=nombre + EXTENSION, defaultextension=EXTENSION,
                filetypes=TIPOS_ARCHIVO)
            if not ruta:
                return  # Apretaste "Cancelar"
            self.ruta = ruta

        #Solo se guarda lo que importa: título, texto y color
        contenido = {
            "titulo": self.leer_titulo(),
            "texto": self.leer_texto(),
            "color": self.color,
        }
        try:
            with open(self.ruta, "w", encoding="utf-8") as f:
                json.dump(contenido, f, ensure_ascii=False, indent=2)
        except OSError:
            messagebox.showerror("Error", "No se pudo guardar la nota.", parent=self.ventana)
            self.ruta = None
            return

        self.avisar("Guardada ✓")

    def avisar(self, mensaje):
        #Muestra un mensaje cortito en la barra por 1,5 segundos
        if self.minimizada:
            return  # Minimizada, la barra está mostrando el título
        self.etiqueta.config(text=mensaje)
        self.ventana.after(1500, self.limpiar_aviso_barra)

    def limpiar_aviso_barra(self):
        #Borra el mensaje de la barra (si la nota sigue abierta y no está minimizada)
        if self.etiqueta.winfo_exists() and not self.minimizada:
            self.etiqueta.config(text="")

    def esta_vacia(self):
        #Devuelve True si la nota no tiene título ni texto
        return not self.leer_titulo().strip() and not self.leer_texto().strip()

    def cargar_contenido(self, guardado, ruta):
        #Pone en esta misma nota el título, texto y color de una nota guardada
        #Título: primero quita el aviso gris (si está) y lo que haya escrito
        self.titulo.delete(0, "end")
        self.titulo.config(fg="#222")
        self.hay_aviso = False
        self.titulo.insert(0, guardado.get("titulo", ""))
        self.poner_aviso()  # Si el título venía vacío, vuelve el aviso gris

        #Texto: borra lo que había y pone el guardado
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", guardado.get("texto", ""))
        self.marcar_links()

        #Color y ruta (así Guardar vuelve a guardar en el mismo archivo)
        self.color = guardado.get("color", COLORES[0])
        self.aplicar_color()
        self.ruta = ruta

        #Si está minimizada, actualiza el título que se ve en la barra
        if self.minimizada:
            self.etiqueta.config(text=self.leer_titulo() or "Sin título")



# ---------------------------------------------------------------------
# Tiene la lista de notas y se encarga de lo que afecta a todas:
#   - crear notas nuevas
#   - abrir notas guardadas
#   - escuchar el atajo de teclado
#   - cerrar el programa
# Las notas solo se guardan cuando apretas Guardar (no hay guardado automático)
# ---------------------------------------------------------------------
class App:

    def __init__(self, servidor):
        self.raiz = tk.Tk()   # Ventana principal (Tkinter siempre necesita una)
        self.raiz.withdraw()  # La escondemos: solo queremos ver las notas
        self.notas = []       # Aquí se guardan todas las notas abiertas
        self.avisos = queue.Queue()  # Avisos que llegan del atajo o de otra copia de la app

        # Escucha el atajo de teclado y a otras copias de la app, cada uno en su propio "hilo"
        threading.Thread(target=self.escuchar_atajo, daemon=True).start()
        threading.Thread(target=self.escuchar_otras_copias, args=(servidor,), daemon=True).start()
        self.raiz.after(200, self.revisar_avisos)

        # Siempre parte con una nota vacía
        self.nueva_nota()

    def posicion_nueva(self):
        #Devuelve dónde poner una nota nueva: un poco corrida para que no tape a las otras
        desplazamiento = 30 * len(self.notas)
        return 150 + desplazamiento, 150 + desplazamiento

    def nueva_nota(self):
        #Crea una nota nueva vacía
        x, y = self.posicion_nueva()
        nota = Nota(self, {"x": x, "y": y})
        self.notas.append(nota)
        nota.titulo.focus_force()  # Lo primero que se escribe es el título

    def abrir_nota_guardada(self, nota_actual):
        #Abre un archivo .nota
        #Si la nota desde donde se apretó Abrir está vacía, lo carga ahí; si no, crea una nota nueva
        ventana_padre = nota_actual.ventana
        ruta = filedialog.askopenfilename(parent=ventana_padre, title="Abrir nota guardada",
                                          filetypes=TIPOS_ARCHIVO)
        if not ruta:
            return  # Apretaste "Cancelar"
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            if not isinstance(guardado, dict):
                raise ValueError
        except (OSError, ValueError):  # ValueError también cubre un JSON dañado
            messagebox.showerror("Error", "No se pudo abrir ese archivo.", parent=ventana_padre)
            return

        #Si la nota actual está vacía, se usa esa misma y no se crea otra
        if nota_actual.esta_vacia():
            nota_actual.cargar_contenido(guardado, ruta)
            return

        x, y = self.posicion_nueva()
        nota = Nota(self, {
            "titulo": guardado.get("titulo", ""),
            "texto": guardado.get("texto", ""),
            "color": guardado.get("color", COLORES[0]),
            "ruta": ruta,  # Así Guardar vuelve a guardar en el mismo archivo
            "x": x,
            "y": y,
        })
        self.notas.append(nota)

    #Atajo de teclado
    def escuchar_atajo(self):
        #Registra Ctrl + Alt + TECLA_RAPIDA en Windows y espera a que lo presiones
        #Corre en su propio hilo, por eso no toca las notas: solo deja un aviso
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
        WM_HOTKEY = 0x0312
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(TECLA_RAPIDA)):
            self.avisos.put("atajo_ocupado")  # Otro programa ya usa esa combinación
            return
        mensaje = ctypes.wintypes.MSG()
        #GetMessageW espera (sin gastar procesador) hasta que llegue un mensaje de Windows
        while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) != 0:
            if mensaje.message == WM_HOTKEY:
                self.avisos.put("nueva_nota")

    def escuchar_otras_copias(self, servidor):
        #Si abres el .exe otra vez, esa segunda copia avisa aquí y se cierra
        #Así nunca quedan dos apps abiertas al mismo tiempo
        while True:
            try:
                conexion, _ = servidor.accept()
            except OSError:
                return  # El puerto se cerró: deja de escuchar
            with conexion:
                #Si la conexión no envía nada en 2 segundos, se descarta (así este hilo nunca se queda pegado)
                conexion.settimeout(2)
                try:
                    if conexion.recv(32) == b"nueva_nota":
                        self.avisos.put("nueva_nota")
                except OSError:
                    pass  # No llegó nada a tiempo: sigue esperando la próxima

    def revisar_avisos(self):
        #Cada 0,2 segundos revisa si llegó algún aviso y lo atiende
        #(las notas solo se pueden tocar desde aquí, no desde los otros hilos)
        while not self.avisos.empty():
            aviso = self.avisos.get()
            if aviso == "nueva_nota":
                self.nueva_nota()
            elif aviso == "atajo_ocupado":
                messagebox.showwarning("Notas-adhesivas",
                                       f"El atajo Ctrl + Alt + {TECLA_RAPIDA} ya lo usa otro programa.")
        self.raiz.after(200, self.revisar_avisos)

    #Abrir y cerrar
    def confirmar_salir(self, ventana_padre):
        #Si alguna nota tiene contenido, pregunta antes de cerrar (lo no guardado con Guardar se pierde)
        if any(not nota.esta_vacia() for nota in self.notas):
            if not messagebox.askyesno("Notas-adhesivas",
                                       "¿Salir de Notas-adhesivas?\nLo que no guardaste con el botón Guardar se perderá.",
                                       parent=ventana_padre):
                return  # Dijiste que no: no hace nada
        self.salir()

    def salir(self):
        #Cierra el programa
        self.raiz.destroy()

    def iniciar(self):
        #Deja el programa abierto, esperando clics y teclas
        self.raiz.mainloop()



# PUNTO DE PARTIDA
# Esto solo se ejecuta cuando abres este archivo directamente
if __name__ == "__main__":
    #Intenta "reservar" el puerto interno: si ya está ocupado, la app ya está abierta
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        servidor.bind(("127.0.0.1", PUERTO_INTERNO))  # 127.0.0.1 = solo este PC, nada de internet
        servidor.listen()
    except OSError:
        #Ya hay una copia abierta: le pide una nota nueva y esta copia se cierra
        try:
            with socket.create_connection(("127.0.0.1", PUERTO_INTERNO), timeout=2) as conexion:
                conexion.sendall(b"nueva_nota")
        except OSError:
            pass
        sys.exit()

    App(servidor).iniciar()
