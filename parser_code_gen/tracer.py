"""Sistema de telemetría paso a paso (TraceStep) exportable a JSON para Fase 2."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from lexer.tokens import Token


@dataclass(frozen=True)
class AttributeFrame:
    """Marco de activación semántica de un no terminal (.inh y .place)."""

    non_terminal: str
    production: Optional[str] = None
    inh: Optional[str] = None
    place: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "non_terminal": self.non_terminal,
            "production": self.production,
            "inh": self.inh,
            "place": self.place,
        }


@dataclass(frozen=True)
class TraceStep:
    """Instantánea inmutable de una transición del compilador."""

    step_id: int
    phase: str
    action: str
    token_index: int
    current_token: Optional[Dict[str, Any]]
    ll_stack: List[str]
    call_frames: List[Dict[str, Any]]
    production: Optional[str]
    emitted_tac: Optional[str]
    tac_buffer_snapshot: List[str]
    symbol_table_snapshot: List[Dict[str, Any]]
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "phase": self.phase,
            "action": self.action,
            "token_index": self.token_index,
            "current_token": self.current_token,
            "ll_stack": list(self.ll_stack),
            "call_frames": list(self.call_frames),
            "production": self.production,
            "emitted_tac": self.emitted_tac,
            "tac_buffer_snapshot": list(self.tac_buffer_snapshot),
            "symbol_table_snapshot": list(self.symbol_table_snapshot),
            "message": self.message,
        }


class CompilerTracer:
    """Captura inmutable de cada transición para depuración y visualización web."""

    def __init__(self) -> None:
        self.steps: List[TraceStep] = []
        self._ll_stack: List[str] = []
        self._call_frames: List[AttributeFrame] = []

    def init_ll_stack(self, start_symbol: str) -> None:
        self._ll_stack = ["$", start_symbol]
        self._call_frames.clear()

    def expand_ll(self, non_terminal: str, rhs: List[str]) -> None:
        """Actualiza la pila simbólica LL(1) al aplicar non_terminal -> rhs."""
        if self._ll_stack and self._ll_stack[-1] == non_terminal:
            self._ll_stack.pop()
        for symbol in reversed(rhs):
            if symbol != "ε":
                self._ll_stack.append(symbol)

    def match_ll(self, terminal_symbol: str) -> None:
        """Consume el terminal del tope de la pila simbólica LL(1)."""
        if self._ll_stack and self._ll_stack[-1] == terminal_symbol:
            self._ll_stack.pop()

    def push_frame(
        self,
        non_terminal: str,
        production: Optional[str] = None,
        inh: Optional[str] = None,
        place: Optional[str] = None,
    ) -> None:
        self._call_frames.append(
            AttributeFrame(
                non_terminal=non_terminal,
                production=production,
                inh=inh,
                place=place,
            )
        )

    def update_top_frame(
        self,
        *,
        production: Optional[str] = None,
        inh: Optional[str] = None,
        place: Optional[str] = None,
    ) -> None:
        if not self._call_frames:
            return
        top = self._call_frames[-1]
        self._call_frames[-1] = AttributeFrame(
            non_terminal=top.non_terminal,
            production=production if production is not None else top.production,
            inh=inh if inh is not None else top.inh,
            place=place if place is not None else top.place,
        )

    def pop_frame(self) -> Optional[AttributeFrame]:
        return self._call_frames.pop() if self._call_frames else None

    def record(
        self,
        *,
        phase: str,
        action: str,
        token_index: int,
        current_token: Optional[Token],
        tac_buffer: List[str],
        symbol_table_snapshot: List[Dict[str, Any]],
        message: str,
        production: Optional[str] = None,
        emitted_tac: Optional[str] = None,
    ) -> TraceStep:
        step = TraceStep(
            step_id=len(self.steps) + 1,
            phase=phase,
            action=action,
            token_index=token_index,
            current_token=current_token.to_dict() if current_token else None,
            ll_stack=list(self._ll_stack),
            call_frames=[frame.to_dict() for frame in self._call_frames],
            production=production,
            emitted_tac=emitted_tac,
            tac_buffer_snapshot=list(tac_buffer),
            symbol_table_snapshot=[dict(entry) for entry in symbol_table_snapshot],
            message=message,
        )
        self.steps.append(step)
        return step

    def export_json(self, filepath: Optional[str] = None, indent: int = 2) -> str:
        """Serializa toda la traza a JSON y opcionalmente la guarda en disco."""
        payload = json.dumps(
            [step.to_dict() for step in self.steps],
            ensure_ascii=False,
            indent=indent,
        )
        if filepath is not None:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        return payload

    @staticmethod
    def format_step(step: TraceStep) -> str:
        tok = (
            f"{step.current_token['type']}({step.current_token['lexeme']})"
            if step.current_token
            else "NONE"
        )
        frames_str = (
            ", ".join(
                f"{f['non_terminal']}(inh={f['inh']}, place={f['place']})"
                for f in step.call_frames
            )
            or "-"
        )
        lines = [
            f"[Paso {step.step_id:02d}] {step.phase} | {step.action} | Lookahead[{step.token_index}]: {tok}",
            f"  Pila LL  : {step.ll_stack}",
            f"  Atributos: {frames_str}",
        ]
        if step.production:
            lines.append(f"  Regla    : {step.production}")
        if step.emitted_tac:
            lines.append(f"  Emitido  : {step.emitted_tac}")
        lines.append(f"  Detalle  : {step.message}")
        return "\n".join(lines)