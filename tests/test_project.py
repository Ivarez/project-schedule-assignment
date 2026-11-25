"""Pruebas unitarias y de integración del sistema de Asignación de Horarios."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.data_manager import (
    generate_instance,
    load_instance,
    save_instance,
    validate_instance_consistency,
)
from src.evaluator import assignment_to_binary_matrix, evaluate_assignment
from src.models import (
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
from src.solver import (
    _ScheduleState,
    solve_exact_branch_and_bound,
    solve_greedy,
    solve_hybrid_local_search,
)


def _build_hand_instance() -> Instance:
    """Instancia pequeña calculada a mano para verificar fórmulas y restricciones."""
    t1 = TimeSlot("T01", "Lunes", 0, 0, "07:00-09:00")
    t2 = TimeSlot("T02", "Lunes", 0, 1, "09:00-11:00")
    t3 = TimeSlot("T03", "Martes", 1, 0, "07:00-09:00")

    b1 = Building("U1", "Maldonado", "Maldonado", 10, 10)
    b2 = Building("U2", "Barón", "Barón", 50, 50)
    loc = LocationGraph(
        buildings={"U1": b1, "U2": b2},
        distances={"U1": {"U1": 0.0, "U2": 5.0}, "U2": {"U1": 5.0, "U2": 0.0}},
    )

    courses = {
        "A01": Course("A01", "Algoritmos", 3),
        "A02": Course("A02", "Bases de Datos", 3),
    }
    sections = {
        "S01": Section("S01", "A01", capacity=2, schedule=("T01",), rooms={"T01": "U1"}),
        "S02": Section("S02", "A01", capacity=1, schedule=("T02",), rooms={"T02": "U2"}),
        "S03": Section("S03", "A02", capacity=2, schedule=("T02",), rooms={"T02": "U2"}),
        "S04": Section("S04", "A02", capacity=2, schedule=("T01",), rooms={"T01": "U1"}),
    }
    students = {
        "E01": Student(
            id="E01",
            name="Iván",
            requested_courses=["A01", "A02"],
            priorities={"A01": 10.0, "A02": 8.0},
            empathy={"S01": 0.8, "S02": 0.2, "S03": 0.9, "S04": 0.5},
            time_preferences={"T01": 1.0, "T02": 1.0, "T03": 0.0},
        ),
        "E02": Student(
            id="E02",
            name="Nassin",
            requested_courses=["A01"],
            priorities={"A01": 9.0},
            empathy={"S01": 1.0, "S02": 0.4},
            time_preferences={"T01": 1.0, "T02": -1.0, "T03": 0.0},
        ),
    }
    social = [SocialLink("E01", "E02", "A01", 0.8)]
    return Instance(
        name="hand_test",
        description="Prueba manual",
        seed=1,
        time_slots={"T01": t1, "T02": t2, "T03": t3},
        locations=loc,
        courses=courses,
        sections=sections,
        students=students,
        social_links=social,
        default_weights=Weights(2.0, 3.0, 1.0, 4.0, 0.5),
    )


class TestSchedulingProject(unittest.TestCase):
    def test_hand_calculated_objective_and_matrix(self) -> None:
        inst = _build_hand_instance()
        ok, errs = validate_instance_consistency(inst)
        self.assertTrue(ok, f"Errores inesperados: {errs}")

        # Asignación válida: E01 -> {S01 (T01, U1), S03 (T02, U2)}, E02 -> {S01 (T01, U1)}
        assignment = {"E01": {"S01", "S03"}, "E02": {"S01"}}
        ev = evaluate_assignment(inst, assignment)
        self.assertTrue(ev.valid)
        # Cálculo manual exacto:
        # Prioridad = (10 + 8) + 9 = 27 -> *2 = 54
        # Empatía = (0.8 + 0.9) + 1.0 = 2.7 -> *3 = 8.1
        # Planificación = (1 + 1) + 1 = 3.0 -> *1 = 3.0
        # Social = 0.8 (coinciden en S01) -> *4 = 3.2
        # Logística = E01 pasa de T01(U1) a T02(U2) consec=1 => D(U1,U2)=5.0 -> *0.5 = 2.5
        # Z = 54 + 8.1 + 3.0 + 3.2 - 2.5 = 65.8
        self.assertAlmostEqual(ev.raw_priority, 27.0, places=5)
        self.assertAlmostEqual(ev.raw_empathy, 2.7, places=5)
        self.assertAlmostEqual(ev.raw_planning, 3.0, places=5)
        self.assertAlmostEqual(ev.raw_social, 0.8, places=5)
        self.assertAlmostEqual(ev.raw_logistics, 5.0, places=5)
        self.assertAlmostEqual(ev.z_score, 65.8, places=5)

        eids, sids, mat = assignment_to_binary_matrix(inst, assignment)
        self.assertEqual(len(eids), 2)
        self.assertEqual(len(sids), 4)
        self.assertEqual(sum(mat[0]), 2)
        self.assertEqual(sum(mat[1]), 1)

    def test_evaluator_catches_all_three_hard_constraints(self) -> None:
        inst = _build_hand_instance()

        # 1. Repetición de asignatura (E01 toma S01 y S02, ambas de A01)
        ev_dup = evaluate_assignment(inst, {"E01": {"S01", "S02"}, "E02": set()})
        self.assertFalse(ev_dup.valid)
        self.assertTrue(any("Repetición" in v for v in ev_dup.violations))

        # 1b. Asignatura no solicitada (E02 toma S03 de A02, que no está en A_E02)
        ev_unreq = evaluate_assignment(inst, {"E01": set(), "E02": {"S03"}})
        self.assertFalse(ev_unreq.valid)
        self.assertTrue(any("No solicitada" in v for v in ev_unreq.violations))

        # 2. Cruce horario (E01 toma S01 y S04, ambas en T01)
        ev_clash = evaluate_assignment(inst, {"E01": {"S01", "S04"}, "E02": set()})
        self.assertFalse(ev_clash.valid)
        self.assertTrue(any("Cruce horario" in v for v in ev_clash.violations))

        # 3. Exceso de cupo (S02 tiene cupo=1, pero se asignan E01 y E02)
        ev_cap = evaluate_assignment(inst, {"E01": {"S02"}, "E02": {"S02"}})
        self.assertFalse(ev_cap.valid)
        self.assertTrue(any("Cupo excedido" in v for v in ev_cap.violations))

    def test_incremental_state_matches_full_evaluator(self) -> None:
        inst = generate_instance(
            name="inc_check",
            description="Verificación delta",
            num_students=8,
            num_courses=6,
            sections_per_course=(2, 3),
            courses_per_student=(3, 4),
            capacity_range=(3, 6),
            seed=55,
        )
        st = _ScheduleState(inst, inst.default_weights)
        for eid, student in inst.students.items():
            for cid in student.requested_courses:
                for sid in inst.sections_by_course[cid]:
                    if st.can_add(eid, sid):
                        st.add(eid, sid)
                        break
        ev_full = evaluate_assignment(inst, st.assignment, inst.default_weights)
        self.assertTrue(ev_full.valid)
        self.assertAlmostEqual(st.z_score, ev_full.z_score, places=5)

    def test_persistence_json_csv_roundtrip(self) -> None:
        inst = generate_instance(
            name="rt_test",
            description="Roundtrip",
            num_students=6,
            num_courses=5,
            sections_per_course=(2, 2),
            courses_per_student=(3, 3),
            capacity_range=(3, 5),
            seed=99,
        )
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "rt_test"
            save_instance(inst, folder)
            loaded = load_instance(folder)
            ok, errs = validate_instance_consistency(loaded)
            self.assertTrue(ok, f"Errores tras recarga: {errs}")
            self.assertEqual(len(loaded.students), len(inst.students))
            self.assertEqual(len(loaded.sections), len(inst.sections))
            self.assertEqual(len(loaded.social_links), len(inst.social_links))

    def test_solvers_validity_and_quality_ordering(self) -> None:
        inst = generate_instance(
            name="small_opt",
            description="Comparativa de calidad",
            num_students=6,
            num_courses=5,
            sections_per_course=(2, 3),
            courses_per_student=(3, 4),
            capacity_range=(3, 5),
            social_density=0.45,
            include_saturday=False,
            blocks_per_day=5,
            seed=101,
        )
        r_greedy = solve_greedy(inst)
        r_hybrid = solve_hybrid_local_search(inst)
        r_exact = solve_exact_branch_and_bound(inst, time_limit_sec=3.0)

        for r in (r_greedy, r_hybrid, r_exact):
            self.assertTrue(r.evaluation.valid, f"{r.algorithm} violó restricciones: {r.evaluation.violations}")

        self.assertGreaterEqual(r_hybrid.evaluation.z_score + 1e-6, r_greedy.evaluation.z_score)
        self.assertGreaterEqual(r_exact.evaluation.z_score + 1e-6, r_hybrid.evaluation.z_score)


if __name__ == "__main__":
    unittest.main()
