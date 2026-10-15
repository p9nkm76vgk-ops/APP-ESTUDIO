# Sistema de Estudio

Aplicación web personal que convierte documentos académicos (PDF, Word, PowerPoint, texto o fotos de apuntes) en material de estudio adaptado a cada asignatura: apuntes desarrollados, resúmenes, esquemas, preguntas de examen o tarjetas de memoria. Clasifica cada documento en una de las nueve asignaturas, controla la calidad, exporta PDF listo para Goodnotes y lo guarda todo ordenado por carpetas.

Reproduce el método con el que se hicieron a mano los apuntes de La Regenta, Machado, Rosselló-Pòrcel, Rusiñol y los valores del SE (ver [docs/AUDITORIA.md](docs/AUDITORIA.md)).

## Puesta en marcha

Requisitos: Python 3.11 o superior y Tesseract (solo para fotos o PDF escaneados).

```bash
git clone <url-de-tu-repositorio> sistema-estudio
cd sistema-estudio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # y pon tu clave de API si la tienes
python -m app.main
```

Abre <http://127.0.0.1:8765>.

En Mac, Tesseract se instala con `brew install tesseract tesseract-lang` (incluye español y catalán).

### Con IA o sin IA

- **Con IA (recomendado):** pon `ESTUDIO_ANTHROPIC_API_KEY` en `.env`. La API de Anthropic se paga aparte de la suscripción de Claude.ai; ver costes en [docs/INVESTIGACION.md](docs/INVESTIGACION.md).
- **Sin IA:** si no hay clave, la app funciona igual de principio a fin, pero genera un *borrador extractivo*: reorganiza el original por apartados y añade preguntas de recuperación, sin simplificar el texto. Sirve para probar y como respaldo.

### Usarla desde el iPad

Arranca la app en el ordenador con `ESTUDIO_HOST=0.0.0.0` y abre `http://<ip-del-ordenador>:8765` en el iPad (misma red wifi). La app no tiene usuarios ni contraseña: hazlo solo en una red de confianza.

## Cómo se usa

1. Arrastra un archivo, deja que detecte la asignatura (o elígela) y escoge el tipo de material.
2. Si la clasificación es dudosa o el documento mezcla asignaturas, la app pregunta antes de guardar.
3. Revisa la vista previa, la pestaña **Calidad** y edita si hace falta (cada guardado crea una versión).
4. **Corregir** permite regenerar una sección (con IA), mover el documento de asignatura, guardar correcciones para la IA y borrar.
5. Descarga el PDF y pásalo a Goodnotes con los pasos de la pestaña **Goodnotes**.

Si subes el mismo archivo para el mismo tipo de material, la app avisa del duplicado en lugar de volver a generarlo.

## Dónde se guarda todo

En `data/Sistema-de-Estudio/` (configurable), fuera del código y excluido de git:

```
01-Lengua-Castellana/  02-Catalan/  03-Ingles/  04-Fisica/  05-Quimica/
06-Matematicas/  07-Historia-de-Espana/  08-Historia-de-la-Filosofia/  09-Business/
   └── Apuntes-Originales/  Apuntes/  Resumenes/  Esquemas/  Preguntas-de-Examen/  Tarjetas/
_sistema/   index.json · historial.jsonl · correcciones.jsonl
```

Cada documento tiene `.md` (editable), `.pdf`, `.html`, `.meta.json` (asignatura, tema, fecha, archivo de origen, versión, calidad) y sus versiones anteriores en `.versiones/`.

## Personalizar sin tocar código

| Qué | Dónde |
| --- | --- |
| Metodología, estructura, ejercicios, criterios de calidad, colores y palabras clave de cada asignatura | `config/subjects/*.yaml` |
| Método general de elaboración de apuntes (las instrucciones a la IA) | `prompts/metodo_apuntes.md` |
| Instrucciones por tipo de material | `prompts/tipos_salida.yaml` |
| Carpetas, modelo de IA, umbral de confianza | `config/app.yaml` |
| Técnicas de estudio y su nivel de evidencia | `config/evidencia.yaml` |

## Pruebas

```bash
python -m unittest discover -s tests -v
```

32 pruebas: extracción de los cinco formatos (incluido OCR), clasificación, idioma, calidad, exportación PDF de las nueve asignaturas, proveedor de IA simulado (sin red), duplicados, versiones, confirmación de clasificación, reclasificación, borrado y la API web de extremo a extremo.

## Estructura del código

```
app/
  main.py        servidor web y API
  pipeline.py    flujo completo y trabajos en segundo plano
  extract.py     lectura de PDF/DOCX/PPTX/TXT/imágenes + OCR
  classify.py    asignatura, idioma y tema
  generate.py    instrucciones para la IA y regeneración por secciones
  providers/     Claude (API) y modo sin IA; se pueden añadir otros
  quality.py     control de calidad automático
  storage.py     carpetas, metadatos, versiones, duplicados, historial
  export.py      PDF (reportlab) y HTML con el diseño de cada asignatura
  goodnotes.py   adaptador de Goodnotes, separado de la exportación
config/  prompts/  static/  tests/  docs/
```

Más información: [decisiones técnicas](docs/DECISIONES.md) · [investigación de integraciones y costes](docs/INVESTIGACION.md) · [estado y siguientes pasos](docs/ESTADO.md).

Las fuentes DejaVu incluidas en `app/fonts/` tienen licencia libre (ver `LICENSE-DejaVu.txt`).
