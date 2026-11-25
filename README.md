# Asignación de Horarios Estudiantiles (PUJ — Análisis de Algoritmos 2026-30)

**Autores:** Iván Álvarez Fuenmayor · Nassin Suz Soler  
**Repositorio:** `https://github.com/Ivarez/project-schedule-assignment.git`

## Objetivo del proyecto

Diseñar, implementar y evaluar un algoritmo de asignación de horarios semanales para un conjunto de estudiantes de la Pontificia Universidad Javeriana, fiel a la formalización matemática de la Entrega 1:

- **Validez (3 restricciones duras):**
  1. Máximo una sección por asignatura solicitada (y nunca asignar asignaturas no solicitadas).
  2. Cero cruces de horario para cada estudiante.
  3. Respeto estricto del cupo máximo de cada sección.
- **Optimización (función objetivo $Z(X)$):**
  Maximizar `w1·Prioridad + w2·Empatía + w3·Planificación + w4·Social − w5·Logística` integrando el grafo de ubicaciones del campus $G_U = (U, D)$ y el grafo de vínculos sociales $G_{\text{soc}}$.

El proyecto incluye **tres algoritmos comparables** sobre las mismas instancias:
1. **Voraz Constructivo** (`solve_greedy`): línea base polinomial rápida.
2. **Híbrido: Voraz Multi-Criterio + Búsqueda Local** (`solve_hybrid_local_search`): algoritmo principal con operadores `Relocate`, `Insert` y `Swap` (incluso entre secciones llenas).
3. **Exacto: Backtracking + Branch & Bound** (`solve_exact_branch_and_bound`): obtiene el óptimo global $Z^*$ en instancias pequeñas para medir el *gap* de optimalidad de las heurísticas.

---

## Requisitos

Solo **Python 3.10+** (no requiere instalar librerías ni entornos virtuales; usa 100% biblioteca estándar).

---

## Cómo clonar y ejecutar

```bash
git clone https://github.com/Ivarez/project-schedule-assignment.git
cd project-schedule-assignment
```

### 1. Lanzar la interfaz visual (recomendado para estudiar y sustentar)
```bash
python run_app.py
```
Abre automáticamente `http://127.0.0.1:8080` en tu navegador. Desde la interfaz puedes:
- Cambiar entre los 4 escenarios (`pequeno`, `intermedio`, `grande`, `extremo_conflictos`) o generar instancias nuevas con semilla personalizada.
- Modificar los pesos `w1..w5` en tiempo real y ver cómo cambia la asignación.
- Comparar Voraz, Híbrido y Exacto con instrumentación real (iteraciones, vecinos evaluados, movimientos, nodos/podas, *gap* vs. $Z^*$ y tiempo en `ms`).
- Auditar visualmente el desglose divergente de $Z(X)$ con eje cero, el horario semanal por estudiante, la ocupación de cupos de todas las secciones y el grafo del campus $G_U$.

### 2. Correr las pruebas unitarias
```bash
python -m unittest discover -s tests -v
```

### 3. Correr el benchmark experimental completo
```bash
python run_experiments.py
```
Imprime la tabla comparativa en consola y guarda los resultados reproducibles en `results/benchmark_results.csv` y `results/benchmark_results.json`.

---

## Estructura del repositorio

```text
├── src/
│   ├── models.py          # Entidades formales (E, A, T, G_U, S, G_soc, Weights, X)
│   ├── data_manager.py    # Generador con semillas, persistencia JSON/CSV y validador de consistencia
│   ├── evaluator.py       # Juez independiente: verifica 3 restricciones duras y calcula Z(X)
│   ├── solver.py          # Voraz, Híbrido (Búsqueda Local) y Exacto (Branch & Bound)
│   └── server.py          # Servidor HTTP local para la interfaz web
├── web/
│   ├── index.html         # Interfaz técnica de auditoría y comparativa
│   ├── styles.css         # Estilos sobrios de herramienta académica
│   └── app.js             # Renderizado de tablas, horario semanal, cupos y grafo SVG G_U
├── data/                  # 4 escenarios reproducibles en JSON + CSV
├── results/               # Resultados de benchmarks (JSON y CSV)
├── tests/
│   └── test_project.py    # Pruebas unitarias y de integración
├── run_app.py             # Lanza la interfaz web
├── run_experiments.py     # Corre todos los escenarios y guarda resultados
└── SUSTENTACION.md        # Guía didáctica de estudio y preparación para la sustentación
```

---

## Ruta recomendada para estudiar antes de la sustentación

1. Lee [SUSTENTACION.md](SUSTENTACION.md) de principio a fin (está escrito en lenguaje claro y directo, con el significado de cada símbolo, cómo funciona cada algoritmo y 10 preguntas clave que puede hacer el profesor).
2. Ejecuta `python run_app.py` y recorre el escenario `pequeno` y `extremo_conflictos` siguiendo la sección 8 de `SUSTENTACION.md`.
3. Ejecuta `python -m unittest discover -s tests -v` y `python run_experiments.py` para ver cómo el juez independiente (`evaluator.py`) valida las soluciones.
