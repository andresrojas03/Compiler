"""Generador transaccional de Código de Tres Direcciones (TAC) y optimizador."""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple


_TEMP_PATTERN = re.compile(r"^t\d+$")
_BINARY_INSTR_PATTERN = re.compile(
    r"^\s*(?P<result>[A-Za-z_]\w*)\s*=\s*(?P<arg1>[^\s]+)\s*(?P<op>[+\-*/])\s*(?P<arg2>[^\s]+)\s*$"
)
_COPY_INSTR_PATTERN = re.compile(
    r"^\s*(?P<result>[A-Za-z_]\w*)\s*=\s*(?P<arg1>[^\s]+)\s*$"
)


@dataclass(frozen=True)
class TACInstruction:
    """Instrucción de código de tres direcciones en formato estructurado y textual."""

    index: int
    op: str
    arg1: str
    arg2: Optional[str]
    result: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "op": self.op,
            "arg1": self.arg1,
            "arg2": self.arg2,
            "result": self.result,
            "text": self.text,
        }


def _parse_number(token: str) -> Optional[float]:
    try:
        return float(token)
    except ValueError:
        return None


def _format_number(value: float, both_ints: bool = False) -> str:
    if both_ints and value.is_integer():
        return str(int(value))
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _is_temp(name: str) -> bool:
    return bool(_TEMP_PATTERN.match(name))


class CodeGenerator:
    """
    Generador de TAC con buffer transaccional y optimizador no destructivo.

    - `emit()` escribe únicamente en `_staging_buffer`.
    - `commit()` consolida el código solo si el análisis finaliza sin errores.
    - `rollback()` descarta `_staging_buffer`, garantizando cero salida ante errores.
    """

    def __init__(self) -> None:
        self._temp_counter: int = 0
        self._staging_buffer: List[TACInstruction] = []
        self._committed_code: List[TACInstruction] = []
        self.rolled_back: bool = False

    def new_temp(self) -> str:
        """Genera variables temporales secuenciales: t1, t2, t3, ..."""
        self._temp_counter += 1
        return f"t{self._temp_counter}"

    # Alias compatible con la notación del documento de requerimientos
    newTemp = new_temp

    def emit(self, instruction: str) -> TACInstruction:
        """
        Registra una instrucción TAC en el buffer transaccional con formato:
        `t1 = op1 * op2` o `x = t2`.
        """
        text = instruction.strip()
        index = len(self._staging_buffer) + 1

        bin_match = _BINARY_INSTR_PATTERN.match(text)
        if bin_match:
            instr = TACInstruction(
                index=index,
                op=bin_match.group("op"),
                arg1=bin_match.group("arg1"),
                arg2=bin_match.group("arg2"),
                result=bin_match.group("result"),
                text=(
                    f"{bin_match.group('result')} = "
                    f"{bin_match.group('arg1')} {bin_match.group('op')} {bin_match.group('arg2')}"
                ),
            )
        else:
            copy_match = _COPY_INSTR_PATTERN.match(text)
            if not copy_match:
                raise ValueError(f"Formato de instrucción TAC no reconocido: {instruction!r}")
            instr = TACInstruction(
                index=index,
                op="=",
                arg1=copy_match.group("arg1"),
                arg2=None,
                result=copy_match.group("result"),
                text=f"{copy_match.group('result')} = {copy_match.group('arg1')}",
            )

        self._staging_buffer.append(instr)
        return instr

    def commit(self) -> List[TACInstruction]:
        """Consolida las instrucciones del buffer como TAC definitivo."""
        self.rolled_back = False
        self._committed_code = list(self._staging_buffer)
        return list(self._committed_code)

    def rollback(self) -> List[TACInstruction]:
        """Descarta todas las instrucciones emitidas ante un error léxico, sintáctico o semántico."""
        discarded = list(self._staging_buffer)
        self._staging_buffer.clear()
        self._committed_code.clear()
        self.rolled_back = True
        return discarded

    def get_staging_lines(self) -> List[str]:
        return [instr.text for instr in self._staging_buffer]

    def get_committed_code(self) -> List[TACInstruction]:
        return list(self._committed_code)

    @staticmethod
    def optimize(
        raw_instructions: List[TACInstruction],
    ) -> Tuple[List[TACInstruction], List[str]]:
        """
        Aplica un pase de optimización sobre una copia del TAC crudo sin alterarlo:
        1. Plegado de constantes (Constant Folding).
        2. Simplificación algebraica básica (identidades de +, -, *, /).
        3. Propagación de copias y fusión de temporales redundantes.
        """
        if not raw_instructions:
            return [], []

        working: List[TACInstruction] = list(raw_instructions)
        notes: List[str] = []

        for _ in range(10):
            changed = False

            # --- Paso 1: Plegado de constantes y simplificación algebraica ---
            folded: List[TACInstruction] = []
            for instr in working:
                if instr.op == "=" or instr.arg2 is None:
                    folded.append(instr)
                    continue

                n1 = _parse_number(instr.arg1)
                n2 = _parse_number(instr.arg2)
                both_ints = (
                    n1 is not None
                    and n2 is not None
                    and "." not in instr.arg1
                    and "." not in instr.arg2
                )

                # 1a. Plegado de constantes
                if n1 is not None and n2 is not None:
                    if instr.op == "+":
                        val = _format_number(n1 + n2, both_ints)
                    elif instr.op == "-":
                        val = _format_number(n1 - n2, both_ints)
                    elif instr.op == "*":
                        val = _format_number(n1 * n2, both_ints)
                    elif instr.op == "/" and n2 != 0:
                        val = _format_number(n1 / n2, False)
                    else:
                        folded.append(instr)
                        continue
                    new_instr = TACInstruction(
                        instr.index, "=", val, None, instr.result, f"{instr.result} = {val}"
                    )
                    notes.append(f"Plegado de constantes: '{instr.text}' -> '{new_instr.text}'")
                    folded.append(new_instr)
                    changed = True
                    continue

                # 1b. Simplificación algebraica básica
                simplified_rhs: Optional[str] = None
                if instr.op == "+":
                    if n2 == 0:
                        simplified_rhs = instr.arg1
                    elif n1 == 0:
                        simplified_rhs = instr.arg2
                elif instr.op == "-":
                    if n2 == 0:
                        simplified_rhs = instr.arg1
                    elif instr.arg1 == instr.arg2:
                        simplified_rhs = "0"
                elif instr.op == "*":
                    if n2 == 1:
                        simplified_rhs = instr.arg1
                    elif n1 == 1:
                        simplified_rhs = instr.arg2
                    elif n1 == 0 or n2 == 0:
                        simplified_rhs = "0"
                elif instr.op == "/":
                    if n2 == 1:
                        simplified_rhs = instr.arg1
                    elif n1 == 0:
                        simplified_rhs = "0"

                if simplified_rhs is not None:
                    new_instr = TACInstruction(
                        instr.index,
                        "=",
                        simplified_rhs,
                        None,
                        instr.result,
                        f"{instr.result} = {simplified_rhs}",
                    )
                    notes.append(
                        f"Simplificación algebraica: '{instr.text}' -> '{new_instr.text}'"
                    )
                    folded.append(new_instr)
                    changed = True
                else:
                    folded.append(instr)

            working = folded

            # --- Paso 2: Propagación de copias (t = operando) ---
            copies: Dict[str, str] = {}
            propagated: List[TACInstruction] = []
            for instr in working:
                new_arg1 = copies.get(instr.arg1, instr.arg1)
                new_arg2 = (
                    copies.get(instr.arg2, instr.arg2)
                    if instr.arg2 is not None
                    else None
                )
                if new_arg1 != instr.arg1 or new_arg2 != instr.arg2:
                    changed = True
                    new_text = (
                        f"{instr.result} = {new_arg1}"
                        if instr.op == "=" or new_arg2 is None
                        else f"{instr.result} = {new_arg1} {instr.op} {new_arg2}"
                    )
                    notes.append(f"Propagación de copia: '{instr.text}' -> '{new_text}'")
                    instr = TACInstruction(
                        instr.index, instr.op, new_arg1, new_arg2, instr.result, new_text
                    )

                for key in list(copies.keys()):
                    if key == instr.result or copies[key] == instr.result:
                        del copies[key]

                if instr.op == "=" and instr.arg2 is None and _is_temp(instr.result):
                    copies[instr.result] = instr.arg1

                propagated.append(instr)

            working = propagated

            # --- Paso 3: Fusión de temporal redundante antes de asignación (t = a op b; x = t -> x = a op b) ---
            merged: List[TACInstruction] = []
            i = 0
            while i < len(working):
                curr = working[i]
                if (
                    i + 1 < len(working)
                    and _is_temp(curr.result)
                    and working[i + 1].op == "="
                    and working[i + 1].arg1 == curr.result
                    and working[i + 1].arg2 is None
                ):
                    nxt = working[i + 1]
                    used_later = any(
                        later.arg1 == curr.result or later.arg2 == curr.result
                        for later in working[i + 2 :]
                    )
                    if not used_later:
                        new_text = (
                            f"{nxt.result} = {curr.arg1}"
                            if curr.op == "=" or curr.arg2 is None
                            else f"{nxt.result} = {curr.arg1} {curr.op} {curr.arg2}"
                        )
                        fused = TACInstruction(
                            curr.index,
                            curr.op,
                            curr.arg1,
                            curr.arg2,
                            nxt.result,
                            new_text,
                        )
                        notes.append(
                            f"Eliminación de temporal redundante: '{curr.text}; {nxt.text}' -> '{new_text}'"
                        )
                        merged.append(fused)
                        changed = True
                        i += 2
                        continue
                merged.append(curr)
                i += 1

            working = merged

            # --- Paso 4: Eliminación de temporales muertos ---
            live_filtered: List[TACInstruction] = []
            for idx, instr in enumerate(working):
                if _is_temp(instr.result):
                    used_later = any(
                        later.arg1 == instr.result or later.arg2 == instr.result
                        for later in working[idx + 1 :]
                    )
                    if not used_later:
                        notes.append(f"Eliminación de temporal sin uso: '{instr.text}'")
                        changed = True
                        continue
                live_filtered.append(instr)

            working = live_filtered

            if not changed:
                break

        reindexed = [
            TACInstruction(
                index=idx + 1,
                op=instr.op,
                arg1=instr.arg1,
                arg2=instr.arg2,
                result=instr.result,
                text=instr.text,
            )
            for idx, instr in enumerate(working)
        ]
        return reindexed, notes