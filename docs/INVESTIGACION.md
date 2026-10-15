# Investigación técnica (15/10/2026)

Clave: **verificado** = probado en este entorno o confirmado en la fuente oficial; **con autorización** = posible si das un permiso; **no posible** = no se puede hacer directamente.

## GitHub

| Función | Estado |
| --- | --- |
| Ver tus repositorios y si puedo escribir en ellos | Verificado (13 repositorios, permiso de escritura) |
| Subir este proyecto a un repositorio que ya exista | Con autorización: necesito que me digas cuál |
| Crear un repositorio nuevo desde aquí | No posible en esta sesión: la herramienta disponible solo conecta repositorios existentes |
| Cambiar visibilidad o borrar | No se hará sin tu autorización expresa |

Recomendación: crea un repositorio **privado** vacío en github.com (por ejemplo `sistema-estudio`) y lo conecto; o usa uno existente. Los apuntes y los originales quedan siempre fuera de git (`data/` en `.gitignore`).

## Goodnotes

| Pregunta | Respuesta |
| --- | --- |
| ¿API oficial? | No. Solo existe una petición de usuarios en su foro (abril de 2026) sin respuesta oficial. [Fuente](https://feedback.goodnotes.com/forums/191274-customer-suggestions-for-goodnotes-apple/suggestions/51189895-api) |
| ¿Importar documentos automáticamente? | No desde una app externa. |
| ¿Carpetas y subcarpetas? | No por programa; se crean a mano una vez. |
| ¿Actualizar documentos existentes? | No. |
| ¿Detectar duplicados? | No en Goodnotes; la app lo hace antes de exportar. |
| ¿Integración con Claude? | Sí, un conector con 3 herramientas: texto Markdown, diagrama Mermaid y dibujo SVG. Probado: crea documentos nuevos desde una conversación. No importa PDF, no elige carpetas, no actualiza ni lee notas. [Fuente](https://hackceleration.com/resources/integrations/claude/goodnotes) |
| ¿Qué es manual? | Pasar el PDF a Goodnotes (Compartir → Goodnotes) y elegir la carpeta. |

Solución implementada: PDF con nombre estable (`02 Catalán - Brollador - Apuntes desarrollados - v1.pdf`), márgenes para anotar e instrucciones en la app. El adaptador `app/goodnotes.py` está separado para cambiarlo si aparece un mecanismo oficial.

## Motor de IA

| Opción | Ventajas | Limitaciones |
| --- | --- | --- |
| **API de Anthropic (Claude)** — implementada | Mismo tipo de resultado que en la conversación; control total de las instrucciones | Requiere clave de pago; se factura aparte de Claude Pro/Max ([fuente](https://support.claude.com/en/articles/8114521-how-can-i-access-the-claude-api)) |
| Seguir usando Claude.ai a mano | Sin coste extra | No se puede automatizar ni acceder a conversaciones por programa |
| Otros modelos (OpenAI, Gemini, locales) | Posible ahorro | Habría que validar la calidad con los documentos de referencia; basta con añadir una clase en `app/providers/` |

### Costes de la API (precios oficiales por millón de tokens, USD)

| Modelo | Entrada | Salida |
| --- | --- | --- |
| Claude Opus 5.5 | 4 $ | 20 $ |
| Claude Sonnet 5.5 (por defecto) | 2 $ | 10 $ |
| Claude Haiku 5.5 (hasta 100.000 tokens) | 0,10 $ | 0,50 $ |

[Fuente](https://platform.claude.com/docs/en/about-claude/pricing). La Batch API rebaja un 50 %.

**Estimación (no medida):** un documento como los de prueba son unos 11.000 tokens de entrada (original + instrucciones) y unos 6.000 de salida. Con Sonnet 5.5 serían unos 0,08 $ por documento; con Haiku 5.5, menos de 0,01 $; con Opus 5.5, unos 0,16 $. El coste real depende de la longitud de cada documento y se verá en la consola de Anthropic.

## Privacidad: qué datos salen de tu equipo

| Destino | Qué se envía | Cuándo |
| --- | --- | --- |
| API de Anthropic | Texto extraído del documento + instrucciones de la asignatura + tus correcciones activas | Solo en modo IA, al generar o regenerar |
| Nadie más | — | El OCR, la clasificación, la exportación y el almacenamiento son locales |

La clave de API se lee solo de la variable `ESTUDIO_ANTHROPIC_API_KEY` (archivo `.env`, excluido de git) y nunca llega al navegador. Por defecto el servidor solo escucha en tu propio equipo.

## Limitación del entorno de desarrollo

En esta sesión no se podían instalar paquetes nuevos, así que la app usa solo bibliotecas comunes ya disponibles (Starlette, uvicorn, reportlab, pdfplumber…). No es una limitación para ti: `requirements.txt` instala todo.
