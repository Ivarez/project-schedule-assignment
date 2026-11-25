"""Modelos de datos alineados con la definición formal de la Entrega 1.

Entidades:
- E: Estudiantes (Student)
- A: Asignaturas (Course)
- T: Franjas horarias (TimeSlot) + consec(t_x, t_y)
- G_U = (U, D): Grafo de ubicaciones y matriz de distancias (LocationGraph)
- S: Secciones (Section)
- G_soc: Vínculos sociales y académicos (SocialLink)
- X: Matriz binaria de asignación |E| x |S| (representada eficientemente como
     dict[student_id, set[section_id]] con conversión directa a matriz binaria).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple


@dataclass(frozen=True)
class TimeSlot:
    """Franja horaria discreta t ∈ T."""
    id: str
    day: str          # Ej: "Lunes", "Martes", ...
    day_index: int    # 0=Lunes .. 5=Sábado
    block_index: int  # 0=07:00-09:00, 1=09:00-11:00, ...
    label: str        # Ej: "07:00-09:00"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day": self.day,
            "day_index": self.day_index,
            "block_index": self.block_index,
            "label": self.label,
        }


@dataclass(frozen=True)
class Building:
    """Vértice u ∈ U del grafo de ubicaciones del campus G_U."""
    id: str
    name: str
    short_name: str
    x: float  # Coordenada relativa para visualización SVG (0..100)
    y: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "x": self.x,
            "y": self.y,
        }


@dataclass
class LocationGraph:
    """Grafo ponderado G_U = (U, D) con consulta de distancia D(u_x, u_y) en O(1)."""
    buildings: Dict[str, Building]
    distances: Dict[str, Dict[str, float]]  # D[u1][u2] >= 0

    def distance(self, u1: str, u2: str) -> float:
        if u1 == u2:
            return 0.0
        return self.distances[u1][u2]

    def to_dict(self) -> dict:
        return {
            "buildings": [b.to_dict() for b in self.buildings.values()],
            "distances": self.distances,
        }


@dataclass(frozen=True)
class Course:
    """Asignatura a ∈ A."""
    id: str
    name: str
    credits: int = 3

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "credits": self.credits}


@dataclass(frozen=True)
class Section:
    """Sección s ∈ S perteneciente a una asignatura asig(s) ∈ A."""
    id: str
    course_id: str                  # asig(s) ∈ A
    capacity: int                   # cupo(s) ∈ Z+
    schedule: Tuple[str, ...]       # horario(s) ⊆ T
    rooms: Dict[str, str]           # salon(s, t) ∈ U para t ∈ horario(s)
    professor: str = "Docente PUJ"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "capacity": self.capacity,
            "schedule": list(self.schedule),
            "rooms": dict(self.rooms),
            "professor": self.professor,
        }


@dataclass
class Student:
    """Estudiante e ∈ E con sus preferencias y materias solicitadas."""
    id: str
    name: str
    requested_courses: List[str]          # A_e ⊆ A
    priorities: Dict[str, float]          # P_e(a) ∈ [1, 10]
    empathy: Dict[str, float]             # M_e(s) ∈ [0, 1]
    time_preferences: Dict[str, float]    # L_e(t) ∈ [-1, 1]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "requested_courses": list(self.requested_courses),
            "priorities": dict(self.priorities),
            "empathy": dict(self.empathy),
            "time_preferences": dict(self.time_preferences),
        }


@dataclass(frozen=True)
class SocialLink:
    """Tupla (e_i, e_j, a, w_ij) ∈ G_soc."""
    student_i: str
    student_j: str
    course_id: str
    weight: float  # w_ij ∈ [0, 1]

    def to_dict(self) -> dict:
        return {
            "student_i": self.student_i,
            "student_j": self.student_j,
            "course_id": self.course_id,
            "weight": self.weight,
        }


@dataclass
class Weights:
    """Pesos de ponderación (w1..w5) de la función objetivo Z(X).

    Valores por defecto balanceados para compensar las distintas escalas
    de entrada (P_e en [1,10], M_e en [0,1], L_e en [-1,1], w_ij en [0,1], D en min).
    """
    w1_priority: float = 1.0
    w2_empathy: float = 4.0
    w3_planning: float = 2.0
    w4_social: float = 5.0
    w5_logistics: float = 1.5

    def to_dict(self) -> dict:
        return {
            "w1_priority": self.w1_priority,
            "w2_empathy": self.w2_empathy,
            "w3_planning": self.w3_planning,
            "w4_social": self.w4_social,
            "w5_logistics": self.w5_logistics,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Weights":
        return cls(
            w1_priority=float(data.get("w1_priority", 1.0)),
            w2_empathy=float(data.get("w2_empathy", 4.0)),
            w3_planning=float(data.get("w3_planning", 2.0)),
            w4_social=float(data.get("w4_social", 5.0)),
            w5_logistics=float(data.get("w5_logistics", 1.5)),
        )


@dataclass
class Instance:
    """Instancia completa del problema de asignación de horarios."""
    name: str
    description: str
    seed: int
    time_slots: Dict[str, TimeSlot]
    locations: LocationGraph
    courses: Dict[str, Course]
    sections: Dict[str, Section]
    students: Dict[str, Student]
    social_links: List[SocialLink]
    default_weights: Weights = field(default_factory=Weights)

    # Índices auxiliares precalculados para consultas O(1)
    sections_by_course: Dict[str, List[str]] = field(init=False, repr=False)
    consec_pairs: Set[Tuple[str, str]] = field(init=False, repr=False)
    slot_bit: Dict[str, int] = field(init=False, repr=False)
    section_mask: Dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.sections_by_course = {cid: [] for cid in self.courses}
        for sid, sec in self.sections.items():
            if sec.course_id in self.sections_by_course:
                self.sections_by_course[sec.course_id].append(sid)

        # Precalcular consec(t_x, t_y) ∈ {0, 1}
        self.consec_pairs = set()
        slots_list = list(self.time_slots.values())
        for tx in slots_list:
            for ty in slots_list:
                if tx.day_index == ty.day_index and ty.block_index == tx.block_index + 1:
                    self.consec_pairs.add((tx.id, ty.id))

        # Bitmasks para verificación de cruces horarios en O(1)
        self.slot_bit = {tid: (1 << idx) for idx, tid in enumerate(self.time_slots)}
        self.section_mask = {}
        for sid, sec in self.sections.items():
            mask = 0
            for tid in sec.schedule:
                if tid in self.slot_bit:
                    mask |= self.slot_bit[tid]
            self.section_mask[sid] = mask

    def consec(self, tx: str, ty: str) -> int:
        """Retorna 1 si ty ocurre inmediatamente después de tx el mismo día, 0 en caso contrario."""
        return 1 if (tx, ty) in self.consec_pairs else 0


# Tipo de salida: asignación X[e] = conjunto de section_ids asignados al estudiante e
Assignment = Dict[str, Set[str]]


@dataclass
class EvaluationResult:
    """Resultado completo del Módulo Validador y Evaluador sobre una asignación X."""
    valid: bool
    violations: List[str]
    z_score: float
    raw_priority: float
    raw_empathy: float
    raw_planning: float
    raw_social: float
    raw_logistics: float
    weighted_priority: float
    weighted_empathy: float
    weighted_planning: float
    weighted_social: float
    weighted_logistics: float
    assigned_count: int
    requested_count: int
    assignment_rate: float
    social_matches: int
    total_social_links: int
    section_occupancy: Dict[str, int]
    student_details: Dict[str, dict]

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "violations": self.violations,
            "z_score": round(self.z_score, 4),
            "raw": {
                "priority": round(self.raw_priority, 4),
                "empathy": round(self.raw_empathy, 4),
                "planning": round(self.raw_planning, 4),
                "social": round(self.raw_social, 4),
                "logistics": round(self.raw_logistics, 4),
            },
            "weighted": {
                "priority": round(self.weighted_priority, 4),
                "empathy": round(self.weighted_empathy, 4),
                "planning": round(self.weighted_planning, 4),
                "social": round(self.weighted_social, 4),
                "logistics": round(self.weighted_logistics, 4),
            },
            "assigned_count": self.assigned_count,
            "requested_count": self.requested_count,
            "assignment_rate": round(self.assignment_rate, 4),
            "social_matches": self.social_matches,
            "total_social_links": self.total_social_links,
            "section_occupancy": self.section_occupancy,
            "student_details": self.student_details,
        }


@dataclass
class SolverResult:
    """Resultado de ejecutar un algoritmo de asignación."""
    algorithm: str
    assignment: Assignment
    evaluation: EvaluationResult
    runtime_ms: float
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "runtime_ms": round(self.runtime_ms, 3),
            "metadata": self.metadata,
            "evaluation": self.evaluation.to_dict(),
            "assignment": {eid: sorted(list(secs)) for eid, secs in self.assignment.items()},
        }
