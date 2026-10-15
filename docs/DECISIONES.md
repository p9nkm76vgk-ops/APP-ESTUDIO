# Decisiones técnicas

| Decisión | Motivo |
| --- | --- |
| App web local en Python (Starlette + uvicorn), sin base de datos | Funciona en ordenador e iPad desde el navegador; los datos son archivos normales que puedes abrir, copiar y respaldar. |
| Configuración en YAML y Markdown editables (`config/`, `prompts/`) | Pedido explícito: nada de reglas rígidas en el código. |
| Proveedor de IA intercambiable (`app/providers/`) y modo sin IA | Poder cambiar de modelo y que el flujo funcione aunque no haya clave. |
| Llamada a la API con `requests`, sin el SDK | Menos dependencias; la llamada es una sola petición. |
| Clasificador por palabras clave + idioma, con confianza y aviso de mezcla | Transparente, gratuito y editable. Probado: acierta los 8 documentos de referencia. Si duda, pregunta antes de guardar. |
| Control de calidad con tres estados (ok / aviso / no verificable) | No afirmar nunca que se ha comprobado algo que no se puede comprobar automáticamente. |
| Fidelidad: números y nombres propios del resultado que no estén en el original | Es la forma de invención más peligrosa en apuntes y se puede detectar sin IA. |
| PDF con reportlab y fuentes DejaVu incluidas | Sin servicios externos; admite «·», «ç», «→» y comillas. |
| Margen derecho de 2,6 cm | Espacio para anotar en Goodnotes. |
| Carpetas añadidas: `Apuntes/` y `Tarjetas/` | La propuesta original no tenía sitio para los apuntes desarrollados (el formato principal) ni para las tarjetas. |
| Duplicados por huella SHA-256 del archivo + tipo de material | Mismo archivo para otro tipo de material sí se permite; el original se guarda una sola vez. |
| Versiones en `.versiones/` al editar o regenerar | Poder volver atrás sin perder trabajo. |
| Correcciones con casilla «aplicar en el futuro» | Las correcciones no cambian reglas generales automáticamente a partir de un solo ejemplo: tú decides cuáles se aplican. |
| Datos privados fuera de git (`data/`, `referencias/`, `.env`) | No publicar apuntes ni claves. |
| Servidor solo en `127.0.0.1` por defecto | La app no tiene usuarios; abrirla a la red es una decisión tuya. |
