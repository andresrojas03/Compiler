"""
Punto de entrada CLI del Compilador (Lexer + Parser LL(1) SDT + TAC + Optimizador).

Uso:
    python main/main.py                       -> Menú interactivo
    python main/main.py --official            -> Ejecuta los casos oficiales + borde
    python main/main.py --test                -> Ejecuta la suite unittest completa
    python main/main.py -e "x = a + b * c;"   -> Compila una expresión directa
    python main/main.py -e "x = a + b * c;" --trace --export-json trace.json
    python main/main.py -f archivo.txt        -> Compila desde archivo
"""

import argparse
from pathlib import Path
import sys
from typing import List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from parser_code_gen import CompilationResult, CompilerTracer, compile_source
from tests.test_compiler import run_test_suite


OFFICIAL_CASES: List[Tuple[str, str, bool]] = [
    ("Válido (a)", "x = a;", True),
    ("Válido (b)", "x = a + b;", True),
    ("Válido (c)", "x = a + b * c;", True),
    ("Válido (d) [normalizado con ';']", "x = (a + b) * c;", True),
    ("Válido sin espacios", "x=(a+b)*c;", True),
    ("Inválido (a) operador duplicado", "x = a + * b;", False),
    ("Inválido (b) paréntesis sin cerrar", "x = (a + b;", False),
    ("Inválido (c) error tardío + rollback", "x = ((a + b) *", False),
    ("Borde: error léxico '@'", "x = a @ b;", False),
    ("Borde: falta ';' obligatorio", "x = a + b", False),
]


def print_compilation_report(
    result: CompilationResult,
    *,
    show_tokens: bool = True,
    show_trace: bool = False,
) -> None:
    """Imprime un reporte estructurado del proceso completo de compilación."""
    print("=" * 76)
    print(f"ENTRADA : {result.source.strip()}")
    print(f"MODO    : {'Estricto' if result.strict_mode else 'Compatible'}")
    print(
        f"ESTADO  : {'VÁLIDA (Compilación exitosa)' if result.success else 'INVÁLIDA (Sin generación de TAC)'}"
    )
    print("=" * 76)

    if show_tokens:
        toks = ", ".join(f"({t.type.value}, '{t.lexeme}')" for t in result.tokens)
        print(f"Tokens  : {toks}")

    if result.errors:
        print("\nErrores detectados:")
        for err in result.errors:
            print(f"  - [{err.phase}] {err.message}")

    if result.warnings:
        print("\nAdvertencias semánticas:")
        for warn in result.warnings:
            print(f"  - {warn}")

    print("\nCódigo de Tres Direcciones (TAC Crudo - generado durante el parsing):")
    if result.tac_raw:
        for instr in result.tac_raw:
            print(f"  {instr.text}")
    else:
        print("  (Ninguno — buffer vacío / rollback aplicado)")

    if result.success:
        print("\nCódigo de Tres Direcciones (TAC Optimizado):")
        for instr in result.tac_optimized:
            print(f"  {instr.text}")
        if result.optimization_notes:
            print("\nTransformaciones de optimización aplicadas:")
            for note in result.optimization_notes:
                print(f"  * {note}")
        else:
            print("  (Sin optimizaciones adicionales aplicables)")

    print("\nTabla de Símbolos:")
    print(result.symbol_table_text)

    if show_trace:
        print("\nTraza Paso a Paso (TraceStep):")
        for step in result.trace:
            print(CompilerTracer.format_step(step))
            print("-" * 76)
    print()


def run_official_battery(strict_mode: bool = False) -> bool:
    """Ejecuta todos los ejemplos oficiales del PDF más los casos borde."""
    passed = 0
    for title, src, expected_valid in OFFICIAL_CASES:
        print(f">>> {title}")
        res = compile_source(src, strict_mode=strict_mode)
        ok = (res.success == expected_valid) and (expected_valid or len(res.tac_raw) == 0)
        if ok:
            passed += 1
        print_compilation_report(res, show_tokens=True, show_trace=False)
    print(
        f"Resumen batería oficial: {passed}/{len(OFFICIAL_CASES)} casos verificados correctamente.\n"
    )
    return passed == len(OFFICIAL_CASES)


def inspect_trace_interactive(result: CompilationResult) -> None:
    """Visor interactivo en terminal para recorrer TraceStep paso a paso."""
    if not result.trace:
        print("No hay pasos de traza disponibles.")
        return

    idx = 0
    total = len(result.trace)
    print(
        "\nVisor de traza: [Enter/n] siguiente | [p] anterior | [a] ver todo | [j] exportar JSON | [q] salir"
    )
    while True:
        print("\n" + "-" * 76)
        print(f"Paso {idx + 1} de {total}")
        print(CompilerTracer.format_step(result.trace[idx]))
        cmd = input("Acción [n/p/a/j/q]: ").strip().lower()
        if cmd in ("", "n"):
            if idx < total - 1:
                idx += 1
            else:
                print("Has llegado al último paso de la traza.")
        elif cmd == "p":
            if idx > 0:
                idx -= 1
            else:
                print("Ya estás en el primer paso.")
        elif cmd == "a":
            for step in result.trace:
                print("-" * 76)
                print(CompilerTracer.format_step(step))
            break
        elif cmd == "j":
            out_path = input("Ruta del archivo JSON [trace.json]: ").strip() or "trace.json"
            if result.tracer is not None:
                result.tracer.export_json(out_path)
                print(f"Traza exportada correctamente a '{out_path}'.")
        elif cmd == "q":
            break


def interactive_menu() -> None:
    """Menú interactivo principal del compilador."""
    strict_mode = False
    last_result: Optional[CompilationResult] = None

    while True:
        mode_lbl = (
            "ESTRICTO (exige declaraciones)"
            if strict_mode
            else "COMPATIBLE (inferencia automática)"
        )
        print("\n" + "=" * 64)
        print("  COMPILADOR LL(1) + GENERADOR DE CÓDIGO DE TRES DIRECCIONES")
        print(f"  Modo semántico actual: {mode_lbl}")
        print("=" * 64)
        print("1. Compilar una expresión o programa (con ';' obligatorio)")
        print("2. Ejecutar batería oficial del PDF + casos borde")
        print("3. Inspeccionar traza paso a paso de la última compilación")
        print("4. Exportar última traza a JSON (para Fase 2 / Vercel)")
        print("5. Alternar modo semántico (Compatible / Estricto)")
        print("6. Ejecutar suite de pruebas automatizadas (unittest)")
        print("0. Salir")

        choice = input("\nSelecciona una opción: ").strip()

        if choice == "1":
            print(
                "Ingresa el código fuente (termina cada sentencia con ';'; "
                "línea vacía para finalizar si ingresas múltiples líneas o bloques '{ }'):"
            )
            first = input("> ")
            lines = [first]
            open_braces = first.count("{") - first.count("}")
            if not first.strip().endswith(";") or open_braces > 0:
                while True:
                    nxt = input("... ")
                    if nxt == "":
                        break
                    lines.append(nxt)
            source = "\n".join(lines)
            last_result = compile_source(source, strict_mode=strict_mode)
            print_compilation_report(last_result, show_tokens=True, show_trace=False)

        elif choice == "2":
            run_official_battery(strict_mode=strict_mode)

        elif choice == "3":
            if last_result is None:
                print("Primero compila una expresión (opción 1) para inspeccionar su traza.")
            else:
                inspect_trace_interactive(last_result)

        elif choice == "4":
            if last_result is None or last_result.tracer is None:
                print("Primero compila una expresión (opción 1) para exportar su traza.")
            else:
                out_path = input("Ruta de salida JSON [trace.json]: ").strip() or "trace.json"
                last_result.tracer.export_json(out_path)
                print(f"Traza exportada exitosamente a '{out_path}'.")

        elif choice == "5":
            strict_mode = not strict_mode
            print(f"Modo semántico cambiado a: {'ESTRICTO' if strict_mode else 'COMPATIBLE'}.")

        elif choice == "6":
            run_test_suite(verbosity=2)

        elif choice == "0":
            print("Saliendo del compilador.")
            break
        else:
            print("Opción no reconocida. Intenta nuevamente.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compilador integrado: Lexer + Parser LL(1) SDT + Generador TAC + Optimizador."
    )
    parser.add_argument("-e", "--expr", type=str, help="Compila directamente la cadena proporcionada.")
    parser.add_argument("-f", "--file", type=str, help="Compila el código fuente desde un archivo.")
    parser.add_argument("--strict", action="store_true", help="Activa el modo semántico estricto.")
    parser.add_argument("--trace", action="store_true", help="Muestra la traza completa paso a paso.")
    parser.add_argument("--export-json", type=str, help="Exporta la traza a un archivo JSON.")
    parser.add_argument("--official", action="store_true", help="Ejecuta la batería oficial de pruebas.")
    parser.add_argument("--test", action="store_true", help="Ejecuta la suite unittest automatizada.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    if args.test:
        ok = run_test_suite(verbosity=2)
        sys.exit(0 if ok else 1)

    if args.official:
        ok = run_official_battery(strict_mode=args.strict)
        sys.exit(0 if ok else 1)

    if args.expr is not None or args.file is not None:
        source = (
            args.expr
            if args.expr is not None
            else Path(args.file).read_text(encoding="utf-8")
        )
        res = compile_source(source, strict_mode=args.strict)
        print_compilation_report(res, show_tokens=True, show_trace=args.trace)
        if args.export_json and res.tracer is not None:
            res.tracer.export_json(args.export_json)
            print(f"Traza exportada a '{args.export_json}'.")
        sys.exit(0 if res.success else 1)

    interactive_menu()


if __name__ == "__main__":
    main()
