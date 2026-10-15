# Auditoría: el método que hay que reproducir

Análisis de los 8 documentos de apuntes elaborados a mano en la conversación del 14/10/2026 (La Regenta; Brollador, Història del soldat, En la meva mort y A Mallorca durant la Guerra Civil de Rosselló-Pòrcel; L'alegria que passa de Rusiñol; Retrato de Machado; valores del SE y coordinación).

## Proceso seguido

1. Leer el documento de la profesora completo e identificar su organización (preguntas de examen o apartados numerados).
2. Decidir el idioma de salida por la asignatura: catalán para los textos de Catalán, castellano para Lengua.
3. Mantener todos los apartados del original, en el mismo orden, y explicarlos con frases cortas.
4. Convertir en tabla todo lo que se compara (estrofa por estrofa, tipos, influencias, valores).
5. Añadir apoyos para el examen: párrafo modelo «Así lo escribiría», trucos de memoria, conclusión y chuleta.
6. Añadir práctica (ejercicios con soluciones en el SE).
7. Señalar los errores o datos dudosos del original en lugar de copiarlos.

## Instrucciones que mejor funcionaron

- «Igual de completo, pero explicado más simple, fácil de empollar y de explicar en el examen como si lo hubiera hecho yo con mis palabras» (petición original del alumno).
- Seguir las preguntas del examen cuando el original las indica (La Regenta: 3 preguntas de 1 punto).
- Párrafo modelo redactado en primera persona del alumno, en bloque de cita.
- Lo marcado como «no estudiar» se resume en pocas líneas.

## Profundidad y estructura

- Completitud total: ningún apartado eliminado. Simplificación del lenguaje, no del contenido.
- Secciones de 1 a 4 por documento; subsecciones `###`; listas con términos clave en negrita; tablas de 3-4 columnas.
- Frases de menos de 25 palabras.

## Criterios para decidir qué conservar

- Se conserva todo lo que pueda preguntarse: fechas, obras, autores, movimientos, ejemplos del texto, pruebas gramaticales.
- Se condensa lo repetido entre apartados (los cuatro documentos de Rosselló-Pòrcel repiten el bloque de identificación).
- Se marcan los datos dudosos.

## Errores del original detectados (y cómo se trataron)

| Documento | Problema | Tratamiento |
| --- | --- | --- |
| La Regenta | Lista de «modismos asturianos» con significados poco fiables | Nota: basta saber que hay regionalismos; no memorizar la lista |
| En la meva mort | Fechado en marzo de 1936 pero el contexto dice «escrito durante la Guerra Civil» y «diagnosticado en 1937» | Nota «Compte amb la data» |
| Retrato (Machado) | «Afaite» por «afeite», «gay-saber» por «gay-trinar», «recorrido biológico» por «biográfico» | Corregido en los apuntes |
| Valores del SE | Ejercicios sin soluciones; algunos admiten dos lecturas | Soluciones orientativas marcadas con \* |

## Diseño

Documentos en Claude Docs: título, fecha, secciones `##`, tablas con cabecera, citas para los párrafos modelo. En la app se traslada a PDF con color por asignatura, cabecera de color, tablas con filas alternas, cajas para las citas y un margen derecho más ancho para anotar en Goodnotes.

## Limitaciones y mejoras incorporadas a la app

- Los apuntes de la conversación solo tenían práctica activa en el SE. La app añade **preguntas de recuperación siempre** (respaldo científico sólido: ver `config/evidencia.yaml`).
- Las soluciones dudosas se marcaban a mano; la app pide a la IA que lo haga y el control de calidad avisa de datos que no están en el original.
- Hacer 7 documentos llevó muchos pasos manuales y se cortó por límite de uso; la app procesa archivo a archivo con historial y reintento.
