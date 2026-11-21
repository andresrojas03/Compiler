"""Tabla de símbolos jerárquica con ámbitos, verificación/inferencia de tipos y advertencias."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


class SemanticError(Exception):
    """Error semántico fatal (modo estricto o división explícita entre cero)."""

    def __init__(self, message: str, line: int, column: int) -> None:
        self.message = f"Error semántico en línea {line}, columna {column}: {message}"
        self.line = line
        self.column = column
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": "SEMANTIC",
            "line": self.line,
            "column": self.column,
            "message": self.message,
        }


@dataclass
class SemanticWarning:
    """Advertencia semántica no fatal."""

    message: str
    line: int
    column: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line": self.line,
            "column": self.column,
            "message": self.message,
        }

    def __str__(self) -> str:
        return f"Advertencia semántica (L{self.line}:C{self.column}): {self.message}"


@dataclass
class SymbolEntry:
    """Registro de un identificador dentro de un ámbito específico."""

    name: str
    data_type: str  # "int" | "float" | "inferred"
    scope_level: int
    scope_id: str
    declared: bool
    initialized: bool
    line: int
    column: int
    last_place: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "data_type": self.data_type,
            "scope_level": self.scope_level,
            "scope_id": self.scope_id,
            "declared": self.declared,
            "initialized": self.initialized,
            "line": self.line,
            "column": self.column,
            "last_place": self.last_place,
        }


class SymbolTable:
    """
    Administra identificadores, ámbitos léxicos y verificación/inferencia de tipos.

    - strict_mode=False (por defecto): compatible con expresiones sin declaración previa;
      registra símbolos implícitamente y emite advertencias claras.
    - strict_mode=True: exige declaración previa (`int` / `float`) antes de leer o asignar.
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self.strict_mode: bool = strict_mode
        self._scope_stack: List[Tuple[str, Dict[str, SymbolEntry]]] = [("global", {})]
        self._all_entries: List[SymbolEntry] = []
        self._block_counter: int = 0
        self.warnings: List[SemanticWarning] = []
        self._warned_keys: Set[Tuple[str, str, str]] = set()

    @property
    def current_scope_level(self) -> int:
        return len(self._scope_stack) - 1

    @property
    def current_scope_id(self) -> str:
        return self._scope_stack[-1][0]

    def enter_scope(self) -> str:
        self._block_counter += 1
        scope_id = f"block_{self._block_counter}"
        self._scope_stack.append((scope_id, {}))
        return scope_id

    def exit_scope(self) -> str:
        if len(self._scope_stack) <= 1:
            return "global"
        scope_id, _ = self._scope_stack.pop()
        return scope_id

    def _add_warning_once(
        self, category: str, symbol_name: str, message: str, line: int, col: int
    ) -> None:
        key = (category, self.current_scope_id, symbol_name)
        if key not in self._warned_keys:
            self._warned_keys.add(key)
            self.warnings.append(SemanticWarning(message, line, col))

    def lookup(self, name: str) -> Optional[SymbolEntry]:
        """Busca un símbolo desde el ámbito más interno hacia el global."""
        for _, table in reversed(self._scope_stack):
            if name in table:
                return table[name]
        return None

    def declare(self, name: str, data_type: str, line: int, column: int) -> SymbolEntry:
        """Declara explícitamente un identificador en el ámbito actual."""
        scope_id, current_table = self._scope_stack[-1]
        if name in current_table:
            raise SemanticError(
                f"La variable '{name}' ya fue declarada en el ámbito '{scope_id}'.",
                line,
                column,
            )
        entry = SymbolEntry(
            name=name,
            data_type=data_type,
            scope_level=self.current_scope_level,
            scope_id=scope_id,
            declared=True,
            initialized=False,
            line=line,
            column=column,
        )
        current_table[name] = entry
        self._all_entries.append(entry)
        return entry

    def record_use(self, name: str, line: int, column: int) -> SymbolEntry:
        """Registra la lectura de un identificador en una expresión."""
        entry = self.lookup(name)
        if entry is None:
            if self.strict_mode:
                raise SemanticError(
                    f"La variable '{name}' se utiliza sin haber sido declarada previamente.",
                    line,
                    column,
                )
            scope_id, current_table = self._scope_stack[-1]
            entry = SymbolEntry(
                name=name,
                data_type="inferred",
                scope_level=self.current_scope_level,
                scope_id=scope_id,
                declared=False,
                initialized=False,
                line=line,
                column=column,
            )
            current_table[name] = entry
            self._all_entries.append(entry)
            self._add_warning_once(
                "undeclared_read",
                name,
                f"Variable '{name}' utilizada sin declaración ni inicialización previa (registrada como 'inferred').",
                line,
                column,
            )
            return entry

        if not entry.initialized:
            self._add_warning_once(
                "uninitialized_read",
                name,
                f"Variable '{name}' leída antes de recibir una asignación previa.",
                line,
                column,
            )
        return entry

    def record_assignment(
        self,
        name: str,
        expr_type: str,
        place: str,
        line: int,
        column: int,
    ) -> SymbolEntry:
        """Registra una asignación y valida compatibilidad o inferencia de tipos."""
        entry = self.lookup(name)
        if entry is None:
            if self.strict_mode:
                raise SemanticError(
                    f"No se puede asignar a '{name}' porque no ha sido declarada.",
                    line,
                    column,
                )
            scope_id, current_table = self._scope_stack[-1]
            inferred_type = expr_type if expr_type in ("int", "float") else "inferred"
            entry = SymbolEntry(
                name=name,
                data_type=inferred_type,
                scope_level=self.current_scope_level,
                scope_id=scope_id,
                declared=False,
                initialized=True,
                line=line,
                column=column,
                last_place=place,
            )
            current_table[name] = entry
            self._all_entries.append(entry)
            self._add_warning_once(
                "undeclared_assign",
                name,
                f"Variable '{name}' asignada sin declaración explícita (tipo inferido: '{inferred_type}').",
                line,
                column,
            )
            return entry

        if entry.data_type == "int" and expr_type == "float":
            if self.strict_mode:
                raise SemanticError(
                    f"Incompatibilidad de tipos: no se puede asignar 'float' a '{name}' de tipo 'int'.",
                    line,
                    column,
                )
            self._add_warning_once(
                "narrowing",
                name,
                f"Posible pérdida de precisión al asignar expresión 'float' a variable 'int' ('{name}').",
                line,
                column,
            )
        elif entry.data_type == "inferred" and expr_type in ("int", "float"):
            entry.data_type = expr_type

        entry.initialized = True
        entry.last_place = place
        return entry

    @staticmethod
    def resolve_binary_type(left_type: str, right_type: str, op: str) -> str:
        """Determina el tipo resultante de una operación binaria."""
        if op == "/":
            return "float"
        if "float" in (left_type, right_type):
            return "float"
        if left_type == "int" and right_type == "int":
            return "int"
        return "inferred"

    def entries(self) -> List[SymbolEntry]:
        return list(self._all_entries)

    def snapshot(self) -> List[Dict[str, Any]]:
        """Retorna una instantánea inmutable para TraceStep."""
        return [entry.to_dict() for entry in self._all_entries]

    def format_table(self) -> str:
        """Genera una representación tabular legible de la tabla de símbolos."""
        if not self._all_entries:
            return "(Tabla de símbolos vacía)"

        headers = [
            "Nombre",
            "Tipo",
            "Ámbito",
            "Nivel",
            "Declarada",
            "Inicializada",
            "Ubicación",
            "Último Place",
        ]
        rows = [
            [
                e.name,
                e.data_type,
                e.scope_id,
                str(e.scope_level),
                "Sí" if e.declared else "No",
                "Sí" if e.initialized else "No",
                f"L{e.line}:C{e.column}",
                e.last_place or "-",
            ]
            for e in self._all_entries
        ]
        widths = [
            max(len(headers[i]), max(len(r[i]) for r in rows))
            for i in range(len(headers))
        ]

        sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
        header_line = (
            "| "
            + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers)))
            + " |"
        )
        body_lines = [
            "| "
            + " | ".join(row[i].ljust(widths[i]) for i in range(len(headers)))
            + " |"
            for row in rows
        ]
        return "\n".join([sep, header_line, sep, *body_lines, sep])