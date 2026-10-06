# DirtyData Lab

**Introduce errores de forma controlada y mide cuáles detecta tu herramienta.**

Herramienta local para generar CSV sintéticos con errores conocidos. Incluye una respuesta correcta por fila, columna y tipo de error, para practicar limpieza y probar controles de calidad.

## Ejecutar

Python 3.10 o superior. Sin dependencias para ejecutar el motor.

```bash
git clone https://github.com/jairoequelal-ctrl/dirtydata-lab.git
cd dirtydata-lab
python -m dirtydata_lab generate --rows 100 --seed 42 --rate 0.2 --output output
python -m dirtydata_lab detect --input output/dirty.csv --contract output/contract.json --output output/predictions.json
python -m dirtydata_lab evaluate --truth output/ground_truth.json --predictions output/predictions.json --output output/evaluation.json
python -m unittest discover -s tests -v
```

Abre `output/report.html` para ver el resumen visual. El reporte muestra las respuestas: no lo uses como entrada del detector.

## Qué incluye

- Perfiles de clientes, productos y pagos.
- Ocho errores: nombre vacío, ID duplicado, fecha inválida, importe negativo, categoría incorrecta, espacios extra, pérdida del cero inicial y referencia a un padre inexistente.
- `clean.csv`, `dirty.csv`, tabla de padres y contrato público.
- Registro de cada cambio con valores anteriores y posteriores.
- Semilla reproducible y hashes SHA-256.
- Evaluación con precisión, recall y F1, general y por tipo de error.
- Licencia MIT y guía para contribuir.

`--rate 0.2` significa un presupuesto de `floor(filas * 0.2)` eventos. Los duplicados agregan filas. No significa que el 20% de las celdas esté mal. Los errores se distribuyen por turno entre los tipos elegidos; un conjunto pequeño podría no incluirlos todos. Se reserva una fila limpia y se rechazan presupuestos imposibles.

## Probar tu propio detector

Usa solo `dirty.csv` y `contract.json`. Genera un JSON así:

```json
[{"row_id": "R000011", "column": "signup_date", "error_type": "invalid_date"}]
```

Este ejemplo muestra el formato, no una respuesta válida para toda semilla. Conserva `row_id`: es el localizador del benchmark y no el ID comercial.

La evaluación exige coincidencia exacta de fila, columna y tipo. Una etiqueta incorrecta cuenta como falso positivo y deja un error sin detectar. Las predicciones repetidas se deduplican. Cuando el denominador es cero, la métrica vale cero.

El detector incluido conoce estas reglas y obtiene resultados perfectos en la demo: eso comprueba su funcionamiento, pero no demuestra rendimiento sobre datos reales. Las reglas son ficticias: un importe negativo puede ser correcto en otro contexto y los códigos postales no representan reglas de un país.

## Aprender y contribuir

1. Genera la demo y compara cinco filas con el registro de respuestas.
2. Escribe un detector propio sin consultar ese registro.
3. Evalúalo y revisa falsos positivos y errores omitidos.
4. Cambia la semilla y repite.
5. Agrega un operador nuevo con una prueba de reversibilidad.

No usa datos personales reales ni transmite archivos a un servidor. No limpia automáticamente ni acepta esquemas arbitrarios en esta versión. Consulta [README.md](README.md) para detalles y [CONTRIBUTING.md](CONTRIBUTING.md) para aportar mejoras.
