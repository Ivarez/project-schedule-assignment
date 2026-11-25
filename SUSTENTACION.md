# Guia de Sustentacion - Asignacion de Horarios Estudiantiles (PUJ)

Esta guia esta escrita para leer rapido y entender de verdad cada concepto antes de la sustentacion individual. Usa ejemplos concretos, analogias simples y explicaciones directas sin relleno.

Autores: Ivan Alvarez Fuenmayor y Nassin Suz Soler
Curso: Analisis de Algoritmos (2026-30), Pontificia Universidad Javeriana

## 1. De que trata el proyecto en una frase

El proyecto construye automaticamente los horarios semanales de un grupo de estudiantes sin violar ninguna regla de la universidad (ni cruces de hora, ni repetir materias, ni pasarse del cupo de un salon) y buscando que el horario final sea lo mejor posible segun cinco criterios: prioridad academica, empatia con el profesor, preferencias de horario libre, estudiar con amigos y caminar lo menos posible entre edificios.

Piensalo como armar un rompecabezas donde cada pieza es una clase con horario y cupo fijo: primero hay que lograr que ninguna pieza choque con otra (validez) y luego encontrar el acomodo que deje a todos mas satisfechos (optimizacion).

## 2. Que significa cada letra del modelo matematico (Entrega 1)

En la sustentacion el profesor puede señalar cualquier letra de la formula y preguntarte que es. Aqui tienes el diccionario rapido:

1. E (Estudiantes): el conjunto de estudiantes que van a inscribir materias. Ejemplo: E001 es Ivan, E002 es Nassin. La cantidad de estudiantes se escribe |E| o n.
2. A (Asignaturas): las materias que existen en el semestre (Analisis de Algoritmos, Bases de Datos, etc.). Su cantidad es |A| o m.
3. T (Franjas horarias): los bloques de tiempo de la semana, por ejemplo T01 = Lunes 07:00-09:00, T02 = Lunes 09:00-11:00.
4. consec(tx, ty): una funcion que vale 1 si la franja ty va justo despues de tx el mismo dia (por ejemplo Lunes 7-9 y Lunes 9-11), y vale 0 en cualquier otro caso. Sirve para saber cuando un estudiante tiene dos clases pegadas y debe salir corriendo de un edificio a otro.
5. G_U = (U, D) (Grafo del campus): un grafo ponderado donde cada nodo u en U es un edificio real de la Javeriana (Maldonado, Baron, Giraldo, Ciencias, Pablo VI, Arboleda, Hoyos, Briceño) y cada arista tiene el tiempo en minutos D(ux, uy) que toma caminar de un edificio a otro. Consultar D(ux, uy) cuesta tiempo constante O(1) porque esta en una tabla hash.
6. S (Secciones): los grupos abiertos de cada materia. Una misma materia puede tener 2, 3 o 4 secciones distintas. Cada seccion s tiene:
   - asig(s): a que materia pertenece.
   - cupo(s): cuantos estudiantes caben como maximo.
   - horario(s): en que franjas de T se dicta (normalmente 1 o 2 bloques a la semana).
   - salon(s, t): en que edificio se dicta esa seccion en la franja t.
7. A_e: la lista de materias que pidio el estudiante e.
8. P_e(a) en [1, 10] (Prioridad academica): que tan urgente es la materia a para el estudiante e. 10 significa critica (prerrequisito o atraso), 1 significa electiva flexible.
9. M_e(s) en [0, 1] (Empatia con el profesor): que tanto le gusta al estudiante e el profesor de la seccion s. 1 es maxima afinidad, 0 es indiferente.
10. L_e(t) en [-1, 1] (Planificacion personal): como se siente el estudiante e teniendo clase en la franja t. +1 significa quiere clase ahi, 0 indiferente, -1 quiere ese bloque libre.
11. G_soc (Criterio social): lista de parejas (ei, ej, a, wij) que quieren ver juntos la materia a con una importancia wij entre 0 y 1.
12. X (La salida del algoritmo): una matriz de ceros y unos de tamaño |E| por |S|. X[e, s] = 1 significa que el estudiante e quedo inscrito en la seccion s; 0 significa que no.

## 3. Las 3 restricciones obligatorias (si falla una, la solucion NO sirve)

1. No repetir materias y solo inscribir lo pedido: un estudiante puede quedar en maximo 1 seccion de cada materia que pidio (<= 1, no = 1, porque a veces por cupos o cruces no caben todas), y nunca en una materia que no pidio.
2. Compatibilidad de horarios: un estudiante no puede tener dos clases en la misma franja horaria t. En el codigo esto se verifica en tiempo O(1) con un bitmask entero: cada franja es un bit, y si (mask_estudiante & mask_seccion) != 0, hay cruce.
3. Respeto de cupos: la suma de estudiantes inscritos en una seccion s nunca puede superar cupo(s).

## 4. La funcion objetivo Z(X) y por que importa balancear los pesos

Cuando una matriz X cumple las 3 restricciones anteriores, medimos que tan buena es con:

Z(X) = w1 * Prioridad(X) + w2 * Empatia(X) + w3 * Planificacion(X) + w4 * Social(X) - w5 * Logistica(X)

Fijate en dos detalles clave que suelen preguntar en sustentacion:
1. Logistica RESTA porque caminar entre edificios distantes en clases seguidas es un costo que queremos reducir, no un beneficio.
2. Escalas de los criterios: Prioridad suma numeros entre 1 y 10, mientras Empatia y Social suman numeros entre 0 y 1, y Logistica suma minutos de caminata. Por eso configuramos pesos por defecto balanceados (w1=1.0, w2=4.0, w3=2.0, w4=5.0, w5=1.5) y en la interfaz mostramos la tabla de desglose con unidades, aporte ponderado y porcentaje real sobre el eje cero. Asi se comprueba que todos los criterios influyen y ninguno aplasta a los demas.

## 5. Tipo y clase de complejidad del problema (Pregunta segura del profesor)

1. Que tipo de problema es: es un problema de optimizacion combinatoria (busca maximizar Z(X) entre todas las matrices binarias validas).
2. A que clase pertenece: como optimizacion es NP-dificil. Si lo formulamos como problema de decision ("existe una asignacion valida X tal que Z(X) >= K?"), es NP-completo.
3. Por que es NP-completo en su version de decision:
   - Esta en NP porque dada cualquier matriz X, nuestro modulo evaluator.py verifica las 3 restricciones y calcula Z(X) en tiempo polinomial.
   - Es NP-dificil porque contiene como casos particulares al Problema de Asignacion Generalizada (GAP), variantes multidimensionales de la Mochila (cupos de salones y bloques horarios) y Conjunto Independiente Ponderado sobre grafos de conflicto, ademas de terminos cuadraticos por parejas de amigos y transiciones consecutivas.
4. Por que no sirve fuerza bruta en instancias grandes: si hay R solicitudes estudiante-materia y cada materia tiene en promedio q secciones, el numero de combinaciones posibles es del orden (q + 1)^R. Con solo 30 estudiantes y 4 materias cada uno (R = 120, q = 3), 4^120 supera el numero de atomos del universo.

## 6. Como funciona la arquitectura del codigo (3 modulos separados)

Seguimos exactamente el diseño modular de la Entrega 1:

1. src/data_manager.py: genera los 4 escenarios con semillas fijas (pequeno, intermedio, grande, extremo_conflictos), los guarda en archivos separados JSON y CSV en la carpeta data/, y valida consistencia antes de correr cualquier algoritmo (cupos > 0, rangos validos, edificios existentes).
2. src/evaluator.py: es el juez independiente. Recibe cualquier solucion X sin saber que algoritmo la creo, revisa las 3 restricciones duras y calcula Z(X) desde cero. Si un algoritmo cometiera un error, el juez lo detecta al instante.
3. src/solver.py: implementa 3 algoritmos sobre los mismos datos para poder compararlos cientificamente en tiempo, puntaje Z(X) y cercania al optimo.

Ademas agregamos src/server.py + carpeta web/ para visualizar en vivo los resultados y auditar visualmente cada horario, cada cupo y el grafo del campus G_U.

## 7. Como funciona cada uno de los 3 algoritmos (con ejemplo mental)

Antes de explicar los algoritmos, recuerda nuestro truco de eficiencia: en vez de recalcular todo Z(X) cada vez que probamos meter un estudiante en una seccion, usamos evaluacion incremental exacta Delta Z(e, s). Eso calcula en tiempo O(t + g) (practicamente constante) cuanto sube o baja Z al inscribir al estudiante e en la seccion s, incluyendo amigos ya inscritos en s y caminatas con clases inmediatamente anteriores o siguientes.

### Algoritmo 1: Voraz Constructivo (solve_greedy)
- Idea: ordena todas las solicitudes (estudiante, materia) de mayor prioridad a menor prioridad (desempatando por materias con menos secciones disponibles). Va una por una y le asigna la seccion valida que de la mayor ganancia inmediata Delta Z > 0.
- Analogia: es como inscribir materias por orden de urgencia agarrando el mejor grupo que este libre en ese instante, sin volver atras nunca.
- Complejidad: O(R log R + R * q * (t + g)), totalmente polinomial (tarda pocos milisegundos).
- Debilidad: es miope. Un estudiante puede tomar el ultimo cupo de una seccion que otro necesitaba para no cruzarse, o quedar separado de su amigo porque el amigo todavia no se habia asignado.

### Algoritmo 2: Hibrido = Voraz Multi-Criterio + Busqueda Local (solve_hybrid_local_search) [Algoritmo principal]
- Fase 1 (Multi-semilla): corre 3 versiones rapidas del voraz (una por prioridad pura, otra que primero intenta juntar parejas de amigos G_soc en la misma seccion, y otra que prioriza materias con cupos mas escasos) y arranca desde la que dio mejor Z(X).
- Fase 2 (Busqueda Local): repite iteraciones mejorando Z(X) con 3 movimientos que siempre respetan las 3 restricciones:
  1. Relocate (Reasignacion): mueve un estudiante a otra seccion con cupo de la misma materia si mejora Z (por ejemplo para evitar una caminata larga o juntarse con un amigo).
  2. Insert (Insercion): revisa si alguna materia que habia quedado sin asignar ahora cabe en un hueco o cupo liberado.
  3. Swap (Intercambio): toma dos estudiantes de la misma materia que estan en secciones distintas y los intercambia entre si. Este movimiento es clave porque funciona incluso cuando ambas secciones estan al 100% de cupo, rompiendo bloqueos que el voraz nunca puede arreglar.
- Complejidad: polinomial por iteracion, converge rapido en pocas pasadas (tarda menos de medio segundo incluso con 120 estudiantes).
- Es heuristica o aproximacion: es una heuristica (no tiene cota matematica garantizada en el peor caso teorico, pero en la practica queda muy cerca del optimo global).

### Algoritmo 3: Exacto = Backtracking con Branch and Bound (solve_exact_branch_and_bound)
- Idea: explora el arbol exacto de decisiones para encontrar el verdadero optimo global Z* en instancias pequeñas.
- Como evita explorar todo el arbol:
  1. Warm start: arranca usando el puntaje del Hibrido como mejor solucion inicial (incumbent), asi poda desde el principio.
  2. Poda por factibilidad: descarta al instante cualquier seccion con cruce (bitmask) o sin cupo.
  3. Poda por cota superior (Upper Bound): en cada paso suma el puntaje actual mas el maximo beneficio optimista de las decisiones que faltan (asumiendo caminata 0, porque la logistica solo resta). Si ese techo optimista no supera la mejor solucion ya conocida, poda toda esa rama sin perder nunca el optimo real.
- Para que lo incluimos: no para usarlo con 120 estudiantes (ahi explota exponencialmente), sino para certificar Z* en el escenario pequeño y medir exactamente que tan buena es nuestra heuristica hibrida (Gap vs Z*).

## 8. Como guiar la demo en vivo durante la sustentacion (paso a paso)

1. Abre la terminal en la carpeta Proyecto y corre: python run_app.py
2. En la interfaz web (http://127.0.0.1:8080):
   - Paso 1 (Escenario pequeno): señala la tabla comparativa de los 3 algoritmos. Muestra que los 3 son VALIDOS (0 violaciones), que el Exacto certifica Z* y que el Hibrido logra casi el mismo puntaje en una fraccion minima del tiempo.
   - Paso 2 (Instrumentacion y Convergencia): señala la columna de instrumentacion (iteraciones, vecinos evaluados, relocates, swaps, inserts, nodos y podas de Branch and Bound) y la linea de convergencia Z0 -> Z1 -> ... -> Zk debajo de la tabla.
   - Paso 3 (Desglose con eje cero): muestra la tabla de desglose de Z(X) donde se ven las unidades de cada criterio, el peso w_i, el aporte positivo y la barra roja negativa de Logistica a la izquierda del eje cero.
   - Paso 4 (Auditoria visual): selecciona un estudiante y muestra su horario semanal (colores de L_e(t), coincidencia social, caminatas en minutos), la tabla de ocupacion de cupos (probando que ninguna seccion pasa del 100%) y el grafo del campus G_U con las rutas resaltadas en dorado.
   - Paso 5 (Sensibilidad en vivo): cambia al escenario extremo_conflictos o intermedio, sube w4 (Social) o w5 (Logistica) con los sliders y dale clic a Ejecutar algoritmos para demostrar en tiempo real como se reorganizan los horarios.

## 9. Preguntas dificiles que puede hacer el profesor (y como responder en 20 segundos)

1. Como saben que su algoritmo no hace trampa violando cupos o cruces?
   Respuesta: Por doble verificacion. Primero el solver revisa cupo restante y cruces con bitmasks en O(1) antes de cada insercion. Segundo, toda solucion pasa obligatoriamente por evaluator.py, un juez independiente que audita las 3 restricciones desde cero, y tenemos pruebas unitarias en tests/test_project.py que inyectan matrices invalidas a proposito para comprobar que el juez las rechaza.

2. Como saben que su calculo incremental Delta Z es exacto y no tiene un bug?
   Respuesta: Tenemos la prueba unitaria test_incremental_state_matches_full_evaluator que compara el puntaje acumulado paso a paso por _ScheduleState contra el calculo completo independiente de evaluate_assignment(), verificando coincidencia exacta hasta 5 decimales.

3. Por que usan bitmasks para los horarios?
   Respuesta: Porque las franjas semanales son maximo 36. Guardando el horario en un entero de bits, verificar cruces (mask_e & mask_s != 0) y agregar o quitar clases (|= y ^=) cuesta tiempo constante O(1), lo que acelera muchisimo la Busqueda Local y el Branch and Bound.

4. Por que el Hibrido logra asignar mas materias que el Voraz en extremo_conflictos?
   Respuesta: Porque el operador Swap intercambia estudiantes entre secciones llenas y Relocate mueve estudiantes a secciones alternativas, liberando franjas o cupos que permiten al operador Insert rescatar materias que habian quedado por fuera.

5. Por que su cota superior en Branch and Bound es admisible (nunca descarta el optimo)?
   Respuesta: Porque para las decisiones pendientes suma el mejor aporte individual posible y todos los vinculos sociales pendientes asumiendo costo logistico cero. Como la distancia entre edificios siempre es mayor o igual a cero, el valor real de cualquier rama nunca puede superar esa cota.

6. Que pasa si un estudiante pide 6 materias pero por cupos o cruces solo caben 4?
   Respuesta: La restriccion formal es <= 1 por materia solicitada, no = 1. El algoritmo asigna las de mayor prioridad posible sin violar ninguna restriccion dura, y la interfaz lista explicitamente cuales materias quedaron sin asignar para ese estudiante.

7. Que pasa si la universidad tiene 5.000 estudiantes? Escala?
   Respuesta: El Voraz es O(R log R) y sigue tardando milisegundos. En el Hibrido, Relocate es lineal en el numero de solicitudes, y Swap compara pares dentro de cada seccion; como los cupos por seccion estan acotados por el tamaño fisico del salon (25-40 estudiantes, una constante), el costo total crece linealmente con el numero de secciones y ademas podemos fijar un limite maximo de iteraciones o tiempo.

8. Cual es la diferencia entre su algoritmo Hibrido y un algoritmo de aproximacion?
   Respuesta: Un algoritmo de aproximacion demuestra matematicamente que su solucion nunca se aleja mas de un factor rho del optimo en cualquier instancia. Nuestro Hibrido es una heuristica: no tiene garantia teorica de peor caso, pero empíricamente en instancias pequeñas alcanza cerca del 98-100% del optimo Z* en milisegundos.

9. Por que la funcion consec(tx, ty) no cuenta doble una caminata entre dos clases seguidas?
   Respuesta: Porque consec(tx, ty) es direccional: solo vale 1 cuando ty es el bloque inmediatamente siguiente a tx el mismo dia (por ejemplo 7-9 seguido de 9-11), y vale 0 al reves (9-11 hacia 7-9). Asi cada transicion se suma exactamente una vez.

10. Que demostraron con la estrategia de datos de la Entrega 1?
    Respuesta: Generamos 4 escenarios reproducibles con semillas fijas (pequeno, intermedio, grande y extremo_conflictos), persistidos en archivos separados JSON y CSV en la carpeta data/, validados automaticamente en consistencia, y guardamos los resultados experimentales en results/ para que cualquier persona pueda repetir exactamente las mismas pruebas.
