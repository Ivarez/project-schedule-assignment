"""Módulo de Asignación de Horarios (Sección 4.2 y Sección 3 de la Entrega 1).

Implementa tres estrategias complementarias sobre la misma formalización:
1. Voraz Constructivo (`solve_greedy`):
   Ordena solicitudes por prioridad académica + escasez de secciones y elige en
   cada paso la sección factible con mayor ganancia marginal exacta ΔZ(e, s).
   Complejidad polinomial: O(R log R + R · q̄ · (t̄ + ḡ)).

2. Híbrido: Voraz Multi-Criterio + Búsqueda Local Multi-Vecindario (`solve_hybrid_local_search`):
   Fase 1: Genera semillas factibles (prioridad pura, coordinación social de pares G_soc
   y escasez) y selecciona la mejor.
   Fase 2: Refina Z(X) respetando las 3 restricciones duras con 3 operadores de vecindad:
   - Reasignación (Relocate): mover un estudiante a otra sección compatible con cupo.
   - Intercambio (Swap): intercambiar dos estudiantes entre secciones llenas de la misma materia.
   - Inserción / Reemplazo: inscribir materias pendientes que se liberaron.

3. Exacto: Backtracking con Ramificación y Poda (`solve_exact_branch_and_bound`):
   Explora el árbol de asignaciones válidas con poda por conflictos (bitmasks O(1)),
   poda por cupos y poda por cota superior admisible (Upper Bound) sobre Z(X).
   Garantiza el óptimo global Z* en instancias pequeñas para medir la brecha de optimalidad
   (optimality gap) de las heurísticas.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Set, Tuple

from .evaluator import evaluate_assignment
from .models import Assignment, Instance, SolverResult, Weights


class _ScheduleState:
    """Estado mutable optimizado para evaluación incremental exacta de ΔZ en O(t̄ + ḡ)."""

    def __init__(self, inst: Instance, weights: Weights) -> None:
        self.inst = inst
        self.w = weights
        self.assignment: Assignment = {eid: set() for eid in inst.students}
        self.course_to_sec: Dict[str, Dict[str, str]] = {eid: {} for eid in inst.students}
        self.student_mask: Dict[str, int] = {eid: 0 for eid in inst.students}
        # slot_to_sec[eid][tid] = sid
        self.slot_to_sec: Dict[str, Dict[str, str]] = {eid: {} for eid in inst.students}
        self.rem_cap: Dict[str, int] = {sid: sec.capacity for sid, sec in inst.sections.items()}
        self.sec_students: Dict[str, Set[str]] = {sid: set() for sid in inst.sections}

        # Índice rápido de vínculos sociales: social_adj[(eid, cid)] -> list[(friend_id, weight)]
        self.social_adj: Dict[Tuple[str, str], List[Tuple[str, float]]] = {}
        for lk in inst.social_links:
            self.social_adj.setdefault((lk.student_i, lk.course_id), []).append((lk.student_j, lk.weight))
            self.social_adj.setdefault((lk.student_j, lk.course_id), []).append((lk.student_i, lk.weight))

        # Índice rápido de franjas previas/siguientes en el mismo día
        self.prev_slot: Dict[str, Optional[str]] = {tid: None for tid in inst.time_slots}
        self.next_slot: Dict[str, Optional[str]] = {tid: None for tid in inst.time_slots}
        for tx, ty in inst.consec_pairs:
            self.next_slot[tx] = ty
            self.prev_slot[ty] = tx

        # Precalcular aporte base individual (prioridad + empatía + planificación) por (eid, sid)
        self.base_contrib: Dict[Tuple[str, str], float] = {}
        for eid, st in inst.students.items():
            for cid in st.requested_courses:
                p_term = weights.w1_priority * st.priorities.get(cid, 0.0)
                for sid in inst.sections_by_course.get(cid, []):
                    sec = inst.sections[sid]
                    m_term = weights.w2_empathy * st.empathy.get(sid, 0.0)
                    l_term = weights.w3_planning * sum(
                        st.time_preferences.get(tid, 0.0) for tid in sec.schedule
                    )
                    self.base_contrib[(eid, sid)] = p_term + m_term + l_term

        self.z_score: float = 0.0

    def can_add(self, eid: str, sid: str) -> bool:
        """Verifica en O(1) las 3 restricciones duras antes de agregar (eid, sid)."""
        sec = self.inst.sections[sid]
        if self.rem_cap[sid] <= 0:
            return False
        if sec.course_id in self.course_to_sec[eid]:
            return False
        if (self.student_mask[eid] & self.inst.section_mask[sid]) != 0:
            return False
        return True

    def delta_add(self, eid: str, sid: str) -> float:
        """Calcula el cambio exacto ΔZ al inscribir al estudiante eid en la sección sid."""
        sec = self.inst.sections[sid]
        delta = self.base_contrib[(eid, sid)]

        # Aporte social con amigos ya inscritos en la misma sección
        for friend_id, w_ij in self.social_adj.get((eid, sec.course_id), ()):
            if friend_id in self.sec_students[sid]:
                delta += self.w.w4_social * w_ij

        # Costo logístico con clases consecutivas ya asignadas al estudiante
        # (y posibles transiciones internas si la sección tuviera 2 bloques seguidos el mismo día)
        occupied = self.slot_to_sec[eid]
        sec_slots_set = set(sec.schedule)
        log_cost = 0.0
        for tid in sec.schedule:
            prev_t = self.prev_slot[tid]
            if prev_t is not None and prev_t in occupied:
                s_prev = occupied[prev_t]
                u_prev = self.inst.sections[s_prev].rooms[prev_t]
                u_cur = sec.rooms[tid]
                log_cost += self.inst.locations.distance(u_prev, u_cur)
            next_t = self.next_slot[tid]
            if next_t is not None:
                if next_t in occupied:
                    s_next = occupied[next_t]
                    u_cur = sec.rooms[tid]
                    u_next = self.inst.sections[s_next].rooms[next_t]
                    log_cost += self.inst.locations.distance(u_cur, u_next)
                elif next_t in sec_slots_set:
                    log_cost += self.inst.locations.distance(sec.rooms[tid], sec.rooms[next_t])

        return delta - self.w.w5_logistics * log_cost

    def add(self, eid: str, sid: str) -> float:
        """Agrega (eid, sid) al estado y actualiza Z en O(t̄ + ḡ)."""
        d = self.delta_add(eid, sid)
        sec = self.inst.sections[sid]
        self.assignment[eid].add(sid)
        self.course_to_sec[eid][sec.course_id] = sid
        self.student_mask[eid] |= self.inst.section_mask[sid]
        for tid in sec.schedule:
            self.slot_to_sec[eid][tid] = sid
        self.rem_cap[sid] -= 1
        self.sec_students[sid].add(eid)
        self.z_score += d
        return d

    def remove(self, eid: str, sid: str) -> float:
        """Remueve (eid, sid) del estado y retorna el ΔZ (negativo del delta_add)."""
        sec = self.inst.sections[sid]
        self.assignment[eid].remove(sid)
        del self.course_to_sec[eid][sec.course_id]
        self.student_mask[eid] ^= self.inst.section_mask[sid]
        for tid in sec.schedule:
            del self.slot_to_sec[eid][tid]
        self.rem_cap[sid] += 1
        self.sec_students[sid].remove(eid)
        # El costo removido es exactamente delta_add si se volviera a agregar ahora
        removed_gain = self.delta_add(eid, sid)
        self.z_score -= removed_gain
        return -removed_gain

    def clone_assignment(self) -> Assignment:
        return {eid: set(secs) for eid, secs in self.assignment.items()}


def _run_greedy_order(
    inst: Instance,
    weights: Weights,
    mode: str = "priority",
) -> Tuple[_ScheduleState, int]:
    """Ejecuta construcción voraz según distintos criterios de ordenamiento.

    Retorna (estado_final, candidatas_evaluadas).
    """
    state = _ScheduleState(inst, weights)
    evals = 0

    # Modo social_first: primero intenta asignar pares con fuerte vínculo G_soc juntos
    if mode == "social_first":
        sorted_links = sorted(inst.social_links, key=lambda lk: lk.weight, reverse=True)
        for lk in sorted_links:
            ei, ej, cid = lk.student_i, lk.student_j, lk.course_id
            if cid not in inst.students[ei].priorities or cid not in inst.students[ej].priorities:
                continue
            if cid in state.course_to_sec[ei] or cid in state.course_to_sec[ej]:
                continue
            best_sid = None
            best_gain = 0.0
            for sid in inst.sections_by_course.get(cid, []):
                evals += 1
                if state.rem_cap[sid] < 2:
                    continue
                if (state.student_mask[ei] & inst.section_mask[sid]) != 0:
                    continue
                if (state.student_mask[ej] & inst.section_mask[sid]) != 0:
                    continue
                # Evaluar ganancia conjunta exacta
                g_i = state.delta_add(ei, sid)
                state.add(ei, sid)
                g_j = state.delta_add(ej, sid)
                state.remove(ei, sid)
                total_g = g_i + g_j
                if total_g > best_gain:
                    best_gain = total_g
                    best_sid = sid
            if best_sid is not None:
                state.add(ei, best_sid)
                state.add(ej, best_sid)

    # Construir lista de solicitudes (eid, cid)
    requests: List[Tuple[str, str]] = []
    for eid, st in inst.students.items():
        for cid in st.requested_courses:
            if cid not in state.course_to_sec[eid]:
                requests.append((eid, cid))

    # Calcular demanda por materia para heurística de escasez (Most Constrained Variable)
    demand: Dict[str, int] = {cid: 0 for cid in inst.courses}
    for _, cid in requests:
        demand[cid] += 1
    total_cap: Dict[str, int] = {
        cid: sum(inst.sections[sid].capacity for sid in inst.sections_by_course.get(cid, []))
        for cid in inst.courses
    }

    if mode == "scarcity":
        requests.sort(
            key=lambda rc: (
                -(demand[rc[1]] / max(1, total_cap[rc[1]])),
                -inst.students[rc[0]].priorities[rc[1]],
                len(inst.sections_by_course.get(rc[1], [])),
                rc[0],
                rc[1],
            )
        )
    else:
        # Ordenamiento principal: prioridad académica descendente, luego menos secciones disponibles, luego grado social
        requests.sort(
            key=lambda rc: (
                -inst.students[rc[0]].priorities[rc[1]],
                len(inst.sections_by_course.get(rc[1], [])),
                -len(state.social_adj.get(rc, ())),
                rc[0],
                rc[1],
            )
        )

    for eid, cid in requests:
        if cid in state.course_to_sec[eid]:
            continue
        best_sid = None
        best_delta = 0.0  # Solo inscribir si aporta beneficio neto positivo
        for sid in inst.sections_by_course.get(cid, []):
            evals += 1
            if state.can_add(eid, sid):
                d = state.delta_add(eid, sid)
                if d > best_delta:
                    best_delta = d
                    best_sid = sid
        if best_sid is not None:
            state.add(eid, best_sid)

    return state, evals


def solve_greedy(inst: Instance, weights: Weights | None = None) -> SolverResult:
    """Algoritmo 1: Heurística Voraz Constructiva por prioridad y ganancia marginal ΔZ."""
    w = weights if weights is not None else inst.default_weights
    t0 = time.perf_counter()
    state, evals = _run_greedy_order(inst, w, mode="priority")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assignment = state.clone_assignment()
    evaluation = evaluate_assignment(inst, assignment, w)
    return SolverResult(
        algorithm="Voraz Constructivo",
        assignment=assignment,
        evaluation=evaluation,
        runtime_ms=elapsed_ms,
        metadata={
            "strategy": "greedy",
            "complexity": "O(R log R + R · q̄ · (t̄ + ḡ))",
            "evaluations": evals,
            "guaranteed_optimal": False,
        },
    )


def solve_hybrid_local_search(
    inst: Instance,
    weights: Weights | None = None,
    max_iterations: int = 80,
) -> SolverResult:
    """Algoritmo 2 (Principal): Voraz Multi-Criterio + Búsqueda Local Multi-Vecindario."""
    w = weights if weights is not None else inst.default_weights
    t0 = time.perf_counter()

    # Fase 1: Evaluar 3 semillas constructivas rápidas y elegir la mejor
    seed_runs = [
        ("priority", *_run_greedy_order(inst, w, mode="priority")),
        ("social_first", *_run_greedy_order(inst, w, mode="social_first")),
        ("scarcity", *_run_greedy_order(inst, w, mode="scarcity")),
    ]
    seed_evals = sum(item[2] for item in seed_runs)
    best_seed_name, state, _ = max(seed_runs, key=lambda item: item[1].z_score)
    initial_z = state.z_score

    # Fase 2: Búsqueda Local con 3 operadores de vecindad (Relocate, Insert, Swap)
    relocates = 0
    swaps = 0
    inserts = 0
    neighbors_evaluated = seed_evals
    iterations = 0
    convergence_history: List[float] = [round(initial_z, 3)]
    eps = 1e-9

    eids = sorted(inst.students.keys())

    while iterations < max_iterations:
        iterations += 1
        improved = False

        # Operador 1: Reasignación (Relocate) — mover estudiante a otra sección con cupo
        for eid in eids:
            for cid, s_old in list(state.course_to_sec[eid].items()):
                alternatives = inst.sections_by_course.get(cid, [])
                if len(alternatives) <= 1:
                    continue
                z_before = state.z_score
                state.remove(eid, s_old)
                best_s = s_old
                best_d = state.delta_add(eid, s_old)
                for s_new in alternatives:
                    if s_new == s_old:
                        continue
                    neighbors_evaluated += 1
                    if state.can_add(eid, s_new):
                        d_new = state.delta_add(eid, s_new)
                        if d_new > best_d + eps:
                            best_d = d_new
                            best_s = s_new
                state.add(eid, best_s)
                if best_s != s_old and state.z_score > z_before + eps:
                    relocates += 1
                    improved = True

        # Operador 2: Inserción de materias aún no asignadas (aprovechando cupos/huecos liberados)
        for eid in eids:
            st = inst.students[eid]
            unassigned = [c for c in st.requested_courses if c not in state.course_to_sec[eid]]
            if not unassigned:
                continue
            unassigned.sort(key=lambda c: -st.priorities[c])
            for cid in unassigned:
                best_s = None
                best_d = eps
                for sid in inst.sections_by_course.get(cid, []):
                    neighbors_evaluated += 1
                    if state.can_add(eid, sid):
                        d = state.delta_add(eid, sid)
                        if d > best_d:
                            best_d = d
                            best_s = sid
                if best_s is not None:
                    state.add(eid, best_s)
                    inserts += 1
                    improved = True

        # Operador 3: Intercambio (Swap) entre dos estudiantes en secciones distintas de la misma materia
        for cid, s_list in inst.sections_by_course.items():
            if len(s_list) < 2:
                continue
            for idx_a in range(len(s_list)):
                sa = s_list[idx_a]
                if not state.sec_students[sa]:
                    continue
                for idx_b in range(idx_a + 1, len(s_list)):
                    sb = s_list[idx_b]
                    if not state.sec_students[sb]:
                        continue
                    studs_a = list(state.sec_students[sa])
                    studs_b = list(state.sec_students[sb])
                    mask_a = inst.section_mask[sa]
                    mask_b = inst.section_mask[sb]
                    swapped_pair = False
                    for e1 in studs_a:
                        if e1 not in state.sec_students[sa]:
                            continue
                        if ((state.student_mask[e1] ^ mask_a) & mask_b) != 0:
                            continue
                        for e2 in studs_b:
                            if e2 not in state.sec_students[sb]:
                                continue
                            neighbors_evaluated += 1
                            if ((state.student_mask[e2] ^ mask_b) & mask_a) != 0:
                                continue
                            z_before = state.z_score
                            state.remove(e1, sa)
                            state.remove(e2, sb)
                            state.add(e1, sb)
                            state.add(e2, sa)
                            if state.z_score > z_before + eps:
                                swaps += 1
                                improved = True
                                swapped_pair = True
                                break
                            state.remove(e1, sb)
                            state.remove(e2, sa)
                            state.add(e1, sa)
                            state.add(e2, sb)
                        if swapped_pair:
                            break

        convergence_history.append(round(state.z_score, 3))
        if not improved:
            break

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assignment = state.clone_assignment()
    evaluation = evaluate_assignment(inst, assignment, w)
    return SolverResult(
        algorithm="Híbrido (Voraz + Búsqueda Local)",
        assignment=assignment,
        evaluation=evaluation,
        runtime_ms=elapsed_ms,
        metadata={
            "strategy": "hybrid_local_search",
            "best_seed": best_seed_name,
            "initial_z": round(initial_z, 4),
            "improvement_z": round(evaluation.z_score - initial_z, 4),
            "iterations": iterations,
            "neighbors_evaluated": neighbors_evaluated,
            "moves": {"relocates": relocates, "swaps": swaps, "inserts": inserts},
            "convergence_history": convergence_history,
            "guaranteed_optimal": False,
        },
    )


def solve_exact_branch_and_bound(
    inst: Instance,
    weights: Weights | None = None,
    time_limit_sec: float = 2.5,
) -> SolverResult:
    """Algoritmo 3: Backtracking con Ramificación y Poda (Exacto para instancias pequeñas).

    Utiliza la solución del algoritmo híbrido como cota inferior inicial (incumbent)
    y poda ramas cuya cota superior admisible (Upper Bound) no supere la mejor solución actual.
    """
    w = weights if weights is not None else inst.default_weights
    t0 = time.perf_counter()

    # Cota inferior inicial (incumbent) usando el híbrido para podar agresivamente desde el inicio
    warm = solve_hybrid_local_search(inst, w, max_iterations=25)
    best_z = warm.evaluation.z_score
    best_assignment: Assignment = {eid: set(secs) for eid, secs in warm.assignment.items()}

    state = _ScheduleState(inst, w)

    # Decisiones ordenadas por mayor beneficio potencial (fail-first / best-first)
    decisions: List[Tuple[str, str]] = []
    for eid, st in inst.students.items():
        for cid in st.requested_courses:
            decisions.append((eid, cid))
    decisions.sort(
        key=lambda rc: (
            -inst.students[rc[0]].priorities[rc[1]],
            len(inst.sections_by_course.get(rc[1], [])),
            rc[0],
            rc[1],
        )
    )

    # Precalcular cota superior optimista individual por decisión (logística >= 0)
    # y cota superior de enlaces sociales aún no decididos
    n_dec = len(decisions)
    dec_index: Dict[Tuple[str, str], int] = {d: idx for idx, d in enumerate(decisions)}

    max_indiv: List[float] = []
    for eid, cid in decisions:
        best_base = 0.0
        for sid in inst.sections_by_course.get(cid, []):
            val = state.base_contrib[(eid, sid)]
            if val > best_base:
                best_base = val
        max_indiv.append(best_base)

    # Cada enlace social (ei, ej, cid) solo se cuenta cuando se decide el segundo de los dos
    social_at_idx: List[float] = [0.0] * n_dec
    for lk in inst.social_links:
        i1 = dec_index.get((lk.student_i, lk.course_id))
        i2 = dec_index.get((lk.student_j, lk.course_id))
        if i1 is not None and i2 is not None:
            later = max(i1, i2)
            social_at_idx[later] += w.w4_social * lk.weight

    # Suma de sufijos para consulta O(1) de la cota superior restante
    suffix_ub: List[float] = [0.0] * (n_dec + 1)
    for idx in range(n_dec - 1, -1, -1):
        suffix_ub[idx] = suffix_ub[idx + 1] + max_indiv[idx] + social_at_idx[idx]

    nodes_explored = 0
    pruned_bound = 0
    time_exceeded = False
    deadline = t0 + time_limit_sec
    eps = 1e-9

    def dfs(idx: int) -> None:
        nonlocal best_z, best_assignment, nodes_explored, pruned_bound, time_exceeded
        if time_exceeded:
            return
        nodes_explored += 1
        if (nodes_explored & 1023) == 0 and time.perf_counter() >= deadline:
            time_exceeded = True
            return

        # Poda por cota superior admisible (Upper Bound)
        if state.z_score + suffix_ub[idx] <= best_z + eps:
            pruned_bound += 1
            return

        if idx == n_dec:
            if state.z_score > best_z + eps:
                best_z = state.z_score
                best_assignment = state.clone_assignment()
            return

        eid, cid = decisions[idx]
        # Ordenar secciones candidatas factibles por ganancia marginal descendente
        feasible: List[Tuple[float, str]] = []
        for sid in inst.sections_by_course.get(cid, []):
            if state.can_add(eid, sid):
                feasible.append((state.delta_add(eid, sid), sid))
        feasible.sort(key=lambda x: -x[0])

        for _, sid in feasible:
            state.add(eid, sid)
            dfs(idx + 1)
            state.remove(eid, sid)
            if time_exceeded:
                return

        # Rama de no asignar la materia (siempre válida según restricción ≤ 1)
        dfs(idx + 1)

    dfs(0)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    evaluation = evaluate_assignment(inst, best_assignment, w)
    return SolverResult(
        algorithm="Exacto (Backtracking + Branch & Bound)",
        assignment=best_assignment,
        evaluation=evaluation,
        runtime_ms=elapsed_ms,
        metadata={
            "strategy": "exact_bnb",
            "optimal": not time_exceeded,
            "time_limit_reached": time_exceeded,
            "nodes_explored": nodes_explored,
            "pruned_by_bound": pruned_bound,
            "guaranteed_optimal": not time_exceeded,
        },
    )


def run_all_solvers(
    inst: Instance,
    weights: Weights | None = None,
    include_exact: bool = True,
    exact_time_limit: float = 2.0,
) -> Dict[str, SolverResult]:
    """Ejecuta todos los algoritmos configurados y retorna un diccionario comparativo."""
    results: Dict[str, SolverResult] = {
        "greedy": solve_greedy(inst, weights),
        "hybrid": solve_hybrid_local_search(inst, weights),
    }
    if include_exact:
        results["exact"] = solve_exact_branch_and_bound(inst, weights, time_limit_sec=exact_time_limit)
    return results
