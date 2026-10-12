# Notas-adhesivas

---

## ¿Qué es Notas-adhesivas?

Es una app de notas adhesivas (post-its) para el escritorio de Windows cada nota queda siempre encima de las demás ventanas, así tienes a la vista lo que necesitas recordar (links, tareas, apuntes) mientras trabajas o estudias, sin cambiar de ventana.

Cada nota tiene **título**, **pestañas** (varias notas dentro de una misma ventana), **color** y **tipo de letra**, y se puede mover, agrandar, minimizar o maximizar.

### ¿Qué tiene que no tenga el Bloc de notas de Windows?

El Bloc de notas sirve para escribir texto, pero no está pensado para tener notas a la vista. Esto es lo que agrega Notas-adhesivas:

| | Bloc de notas | Notas-adhesivas |
|---|:---:|:---:|
| Queda siempre encima de las otras ventanas | ❌ | ✅ |
| Un color distinto para cada nota | ❌ | ✅ |
| Elegir tipo y tamaño de letra para partes del texto | ❌ | ✅ |
| Minimizar a solo una barra con el título | ❌ | ✅ |
| Crear una nota desde cualquier programa con un atajo | ❌ | ✅ |
| Ocultar y mostrar todas las notas con un atajo | ❌ | ✅ |
| Notas transparentes para que no tapen lo de atrás | ❌ | ✅ |

## Ventajas y próximas mejoras

### Ventajas

- Siempre a la vista: las notas no se esconden detrás de otras ventanas.
- Rápida y liviana: no usa internet, no necesita cuenta y casi no consume recursos.
- Ordenada: pestañas que se pueden **arrastrar para ordenarlas**, colores y títulos para separar temas.
- Letra como en Word: cambia el tipo y el tamaño solo de lo que seleccionas, o de lo que escribes desde el cursor.
- No pierdes lo importante: las pestañas fijadas con 📌 se guardan solas y vuelven a aparecer cada vez que abres la app.
- Atajos de teclado para crear una nota (`Ctrl + Alt + N`) o esconder todas (`Ctrl + Alt + B`), y las letras se pueden cambiar.
- **Modo transparente:** las notas quedan al 60 % mientras no las usas y se ven sólidas al pasar el mouse o escribir.
- **Detalles cuidados:** la nota se enrolla con una animación al minimizarla y las pestañas se deslizan al arrastrarlas.

### Próximas mejoras

Ideas para las siguientes versiones:

- [ ] **Lista de tareas** con casillas ☐ ☑ que se marcan con un clic.
- [ ] **Negrita, cursiva y subrayado** (`Ctrl + B`, `Ctrl + I`, `Ctrl + U`).
- [ ] **Recordatorios:** que una nota aparezca al frente a una hora elegida.
- [ ] **Buscar** dentro de las notas con `Ctrl + F`.
- [ ] **Guardado de emergencia** de todas las pestañas, por si se corta la luz.
- [ ] **Iniciar con Windows** (como opción en Configuración).
- [ ] Poner la **versión de Linux** al día con las novedades de la 1.3.

- [ ] Cómo funciona y con qué está hecha

La app es de **código abierto**: todo el código está en este repositorio y cualquiera puede revisarlo.

### Tecnologías

| Herramienta | Para qué se usa |
|---|---|
| [Python 3](https://www.python.org) | Lenguaje en el que está escrita la app |
| Tkinter | Las ventanas, botones y el texto de las notas (viene incluido con Python) |
| [pystray](https://pypi.org/project/pystray/) | El ícono junto al reloj de Windows |
| [Pillow](https://pypi.org/project/pillow/) | Cargar la imagen de ese ícono |
| ctypes | Hablar con Windows: los atajos de teclado y el tamaño de la pantalla al maximizar |
| [PyInstaller](https://pyinstaller.org) | Convertir el código en un programa `.exe` |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Crear el instalador |

### 🔒 Privacidad y seguridad

- **No se conecta a internet.** Solo abre tu navegador cuando haces clic en un link de una nota.
- **Para saber si ya está abierta**, la app usa una conexión interna de tu PC (`127.0.0.1`), que no sale a internet. Así, si la abres dos veces, crea una nota nueva en vez de abrir otra copia
- **Todo se guarda en tu PC:**
  - Las pestañas fijadas y la configuración van en `%APPDATA%\Notas-adhesivas` (`fijadas.json` y `config.json`).
  - Las notas que guardas van en archivos `.nota` donde tú elijas
  - Todos son archivos de texto que puedes abrir y leer con cualquier editor
- **No pide permisos de administrador** para instalarse
- Windows puede mostrar el aviso **"Windows protegió su PC"** porque la app no tiene firma digital, ya que el certificado tiene un costo anual para abrirla, elige **Más información → Ejecutar de todas formas**

- ## Descarga e instalación

1- Entra a **[Releases](https://github.com/Alonozxd/Notas-adhesivas/releases)**, descarga **`Instalador-Notas-adhesivas.zip`**
2- Ábrelo y sigue los pasos si aparece "Windows protegió su PC", elige **Más información → Ejecutar de todas formas**
3- Listo: la app queda en el menú Inicio (y en el Escritorio, si marcaste esa opción)

- ### 🖱️ Botones

| Botón | Qué hace |
|---|---|
| ☰ | Menú con **Abrir**, **Guardar** y **Configuración** |
| Paleta de colores | Cambia el color de la pestaña abierta |
| 📌 | Fija la pestaña: se guarda sola y vuelve a aparecer al abrir la app |
| + | Crea una pestaña nueva |
| — | Minimiza la nota (queda solo la barra) o la vuelve a abrir |
| 🗖 / 🗗 | Maximiza la nota o la vuelve a su tamaño |
| ✕ | Cierra la nota |
| Aa ▾ / 11 ▾ | Tipo y tamaño de letra (abajo a la izquierda) |
| ◢ | Arrástrala para cambiar el tamaño de la nota |

### ⌨️ Atajos y trucos

| Atajo | Qué hace |
|---|---|
| `Ctrl + Alt + N` | Crea una nota nueva desde cualquier programa |
| `Ctrl + Alt + B` | Oculta todas las notas, o las vuelve a mostrar |
| `Ctrl + A` | Selecciona todo el texto (por ejemplo, para cambiarle la letra) |
| `Enter` en el título | Pasa a escribir el texto |

- **Arrastra una pestaña** para cambiarla de lugar.
- **Clic derecho en la barra** → **Nueva nota** y **Salir**.
- Los atajos y el modo **Transparente** se cambian en **☰ → Configuración**.
- Al cerrar la última nota, la app sigue abierta en segundo plano (ícono junto al reloj) para que los atajos sigan funcionando. Para cerrarla del todo, usa **Salir**.

> ⚠️ Solo las pestañas fijadas con 📌 se guardan solas. Para las demás, usa **☰ → Guardar**.

# IMAGENES DEL PROYECTO

<p align="center">
  <img width="80%" alt="Notas-adhesivas en el escritorio" src="https://github.com/user-attachments/assets/7447f7a2-3bfd-4aa2-a75a-e92b8a9e057c" />
  <br><br>
  <img width="80%" alt="Captura 2" src="https://github.com/user-attachments/assets/691bc82e-5132-402a-9fdc-528460d2d8fa" />
  <br><br>
  <img width="80%" alt="Captura 3" src="https://github.com/user-attachments/assets/38b13a97-65b9-479c-a8e0-140e2fbbab67" />
</p>












