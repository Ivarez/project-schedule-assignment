"""Módulo Validador y Evaluador Independiente (Secciones 2.3, 2.4 y 4.2).

Actúa como juez objetivo: recibe cualquier instancia y cualquier matriz/asignación X,
comprueba las 3 restricciones obligatorias y calcula Z(X) con desglose completo.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .models import Assignment, EvaluationResult, Instance, Weights


def assignment_to_binary_matrix(inst: Instance, assignment: Assignment) -> Tuple[List[str], List[str], List[List[int]]]:
    """Convierte la asignación en la matriz binaria explícita X de dimensiones |E| x |S|."""
    eids = sorted(inst.students.keys())
    sids = sorted(inst.sections.keys())
    matrix: List[List[int]] = []
    for eid in eids:
        assigned = assignment.get(eid, set())
        matrix.append([1 if sid in assigned else 0 for sid in sids])
    return eids, sids, matrix


def evaluate_assignment(
    inst: Instance,
    assignment: Assignment,
    weights: Weights | None = None,
) -> EvaluationResult:
    """Valida las 3 restricciones duras y evalúa la función objetivo Z(X)."""
    w = weights if weights is not None else inst.default_weights
    violations: List[str] = []

    section_occupancy: Dict[str, int] = {sid: 0 for sid in inst.sections}
    student_details: Dict[str, dict] = {}

    raw_priority = 0.0
    raw_empathy = 0.0
    raw_planning = 0.0
    raw_social = 0.0
    raw_logistics = 0.0

    assigned_count = 0
    requested_count = sum(len(st.requested_courses) for st in inst.students.values())

    # Índice de quién está inscrito en cada sección para evaluar cupos y criterio social
    students_in_section: Dict[str, Set[str]] = {sid: set() for sid in inst.sections}

    # Verificar claves desconocidas
    for eid in assignment:
        if eid not in inst.students:
            violations.append(f"Estudiante desconocido en asignación X: {eid}")

    # 1. Restricciones por estudiante (No repetición / solicitadas + Compatibilidad horaria)
    for eid, st in inst.students.items():
        assigned_sids = assignment.get(eid, set())
        req_set = set(st.requested_courses)
        courses_taken: Dict[str, List[str]] = {}
        slots_taken: Dict[str, List[str]] = {}  # tid -> list of (sid, building_id)
        slot_to_sec: Dict[str, str] = {}

        st_priority = 0.0
        st_empathy = 0.0
        st_planning = 0.0
        st_logistics = 0.0
        st_transitions: List[dict] = []

        for sid in sorted(assigned_sids):
            if sid not in inst.sections:
                violations.append(f"Estudiante {eid} asignado a sección inexistente {sid}")
                continue

            sec = inst.sections[sid]
            section_occupancy[sid] += 1
            students_in_section[sid].add(eid)
            assigned_count += 1

            # Restricción 1a: Solo materias solicitadas
            if sec.course_id not in req_set:
                violations.append(
                    f"[No solicitada] {eid} inscrito en {sid} ({sec.course_id}), que no está en A_e."
                )

            # Restricción 1b: Máximo una sección por asignatura
            courses_taken.setdefault(sec.course_id, []).append(sid)

            # Restricción 2: Compatibilidad de horarios
            for tid in sec.schedule:
                slots_taken.setdefault(tid, []).append(sid)
                slot_to_sec[tid] = sid

            # Aportes individuales a Z(X)
            p_val = st.priorities.get(sec.course_id, 0.0)
            m_val = st.empathy.get(sid, 0.0)
            l_sum = sum(st.time_preferences.get(tid, 0.0) for tid in sec.schedule)

            st_priority += p_val
            st_empathy += m_val
            st_planning += l_sum

        for cid, s_list in courses_taken.items():
            if len(s_list) > 1:
                violations.append(
                    f"[Repetición] {eid} tiene {len(s_list)} secciones de {cid}: {s_list}"
                )

        for tid, s_list in slots_taken.items():
            if len(s_list) > 1:
                violations.append(
                    f"[Cruce horario] {eid} tiene cruce en {tid} entre secciones {s_list}"
                )

        # Criterio 5: Logística — desplazamientos entre franjas consecutivas el mismo día
        occupied_tids = list(slot_to_sec.keys())
        for tx in occupied_tids:
            for ty in occupied_tids:
                if tx != ty and inst.consec(tx, ty) == 1:
                    s1 = slot_to_sec[tx]
                    s2 = slot_to_sec[ty]
                    u1 = inst.sections[s1].rooms[tx]
                    u2 = inst.sections[s2].rooms[ty]
                    dist = inst.locations.distance(u1, u2)
                    st_logistics += dist
                    if dist > 0:
                        st_transitions.append({
                            "from_slot": tx,
                            "to_slot": ty,
                            "from_section": s1,
                            "to_section": s2,
                            "from_building": u1,
                            "to_building": u2,
                            "distance": dist,
                        })

        raw_priority += st_priority
        raw_empathy += st_empathy
        raw_planning += st_planning
        raw_logistics += st_logistics

        student_details[eid] = {
            "assigned_sections": sorted(list(assigned_sids)),
            "assigned_courses": sorted(list(courses_taken.keys())),
            "unassigned_courses": sorted(list(req_set - set(courses_taken.keys()))),
            "priority": round(st_priority, 3),
            "empathy": round(st_empathy, 3),
            "planning": round(st_planning, 3),
            "logistics": round(st_logistics, 3),
            "social": 0.0,
            "social_friends": [],
            "transitions": st_transitions,
        }

    # 3. Restricción 3: Respeto del límite de cupos
    for sid, occ in section_occupancy.items():
        cap = inst.sections[sid].capacity
        if occ > cap:
            violations.append(
                f"[Cupo excedido] Sección {sid} tiene {occ} estudiantes (cupo máximo = {cap})."
            )

    # 4. Criterio 4: Social y Académico G_soc
    social_matches = 0
    for lk in inst.social_links:
        matched_sid = None
        for sid in inst.sections_by_course.get(lk.course_id, []):
            if lk.student_i in students_in_section[sid] and lk.student_j in students_in_section[sid]:
                matched_sid = sid
                break
        if matched_sid is not None:
            raw_social += lk.weight
            social_matches += 1
            student_details[lk.student_i]["social"] = round(
                student_details[lk.student_i]["social"] + lk.weight, 3
            )
            student_details[lk.student_j]["social"] = round(
                student_details[lk.student_j]["social"] + lk.weight, 3
            )
            student_details[lk.student_i]["social_friends"].append({
                "friend_id": lk.student_j,
                "friend_name": inst.students[lk.student_j].name,
                "course_id": lk.course_id,
                "section_id": matched_sid,
                "weight": lk.weight,
            })
            student_details[lk.student_j]["social_friends"].append({
                "friend_id": lk.student_i,
                "friend_name": inst.students[lk.student_i].name,
                "course_id": lk.course_id,
                "section_id": matched_sid,
                "weight": lk.weight,
            })

    weighted_priority = w.w1_priority * raw_priority
    weighted_empathy = w.w2_empathy * raw_empathy
    weighted_planning = w.w3_planning * raw_planning
    weighted_social = w.w4_social * raw_social
    weighted_logistics = w.w5_logistics * raw_logistics

    z_score = (
        weighted_priority
        + weighted_empathy
        + weighted_planning
        + weighted_social
        - weighted_logistics
    )

    assignment_rate = (assigned_count / requested_count) if requested_count > 0 else 1.0

    return EvaluationResult(
        valid=(len(violations) == 0),
        violations=violations,
        z_score=z_score,
        raw_priority=raw_priority,
        raw_empathy=raw_empathy,
        raw_planning=raw_planning,
        raw_social=raw_social,
        raw_logistics=raw_logistics,
        weighted_priority=weighted_priority,
        weighted_empathy=weighted_empathy,
        weighted_planning=weighted_planning,
        weighted_social=weighted_social,
        weighted_logistics=weighted_logistics,
        assigned_count=assigned_count,
        requested_count=requested_count,
        assignment_rate=assignment_rate,
        social_matches=social_matches,
        total_social_links=len(inst.social_links),
        section_occupancy=section_occupancy,
        student_details=student_details,
    )
