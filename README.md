# ComexData Analytics · calculadora de referencia (prototipo)

Calculadora de referencia de costos hasta Aduanas y plazos de importación a Chile, con declaraciones reales de Aduanas (DIN).

## Contenido de la carpeta
- `app.py` — la aplicación web (Streamlit).
- `motor.py` — el motor de cálculo (niveles de referencia, arancel en dos escenarios, alerta de cotización).
- `referencias/` — las tablas de referencia generadas por la Celda 18 (flete, seguro, plazo, arancel, mercado).
- `paises.csv` — nombres de los códigos de país (fuente: tabla de códigos de países del SII; el 904 es un código propio de Aduanas).
- `requirements.txt` — librerías necesarias.

## Cómo ejecutarla (Windows o Mac)
1. Instala Python 3.11 o superior desde python.org. En Windows, marca la casilla **"Add Python to PATH"** al instalar.
2. Descomprime esta carpeta donde quieras (por ejemplo, en el Escritorio).
3. Abre una terminal **dentro de la carpeta**:
   - Windows: abre la carpeta, haz clic en la barra de direcciones, escribe `cmd` y presiona Enter.
   - Mac: clic derecho en la carpeta > "Nuevo terminal en la carpeta".
4. Instala las librerías (solo la primera vez):
   ```
   pip install -r requirements.txt
   ```
5. Ejecuta la aplicación:
   ```
   streamlit run app.py
   ```
   Se abre sola en el navegador (dirección `http://localhost:8501`). Si pide un correo electrónico, deja el campo vacío y presiona Enter.
6. Para cerrarla, vuelve a la terminal y presiona `Ctrl + C`.

## Cómo actualizar los datos
Cuando agregues meses nuevos: procesa los archivos, ejecuta la Celda 18 y reemplaza el contenido de la carpeta `referencias/` con los archivos del zip nuevo. No hay que cambiar el código.

## Importante
Es una referencia orientativa basada en declaraciones pasadas, no una cotización ni asesoría aduanera. Ver la pestaña "Metodología y límites".
