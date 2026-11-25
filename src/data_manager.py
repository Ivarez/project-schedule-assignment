"""Módulo de Carga, Generación y Validación de Consistencia de Datos (Secciones 4.2 y 5).

Genera instancias realistas basadas en el campus de la Pontificia Universidad Javeriana
con semillas controladas, guarda/carga archivos separados en JSON y CSV (Sección 5.2)
y valida la consistencia completa de los datos de entrada (Sección 5.4).
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

from .models import (
    Building,
    Course,
    Instance,
    LocationGraph,
    Section,
    SocialLink,
    Student,
    TimeSlot,
    Weights,
)

# Edificios reales del campus PUJ Bogotá con coordenadas relativas (0..100)
PUJ_BUILDINGS: List[Tuple[str, str, str, float, float]] = [
    ("U1", "Ed. José Gabriel Maldonado (Ingeniería)", "Maldonado", 72.0, 22.0),
    ("U2", "Ed. Fernando Barón", "Barón", 45.0, 42.0),
    ("U3", "Ed. Gabriel Giraldo", "Giraldo", 30.0, 62.0),
    ("U4", "Ed. Jesús Emilio Ramírez (Ciencias)", "Ciencias", 62.0, 52.0),
    ("U5", "Ed. Pablo VI", "Pablo VI", 22.0, 32.0),
    ("U6", "Ed. Rafael Arboleda (Biblioteca)", "Arboleda", 50.0, 74.0),
    ("U7", "Ed. Jorge Hoyos Vásquez", "Hoyos", 78.0, 68.0),
    ("U8", "Ed. Manuel Briceño", "Briceño", 18.0, 78.0),
]

PUJ_COURSES: List[Tuple[str, str, int]] = [
    ("A01", "Análisis de Algoritmos", 3),
    ("A02", "Estructuras de Datos", 3),
    ("A03", "Bases de Datos", 3),
    ("A04", "Ingeniería de Software", 3),
    ("A05", "Sistemas Operativos", 3),
    ("A06", "Redes de Computadores", 3),
    ("A07", "Arquitectura de Computadores", 3),
    ("A08", "Inteligencia Artificial", 3),
    ("A09", "Cálculo Vectorial", 4),
    ("A10", "Álgebra Lineal", 3),
    ("A11", "Probabilidad y Estadística", 3),
    ("A12", "Matemáticas Discretas", 3),
    ("A13", "Teoría de la Computación", 3),
    ("A14", "Desarrollo Web", 3),
    ("A15", "Seguridad Informática", 3),
    ("A16", "Computación Gráfica", 3),
    ("A17", "Física Mecánica", 4),
    ("A18", "Física Electricidad", 4),
    ("A19", "Ética Profesional", 2),
    ("A20", "Constitución Política", 2),
    ("A21", "Aprendizaje Automático", 3),
    ("A22", "Sistemas Distribuidos", 3),
    ("A23", "Compiladores", 3),
    ("A24", "Gestión de Proyectos TI", 3),
    ("A25", "Electiva de Humanidades", 2),
]

PROFESSORS: List[str] = [
    "Prof. L. Flórez", "Prof. M. González", "Prof. C. Parra", "Prof. A. Carrillo",
    "Prof. R. Pavlich", "Prof. D. Suárez", "Prof. J. Bustacara", "Prof. E. Rueda",
    "Prof. S. Rojas", "Prof. P. Ortiz", "Prof. V. Mendoza", "Prof. H. Torres",
    "Prof. G. Castillo", "Prof. N. Vargas", "Prof. F. Morales", "Prof. K. Díaz",
]

FIRST_NAMES = [
    "Iván", "Nassin", "Sofía", "Mateo", "Valentina", "Santiago", "Camila", "Sebastián",
    "Mariana", "Alejandro", "Lucía", "Nicolás", "Isabella", "Daniel", "Gabriela",
    "Samuel", "Laura", "Tomás", "Paula", "Andrés", "Manuela", "Felipe", "Catalina",
    "Juan", "Valeria", "Diego", "Juliana", "David", "Sara", "Esteban",
]

LAST_NAMES = [
    "Álvarez", "Suz", "Rodríguez", "Martínez", "Gómez", "López", "Hernández",
    "Ramírez", "Torres", "Sánchez", "Castro", "Vargas", "Rojas", "Moreno",
    "Jiménez", "Pérez", "Romero", "Díaz", "Ruiz", "Mendoza",
]

DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
BLOCKS = ["07:00-09:00", "09:00-11:00", "11:00-13:00", "14:00-16:00", "16:00-18:00", "18:00-20:00"]


def build_time_slots(include_saturday: bool = True, blocks_per_day: int = 6) -> Dict[str, TimeSlot]:
    """Construye el conjunto discreto de franjas horarias T."""
    days = DAYS if include_saturday else DAYS[:5]
    slots: Dict[str, TimeSlot] = {}
    idx = 1
    for d_idx, day in enumerate(days):
        max_b = min(blocks_per_day, 3 if day == "Sábado" else blocks_per_day)
        for b_idx in range(max_b):
            tid = f"T{idx:02d}"
            slots[tid] = TimeSlot(
                id=tid,
                day=day,
                day_index=d_idx,
                block_index=b_idx,
                label=BLOCKS[b_idx],
            )
            idx += 1
    return slots


def build_puj_locations(num_buildings: int = 8) -> LocationGraph:
    """Construye el grafo ponderado del campus PUJ G_U = (U, D) con distancias en minutos."""
    selected = PUJ_BUILDINGS[: max(2, min(num_buildings, len(PUJ_BUILDINGS)))]
    buildings: Dict[str, Building] = {}
    for uid, name, short, x, y in selected:
        buildings[uid] = Building(id=uid, name=name, short_name=short, x=x, y=y)

    distances: Dict[str, Dict[str, float]] = {}
    for u1, b1 in buildings.items():
        distances[u1] = {}
        for u2, b2 in buildings.items():
            if u1 == u2:
                distances[u1][u2] = 0.0
            else:
                # Distancia euclidiana escalada a minutos de caminata en campus (2 a 12 min)
                raw = math.hypot(b1.x - b2.x, b1.y - b2.y)
                minutes = round(1.5 + (raw / 100.0) * 11.0, 2)
                distances[u1][u2] = minutes
    return LocationGraph(buildings=buildings, distances=distances)


def _pick_session_slots(
    rng: random.Random,
    slots_by_day: Dict[int, List[str]],
    sessions_per_week: int,
) -> Tuple[str, ...]:
    """Selecciona 1 o 2 franjas semanales en días distintos (patrón realista PUJ)."""
    available_days = [d for d, sl in slots_by_day.items() if sl]
    if sessions_per_week == 1 or len(available_days) < 2:
        d = rng.choice(available_days)
        return (rng.choice(slots_by_day[d]),)
    # Patrones clásicos Lun-Mié, Mar-Jue, Mié-Vie o dos días aleatorios
    common_pairs = [(0, 2), (1, 3), (2, 4), (0, 3), (1, 4)]
    valid_pairs = [p for p in common_pairs if p[0] in slots_by_day and p[1] in slots_by_day]
    if valid_pairs and rng.random() < 0.75:
        d1, d2 = rng.choice(valid_pairs)
    else:
        d1, d2 = sorted(rng.sample(available_days, 2))
    # Misma hora ambos días en el 70% de los casos
    s1_list = slots_by_day[d1]
    s2_list = slots_by_day[d2]
    b_idx = rng.randrange(min(len(s1_list), len(s2_list)))
    if rng.random() < 0.70:
        return (s1_list[b_idx], s2_list[b_idx])
    return (rng.choice(s1_list), rng.choice(s2_list))


def generate_instance(
    name: str,
    description: str,
    num_students: int,
    num_courses: int,
    sections_per_course: Tuple[int, int],
    courses_per_student: Tuple[int, int],
    capacity_range: Tuple[int, int],
    social_density: float = 0.25,
    num_buildings: int = 8,
    include_saturday: bool = True,
    blocks_per_day: int = 6,
    seed: int = 42,
    stress_conflicts: bool = False,
) -> Instance:
    """Genera una instancia reproducible controlada por semilla."""
    rng = random.Random(seed)
    time_slots = build_time_slots(include_saturday=include_saturday, blocks_per_day=blocks_per_day)
    locations = build_puj_locations(num_buildings=num_buildings)
    building_ids = list(locations.buildings.keys())

    slots_by_day: Dict[int, List[str]] = {}
    for tid, ts in time_slots.items():
        slots_by_day.setdefault(ts.day_index, []).append(tid)

    # 1. Asignaturas A
    courses: Dict[str, Course] = {}
    for i in range(num_courses):
        if i < len(PUJ_COURSES):
            cid, cname, cred = PUJ_COURSES[i]
        else:
            cid, cname, cred = f"A{i+1:02d}", f"Asignatura Especial {i+1}", 3
        courses[cid] = Course(id=cid, name=cname, credits=cred)
    course_ids = list(courses.keys())

    # 2. Secciones S
    sections: Dict[str, Section] = {}
    sec_counter = 1
    for cid in course_ids:
        k_sec = rng.randint(sections_per_course[0], sections_per_course[1])
        used_schedules = set()
        for _ in range(k_sec):
            sid = f"S{sec_counter:03d}"
            sec_counter += 1
            sessions_w = 1 if (courses[cid].credits <= 2 or stress_conflicts) else 2
            sched = _pick_session_slots(rng, slots_by_day, sessions_w)
            # Evitar secciones idénticas en la misma materia si es posible
            for _try in range(6):
                if sched not in used_schedules:
                    break
                sched = _pick_session_slots(rng, slots_by_day, sessions_w)
            used_schedules.add(sched)

            # En modo stress_conflicts, concentrar horarios en bloques centrales para forzar cruces y logística
            if stress_conflicts and rng.random() < 0.65:
                d_choice = rng.choice(list(slots_by_day.keys())[:4])
                narrow = slots_by_day[d_choice][:3]
                sched = (rng.choice(narrow),)

            # Asignar salones (a veces distinto salón en cada día)
            primary_b = rng.choice(building_ids)
            rooms = {}
            for tid in sched:
                rooms[tid] = primary_b if rng.random() < 0.8 else rng.choice(building_ids)

            cap = rng.randint(capacity_range[0], capacity_range[1])
            prof = rng.choice(PROFESSORS)
            sections[sid] = Section(
                id=sid,
                course_id=cid,
                capacity=cap,
                schedule=sched,
                rooms=rooms,
                professor=prof,
            )

    # 3. Estudiantes E y preferencias
    students: Dict[str, Student] = {}
    all_tids = list(time_slots.keys())
    all_sids = list(sections.keys())

    for i in range(num_students):
        eid = f"E{i+1:03d}"
        if i == 0:
            full_name = "Iván Álvarez"
        elif i == 1:
            full_name = "Nassin Suz"
        else:
            full_name = f"{FIRST_NAMES[i % len(FIRST_NAMES)]} {LAST_NAMES[(i * 3) % len(LAST_NAMES)]}"

        k_req = rng.randint(
            min(courses_per_student[0], num_courses),
            min(courses_per_student[1], num_courses),
        )
        req_courses = sorted(rng.sample(course_ids, k_req))

        # Prioridades P_e(a) ∈ [1, 10]
        priorities: Dict[str, float] = {}
        for cid in req_courses:
            if stress_conflicts and rng.random() < 0.45:
                priorities[cid] = float(rng.randint(8, 10))
            else:
                priorities[cid] = float(rng.randint(1, 10))

        # Empatía M_e(s) ∈ [0, 1] (solo relevante para secciones de materias solicitadas, pero llenamos todas)
        empathy: Dict[str, float] = {}
        for sid in all_sids:
            if sections[sid].course_id in priorities:
                empathy[sid] = round(rng.uniform(0.0, 1.0), 2)

        # Planificación personal L_e(t) ∈ {-1, 0, 1} con perfil realista (mañana / tarde / balanceado)
        profile = rng.choice(["manana", "tarde", "balanceado"])
        time_prefs: Dict[str, float] = {}
        for tid in all_tids:
            ts = time_slots[tid]
            if profile == "manana":
                val = 1.0 if ts.block_index <= 2 else (-1.0 if ts.block_index >= 4 else 0.0)
            elif profile == "tarde":
                val = -1.0 if ts.block_index == 0 else (1.0 if ts.block_index >= 3 else 0.0)
            else:
                val = rng.choice([-1.0, 0.0, 0.0, 1.0])
            # Pequeña variación individual
            if rng.random() < 0.18:
                val = rng.choice([-1.0, 0.0, 1.0])
            time_prefs[tid] = val

        students[eid] = Student(
            id=eid,
            name=full_name,
            requested_courses=req_courses,
            priorities=priorities,
            empathy=empathy,
            time_preferences=time_prefs,
        )

    # 4. Vínculos sociales G_soc = {(e_i, e_j, a, w_ij)}
    social_links: List[SocialLink] = []
    seen_links = set()
    eids = list(students.keys())
    for i in range(len(eids)):
        for j in range(i + 1, len(eids)):
            ei, ej = eids[i], eids[j]
            common = set(students[ei].requested_courses) & set(students[ej].requested_courses)
            if not common:
                continue
            if rng.random() < social_density:
                cid = rng.choice(sorted(common))
                key = (ei, ej, cid)
                if key not in seen_links:
                    seen_links.add(key)
                    w_ij = round(rng.uniform(0.4, 1.0), 2)
                    social_links.append(SocialLink(student_i=ei, student_j=ej, course_id=cid, weight=w_ij))

    # Limitar enlaces sociales en instancias grandes para mantener densidad realista de grupos de estudio
    max_links = max(4, num_students * 2)
    if len(social_links) > max_links:
        social_links = rng.sample(social_links, max_links)

    return Instance(
        name=name,
        description=description,
        seed=seed,
        time_slots=time_slots,
        locations=locations,
        courses=courses,
        sections=sections,
        students=students,
        social_links=social_links,
        default_weights=Weights(),
    )


def validate_instance_consistency(inst: Instance) -> Tuple[bool, List[str]]:
    """Valida consistencia estructural de los datos de entrada (Sección 5.4)."""
    errors: List[str] = []
    if not inst.students:
        errors.append("El conjunto de estudiantes E está vacío.")
    if not inst.courses:
        errors.append("El conjunto de asignaturas A está vacío.")
    if not inst.sections:
        errors.append("El conjunto de secciones S está vacío.")
    if not inst.time_slots:
        errors.append("El conjunto de franjas horarias T está vacío.")

    # Validar distancias D(u_x, u_y) >= 0
    for u1, row in inst.locations.distances.items():
        if u1 not in inst.locations.buildings:
            errors.append(f"Edificio desconocido en matriz de distancias: {u1}")
        for u2, d in row.items():
            if u2 not in inst.locations.buildings:
                errors.append(f"Edificio destino desconocido: {u2}")
            if d < 0:
                errors.append(f"Distancia negativa D({u1}, {u2}) = {d}")

    # Validar secciones S
    for sid, sec in inst.sections.items():
        if sec.course_id not in inst.courses:
            errors.append(f"Sección {sid} apunta a asignatura inexistente {sec.course_id}")
        if sec.capacity <= 0:
            errors.append(f"Sección {sid} tiene cupo no positivo: {sec.capacity}")
        if not sec.schedule:
            errors.append(f"Sección {sid} no tiene franjas horarias.")
        for tid in sec.schedule:
            if tid not in inst.time_slots:
                errors.append(f"Sección {sid} usa franja inexistente {tid}")
            if tid not in sec.rooms or sec.rooms[tid] not in inst.locations.buildings:
                errors.append(f"Sección {sid} no tiene salón válido en franja {tid}")

    # Validar estudiantes y rangos de preferencias
    for eid, st in inst.students.items():
        for cid in st.requested_courses:
            if cid not in inst.courses:
                errors.append(f"Estudiante {eid} solicita asignatura inexistente {cid}")
            p_val = st.priorities.get(cid)
            if p_val is None or not (1.0 <= p_val <= 10.0):
                errors.append(f"Prioridad fuera de [1, 10] para ({eid}, {cid}): {p_val}")
        for sid, m_val in st.empathy.items():
            if sid not in inst.sections:
                errors.append(f"Empatía de {eid} apunta a sección inexistente {sid}")
            if not (0.0 <= m_val <= 1.0):
                errors.append(f"Empatía fuera de [0, 1] para ({eid}, {sid}): {m_val}")
        for tid, l_val in st.time_preferences.items():
            if tid not in inst.time_slots:
                errors.append(f"Preferencia horaria de {eid} apunta a franja inexistente {tid}")
            if not (-1.0 <= l_val <= 1.0):
                errors.append(f"Planificación L_e(t) fuera de [-1, 1] para ({eid}, {tid}): {l_val}")

    # Validar vínculos sociales G_soc
    for lk in inst.social_links:
        if lk.student_i not in inst.students or lk.student_j not in inst.students:
            errors.append(f"Vínculo social con estudiante inexistente: {lk}")
        if lk.student_i == lk.student_j:
            errors.append(f"Vínculo social reflexivo inválido: {lk}")
        if lk.course_id not in inst.courses:
            errors.append(f"Vínculo social con asignatura inexistente: {lk.course_id}")
        if not (0.0 <= lk.weight <= 1.0):
            errors.append(f"Peso social fuera de [0, 1]: {lk.weight}")

    return (len(errors) == 0, errors)


def save_instance(inst: Instance, folder: Path) -> None:
    """Guarda la instancia en archivos separados JSON y CSV (Sección 5.2)."""
    folder.mkdir(parents=True, exist_ok=True)

    # 1. Franjas horarias (CSV)
    with (folder / "time_slots.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "day", "day_index", "block_index", "label"])
        writer.writeheader()
        for ts in inst.time_slots.values():
            writer.writerow(ts.to_dict())

    # 2. Asignaturas (CSV)
    with (folder / "courses.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "credits"])
        writer.writeheader()
        for c in inst.courses.values():
            writer.writerow(c.to_dict())

    # 3. Vínculos sociales (CSV)
    with (folder / "social_links.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["student_i", "student_j", "course_id", "weight"])
        writer.writeheader()
        for lk in inst.social_links:
            writer.writerow(lk.to_dict())

    # 4. Ubicaciones y matriz de distancias (JSON)
    with (folder / "locations.json").open("w", encoding="utf-8") as f:
        json.dump(inst.locations.to_dict(), f, ensure_ascii=False, indent=2)

    # 5. Secciones (JSON)
    with (folder / "sections.json").open("w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in inst.sections.values()], f, ensure_ascii=False, indent=2)

    # 6. Estudiantes y preferencias (JSON)
    with (folder / "students.json").open("w", encoding="utf-8") as f:
        json.dump([st.to_dict() for st in inst.students.values()], f, ensure_ascii=False, indent=2)

    # 7. Metadatos de la instancia (JSON)
    meta = {
        "name": inst.name,
        "description": inst.description,
        "seed": inst.seed,
        "default_weights": inst.default_weights.to_dict(),
    }
    with (folder / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_instance(folder: Path) -> Instance:
    """Reconstruye en memoria E, A, S, T, G_U y G_soc desde los archivos JSON y CSV."""
    with (folder / "metadata.json").open("r", encoding="utf-8") as f:
        meta = json.load(f)

    time_slots: Dict[str, TimeSlot] = {}
    with (folder / "time_slots.csv").open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = TimeSlot(
                id=row["id"],
                day=row["day"],
                day_index=int(row["day_index"]),
                block_index=int(row["block_index"]),
                label=row["label"],
            )
            time_slots[ts.id] = ts

    courses: Dict[str, Course] = {}
    with (folder / "courses.csv").open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = Course(id=row["id"], name=row["name"], credits=int(row["credits"]))
            courses[c.id] = c

    social_links: List[SocialLink] = []
    with (folder / "social_links.csv").open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            social_links.append(
                SocialLink(
                    student_i=row["student_i"],
                    student_j=row["student_j"],
                    course_id=row["course_id"],
                    weight=float(row["weight"]),
                )
            )

    with (folder / "locations.json").open("r", encoding="utf-8") as f:
        loc_data = json.load(f)
    buildings = {b["id"]: Building(**b) for b in loc_data["buildings"]}
    locations = LocationGraph(buildings=buildings, distances=loc_data["distances"])

    with (folder / "sections.json").open("r", encoding="utf-8") as f:
        sec_list = json.load(f)
    sections = {
        s["id"]: Section(
            id=s["id"],
            course_id=s["course_id"],
            capacity=int(s["capacity"]),
            schedule=tuple(s["schedule"]),
            rooms=dict(s["rooms"]),
            professor=s.get("professor", "Docente PUJ"),
        )
        for s in sec_list
    }

    with (folder / "students.json").open("r", encoding="utf-8") as f:
        st_list = json.load(f)
    students = {
        st["id"]: Student(
            id=st["id"],
            name=st["name"],
            requested_courses=list(st["requested_courses"]),
            priorities={k: float(v) for k, v in st["priorities"].items()},
            empathy={k: float(v) for k, v in st["empathy"].items()},
            time_preferences={k: float(v) for k, v in st["time_preferences"].items()},
        )
        for st in st_list
    }

    return Instance(
        name=meta["name"],
        description=meta["description"],
        seed=int(meta["seed"]),
        time_slots=time_slots,
        locations=locations,
        courses=courses,
        sections=sections,
        students=students,
        social_links=social_links,
        default_weights=Weights.from_dict(meta.get("default_weights", {})),
    )


def ensure_default_scenarios(data_root: Path) -> Dict[str, Path]:
    """Crea (si no existen) los 4 escenarios de prueba definidos en la Sección 5.3."""
    scenarios_spec = {
        "pequeno": dict(
            name="pequeno",
            description="Escenario pequeño (6 estudiantes, 5 materias, 12 secciones) — verificable manualmente y resoluble de forma exacta con Branch & Bound.",
            num_students=6,
            num_courses=5,
            sections_per_course=(2, 3),
            courses_per_student=(3, 4),
            capacity_range=(3, 5),
            social_density=0.45,
            num_buildings=5,
            include_saturday=False,
            blocks_per_day=5,
            seed=101,
            stress_conflicts=False,
        ),
        "intermedio": dict(
            name="intermedio",
            description="Escenario intermedio (30 estudiantes, 12 materias, ~36 secciones) — carga representativa de departamento.",
            num_students=30,
            num_courses=12,
            sections_per_course=(2, 4),
            courses_per_student=(4, 5),
            capacity_range=(10, 18),
            social_density=0.22,
            num_buildings=7,
            include_saturday=True,
            blocks_per_day=6,
            seed=202,
            stress_conflicts=False,
        ),
        "grande": dict(
            name="grande",
            description="Escenario grande (120 estudiantes, 25 materias, ~85 secciones) — prueba de escalabilidad y tiempo de ejecución.",
            num_students=120,
            num_courses=25,
            sections_per_course=(3, 4),
            courses_per_student=(4, 6),
            capacity_range=(20, 35),
            social_density=0.10,
            num_buildings=8,
            include_saturday=True,
            blocks_per_day=6,
            seed=303,
            stress_conflicts=False,
        ),
        "extremo_conflictos": dict(
            name="extremo_conflictos",
            description="Escenario extremo (18 estudiantes, 8 materias, cupos muy reducidos y alta congestión horaria) — evalúa imposibilidad parcial y respeto estricto de restricciones.",
            num_students=18,
            num_courses=8,
            sections_per_course=(2, 2),
            courses_per_student=(5, 6),
            capacity_range=(4, 7),
            social_density=0.35,
            num_buildings=8,
            include_saturday=False,
            blocks_per_day=4,
            seed=404,
            stress_conflicts=True,
        ),
    }

    paths: Dict[str, Path] = {}
    for key, kwargs in scenarios_spec.items():
        folder = data_root / key
        if not (folder / "metadata.json").exists():
            inst = generate_instance(**kwargs)
            ok, errs = validate_instance_consistency(inst)
            if not ok:
                raise ValueError(f"Instancia {key} inconsistente: {errs}")
            save_instance(inst, folder)
        paths[key] = folder
    return paths
