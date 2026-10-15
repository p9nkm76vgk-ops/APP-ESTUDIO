# Estado del proyecto (15/10/2026)

## Funciona y está probado

| Función | Cómo se ha comprobado |
| --- | --- |
| Subida por arrastre o selección, con progreso por pasos | Prueba HTTP de extremo a extremo |
| Lectura de PDF, DOCX, PPTX, TXT e imágenes con OCR | Pruebas con documentos sintéticos + los 8 PDF reales |
| Clasificación de asignatura, idioma y tema | Los 8 PDF reales clasificados correctamente (5 Catalán, 3 Lengua) |
| Confirmación cuando la clasificación es dudosa o mezcla asignaturas | Prueba: no guarda nada hasta confirmar |
| Generación en modo sin IA (borrador extractivo) | Los 8 PDF reales procesados de principio a fin |
| Llamada a la API de Claude | Probada con respuestas simuladas (sin red ni clave real): petición, errores 401, reintentos |
| Control de calidad | Detecta datos inventados en pruebas; los apuntes de referencia de Brollador pasan sin falsos avisos |
| Exportación PDF y HTML con diseño por asignatura | PDF de las 9 asignaturas generados y validados en pruebas; revisados visualmente los de Catalán y Lengua |
| Carpetas por asignatura, metadatos, versiones, historial | Pruebas automáticas |
| Duplicados, reclasificación, correcciones, borrado, comprobación del guardado | Pruebas automáticas |

Total: 32 pruebas automáticas superadas.

## No probado todavía

- **Generación con IA real**: falta una clave de API. Es la parte que da apuntes simplificados como los de referencia; hay que validarla con 2-3 documentos cuando tengas la clave.
- **Regenerar una sección**: implementado, pero necesita la IA.
- **La interfaz en un navegador real**: las rutas y el JavaScript se han comprobado (sintaxis y API), pero no se ha visto la pantalla en un iPad.
- **OCR en español y catalán**: en el entorno de pruebas solo estaba el inglés; en tu equipo instala `tesseract-lang`.

## Siguientes pasos (fase 6)

1. Probar con IA real y ajustar `prompts/metodo_apuntes.md` comparando con los apuntes de referencia.
2. Repasos espaciados: fechas de repaso y registro de aciertos en las preguntas de recuperación.
3. Documentos largos: procesar por partes en lugar de recortar.
4. Comprobación automática de unidades y ecuaciones (Física y Química).
5. Clasificación con IA para desempatar los casos dudosos.
6. Exportar tarjetas a un formato de repaso (por ejemplo CSV para apps de tarjetas).
