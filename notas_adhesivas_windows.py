# =====================================================================
# IMPORTACIONES
# =====================================================================
import json
import re
import webbrowser
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from tkinter import ttk
from tkinter import font as tkfont
import sys
import socket
import threading
import queue
import ctypes
import ctypes.wintypes
import pystray
from PIL import Image, ImageDraw


# =====================================================================
# CONFIGURACIÓN
# =====================================================================

# Colores que aparecen en el menú de colores (el primero es el de las notas nuevas)
# Para agregar un color, solo súmalo a esta lista
COLORES = ["#fff475", "#ccff90", "#a7ffeb", "#aecbfa", "#f8bbd0", "#ffd180", "#e6c9a8"]

# Cómo se ve una pestaña fijada con 📌: botón rojo y una franja roja arriba de la pestaña
COLOR_FIJADA = "#d9534f"
# Color del 📌 cuando la pestaña abierta NO está fijada (gris, se ve "apagado")
COLOR_SIN_FIJAR = "#8a8a8a"

# Texto gris que aparece en el título cuando está vacío
AVISO_TITULO = "Escribe un título..."

# Letra de las pestañas nuevas (se cambia en la barra de abajo de cada nota)
FUENTE_POR_DEFECTO = "Segoe UI"
TAMANO_POR_DEFECTO = 11
# Tamaños que se pueden elegir en la barra de abajo
TAMANOS = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36]

# Qué tanto se ve la nota en el modo "Transparente" (☰ → Configuración): 0.6 = 60 %
OPACIDAD_TRANSPARENTE = 0.6

# Cómo reconocer un link: algo que empieza con http://, https:// o www.
# y sigue hasta el próximo espacio o salto de línea
PATRON_LINK = re.compile(r"(https?://\S+|www\.\S+)")

# Archivos de nota: se guardan con la extensión .nota (por dentro son JSON)
EXTENSION = ".nota"
TIPOS_ARCHIVO = [("Nota adhesiva", "*.nota"), ("Todos los archivos", "*.*")]

# Atajos de teclado POR DEFECTO (funcionan desde cualquier programa)
# Cada usuario puede cambiarlos en ☰ → Configuración
TECLA_RAPIDA = "N"    # Ctrl + Alt + N: crea una nota nueva
TECLA_OCULTAR = "B"   # Ctrl + Alt + B: oculta todas las notas (o las vuelve a mostrar)

# Letras y números que se pueden elegir para los atajos
TECLAS_PERMITIDAS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# Archivo donde se guardan los atajos que elige el usuario
# (en la carpeta de datos de Windows, ej: C:\Users\alons\AppData\Roaming\Notas-adhesivas)
ARCHIVO_CONFIG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                              "Notas-adhesivas", "config.json")

# Archivo donde se guardan solas las pestañas fijadas con 📌 (en la misma carpeta)
ARCHIVO_FIJADAS = os.path.join(os.path.dirname(ARCHIVO_CONFIG), "fijadas.json")

# Puerto interno que usa la app para saber si ya hay una copia abierta
PUERTO_INTERNO = 47231

# Imagen del ícono de la barra de íconos ocultos (va dentro del .exe al compilar)
ARCHIVO_ICONO = "icono.ico"


# =====================================================================
# FUNCIONES DE AYUDA
# =====================================================================

def oscurecer(color_hex, factor=0.85):
    # Recibe un color como "#fff475" y devuelve uno un poco más oscuro
    r = int(int(color_hex[1:3], 16) * factor)
    g = int(int(color_hex[3:5], 16) * factor)
    b = int(int(color_hex[5:7], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def acortar(texto, largo):
    # Corta un texto a "largo" letras como máximo, terminando en "…" si se cortó
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


def pestana_nueva(datos=None):
    # Devuelve una pestaña con todos sus datos; lo que no venga en "datos" queda con el valor por defecto
    datos = datos or {}
    return {
        "titulo": datos.get("titulo", ""),
        "texto": datos.get("texto", ""),
        "color": datos.get("color", COLORES[0]),
        "ruta": datos.get("ruta"),
        "fijada": datos.get("fijada", False),
        "fuente": datos.get("fuente", FUENTE_POR_DEFECTO),
        "tamano": datos.get("tamano", TAMANO_POR_DEFECTO),
        "estilos": list(datos.get("estilos", [])),
    }


def lista_encima(lista):
    # Hace que la lista que se despliega de un ttk.Combobox aparezca ENCIMA de las notas
    desplegable = lista.tk.call("ttk::combobox::PopdownWindow", lista)
    lista.tk.call("wm", "attributes", desplegable, "-topmost", 1)


def ruta_recurso(nombre):
    # Devuelve dónde está un archivo que va incluido en la app (como el ícono)
    carpeta = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(carpeta, nombre)


def imagen_icono():
    # Carga la imagen del ícono; si no la encuentra, dibuja una nota amarilla simple
    try:
        return Image.open(ruta_recurso(ARCHIVO_ICONO))
    except OSError:
        imagen = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        dibujo = ImageDraw.Draw(imagen)
        dibujo.rounded_rectangle((6, 6, 58, 58), radius=8, fill=COLORES[0])
        dibujo.rectangle((6, 6, 58, 18), fill=oscurecer(COLORES[0]))
        return imagen


def area_de_trabajo(ventana, x, y):
    # Devuelve (izquierda, arriba, derecha, abajo) de la pantalla donde está el punto (x, y),
    # sin contar la barra de tareas de Windows (así la nota maximizada no la tapa)
    try:
        class INFO_PANTALLA(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.wintypes.DWORD), ("rcMonitor", ctypes.wintypes.RECT),
                        ("rcWork", ctypes.wintypes.RECT), ("dwFlags", ctypes.wintypes.DWORD)]
        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.argtypes = [ctypes.wintypes.POINT, ctypes.wintypes.DWORD]
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(INFO_PANTALLA)]
        # Con varias pantallas, usa la que tiene a la nota (2 = la más cercana)
        pantalla = user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), 2)
        info = INFO_PANTALLA(cbSize=ctypes.sizeof(INFO_PANTALLA))
        if user32.GetMonitorInfoW(pantalla, ctypes.byref(info)):
            area = info.rcWork  # rcWork = la pantalla sin la barra de tareas
            return area.left, area.top, area.right, area.bottom
    except (AttributeError, OSError):
        pass  # Si no se pudo preguntar a Windows, usa la pantalla completa
    return 0, 0, ventana.winfo_screenwidth(), ventana.winfo_screenheight()


# =====================================================================
# CLASE LISTA BUSCABLE (los botones de letra y tamaño de la barra de abajo)
#
#  Es un botón pequeño (por ejemplo "Aa ▾" o "11 ▾"). Al hacerle clic se
#  despliega una ventanita con un cuadro para buscar arriba y la lista abajo:
#  mientras escribes, la lista muestra solo las opciones que coinciden.
#    Armar             -> __init__, pack, set, get, colores, actualizar_boton
#    Desplegar         -> alternar_lista, abrir_lista, llenar, cerrar_lista, coincidencias
#    Teclado y mouse   -> al_escribir, mover, confirmar, elegir, elegir_con_clic, al_perder_foco
# =====================================================================
class ListaBuscable:

    # -----------------------------------------------------------------
    # ARMAR
    # -----------------------------------------------------------------

    def __init__(self, padre, valores, al_elegir, ancho_lista=200, numeros=None, muestra=None):
        # Crea el botón (la lista se crea recién al hacerle clic)
        self.valores = [str(v) for v in valores]
        self.al_elegir = al_elegir
        self.ancho_lista = ancho_lista
        self.numeros = numeros
        self.muestra = muestra
        self.valor = ""
        self.ventana_lista = None    # La ventanita desplegada (None = cerrada)
        self.fondo = "#ffffff"       # Colores (los cambia la nota con colores())
        self.borde = "#999999"
        self.marcado = "#dddddd"

        self.boton = tk.Label(padre, text="", padx=6, pady=1, cursor="hand2")
        self.boton.bind("<Button-1>", lambda e: self.alternar_lista())
        self.boton.bind("<Enter>", lambda e: self.boton.config(bg=self.fondo))
        self.boton.bind("<Leave>", lambda e: self.boton.config(bg=self.fondo if self.ventana_lista else self.marcado))

    def pack(self, **opciones):
        # Ubica el botón igual que cualquier otro widget
        self.boton.pack(**opciones)

    def set(self, valor):
        # Deja elegida una opción y la muestra en el botón (sin llamar a al_elegir)
        self.valor = str(valor)
        self.actualizar_boton()

    def get(self):
        # Devuelve la opción elegida
        return self.valor

    def colores(self, fondo, borde, marcado):
        # "fondo" = color del papel, "borde" = borde de la lista, "marcado" = color de la barra
        self.fondo, self.borde, self.marcado = fondo, borde, marcado
        self.boton.config(bg=fondo if self.ventana_lista else marcado)

    def actualizar_boton(self):
        # Pone el texto del botón; con "muestra", se escribe con la letra elegida (vista previa)
        if self.muestra:
            self.boton.config(text=f"{self.muestra} ▾", font=(self.valor, 10))
        else:
            self.boton.config(text=f"{self.valor} ▾", font=("Segoe UI", 9))

    # -----------------------------------------------------------------
    # DESPLEGAR
    # -----------------------------------------------------------------

    def alternar_lista(self):
        # Clic en el botón: abre la lista, o la cierra si ya estaba abierta
        if self.ventana_lista:
            self.cerrar_lista()
        else:
            self.abrir_lista()

    def abrir_lista(self):
        # Despliega la ventanita: un cuadro para buscar arriba y la lista abajo
        self.ventana_lista = tk.Toplevel(self.boton)
        self.ventana_lista.overrideredirect(True)
        self.ventana_lista.attributes("-topmost", True)  # Encima de las notas
        self.ventana_lista.config(bg=self.borde, padx=1, pady=1)  # El 1 de margen hace de borde

        self.busqueda = tk.Entry(self.ventana_lista, bd=0, highlightthickness=0, font=("Segoe UI", 9),
                                 bg=self.fondo, insertbackground="#333")
        self.busqueda.pack(fill="x", ipady=3, ipadx=4)
        tk.Frame(self.ventana_lista, bg=self.marcado, height=1).pack(fill="x")
        self.lista = tk.Listbox(self.ventana_lista, bd=0, highlightthickness=0, activestyle="none",
                                font=("Segoe UI", 9), exportselection=False, bg=self.fondo,
                                selectbackground=self.marcado, selectforeground="#222",
                                height=min(10, len(self.valores)))
        self.lista.pack(fill="both", expand=True)

        self.busqueda.bind("<KeyRelease>", self.al_escribir)
        self.busqueda.bind("<Down>", lambda e: self.mover(1))
        self.busqueda.bind("<Up>", lambda e: self.mover(-1))
        self.busqueda.bind("<Return>", lambda e: self.confirmar())
        self.busqueda.bind("<Escape>", lambda e: self.cerrar_lista())
        self.lista.bind("<ButtonRelease-1>", self.elegir_con_clic)
        self.ventana_lista.bind("<FocusOut>", lambda e: self.ventana_lista.after(100, self.al_perder_foco))

        self.llenar(self.valores)
        if self.valor in self.valores:
            numero = self.valores.index(self.valor)
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(numero)
            self.lista.see(numero)

        # Se abre hacia ARRIBA del botón (está abajo en la nota); si no cabe, hacia abajo
        self.ventana_lista.update_idletasks()
        alto = self.ventana_lista.winfo_reqheight()
        x = self.boton.winfo_rootx()
        y = self.boton.winfo_rooty() - alto
        if y < 0:
            y = self.boton.winfo_rooty() + self.boton.winfo_height()
        self.ventana_lista.geometry(f"{self.ancho_lista}x{alto}+{x}+{y}")
        self.boton.config(bg=self.fondo)
        self.busqueda.focus_force()

    def llenar(self, opciones):
        # Pone las opciones en la lista y marca la primera
        self.lista.delete(0, "end")
        self.lista.insert("end", *opciones)  # Todas de una vez (más rápido que de a una)
        if opciones:
            self.lista.selection_set(0)
            self.lista.see(0)

    def cerrar_lista(self):
        # Cierra la ventanita (si está abierta)
        if self.ventana_lista:
            self.ventana_lista.destroy()
            self.ventana_lista = None
            if self.boton.winfo_exists():
                self.boton.config(bg=self.marcado)

    def coincidencias(self, texto):
        # Devuelve las opciones que contienen lo escrito (sin importar mayúsculas)
        texto = texto.strip().lower()
        if not texto:
            return self.valores
        empiezan = [v for v in self.valores if v.lower().startswith(texto)]
        contienen = [v for v in self.valores if texto in v.lower() and v not in empiezan]
        return empiezan + contienen

    # -----------------------------------------------------------------
    # TECLADO Y MOUSE
    # -----------------------------------------------------------------

    def al_escribir(self, evento):
        # Mientras escribes en el buscador, la lista muestra solo lo que coincide
        if evento.keysym in ("Up", "Down", "Return", "Escape"):
            return
        self.llenar(self.coincidencias(self.busqueda.get()))

    def mover(self, paso):
        # Flechas ↑ y ↓: recorren las opciones de la lista
        actual = self.lista.curselection()
        numero = (actual[0] + paso) if actual else 0
        numero = max(0, min(numero, self.lista.size() - 1))
        self.lista.selection_clear(0, "end")
        self.lista.selection_set(numero)
        self.lista.see(numero)
        return "break"  # Evita que el cursor del buscador se mueva

    def confirmar(self):
        # Enter: elige la opción marcada; o lo escrito, si es un número permitido (ej: tamaño 13)
        escrito = self.busqueda.get().strip()
        if self.numeros and escrito.isdigit() and self.numeros[0] <= int(escrito) <= self.numeros[1]:
            self.elegir(escrito)
        elif self.lista.curselection():
            self.elegir(self.lista.get(self.lista.curselection()[0]))
        else:
            self.cerrar_lista()  # Nada que elegir: queda la opción que estaba

    def elegir(self, valor):
        # Deja elegida una opción, cierra la lista y avisa a la nota
        self.set(valor)
        self.cerrar_lista()
        self.al_elegir(valor)

    def elegir_con_clic(self, evento):
        # Clic en una opción de la lista
        numero = self.lista.nearest(evento.y)
        if numero >= 0:
            self.elegir(self.lista.get(numero))

    def al_perder_foco(self):
        # Si hiciste clic fuera de la lista (en otra ventana), se cierra
        if not self.ventana_lista:
            return
        try:
            enfocado = self.ventana_lista.focus_get()
        except (KeyError, tk.TclError):
            enfocado = None
        if enfocado is None or not str(enfocado).startswith(str(self.ventana_lista)):
            self.cerrar_lista()


# =====================================================================
# CLASE NOTA (una sola nota adhesiva)
#
#  Cada vez que se crea una Nota(...) aparece una nota nueva en pantalla.
#  Está dividida en bloques:
#    Armar la nota     -> __init__, crear_boton, abrir_menu_archivo
#    Pestañas          -> nueva_pestana, cambiar_pestana, cargar_pestana, guardar_estado_pestana,
#                         cerrar_pestana, dibujar_pestanas, nombre_pestana, fuente_pestana_de,
#                         dibujar_pestanas_con_largo, empezar_arrastre, arrastrar_pestana,
#                         soltar_de_la_fila, destinos, iniciar_animacion, animar_pestanas,
#                         soltar_pestana, terminar_arrastre,
#                         mostrar_pestanas, mostrar_etiqueta
#    Colores           -> aplicar_color, abrir_colores, elegir_color, cerrar_colores
#    Letra             -> aplicar_fuente, elegir_fuente, elegir_tamano, cambiar_letra, letra_en,
#                         letra_del_cursor, mostrar_letra_actual, poner_letra, partes, posicion,
#                         fijar_letra_del_texto, antes_de_escribir, dar_letra_a_lo_escrito,
#                         leer_estilos, letra_en_nombre, aplicar_estilos, al_enfocar,
#                         al_soltar_clic, seleccionar_todo
#    Título y texto    -> poner_aviso, quitar_aviso, leer_titulo, leer_texto, esta_vacia, todas_vacias,
#                         tiene_contenido_sin_fijar
#    Minimizar         -> alternar_minimizar, minimizar, restaurar, mostrar_contenido, esconder_contenido,
#                         animar_alto, detener_animacion_alto
#    Maximizar         -> alternar_maximizar, maximizar, volver_tamano, dejar_de_maximizar
#    Transparencia     -> programar_opacidad, actualizar_opacidad, en_uso
#    Ocultar           -> ocultar, mostrar
#    Fijar pestañas    -> alternar_fijar, tiene_fijadas, estado
#    Mover             -> empezar_mover, mover
#    Cambiar tamaño    -> empezar_redimensionar, redimensionar, redibujar_pestanas
#    Borrar            -> borrar, cerrar_nota
#    Links             -> al_escribir, marcar_links, abrir_link
#    Guardar y cargar  -> guardar_en_archivo, avisar, limpiar_aviso_barra, cargar_contenido
# =====================================================================
class Nota:

    # -----------------------------------------------------------------
    # ARMAR LA NOTA
    # -----------------------------------------------------------------

    def __init__(self, app, datos):
        # Crea la nota completa
        self.app = app

        # --- Pestañas ---
        if datos.get("pestanas"):
            self.pestanas = [pestana_nueva(p) for p in datos["pestanas"]]
            self.actual = min(datos.get("actual", 0), len(self.pestanas) - 1)
        else:
            self.pestanas = [pestana_nueva(datos)]
            self.actual = 0
        inicial = self.pestanas[self.actual]

        # --- Datos de la nota ---
        self.color = inicial["color"]
        self.ruta = inicial["ruta"]
        self.fuente = inicial.get("fuente", FUENTE_POR_DEFECTO)
        self.tamano = inicial.get("tamano", TAMANO_POR_DEFECTO)
        self.menu_colores = None
        self.minimizada = False
        self.oculta = False
        self.maximizada = False
        self.antes_maximizar = None    # Posición y tamaño de antes de maximizar (para volver)
        self.opacidad_pendiente = None

        # Posición y tamaño: los guardamos nosotros mismos para tenerlos
        # siempre a mano (aunque la nota esté minimizada)
        self.ancho = datos.get("ancho", 360)
        self.alto = datos.get("alto", 240)
        self.x = datos.get("x", 100)
        self.y = datos.get("y", 100)

        # --- La ventana ---
        self.ventana = tk.Toplevel(app.raiz)
        self.ventana.overrideredirect(True)
        self.ventana.attributes("-topmost", True)
        self.ventana.geometry(f"{self.ancho}x{self.alto}+{self.x}+{self.y}")

        # --- La barra de arriba (de aquí se agarra para mover la nota) ---
        self.barra = tk.Frame(self.ventana, height=28)
        self.barra.pack(fill="x")

        # --- Botones de la barra ---
        self.btn_menu = self.crear_boton("☰", self.abrir_menu_archivo)
        self.btn_menu.pack(side="left")
        # El botón de colores es una paleta: 4 puntitos de colores fuertes (se ven sobre cualquier nota)
        self.btn_color = tk.Canvas(self.barra, width=26, height=23, bd=0, highlightthickness=0, cursor="hand2")
        for color, (x, y) in zip(("#e5534b", "#f4b400", "#3fa34d", "#4a86e8"), ((4, 3), (13, 3), (4, 12), (13, 12))):
            self.btn_color.create_oval(x, y, x + 8, y + 8, fill=color, outline=oscurecer(color, 0.7))
        self.btn_color.bind("<Button-1>", lambda e: self.abrir_colores())
        self.btn_color.bind("<Enter>", lambda e: self.btn_color.config(bg=self.color))
        self.btn_color.bind("<Leave>", lambda e: self.btn_color.config(bg=oscurecer(self.color)))
        self.btn_color.pack(side="left", padx=2)
        self.btn_fijar = self.crear_boton("📌", self.alternar_fijar)
        self.btn_fijar.pack(side="left")
        self.btn_borrar = self.crear_boton("✕", self.borrar)
        self.btn_borrar.pack(side="right")
        # El botón 🗖 maximiza la nota; con la nota maximizada se vuelve 🗗 y regresa al tamaño de antes
        self.btn_maximizar = self.crear_boton("🗖", self.alternar_maximizar)
        self.btn_maximizar.pack(side="right")
        self.btn_minimizar = self.crear_boton("—", self.alternar_minimizar)
        self.btn_minimizar.pack(side="right")

        # --- Centro de la barra ---
        self.zona = tk.Frame(self.barra)
        self.zona.pack(side="left", fill="both", expand=True)
        self.btn_pestana = self.crear_boton("+", lambda: self.nueva_pestana(), padre=self.zona)
        self.marco_pestanas = tk.Frame(self.zona)
        self.etiqueta = tk.Label(self.zona, text="", anchor="w",
                                 font=("Segoe UI", 10, "bold"))
        # Letras de las pestañas (normal y negrita); se guardan para poder medir los nombres
        self.fuente_pestana = tkfont.Font(family="Segoe UI", size=9)
        self.fuente_abierta = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.aviso_pendiente = None
        self.links_pendiente = None
        self.redibujo_pendiente = None
        self.arrastre = None  # La pestaña que estás arrastrando (None = ninguna)
        self.animacion = None  # El próximo paso de la animación de las pestañas
        self.animacion_alto = None  # El próximo paso de la animación de minimizar/abrir

        # --- El título ---
        self.titulo = tk.Entry(self.ventana, bd=0, font=("Segoe UI", 12, "bold"),
                               highlightthickness=0)
        self.hay_aviso = False

        self.titulo.bind("<FocusIn>", self.quitar_aviso)
        self.titulo.bind("<FocusIn>", lambda e: self.al_enfocar("titulo"), add="+")
        self.titulo.bind("<FocusOut>", self.poner_aviso)
        self.titulo.bind("<Button-1>", lambda e: self.titulo.focus_force())
        self.titulo.bind("<Return>", lambda e: self.texto.focus_set())
        self.titulo.bind("<KeyRelease>", lambda e: self.dibujar_pestanas())

        self.linea = tk.Frame(self.ventana, height=1)

        # --- La zona donde se escribe ---
        self.texto = tk.Text(self.ventana, wrap="word", bd=0, font=("Segoe UI", 11),
                             padx=8, pady=6, undo=True, highlightthickness=0,
                             exportselection=False)
        self.texto.bind("<KeyRelease>", self.al_escribir)
        # Letra por partes (como en Word)
        self.donde_escribe = None      # "titulo" o "texto": dónde está el cursor
        self.letra_pendiente = None    # Letra elegida sin seleccionar nada (para lo próximo que escribas)
        self.escrito_pendiente = None
        self.texto.mark_set("inicio_escrito", "1.0")
        self.texto.mark_gravity("inicio_escrito", "left")  # Si escribes justo ahí, la marca no se corre
        self.texto.bind("<KeyPress>", self.antes_de_escribir, add="+")
        self.texto.bind("<<Paste>>", self.antes_de_escribir, add="+")
        self.texto.bind("<KeyRelease>", lambda e: self.mostrar_letra_actual(), add="+")
        self.texto.bind("<ButtonRelease-1>", self.al_soltar_clic, add="+")
        self.texto.bind("<FocusIn>", lambda e: self.al_enfocar("texto"), add="+")
        self.texto.bind("<Control-a>", self.seleccionar_todo)
        self.texto.bind("<Control-A>", self.seleccionar_todo)

        # --- Links: se ven azules y subrayados, y se abren con un clic ---
        self.texto.tag_config("link", foreground="#1a5fb4", underline=True)
        self.texto.tag_bind("link", "<Enter>", lambda e: self.texto.config(cursor="hand2"))
        self.texto.tag_bind("link", "<Leave>", lambda e: self.texto.config(cursor="xterm"))
        self.texto.tag_bind("link", "<Button-1>", self.abrir_link)
        self.texto.bind("<Button-1>", lambda e: self.texto.focus_force())

        # --- La barra de abajo: letra y tamaño de la pestaña abierta ---
        self.barra_letra = tk.Frame(self.ventana)
        # "Aa ▾" muestra la letra elegida y "11 ▾" el tamaño; al hacer clic se despliega la lista
        self.lista_fuentes = ListaBuscable(self.barra_letra, app.fuentes, self.elegir_fuente,
                                           ancho_lista=220, muestra="Aa")
        self.lista_fuentes.pack(side="left", padx=(6, 2), pady=2)
        self.lista_tamanos = ListaBuscable(self.barra_letra, TAMANOS, self.elegir_tamano,
                                           ancho_lista=70, numeros=(6, 72))
        self.lista_tamanos.pack(side="left", pady=2)

        # --- La esquina ◢ para cambiar el tamaño ---
        self.esquina = tk.Label(self.ventana, text="◢", cursor="size_nw_se")

        self.mostrar_contenido()

        # --- Conectar el mouse con las acciones ---
        for parte in (self.barra, self.zona, self.marco_pestanas, self.etiqueta):
            parte.bind("<ButtonPress-1>", self.empezar_mover)
            parte.bind("<B1-Motion>", self.mover)

        self.esquina.bind("<ButtonPress-1>", self.empezar_redimensionar)
        self.esquina.bind("<B1-Motion>", self.redimensionar)

        # --- Menú del botón ☰ (Abrir y Guardar) ---
        # Abrir se lo pide a la App, porque abrir puede crear una nota nueva
        # (le pasa esta nota para que, si está vacía, la use en vez de crear otra)
        self.menu_archivo = tk.Menu(self.ventana, tearoff=0)
        self.menu_archivo.add_command(label="Abrir", command=lambda: app.abrir_nota_guardada(self))
        self.menu_archivo.add_command(label="Guardar", command=self.guardar_en_archivo)
        self.menu_archivo.add_separator()
        self.menu_archivo.add_command(label="Configuración", command=lambda: app.abrir_configuracion(self.ventana))

        # --- Menú de clic derecho en la barra ---
        menu = tk.Menu(self.ventana, tearoff=0)
        menu.add_command(label="Nueva nota", command=app.nueva_nota)
        menu.add_command(label="Salir", command=lambda: app.confirmar_salir(self.ventana))
        for parte in (self.barra, self.zona, self.marco_pestanas, self.etiqueta):
            parte.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        # --- Transparencia: al entrar o salir el mouse (o el foco), revisa si se ve sólida ---
        for evento in ("<Enter>", "<Leave>", "<FocusIn>", "<FocusOut>"):
            self.ventana.bind(evento, self.programar_opacidad, add="+")
        self.actualizar_opacidad()

        # --- Toques finales ---
        self.mostrar_pestanas()
        self.cargar_pestana(self.actual)
        if datos.get("maximizada"):
            self.maximizar()
        if datos.get("minimizada"):
            self.minimizar(animar=False)

    def crear_boton(self, simbolo, accion, padre=None):
        # Crea un botón plano para la barra (así no repetimos el mismo código en cada botón)
        ancho = 2 if len(simbolo) == 1 else 0
        # highlightthickness=0 asegura que no aparezca un borde gris alrededor de los botones
        return tk.Button(padre or self.barra, text=simbolo, command=accion, bd=0, highlightthickness=0,
                         relief="flat", font=("Segoe UI", 10), width=ancho, padx=6, cursor="hand2")

    def abrir_menu_archivo(self):
        # El botón ☰: muestra el menú con Abrir y Guardar justo debajo del botón
        self.cerrar_colores()
        x = self.btn_menu.winfo_rootx()
        y = self.btn_menu.winfo_rooty() + self.btn_menu.winfo_height()
        self.menu_archivo.tk_popup(x, y)

    # -----------------------------------------------------------------
    # PESTAÑAS (como las de un navegador, dentro de la misma nota)
    #  Todas las pestañas usan el mismo título y texto de la nota:
    #  al cambiar de pestaña se guarda lo que había y se carga lo de la otra
    # -----------------------------------------------------------------

    def nueva_pestana(self, datos=None):
        # El botón +: agrega una pestaña y la deja abierta
        datos = datos or {}
        self.guardar_estado_pestana()
        self.pestanas.append(pestana_nueva(datos))
        self.cargar_pestana(len(self.pestanas) - 1)
        if not datos:
            self.titulo.focus_force()

    def cambiar_pestana(self, numero):
        # Clic en una pestaña: guarda la que estaba abierta y muestra la elegida
        if numero == self.actual:
            return
        self.guardar_estado_pestana()
        self.cargar_pestana(numero)

    def cargar_pestana(self, numero):
        # Muestra en la nota el título, texto, color y letra de la pestaña indicada
        self.cerrar_colores()
        self.actual = numero
        pestana = self.pestanas[numero]

        self.titulo.delete(0, "end")
        self.titulo.config(fg="#222")
        self.hay_aviso = False
        self.titulo.insert(0, pestana["titulo"])
        self.poner_aviso()

        # Texto (edit_reset borra el "deshacer" para no mezclar pestañas)
        self.texto.delete("1.0", "end")
        self.texto.insert("1.0", pestana["texto"])
        self.texto.edit_reset()
        self.marcar_links()

        self.color = pestana["color"]
        self.ruta = pestana["ruta"]
        self.fuente = pestana.get("fuente", FUENTE_POR_DEFECTO)  # Las notas viejas no traen letra
        self.tamano = pestana.get("tamano", TAMANO_POR_DEFECTO)
        self.aplicar_fuente()
        self.aplicar_estilos(pestana.get("estilos", []))
        self.letra_pendiente = None
        self.mostrar_letra_actual()
        self.aplicar_color()

        if self.minimizada:
            self.mostrar_etiqueta(self.leer_titulo() or "Sin título")

    def guardar_estado_pestana(self):
        # Copia lo que se ve en la nota a la pestaña abierta (antes de cambiar de pestaña)
        self.pestanas[self.actual].update({
            "titulo": self.leer_titulo(),
            "texto": self.leer_texto(),
            "color": self.color,
            "ruta": self.ruta,
            "fuente": self.fuente,
            "tamano": self.tamano,
            "estilos": self.leer_estilos(),
        })

    def cerrar_pestana(self, numero):
        # La × de una pestaña: la cierra (si tiene título o texto, primero pregunta)
        self.guardar_estado_pestana()
        pestana = self.pestanas[numero]
        nombre = pestana["titulo"].strip() or "Sin título"
        if pestana.get("fijada"):
            # Una pestaña fijada se borra también de las fijadas: ya no vuelve a aparecer
            if not messagebox.askyesno("Cerrar pestaña",
                                       f"La pestaña «{nombre}» está fijada.\n¿Cerrarla? Ya no aparecerá al abrir la app.",
                                       parent=self.ventana):
                return
        elif pestana["titulo"].strip() or pestana["texto"].strip():
            if not messagebox.askyesno("Cerrar pestaña",
                                       f"¿Cerrar la pestaña «{nombre}»?\nLo que no guardaste se perderá.",
                                       parent=self.ventana):
                return

        if len(self.pestanas) == 1:
            self.cerrar_nota()
            return

        self.pestanas.pop(numero)
        if numero < self.actual:
            self.actual -= 1
        elif numero == self.actual:
            self.actual = min(numero, len(self.pestanas) - 1)
        self.cargar_pestana(self.actual)
        self.app.guardar_fijadas()

    def dibujar_pestanas(self):
        # Vuelve a dibujar todas las pestañas en el centro de la barra
        self.ventana.update_idletasks()  # Para que las medidas estén al día
        ancho_centro = self.zona.winfo_width()
        if ancho_centro <= 1:
            # Si la nota todavía no aparece en pantalla, se calcula con el ancho de la nota
            fijos = sum(b.winfo_reqwidth() for b in (self.btn_menu, self.btn_color, self.btn_fijar,
                                                      self.btn_borrar, self.btn_maximizar, self.btn_minimizar))
            ancho_centro = self.ancho - fijos
        disponible = ancho_centro - self.btn_pestana.winfo_reqwidth() - 2

        # 1) Dibuja con nombres de hasta 14 letras y mide cuánto ocupa todo
        self.dibujar_pestanas_con_largo(14)
        self.marco_pestanas.update_idletasks()
        ocupado = self.marco_pestanas.winfo_reqwidth()
        if ocupado <= disponible:
            return  # Caben: listo, se dibujó una sola vez

        # 2) No caben: calcula (sin dibujar) con qué largo de nombre caben
        #    Lo que no es texto (márgenes, la ×, separaciones) se mantiene igual con cualquier largo
        nombres = [self.nombre_pestana(n) for n in range(len(self.pestanas))]

        def ancho_textos(largo):
            # Cuánto ocupan solo los nombres, cortados a "largo" letras
            return sum(self.fuente_pestana_de(n).measure(acortar(nombre, largo))
                       for n, nombre in enumerate(nombres))

        extra = ocupado - ancho_textos(14)
        largo = 13
        while largo > 2 and ancho_textos(largo) + extra > disponible:
            largo -= 1
        self.dibujar_pestanas_con_largo(largo)  # Segundo y último dibujo, ya con el largo justo

    def nombre_pestana(self, numero):
        # Devuelve el nombre que muestra una pestaña (su título, o "Sin título")
        titulo = self.leer_titulo() if numero == self.actual else self.pestanas[numero]["titulo"]
        return titulo.strip() or "Sin título"

    def fuente_pestana_de(self, numero):
        # La pestaña abierta va en negrita; las demás, normal
        return self.fuente_abierta if numero == self.actual else self.fuente_pestana

    def dibujar_pestanas_con_largo(self, largo):
        # Dibuja las pestañas cortando cada nombre a "largo" letras como máximo
        # Si se estaba arrastrando una pestaña, se cancela (las pestañas se dibujan de nuevo)
        if self.animacion:
            self.ventana.after_cancel(self.animacion)
            self.animacion = None
        self.arrastre = None
        self.marco_pestanas.pack_propagate(True)
        for hijo in self.marco_pestanas.winfo_children():
            hijo.destroy()
        self.marcos_pestanas = []  # Las pestañas dibujadas, en orden (para arrastrarlas)

        for numero, pestana in enumerate(self.pestanas):
            abierta = numero == self.actual
            nombre = acortar(self.nombre_pestana(numero), largo)
            fondo = self.color if abierta else oscurecer(pestana["color"])
            letra = self.fuente_pestana_de(numero)

            marco = tk.Frame(self.marco_pestanas, bg=fondo)
            marco.pack(side="left", fill="y", padx=(0, 1))
            self.marcos_pestanas.append(marco)
            # Pestaña fijada: franja roja arriba (las demás llevan una franja del mismo color, invisible,
            # para que todas las pestañas tengan el mismo alto)
            franja = COLOR_FIJADA if pestana.get("fijada") else fondo
            tk.Frame(marco, bg=franja, height=3).pack(side="top", fill="x")
            fila = tk.Frame(marco, bg=fondo)
            fila.pack(side="top")
            nombre_pestana = tk.Label(fila, text=nombre, bg=fondo, font=letra, padx=4, cursor="hand2")
            nombre_pestana.pack(side="left")
            cerrar = tk.Label(fila, text="×", bg=fondo, font=self.fuente_pestana, padx=2, cursor="hand2")
            cerrar.pack(side="left")
            # "n=numero" guarda el número de ESTA pestaña para cuando se haga clic
            nombre_pestana.bind("<ButtonPress-1>", lambda e, n=numero: self.empezar_arrastre(e, n))
            nombre_pestana.bind("<B1-Motion>", self.arrastrar_pestana)
            nombre_pestana.bind("<ButtonRelease-1>", self.soltar_pestana)
            cerrar.bind("<Button-1>", lambda e, n=numero: self.cerrar_pestana(n))

    def empezar_arrastre(self, evento, numero):
        # Al apretar una pestaña: recuerda cuál es (si la sueltas sin moverla, solo se abre)
        if self.arrastre:
            return  # Todavía se está acomodando la pestaña anterior
        self.arrastre = {"desde": numero, "inicio": evento.x_root, "movida": False,
                         "orden": list(range(len(self.pestanas)))}

    def arrastrar_pestana(self, evento):
        # Mientras arrastras: la pestaña sigue al mouse y las demás se corren para hacerle espacio
        a = self.arrastre
        if not a or a.get("soltando"):
            return
        if not a["movida"]:
            if abs(evento.x_root - a["inicio"]) < 8:
                return  # Un temblor del mouse al hacer clic no cuenta como arrastre
            a["movida"] = True
            evento.widget.config(cursor="sb_h_double_arrow")
            self.soltar_de_la_fila(a)

        # La pestaña arrastrada va justo donde está el mouse (sin salirse de la barra)
        desde = a["desde"]
        x = evento.x_root - self.marco_pestanas.winfo_rootx() - a["agarre"]
        x = max(0, min(x, a["total"] - a["anchos"][desde]))
        a["x"][desde] = x
        self.marcos_pestanas[desde].place_configure(x=round(x))

        # Su nuevo lugar: el hueco cuyo centro está más cerca del centro de la pestaña arrastrada
        centro = x + a["anchos"][desde] / 2
        otras = [n for n in a["orden"] if n != desde]

        def distancia(lugar):
            inicio = sum(a["anchos"][n] + 1 for n in otras[:lugar])
            return abs(inicio + a["anchos"][desde] / 2 - centro)

        lugar = min(range(len(otras) + 1), key=distancia)
        nuevo = otras[:lugar] + [desde] + otras[lugar:]
        if nuevo != a["orden"]:
            a["orden"] = nuevo
            self.iniciar_animacion()

    def soltar_de_la_fila(self, a):
        # Pasa las pestañas de pack a place, para poder moverlas libremente (de a un píxel)
        self.marco_pestanas.update_idletasks()
        a["anchos"] = [m.winfo_width() for m in self.marcos_pestanas]
        a["x"] = [m.winfo_x() for m in self.marcos_pestanas]
        a["total"] = self.marco_pestanas.winfo_width()
        a["agarre"] = a["inicio"] - self.marcos_pestanas[a["desde"]].winfo_rootx()  # Dónde la agarraste
        alto = self.marco_pestanas.winfo_height()
        self.marco_pestanas.config(width=a["total"], height=alto)
        self.marco_pestanas.pack_propagate(False)
        for numero, marco in enumerate(self.marcos_pestanas):
            marco.pack_forget()
            marco.place(x=a["x"][numero], y=0, height=alto)
        self.marcos_pestanas[a["desde"]].lift()  # La arrastrada se ve por encima de las demás

    def destinos(self, a):
        # Devuelve dónde debe quedar cada pestaña según el orden nuevo (una al lado de la otra)
        destinos, x = {}, 0
        for n in a["orden"]:
            destinos[n] = x
            x += a["anchos"][n] + 1  # +1: la separación entre pestañas
        return destinos

    def iniciar_animacion(self):
        # Arranca la animación (si ya está corriendo, ella misma toma los destinos nuevos)
        if not self.animacion:
            self.animar_pestanas()

    def animar_pestanas(self):
        # Un paso de la animación: cada pestaña avanza un 35 % de lo que le falta (va frenando al llegar)
        self.animacion = None
        a = self.arrastre
        if not a or not self.marco_pestanas.winfo_exists():
            return
        falta = False
        for n, destino in self.destinos(a).items():
            if n == a["desde"] and not a.get("soltando"):
                continue  # La arrastrada no se anima: sigue al mouse
            if abs(destino - a["x"][n]) < 1:
                a["x"][n] = destino
            else:
                a["x"][n] += (destino - a["x"][n]) * 0.35
                falta = True
            self.marcos_pestanas[n].place_configure(x=round(a["x"][n]))
        if falta:
            self.animacion = self.ventana.after(15, self.animar_pestanas)  # Unos 60 pasos por segundo
        elif a.get("soltando"):
            self.terminar_arrastre()

    def soltar_pestana(self, evento):
        # Al soltar: si no la moviste, abre esa pestaña; si la moviste, se desliza a su lugar
        a = self.arrastre
        if not a or a.get("soltando"):
            return
        if not a["movida"]:
            self.arrastre = None
            self.cambiar_pestana(a["desde"])
            return
        a["soltando"] = True
        self.iniciar_animacion()  # Al terminar de deslizarse llama a terminar_arrastre

    def terminar_arrastre(self):
        # Deja las pestañas en el orden nuevo y las vuelve a dibujar normalmente
        a, self.arrastre = self.arrastre, None
        abierta = self.pestanas[self.actual]
        self.pestanas = [self.pestanas[n] for n in a["orden"]]
        self.actual = next(i for i, p in enumerate(self.pestanas) if p is abierta)
        self.dibujar_pestanas()
        self.app.guardar_fijadas()  # Las fijadas vuelven a aparecer en este orden

    def mostrar_pestanas(self):
        # El centro de la barra muestra las pestañas y el +
        self.etiqueta.pack_forget()
        self.btn_pestana.pack(side="right")
        self.marco_pestanas.pack(side="left", fill="both", expand=True)

    def mostrar_etiqueta(self, texto):
        # El centro de la barra muestra un texto en vez de las pestañas
        self.marco_pestanas.pack_forget()
        self.btn_pestana.pack_forget()
        self.etiqueta.config(text=texto)
        self.etiqueta.pack(side="left", fill="x", expand=True)

    # -----------------------------------------------------------------
    # COLORES
    # -----------------------------------------------------------------

    def aplicar_color(self):
        # Pinta cada parte de la nota: el papel con el color y la barra un poco más oscura
        barra = oscurecer(self.color)
        self.ventana.config(bg=self.color)
        self.titulo.config(bg=self.color, insertbackground="#333")
        self.texto.config(bg=self.color, insertbackground="#333",
                          inactiveselectbackground=oscurecer(self.color, 0.8))
        self.linea.config(bg=barra)
        self.barra_letra.config(bg=barra)
        for lista in (self.lista_fuentes, self.lista_tamanos):
            lista.colores(self.color, oscurecer(barra, 0.8), barra)
        self.esquina.config(bg=barra, fg=oscurecer(barra, 0.7))
        self.barra.config(bg=barra)
        self.zona.config(bg=barra)
        self.marco_pestanas.config(bg=barra)
        self.etiqueta.config(bg=barra)
        for boton in (self.btn_menu, self.btn_fijar, self.btn_pestana,
                      self.btn_borrar, self.btn_maximizar, self.btn_minimizar):
            boton.config(bg=barra, activebackground=self.color)
        self.btn_color.config(bg=barra)
        if self.pestanas[self.actual].get("fijada"):
            self.btn_fijar.config(bg=COLOR_FIJADA, fg="white", activebackground=COLOR_FIJADA)
        else:
            self.btn_fijar.config(fg=COLOR_SIN_FIJAR)
        self.dibujar_pestanas()

    def abrir_colores(self):
        # Abre una ventanita debajo del botón de la paleta con un cuadrado por cada color
        if self.menu_colores:
            self.cerrar_colores()
            return

        self.menu_colores = tk.Toplevel(self.ventana)
        self.menu_colores.overrideredirect(True)
        self.menu_colores.attributes("-topmost", True)
        self.menu_colores.config(bg="#ffffff", padx=4, pady=4)

        for color in COLORES:
            borde = 2 if color == self.color else 0
            cuadro = tk.Frame(self.menu_colores, bg=color, width=22, height=22,
                              cursor="hand2", highlightthickness=borde,
                              highlightbackground="#333")
            cuadro.pack(side="left", padx=2)
            # "c=color" guarda el color de ESTE cuadro para cuando se haga clic
            cuadro.bind("<Button-1>", lambda e, c=color: self.elegir_color(c))

        x = self.btn_color.winfo_rootx()
        y = self.btn_color.winfo_rooty() + self.btn_color.winfo_height()
        self.menu_colores.geometry(f"+{x}+{y}")

        self.menu_colores.bind("<FocusOut>", lambda e: self.cerrar_colores())
        self.menu_colores.bind("<Escape>", lambda e: self.cerrar_colores())
        self.menu_colores.focus_force()

    def elegir_color(self, color):
        # Cambia el color de la pestaña abierta al que se eligió en el menú
        self.color = color
        self.pestanas[self.actual]["color"] = color
        self.aplicar_color()
        self.cerrar_colores()

    def cerrar_colores(self):
        # Cierra la ventanita de colores (si está abierta)
        if self.menu_colores:
            self.menu_colores.destroy()
            self.menu_colores = None
        self.lista_fuentes.cerrar_lista()
        self.lista_tamanos.cerrar_lista()

    # -----------------------------------------------------------------
    # LETRA (la barra de abajo; como en Word: cambia lo seleccionado o lo que escribas)
    # -----------------------------------------------------------------

    def aplicar_fuente(self):
        # Pone la letra elegida en el título y el texto, y la muestra en la barra de abajo
        self.titulo.config(font=(self.fuente, self.tamano + 1, "bold"))
        self.texto.config(font=(self.fuente, self.tamano))
        self.lista_fuentes.set(self.fuente)
        self.lista_tamanos.set(self.tamano)

    def elegir_fuente(self, fuente):
        # Elegiste una letra en la barra de abajo
        self.cambiar_letra(fuente=fuente)

    def elegir_tamano(self, tamano):
        # Elegiste un tamaño en la barra de abajo
        self.cambiar_letra(tamano=int(tamano))

    def cambiar_letra(self, fuente=None, tamano=None):
        # Como en Word: cambia lo seleccionado, o lo que escribas desde el cursor
        if self.donde_escribe == "texto" and self.texto.tag_ranges("sel"):
            for inicio, fin, f, t in self.partes("sel.first", "sel.last"):
                self.poner_letra(inicio, fin, fuente or f, tamano or t)
            self.texto.focus_force()
        elif self.donde_escribe == "texto":
            # Nada seleccionado: queda guardada para lo próximo que escribas
            f, t = self.letra_del_cursor()
            self.letra_pendiente = (fuente or f, tamano or t)
            self.texto.focus_force()
        else:
            # Cursor en el título (o en ningún lado): cambia la letra base de la pestaña
            if self.donde_escribe == "titulo":
                self.fijar_letra_del_texto()  # Así el texto que ya está escrito no cambia
            self.fuente = fuente or self.fuente
            self.tamano = tamano or self.tamano
            self.pestanas[self.actual].update({"fuente": self.fuente, "tamano": self.tamano})
            self.aplicar_fuente()
            if self.donde_escribe == "titulo":
                self.titulo.focus_force()
        self.mostrar_letra_actual()

    def letra_en(self, indice):
        # Devuelve (letra, tamaño) de la letra que está en esa posición del texto
        for nombre in self.texto.tag_names(indice):
            if nombre.startswith("letra|"):
                return self.letra_en_nombre(nombre)
        return self.fuente, self.tamano  # Sin marca: usa la letra base de la pestaña

    def letra_del_cursor(self):
        # Devuelve la letra que se usaría al escribir donde está el cursor
        if self.letra_pendiente:
            return self.letra_pendiente
        if self.texto.tag_ranges("sel"):
            return self.letra_en("sel.first")
        if self.texto.compare("insert", ">", "1.0"):
            return self.letra_en("insert -1c")  # La letra que está justo antes del cursor
        return self.letra_en("insert")

    def mostrar_letra_actual(self):
        # Pone en los botones de abajo la letra de donde está el cursor (como hace Word)
        if self.donde_escribe == "texto":
            fuente, tamano = self.letra_del_cursor()
        else:
            fuente, tamano = self.fuente, self.tamano
        self.lista_fuentes.set(fuente)
        self.lista_tamanos.set(tamano)

    def poner_letra(self, inicio, fin, fuente, tamano):
        # Le pone esa letra a un pedazo del texto (con una "marca" de Tkinter llamada tag)
        for nombre in self.texto.tag_names():
            if nombre.startswith("letra|"):
                self.texto.tag_remove(nombre, inicio, fin)
        if (fuente, tamano) != (self.fuente, self.tamano):  # Igual a la base: no necesita marca
            nombre = f"letra|{fuente}|{tamano}"
            self.texto.tag_config(nombre, font=(fuente, tamano))
            self.texto.tag_add(nombre, inicio, fin)

    def partes(self, inicio, fin):
        # Corta el pedazo [inicio, fin] en partes que tienen una sola letra cada una
        a, b = self.posicion(inicio), self.posicion(fin)
        cortes = {a, b}
        for nombre in self.texto.tag_names():
            if nombre.startswith("letra|"):
                for borde in self.texto.tag_ranges(nombre):
                    if a < self.posicion(borde) < b:
                        cortes.add(self.posicion(borde))
        cortes = sorted(cortes)
        return [(f"1.0+{x}c", f"1.0+{y}c", *self.letra_en(f"1.0+{x}c"))
                for x, y in zip(cortes, cortes[1:])]

    def posicion(self, indice):
        # Convierte una posición de Tkinter ("3.7") en cuántas letras hay desde el inicio
        cuenta = self.texto.count("1.0", indice, "chars")
        if isinstance(cuenta, tuple):
            cuenta = cuenta[0]
        return cuenta or 0

    def fijar_letra_del_texto(self):
        # Marca con su letra actual todo el texto, para que no cambie si cambia la letra base
        for inicio, fin, fuente, tamano in self.partes("1.0", "end-1c"):
            nombre = f"letra|{fuente}|{tamano}"
            self.texto.tag_config(nombre, font=(fuente, tamano))
            self.texto.tag_add(nombre, inicio, fin)

    def antes_de_escribir(self, evento):
        # Se llama al apretar una tecla o pegar, ANTES de que la letra aparezca en el texto
        if evento.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"):
            self.letra_pendiente = None  # Moviste el cursor: se olvida la letra pendiente
            return
        control = evento.state & 0x4 and not evento.state & 0x20000  # 0x20000 = Alt (AltGr = Ctrl + Alt)
        if control and evento.keysym.lower() != "v":
            return  # Ctrl + Z, Ctrl + C, etc. no escriben nada nuevo
        if self.escrito_pendiente is None:
            seleccion = self.texto.tag_ranges("sel")
            if seleccion and self.texto.compare(seleccion[0], "<=", "insert") \
                    and self.texto.compare("insert", "<=", seleccion[1]):
                self.texto.mark_set("inicio_escrito", seleccion[0])
            else:
                self.texto.mark_set("inicio_escrito", "insert")
            self.escrito_pendiente = self.ventana.after_idle(self.dar_letra_a_lo_escrito)

    def dar_letra_a_lo_escrito(self):
        # Lo recién escrito toma la letra pendiente, o la de lo que está justo antes
        self.escrito_pendiente = None
        if not self.texto.winfo_exists() or self.texto.compare("inicio_escrito", ">=", "insert"):
            return  # La nota se cerró, o no se escribió nada (ej: borraste)
        if self.letra_pendiente:
            fuente, tamano = self.letra_pendiente
            self.letra_pendiente = None
        elif self.texto.compare("inicio_escrito", ">", "1.0"):
            fuente, tamano = self.letra_en("inicio_escrito -1c")
        else:
            fuente, tamano = self.letra_en("insert")  # Al inicio del texto: la de lo que sigue
        self.poner_letra("inicio_escrito", "insert", fuente, tamano)
        self.mostrar_letra_actual()

    def leer_estilos(self):
        # Devuelve las partes del texto con otra letra, para guardarlas: [inicio, fin, letra, tamaño]
        estilos = []
        for nombre in self.texto.tag_names():
            if nombre.startswith("letra|"):
                fuente, tamano = self.letra_en_nombre(nombre)
                rangos = self.texto.tag_ranges(nombre)
                for inicio, fin in zip(rangos[0::2], rangos[1::2]):
                    estilos.append([self.posicion(inicio), self.posicion(fin), fuente, tamano])
        return estilos

    def letra_en_nombre(self, nombre):
        # Separa el nombre de la marca: "letra|Arial|14" -> ("Arial", 14)
        fuente, tamano = nombre[len("letra|"):].rsplit("|", 1)
        return fuente, int(tamano)

    def aplicar_estilos(self, estilos):
        # Vuelve a poner las partes con otra letra (al cargar una pestaña o un archivo)
        for estilo in estilos:
            try:
                inicio, fin, fuente, tamano = estilo
                nombre = f"letra|{fuente}|{int(tamano)}"
                self.texto.tag_config(nombre, font=(fuente, int(tamano)))
                self.texto.tag_add(nombre, f"1.0+{int(inicio)}c", f"1.0+{int(fin)}c")
            except (ValueError, TypeError, tk.TclError):
                continue  # Un dato dañado no impide cargar el resto

    def al_enfocar(self, lugar):
        # Recuerda si el cursor está en el título o en el texto (para saber qué cambia la letra)
        self.donde_escribe = lugar
        self.mostrar_letra_actual()

    def al_soltar_clic(self, evento=None):
        # Hiciste clic en el texto: el cursor se movió, se olvida la letra pendiente
        self.letra_pendiente = None
        self.mostrar_letra_actual()

    def seleccionar_todo(self, evento=None):
        # Ctrl + A: selecciona todo el texto (para cambiarle la letra a todo de una vez)
        self.texto.tag_add("sel", "1.0", "end-1c")
        self.texto.mark_set("insert", "end-1c")
        self.mostrar_letra_actual()
        return "break"

    # -----------------------------------------------------------------
    # TÍTULO Y TEXTO
    # -----------------------------------------------------------------

    def poner_aviso(self, evento=None):
        # Si el título está vacío, muestra "Escribe un título..." en gris
        if not self.titulo.get():
            self.titulo.insert(0, AVISO_TITULO)
            self.titulo.config(fg="#888")
            self.hay_aviso = True

    def quitar_aviso(self, evento=None):
        # Al entrar al título, borra el texto gris para poder escribir
        if self.hay_aviso:
            self.titulo.delete(0, "end")
            self.titulo.config(fg="#222")
            self.hay_aviso = False

    def leer_titulo(self):
        # Devuelve el título real (vacío si solo está el aviso gris)
        return "" if self.hay_aviso else self.titulo.get()

    def leer_texto(self):
        # Devuelve todo el texto de la nota ("end-1c" = sin el salto de línea final)
        return self.texto.get("1.0", "end-1c")

    # -----------------------------------------------------------------
    # MINIMIZAR (la nota se enrolla y queda solo la barra con el título)
    # -----------------------------------------------------------------

    def alternar_minimizar(self):
        # El botón —: si está abierta la minimiza; si está minimizada, la vuelve a abrir
        if self.minimizada:
            self.restaurar()
        else:
            self.minimizar()

    def minimizar(self, animar=True):
        # Enrolla la nota hacia arriba hasta que solo queda la barra
        self.cerrar_colores()
        self.minimizada = True
        self.btn_minimizar.config(text="▢")
        alto_barra = self.barra.winfo_reqheight()
        if animar:
            self.animar_alto(alto_barra, al_terminar=self.esconder_contenido)
        else:
            self.detener_animacion_alto()
            self.esconder_contenido()
            self.ventana.geometry(f"{self.ancho}x{alto_barra}")

    def esconder_contenido(self):
        # Esconde todo menos la barra y muestra en ella el título de la pestaña abierta
        if not self.minimizada:
            return  # La volviste a abrir antes de que terminara de enrollarse
        self.titulo.pack_forget()
        self.linea.pack_forget()
        self.texto.pack_forget()
        self.barra_letra.pack_forget()
        self.esquina.place_forget()
        self.mostrar_etiqueta(self.leer_titulo() or "Sin título")

    def restaurar(self, animar=True):
        # Despliega la nota hacia abajo hasta su tamaño normal
        self.mostrar_contenido()
        self.mostrar_pestanas()
        self.btn_minimizar.config(text="—")
        self.minimizada = False
        if animar:
            self.animar_alto(self.alto)
        else:
            self.detener_animacion_alto()
            self.ventana.geometry(f"{self.ancho}x{self.alto}")

    def animar_alto(self, hasta, al_terminar=None):
        # Cambia el alto de la nota de a poco: rápido al principio y frenando al final
        self.detener_animacion_alto()
        desde = self.ventana.winfo_height()  # Parte del alto actual (aunque otra animación quedara a medias)
        pasos = 12  # 12 pasos de 15 ms = unos 0,18 segundos

        def paso(numero):
            self.animacion_alto = None
            if not self.ventana.winfo_exists():
                return  # La nota se cerró mientras se animaba
            avance = 1 - (1 - numero / pasos) ** 3
            alto = round(desde + (hasta - desde) * avance)
            self.ventana.geometry(f"{self.ancho}x{alto}")
            if numero < pasos:
                self.animacion_alto = self.ventana.after(15, paso, numero + 1)
            elif al_terminar:
                al_terminar()

        paso(1)

    def detener_animacion_alto(self):
        # Corta la animación de minimizar/abrir si estaba a medias
        if self.animacion_alto:
            self.ventana.after_cancel(self.animacion_alto)
            self.animacion_alto = None

    def mostrar_contenido(self):
        # Muestra el título, la línea, el texto, la barra de abajo y la esquina
        self.titulo.pack(fill="x", padx=8, pady=(6, 0))
        self.linea.pack(fill="x", padx=8, pady=(2, 0))
        self.barra_letra.pack(side="bottom", fill="x")    # Va antes del texto, para que no la tape
        self.texto.pack(fill="both", expand=True)
        self.esquina.place(relx=1, rely=1, anchor="se")

    # -----------------------------------------------------------------
    # MAXIMIZAR (la nota ocupa toda la pantalla, sin tapar la barra de tareas)
    # -----------------------------------------------------------------

    def alternar_maximizar(self):
        # El botón 🗖: maximiza la nota; si ya estaba maximizada (🗗), vuelve al tamaño de antes
        if self.maximizada:
            self.volver_tamano()
        else:
            self.maximizar()

    def maximizar(self):
        # Agranda la nota hasta ocupar la pantalla donde está
        if self.minimizada:
            self.restaurar(animar=False)
        self.cerrar_colores()
        self.antes_maximizar = (self.x, self.y, self.ancho, self.alto)
        izquierda, arriba, derecha, abajo = area_de_trabajo(self.ventana, self.x + self.ancho // 2, self.y + 10)
        self.x, self.y = izquierda, arriba
        self.ancho, self.alto = derecha - izquierda, abajo - arriba
        self.ventana.geometry(f"{self.ancho}x{self.alto}+{self.x}+{self.y}")
        self.maximizada = True
        self.btn_maximizar.config(text="🗗")
        self.ventana.after(50, self.redibujar_pestanas)  # Con más espacio, las pestañas se reacomodan

    def volver_tamano(self):
        # Deja la nota con la posición y el tamaño que tenía antes de maximizar
        if self.minimizada:
            self.restaurar(animar=False)
        self.cerrar_colores()
        self.x, self.y, self.ancho, self.alto = self.antes_maximizar
        self.ventana.geometry(f"{self.ancho}x{self.alto}+{self.x}+{self.y}")
        self.dejar_de_maximizar()
        self.ventana.after(50, self.redibujar_pestanas)

    def dejar_de_maximizar(self):
        # La nota ya no cuenta como maximizada (ej: la moviste o le cambiaste el tamaño a mano)
        self.maximizada = False
        self.btn_maximizar.config(text="🗖")

    # -----------------------------------------------------------------
    # TRANSPARENCIA (se elige en ☰ → Configuración y vale para todas las notas)
    # -----------------------------------------------------------------

    def programar_opacidad(self, evento=None):
        # El mouse entró o salió (o cambió el foco): revisa en un instante, una sola vez
        if self.opacidad_pendiente:
            self.ventana.after_cancel(self.opacidad_pendiente)
        self.opacidad_pendiente = self.ventana.after(80, self.actualizar_opacidad)

    def actualizar_opacidad(self):
        # Pone la nota transparente o sólida, según lo elegido en Configuración
        self.opacidad_pendiente = None
        if not self.ventana.winfo_exists():
            return  # La nota se cerró mientras esperaba
        # En modo "Transparente", la nota se ve sólida mientras la usas (mouse encima o escribiendo)
        transparente = self.app.transparente and not self.en_uso()
        self.ventana.attributes("-alpha", OPACIDAD_TRANSPARENTE if transparente else 1.0)

    def en_uso(self):
        # Devuelve True si el mouse está encima de la nota o si estás escribiendo en ella
        x, y = self.ventana.winfo_pointerxy()
        izquierda, arriba = self.ventana.winfo_rootx(), self.ventana.winfo_rooty()
        encima = (izquierda <= x < izquierda + self.ventana.winfo_width()
                  and arriba <= y < arriba + self.ventana.winfo_height())
        try:
            enfocado = self.ventana.focus_get()
        except (KeyError, tk.TclError):
            enfocado = None
        return encima or (enfocado is not None and str(enfocado).startswith(str(self.ventana)))

    # -----------------------------------------------------------------
    # OCULTAR (la nota desaparece de la pantalla, pero no se borra nada)
    # -----------------------------------------------------------------

    def ocultar(self):
        # Esconde la nota tal como está (con sus pestañas, texto y posición)
        self.cerrar_colores()
        self.ventana.withdraw()
        self.oculta = True

    def mostrar(self):
        # Vuelve a mostrar la nota donde estaba, encima de las demás ventanas
        self.ventana.deiconify()
        self.ventana.attributes("-topmost", True)
        self.ventana.lift()
        self.oculta = False

    # -----------------------------------------------------------------
    # FIJAR PESTAÑAS (una pestaña fijada se guarda sola y aparece cada vez que se abre la app)
    # -----------------------------------------------------------------

    def alternar_fijar(self):
        # El botón 📌: fija la pestaña abierta o la deja de fijar
        pestana = self.pestanas[self.actual]
        pestana["fijada"] = not pestana.get("fijada")
        self.aplicar_color()
        self.app.guardar_fijadas()
        self.avisar("Pestaña fijada 📌" if pestana["fijada"] else "Pestaña sin fijar")

    def tiene_fijadas(self):
        # Devuelve True si al menos una pestaña de la nota está fijada
        return any(p.get("fijada") for p in self.pestanas)

    def estado(self):
        # Devuelve lo necesario para volver a armar la nota al abrir la app,
        self.guardar_estado_pestana()
        fijadas = [p for p in self.pestanas if p.get("fijada")]
        # Si la pestaña abierta está fijada, al volver queda abierta esa; si no, la primera fijada
        abierta = self.pestanas[self.actual]
        actual = next((i for i, p in enumerate(fijadas) if p is abierta), 0)
        # Si está maximizada se guarda su tamaño normal (al volver se maximiza de nuevo)
        x, y, ancho, alto = (self.antes_maximizar if self.maximizada
                             else (self.x, self.y, self.ancho, self.alto))
        return {
            "pestanas": fijadas,
            "actual": actual,
            "x": x,
            "y": y,
            "ancho": ancho,
            "alto": alto,
            "minimizada": self.minimizada,
            "maximizada": self.maximizada,
        }

    # -----------------------------------------------------------------
    # MOVER LA NOTA
    # -----------------------------------------------------------------

    def empezar_mover(self, evento):
        # Al apretar la barra: recuerda en qué punto de la nota la agarraste
        self.cerrar_colores()
        self.dx = evento.x_root - self.x
        self.dy = evento.y_root - self.y

    def mover(self, evento):
        # Mientras arrastras: mueve la nota siguiendo al mouse
        if self.maximizada:
            # Como en Windows: al arrastrar una nota maximizada, vuelve a su tamaño normal bajo el mouse
            _, _, self.ancho, self.alto = self.antes_maximizar
            self.dx = min(self.dx, self.ancho - 60)  # Que el mouse siga quedando sobre la barra
            alto_visible = self.barra.winfo_reqheight() if self.minimizada else self.alto
            self.ventana.geometry(f"{self.ancho}x{alto_visible}")
            self.dejar_de_maximizar()
            self.ventana.after(50, self.redibujar_pestanas)
        self.x = evento.x_root - self.dx
        self.y = evento.y_root - self.dy
        self.ventana.geometry(f"+{self.x}+{self.y}")

    # -----------------------------------------------------------------
    # CAMBIAR TAMAÑO
    # -----------------------------------------------------------------

    def empezar_redimensionar(self, evento):
        # Al apretar la esquina: recuerda dónde estaba el mouse y el tamaño inicial
        self.inicio_x = evento.x_root
        self.inicio_y = evento.y_root
        self.inicio_ancho = self.ancho
        self.inicio_alto = self.alto

    def redimensionar(self, evento):
        # Mientras arrastras: tamaño inicial + lo que se movió el mouse
        self.ancho = max(180, self.inicio_ancho + evento.x_root - self.inicio_x)
        self.alto = max(150, self.inicio_alto + evento.y_root - self.inicio_y)
        if self.maximizada:
            self.dejar_de_maximizar()
        self.ventana.geometry(f"{self.ancho}x{self.alto}")
        # Con más (o menos) espacio, las pestañas se reacomodan, pero no con cada movimiento del mouse:
        # espera un instante (0,05 s) y dibuja una sola vez
        if self.redibujo_pendiente:
            self.ventana.after_cancel(self.redibujo_pendiente)
        self.redibujo_pendiente = self.ventana.after(50, self.redibujar_pestanas)

    def redibujar_pestanas(self):
        # Dibuja las pestañas después de cambiar el tamaño (si la nota sigue abierta)
        self.redibujo_pendiente = None
        if self.ventana.winfo_exists():
            self.dibujar_pestanas()

    # -----------------------------------------------------------------
    # BORRAR
    # -----------------------------------------------------------------

    def borrar(self):
        # El botón ✕: cierra la nota (si tiene pestañas fijadas o algo escrito, primero pregunta)
        self.cerrar_colores()
        if self.tiene_fijadas() or not self.todas_vacias():
            if not messagebox.askyesno("Notas-adhesivas", "¿Seguro que quieres salir?", parent=self.ventana):
                return
        if self.tiene_fijadas():
            self.app.fijadas_cerradas.append(self.estado())
        self.cerrar_nota()

    def cerrar_nota(self):
        # Cierra la nota sin preguntar (borrar y cerrar_pestana ya preguntaron)
        self.cerrar_colores()
        # Cancela lo que estaba esperando para después (avisos, links, redibujos)
        for pendiente in (self.aviso_pendiente, self.links_pendiente, self.redibujo_pendiente):
            if pendiente:
                self.ventana.after_cancel(pendiente)
        self.app.notas.remove(self)
        self.ventana.destroy()
        self.app.guardar_fijadas()
        # Aunque sea la última nota, la app sigue abierta en segundo plano
        # para que el atajo de teclado pueda crear otra (Salir la cierra del todo)

    # -----------------------------------------------------------------
    # LINKS
    # -----------------------------------------------------------------

    def al_escribir(self, evento=None):
        # Se llama cada vez que sueltas una tecla (también al pegar con Ctrl + V)
        if self.links_pendiente:
            self.ventana.after_cancel(self.links_pendiente)
        self.links_pendiente = self.ventana.after(300, self.marcar_links)

    def marcar_links(self):
        # Busca los links en el texto y los pinta azules y subrayados
        self.links_pendiente = None
        if not self.texto.winfo_exists():
            return  # La nota se cerró mientras esperaba
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
        # Abre en el navegador el link donde hiciste clic
        posicion = self.texto.index(f"@{evento.x},{evento.y}")
        rango = self.texto.tag_prevrange("link", f"{posicion}+1c")
        if not rango:
            return
        link = self.texto.get(rango[0], rango[1])
        # Si empieza con "www." le falta el "https://" para que el navegador lo entienda
        if link.startswith("www."):
            link = "https://" + link
        webbrowser.open(link)
        return "break"  # Evita que el clic además mueva el cursor

    # -----------------------------------------------------------------
    # GUARDAR Y CARGAR
    # -----------------------------------------------------------------

    def guardar_en_archivo(self):
        # Guardar (en el menú ☰): guarda esta nota en un archivo .nota
        self.cerrar_colores()

        if not self.leer_titulo().strip():
            messagebox.showwarning("Notas-adhesivas", "Escribe un título antes de guardar la nota.",
                                   parent=self.ventana)
            if self.minimizada:
                self.restaurar()
            self.titulo.focus_force()
            return

        if not self.ruta or not os.path.isdir(os.path.dirname(self.ruta)):
            # Usa el título como nombre del archivo, quitando signos que Windows no acepta
            nombre = re.sub(r'[<>:"/\\|?*]', "", self.leer_titulo()).strip() or "nota"
            ruta = filedialog.asksaveasfilename(
                parent=self.ventana, title="Guardar nota",
                initialfile=nombre + EXTENSION, defaultextension=EXTENSION,
                filetypes=TIPOS_ARCHIVO)
            if not ruta:
                return
            self.ruta = ruta

        contenido = {
            "titulo": self.leer_titulo(),
            "texto": self.leer_texto(),
            "color": self.color,
            "fuente": self.fuente,
            "tamano": self.tamano,
            "estilos": self.leer_estilos(),
        }
        try:
            with open(self.ruta, "w", encoding="utf-8") as f:
                json.dump(contenido, f, ensure_ascii=False, indent=2)
        except OSError:
            messagebox.showerror("Error", "No se pudo guardar la nota.", parent=self.ventana)
            self.ruta = None
            return

        self.guardar_estado_pestana()
        self.avisar("Guardada ✓")

    def avisar(self, mensaje):
        # Muestra un mensaje cortito en la barra por 1,5 segundos
        if self.minimizada:
            return
        self.mostrar_etiqueta(mensaje)
        # Si había otro aviso esperando para borrarse, se cancela (así no corta a este antes de tiempo)
        if self.aviso_pendiente:
            self.ventana.after_cancel(self.aviso_pendiente)
        self.aviso_pendiente = self.ventana.after(1500, self.limpiar_aviso_barra)

    def limpiar_aviso_barra(self):
        # Quita el mensaje y vuelve a mostrar las pestañas (si la nota sigue abierta y no está minimizada)
        self.aviso_pendiente = None
        if self.etiqueta.winfo_exists() and not self.minimizada:
            self.mostrar_pestanas()

    def esta_vacia(self):
        # Devuelve True si la pestaña abierta no tiene título ni texto
        return not self.leer_titulo().strip() and not self.leer_texto().strip()

    def todas_vacias(self):
        # Devuelve True si NINGUNA pestaña de la nota tiene título ni texto
        self.guardar_estado_pestana()
        return all(not p["titulo"].strip() and not p["texto"].strip() for p in self.pestanas)

    def tiene_contenido_sin_fijar(self):
        # Devuelve True si alguna pestaña SIN fijar tiene título o texto (eso se perdería al salir)
        self.guardar_estado_pestana()
        return any(not p.get("fijada") and (p["titulo"].strip() or p["texto"].strip())
                   for p in self.pestanas)

    def cargar_contenido(self, guardado, ruta):
        # Pone en la pestaña abierta el título, texto, color y letra de una nota guardada
        cargada = pestana_nueva({**guardado, "ruta": ruta})
        cargada.pop("fijada")  # Si la pestaña abierta estaba fijada, sigue fijada
        self.pestanas[self.actual].update(cargada)
        self.cargar_pestana(self.actual)


# =====================================================================
# CLASE APP (el "jefe" de todas las notas)
#
#  Tiene la lista de notas y se encarga de lo que afecta a todas.
#  Está dividida en bloques:
#    Arrancar          -> __init__
#    Notas             -> posicion_nueva, nueva_nota, abrir_nota_guardada, mismo_archivo,
#                         ir_a_pestana_abierta
#    Atajo y avisos    -> escuchar_atajo, escuchar_otras_copias, revisar_avisos
#    Pestañas fijadas  -> cargar_fijadas, guardar_fijadas, revisar_fijadas, clave_pestana
#    Configuración     -> cargar_configuracion, guardar_configuracion, abrir_configuracion,
#                         aplicar_configuracion
#    Íconos ocultos    -> crear_icono_bandeja, mostrar_notas, alternar_notas, mostrar_todas,
#                         ocultar_todas
#    Abrir y cerrar    -> ventana_visible, confirmar_salir, salir, iniciar
#
#  Las notas solo se guardan cuando apretas Guardar (no hay guardado automático),
#  salvo las pestañas fijadas con 📌, que se guardan solas para volver a aparecer
# =====================================================================
class App:

    # -----------------------------------------------------------------
    # ARRANCAR
    # -----------------------------------------------------------------

    def __init__(self, servidor):
        self.raiz = tk.Tk()
        self.raiz.withdraw()
        self.notas = []
        self.avisos = queue.Queue()
        self.acciones = {
            "nueva_nota": self.nueva_nota,
            "mostrar_notas": self.mostrar_notas,
            "ocultar_notas": self.ocultar_todas,
            "alternar_notas": self.alternar_notas,
            "salir": self.confirmar_salir,
        }

        # Letras instaladas en el PC, ordenadas (las que empiezan con "@" son letras verticales: se omiten)
        self.fuentes = sorted({f for f in tkfont.families() if not f.startswith("@")}, key=str.lower)

        self.teclas = self.cargar_configuracion()
        self.ventana_config = None
        self.hilo_atajo = None

        # Escucha el atajo de teclado y a otras copias de la app, cada uno en su propio "hilo"
        threading.Thread(target=self.escuchar_atajo, daemon=True).start()
        threading.Thread(target=self.escuchar_otras_copias, args=(servidor,), daemon=True).start()
        self.raiz.after(200, self.revisar_avisos)

        self.crear_icono_bandeja()

        self.ultimo_guardado = None
        self.fijadas_cerradas = []
        for datos in self.cargar_fijadas():
            self.notas.append(Nota(self, datos))
        if not self.notas:
            self.nueva_nota()
        self.raiz.after(2000, self.revisar_fijadas)

    # -----------------------------------------------------------------
    # NOTAS
    # -----------------------------------------------------------------

    def posicion_nueva(self):
        # Devuelve dónde poner una nota nueva: un poco corrida para que no tape a las otras
        desplazamiento = 30 * len(self.notas)
        return 150 + desplazamiento, 150 + desplazamiento

    def nueva_nota(self):
        # Crea una nota nueva vacía
        x, y = self.posicion_nueva()
        datos = {"x": x, "y": y}
        recuperadas = [p for estado in self.fijadas_cerradas for p in estado["pestanas"]]
        # No trae las que ya están abiertas en otra nota (ni las repetidas entre ellas)
        abiertas = set()
        for otra in self.notas:
            otra.guardar_estado_pestana()
            abiertas.update(self.clave_pestana(p) for p in otra.pestanas)
        sin_repetir = []
        for pestana in recuperadas:
            clave = self.clave_pestana(pestana)
            if clave not in abiertas:
                abiertas.add(clave)
                sin_repetir.append(pestana)
        recuperadas = sin_repetir
        self.fijadas_cerradas = []
        if recuperadas:
            datos["pestanas"] = recuperadas + [pestana_nueva()]
            datos["actual"] = len(recuperadas)
        nota = Nota(self, datos)
        self.notas.append(nota)
        nota.titulo.focus_force()

    def abrir_nota_guardada(self, nota_actual):
        # Abrir (en el menú ☰): abre un archivo .nota
        ventana_padre = nota_actual.ventana
        ruta = filedialog.askopenfilename(parent=ventana_padre, title="Abrir nota guardada",
                                          filetypes=TIPOS_ARCHIVO)
        if not ruta:
            return
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            if not isinstance(guardado, dict):
                raise ValueError
        except (OSError, ValueError):  # ValueError también cubre un JSON dañado
            messagebox.showerror("Error", "No se pudo abrir ese archivo.", parent=ventana_padre)
            return

        # Si ese archivo ya está abierto en alguna pestaña, lleva a esa pestaña (así no se duplica)
        if self.ir_a_pestana_abierta(ruta):
            return
        # Si está en una pestaña fijada de una nota cerrada, la trae de vuelta con una nota nueva
        if any(self.mismo_archivo(p.get("ruta"), ruta)
               for estado in self.fijadas_cerradas for p in estado["pestanas"]):
            self.nueva_nota()
            self.ir_a_pestana_abierta(ruta)
            return

        if nota_actual.esta_vacia():
            nota_actual.cargar_contenido(guardado, ruta)
            return

        nota_actual.nueva_pestana({**guardado, "ruta": ruta, "fijada": False})

    def mismo_archivo(self, ruta_a, ruta_b):
        # Devuelve True si las dos rutas son el mismo archivo
        if not ruta_a or not ruta_b:
            return False
        normalizar = lambda r: os.path.normcase(os.path.abspath(r))
        return normalizar(ruta_a) == normalizar(ruta_b)

    def ir_a_pestana_abierta(self, ruta):
        # Busca una pestaña que ya tenga abierto ese archivo y la muestra
        for nota in self.notas:
            nota.guardar_estado_pestana()  # Para que la pestaña abierta tenga su ruta al día
            for numero, pestana in enumerate(nota.pestanas):
                if self.mismo_archivo(pestana.get("ruta"), ruta):
                    nota.mostrar()
                    if nota.minimizada:
                        nota.restaurar()
                    nota.cambiar_pestana(numero)
                    nota.ventana.focus_force()
                    nota.avisar("Ya estaba abierta")
                    return True
        return False

    # -----------------------------------------------------------------
    # ATAJO Y AVISOS
    # -----------------------------------------------------------------

    def escuchar_atajo(self):
        # Registra los atajos en Windows y espera a que los presiones
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
        WM_HOTKEY = 0x0312
        CAMBIAR_ATAJOS = 0x8001  # Mensaje propio: "se cambiaron los atajos en Configuración"
        user32 = ctypes.windll.user32
        self.hilo_atajo = ctypes.windll.kernel32.GetCurrentThreadId()
        avisos_atajos = {1: "nueva_nota", 2: "alternar_notas"}

        def registrar():
            # Quita los atajos anteriores y registra los que están en self.teclas
            for numero, aviso in avisos_atajos.items():
                user32.UnregisterHotKey(None, numero)
                letra = self.teclas[aviso]
                if not user32.RegisterHotKey(None, numero, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(letra)):
                    self.avisos.put(f"atajo_ocupado:{letra}")

        registrar()
        mensaje = ctypes.wintypes.MSG()
        # GetMessageW espera (sin gastar procesador) hasta que llegue un mensaje de Windows
        while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) != 0:
            if mensaje.message == WM_HOTKEY and mensaje.wParam in avisos_atajos:
                # wParam dice cuál de los atajos se presionó
                self.avisos.put(avisos_atajos[mensaje.wParam])
            elif mensaje.message == CAMBIAR_ATAJOS:
                registrar()

    def escuchar_otras_copias(self, servidor):
        # Si abres el .exe otra vez, esa segunda copia avisa aquí y se cierra
        while True:
            try:
                conexion, _ = servidor.accept()
            except OSError:
                return
            with conexion:
                # Si la conexión no envía nada en 2 segundos, se descarta (así este hilo nunca se queda pegado)
                conexion.settimeout(2)
                try:
                    if conexion.recv(32) == b"nueva_nota":
                        self.avisos.put("nueva_nota")
                except OSError:
                    pass

    def revisar_avisos(self):
        # Cada 0,2 segundos revisa si llegó algún aviso y lo atiende
        while not self.avisos.empty():
            aviso = self.avisos.get()
            if aviso in self.acciones:
                self.acciones[aviso]()
            elif aviso.startswith("atajo_ocupado:"):
                letra = aviso.split(":")[1]
                messagebox.showwarning("Notas-adhesivas",
                                       f"El atajo Ctrl + Alt + {letra} ya lo usa otro programa.",
                                       parent=self.ventana_visible())
        self.raiz.after(200, self.revisar_avisos)

    # -----------------------------------------------------------------
    # PESTAÑAS FIJADAS (se guardan solas en ARCHIVO_FIJADAS, agrupadas por nota)
    # -----------------------------------------------------------------

    def cargar_fijadas(self):
        # Lee las notas con pestañas fijadas; si no hay archivo (o está dañado), no hay ninguna
        try:
            with open(ARCHIVO_FIJADAS, "r", encoding="utf-8") as f:
                fijadas = json.load(f)
            notas = [d for d in fijadas if isinstance(d, dict) and d.get("pestanas")]
        except (OSError, ValueError, TypeError):
            return []

        # Descarta las pestañas repetidas (la misma pestaña guardada dos veces abriría dos notas iguales)
        vistas = set()
        sin_repetir = []
        for nota in notas:
            pestanas = []
            for pestana in nota["pestanas"]:
                clave = self.clave_pestana(pestana)
                if clave not in vistas:
                    vistas.add(clave)
                    pestanas.append(pestana)
            if pestanas:
                nota["pestanas"] = pestanas
                nota["actual"] = min(nota.get("actual", 0), len(pestanas) - 1)
                sin_repetir.append(nota)
        return sin_repetir

    def clave_pestana(self, pestana):
        # Devuelve algo que identifica a una pestaña, para reconocer si está repetida
        if pestana.get("ruta"):
            return ("archivo", os.path.normcase(os.path.abspath(pestana["ruta"])))
        return ("contenido", pestana.get("titulo", ""), pestana.get("texto", ""))

    def guardar_fijadas(self):
        # Escribe en el archivo las pestañas fijadas de cada nota (solo si algo cambió desde la última vez)
        abiertas = [nota.estado() for nota in self.notas if nota.tiene_fijadas()]
        contenido = json.dumps(abiertas + self.fijadas_cerradas,
                               ensure_ascii=False, indent=2)
        if contenido == self.ultimo_guardado:
            return
        try:
            os.makedirs(os.path.dirname(ARCHIVO_FIJADAS), exist_ok=True)
            with open(ARCHIVO_FIJADAS, "w", encoding="utf-8") as f:
                f.write(contenido)
            self.ultimo_guardado = contenido
        except OSError:
            pass  # Si no se pudo, lo vuelve a intentar en la próxima revisión

    def revisar_fijadas(self):
        # Cada 2 segundos guarda las pestañas fijadas (así nunca se pierde lo que escribes en ellas)
        self.guardar_fijadas()
        self.raiz.after(2000, self.revisar_fijadas)

    # -----------------------------------------------------------------
    # CONFIGURACIÓN (la ventana para cambiar los atajos de teclado)
    # -----------------------------------------------------------------

    def cargar_configuracion(self):
        # Lee los atajos guardados; si no hay archivo (o está dañado), usa los de por defecto
        teclas = {"nueva_nota": TECLA_RAPIDA, "alternar_notas": TECLA_OCULTAR}
        self.transparente = False  # Por defecto: notas siempre visibles
        try:
            with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            for aviso in teclas:
                if guardado.get(aviso) in TECLAS_PERMITIDAS:
                    teclas[aviso] = guardado[aviso]
            self.transparente = guardado.get("transparente") is True
        except (OSError, ValueError, AttributeError):
            pass
        return teclas

    def guardar_configuracion(self):
        # Guarda los atajos elegidos para la próxima vez que se abra la app
        try:
            os.makedirs(os.path.dirname(ARCHIVO_CONFIG), exist_ok=True)
            with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
                json.dump({**self.teclas, "transparente": self.transparente}, f, indent=2)
        except OSError:
            messagebox.showerror("Error", "No se pudo guardar la configuración.")

    def abrir_configuracion(self, ventana_padre):
        # ☰ → Configuración: abre una ventana para elegir la letra de cada atajo
        if self.ventana_config and self.ventana_config.winfo_exists():
            self.ventana_config.lift()
            self.ventana_config.focus_force()
            return

        ventana = tk.Toplevel(self.raiz)
        self.ventana_config = ventana
        ventana.title("Configuración")
        ventana.resizable(False, False)
        ventana.attributes("-topmost", True)  # Encima de las notas
        ventana.config(padx=16, pady=12)
        ventana.geometry(f"+{ventana_padre.winfo_rootx() + 20}+{ventana_padre.winfo_rooty() + 40}")

        tk.Label(ventana, text="Atajos de teclado", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        listas = {}
        filas = (("nueva_nota", "Nueva nota:"), ("alternar_notas", "Ocultar / mostrar notas:"))
        for fila, (aviso, texto) in enumerate(filas, start=1):
            tk.Label(ventana, text=texto, font=("Segoe UI", 10)).grid(row=fila, column=0, sticky="w", pady=3)
            tk.Label(ventana, text="Ctrl + Alt +", font=("Segoe UI", 10)).grid(row=fila, column=1, padx=(10, 4))
            lista = ttk.Combobox(ventana, values=TECLAS_PERMITIDAS, width=4, state="readonly")
            lista.config(postcommand=lambda l=lista: lista_encima(l))  # Su lista aparece encima de las notas
            lista.set(self.teclas[aviso])
            lista.grid(row=fila, column=2, sticky="w")
            listas[aviso] = lista

        # Transparencia: se puede marcar solo una opción (las dos usan la misma variable)
        tk.Label(ventana, text="Notas", font=("Segoe UI", 11, "bold")).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(14, 4))
        modo = tk.StringVar(ventana, value="transparente" if self.transparente else "visible")
        opciones = (("visible", "Siempre visible"),
                    ("transparente", "Transparente"))
        for fila, (valor, texto) in enumerate(opciones, start=4):
            ttk.Radiobutton(ventana, text=texto, variable=modo, value=valor).grid(
                row=fila, column=0, columnspan=3, sticky="w", pady=2)

        botones = tk.Frame(ventana)
        botones.grid(row=6, column=0, columnspan=3, sticky="e", pady=(12, 0))

        def por_defecto():
            # Vuelve a poner N y B en las listas (se aplican al apretar Guardar)
            listas["nueva_nota"].set(TECLA_RAPIDA)
            listas["alternar_notas"].set(TECLA_OCULTAR)
            modo.set("visible")

        def guardar():
            nuevas = {aviso: lista.get() for aviso, lista in listas.items()}
            if nuevas["nueva_nota"] == nuevas["alternar_notas"]:
                messagebox.showerror("Configuración", "Los dos atajos no pueden usar la misma letra.",
                                     parent=ventana)
                return
            self.aplicar_configuracion(nuevas, modo.get() == "transparente")
            ventana.destroy()

        ttk.Button(botones, text="Por defecto", command=por_defecto).pack(side="left", padx=(0, 16))
        ttk.Button(botones, text="Cancelar", command=ventana.destroy).pack(side="left", padx=(0, 6))
        ttk.Button(botones, text="Guardar", command=guardar).pack(side="left")
        ventana.bind("<Escape>", lambda e: ventana.destroy())
        ventana.focus_force()

    def aplicar_configuracion(self, nuevas, transparente):
        # Usa los atajos y la transparencia nuevos desde ya, y los guarda para la próxima vez
        self.teclas.update(nuevas)
        self.transparente = transparente
        for nota in self.notas:
            nota.actualizar_opacidad()
        self.guardar_configuracion()
        if self.hilo_atajo:
            # 0x8001 es el mensaje CAMBIAR_ATAJOS que espera escuchar_atajo
            ctypes.windll.user32.PostThreadMessageW(self.hilo_atajo, 0x8001, 0, 0)

    # -----------------------------------------------------------------
    # ÍCONOS OCULTOS (el ícono junto al reloj de Windows)
    # -----------------------------------------------------------------

    def crear_icono_bandeja(self):
        # Crea el ícono con su menú de clic derecho
        menu = pystray.Menu(
            # default=True: también se ejecuta al hacer doble clic en el ícono
            pystray.MenuItem("Mostrar notas", lambda: self.avisos.put("mostrar_notas"), default=True),
            pystray.MenuItem("Nueva nota", lambda: self.avisos.put("nueva_nota")),
            pystray.MenuItem("Ocultar notas", lambda: self.avisos.put("ocultar_notas")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", lambda: self.avisos.put("salir")),
        )
        self.icono = pystray.Icon("Notas-adhesivas", imagen_icono(), "Notas-adhesivas", menu)
        self.icono.run_detached()

    def mostrar_notas(self):
        # Trae al frente todas las notas (muestra las ocultas y abre las minimizadas)
        if not self.notas:
            self.nueva_nota()
            return
        for nota in self.notas:
            if nota.minimizada:
                nota.restaurar()
        self.mostrar_todas()

    def alternar_notas(self):
        # Ctrl + Alt + B: si hay alguna nota a la vista, oculta todas
        if any(not nota.oculta for nota in self.notas):
            self.ocultar_todas()
        else:
            self.mostrar_todas()

    def mostrar_todas(self):
        # Muestra todas las notas ocultas; la última queda lista para escribir
        for nota in self.notas:
            nota.mostrar()
        if self.notas:
            self.notas[-1].ventana.focus_force()

    def ocultar_todas(self):
        # Oculta todas las notas (sin borrar nada)
        for nota in self.notas:
            nota.ocultar()

    # -----------------------------------------------------------------
    # ABRIR Y CERRAR
    # -----------------------------------------------------------------

    def ventana_visible(self):
        # Devuelve una nota a la vista, para que las preguntas aparezcan encima de ella
        return next((nota.ventana for nota in self.notas if not nota.oculta), None)

    def confirmar_salir(self, ventana_padre=None):
        # "Salir" (del menú de la nota o del ícono): si alguna nota tiene contenido, pregunta antes de cerrar
        if any(nota.tiene_contenido_sin_fijar() for nota in self.notas):
            # Desde el ícono no llega una nota: se usa cualquiera que esté a la vista
            ventana_padre = ventana_padre or self.ventana_visible()
            if not messagebox.askyesno("Notas-adhesivas",
                                       "¿Salir de Notas-adhesivas?\nLo que no guardaste con Guardar (en el menú ☰) se perderá.",
                                       parent=ventana_padre):
                return
        self.salir()

    def salir(self):
        # Cierra el programa del todo (y quita el ícono de la barra de íconos ocultos)
        self.guardar_fijadas()
        self.icono.stop()
        self.raiz.destroy()

    def iniciar(self):
        # Deja el programa abierto, esperando clics y teclas
        self.raiz.mainloop()


# =====================================================================
#  PUNTO DE PARTIDA
#  Esto solo se ejecuta cuando abres este archivo directamente
# =====================================================================
if __name__ == "__main__":
    # Intenta "reservar" el puerto interno: si ya está ocupado, la app ya está abierta
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        servidor.bind(("127.0.0.1", PUERTO_INTERNO))  # 127.0.0.1 = solo este PC, nada de internet
        servidor.listen()
    except OSError:
        # Ya hay una copia abierta: le pide una nota nueva y esta copia se cierra
        try:
            with socket.create_connection(("127.0.0.1", PUERTO_INTERNO), timeout=2) as conexion:
                conexion.sendall(b"nueva_nota")
        except OSError:
            pass
        sys.exit()

    App(servidor).iniciar()