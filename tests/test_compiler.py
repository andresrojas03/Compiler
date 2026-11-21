"""Suite de pruebas automatizadas para el Proyecto Final del Compilador."""

import json
from pathlib import Path
import sys
import unittest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from lexer import Lexer, LexicalError
from parser_code_gen import compile_source


class TestCompilerPhase1(unittest.TestCase):
    """Valida casos oficiales del PDF, atomicidad, semántica, optimización y trazas."""

    # ---------------- Casos válidos oficiales (con ';' obligatorio) ----------------
    def test_valid_simple_assignment(self) -> None:
        res = compile_source("x = a;")
        self.assertTrue(res.success)
        self.assertEqual(res.raw_lines, ["x = a"])
        self.assertEqual(res.optimized_lines, ["x = a"])

    def test_valid_addition(self) -> None:
        res = compile_source("x = a + b;")
        self.assertTrue(res.success)
        self.assertEqual(res.raw_lines, ["t1 = a + b", "x = t1"])
        self.assertEqual(res.optimized_lines, ["x = a + b"])

    def test_valid_precedence_mul_over_add(self) -> None:
        res = compile_source("x = a + b * c;")
        self.assertTrue(res.success)
        self.assertEqual(
            res.raw_lines,
            ["t1 = b * c", "t2 = a + t1", "x = t2"],
        )
        self.assertEqual(res.optimized_lines, ["t1 = b * c", "x = a + t1"])

    def test_valid_parentheses_override_precedence(self) -> None:
        res = compile_source("x = (a + b) * c;")
        self.assertTrue(res.success)
        self.assertEqual(
            res.raw_lines,
            ["t1 = a + b", "t2 = t1 * c", "x = t2"],
        )
        self.assertEqual(res.optimized_lines, ["t1 = a + b", "x = t1 * c"])

    def test_valid_left_associativity(self) -> None:
        res = compile_source("x = a + b + c;")
        self.assertTrue(res.success)
        self.assertEqual(
            res.raw_lines,
            ["t1 = a + b", "t2 = t1 + c", "x = t2"],
        )

    def test_valid_left_associativity_sub_and_div(self) -> None:
        res_sub = compile_source("x = a - b - c;")
        self.assertTrue(res_sub.success)
        self.assertEqual(
            res_sub.raw_lines,
            ["t1 = a - b", "t2 = t1 - c", "x = t2"],
        )
        res_div = compile_source("x = a / b / c;")
        self.assertTrue(res_div.success)
        self.assertEqual(
            res_div.raw_lines,
            ["t1 = a / b", "t2 = t1 / c", "x = t2"],
        )

    def test_valid_deeply_nested_parentheses(self) -> None:
        res = compile_source("x = (((a + b) * (c - d)) / e);")
        self.assertTrue(res.success)
        self.assertEqual(
            res.raw_lines,
            [
                "t1 = a + b",
                "t2 = c - d",
                "t3 = t1 * t2",
                "t4 = t3 / e",
                "x = t4",
            ],
        )

    def test_valid_compact_no_spaces(self) -> None:
        res = compile_source("x=(a+b)*c;")
        self.assertTrue(res.success)
        self.assertEqual(
            res.raw_lines,
            ["t1 = a + b", "t2 = t1 * c", "x = t2"],
        )

    # ---------------- Casos inválidos oficiales y atomicidad ----------------
    def test_invalid_double_operator(self) -> None:
        res = compile_source("x = a + * b;")
        self.assertFalse(res.success)
        self.assertEqual(res.raw_lines, [])
        self.assertEqual(res.optimized_lines, [])
        self.assertEqual(res.errors[0].phase, "PARSING")

    def test_invalid_unclosed_parenthesis(self) -> None:
        res = compile_source("x = (a + b;")
        self.assertFalse(res.success)
        self.assertEqual(res.raw_lines, [])
        self.assertEqual(res.optimized_lines, [])

    def test_invalid_late_error_triggers_rollback(self) -> None:
        res = compile_source("x = ((a + b) *")
        self.assertFalse(res.success)
        self.assertEqual(res.raw_lines, [])
        self.assertEqual(res.optimized_lines, [])
        self.assertEqual(res.trace[-1].action, "ROLLBACK")

    def test_invalid_rollback_after_multiple_emitted_temps(self) -> None:
        res = compile_source("x = (a + b) * (c + d) + ;")
        self.assertFalse(res.success)
        self.assertEqual(res.raw_lines, [])
        self.assertEqual(res.optimized_lines, [])
        self.assertEqual(res.trace[-1].action, "ROLLBACK")
        self.assertEqual(res.trace[-1].tac_buffer_snapshot, [])

    # ---------------- Casos borde obligatorios ----------------
    def test_edge_lexical_error(self) -> None:
        res = compile_source("x = a @ b;")
        self.assertFalse(res.success)
        self.assertEqual(res.raw_lines, [])
        self.assertEqual(res.errors[0].phase, "LEXING")
        self.assertIn("@", res.errors[0].message)

    def test_edge_malformed_decimals(self) -> None:
        for bad_src in ("x = 3.;", "x = .5;", "x = 3. + 1;"):
            res = compile_source(bad_src)
            self.assertFalse(res.success, f"Debió fallar: {bad_src}")
            self.assertEqual(res.errors[0].phase, "LEXING")
            self.assertEqual(res.raw_lines, [])

    def test_edge_missing_semicolon_is_rejected(self) -> None:
        for bad_src in ("x = a + b", "x = (a + b) * c"):
            res = compile_source(bad_src)
            self.assertFalse(res.success)
            self.assertEqual(res.raw_lines, [])
            self.assertEqual(res.errors[0].phase, "PARSING")
            self.assertIn("';'", res.errors[0].message)

    def test_edge_unclosed_block_comment(self) -> None:
        res = compile_source("/* sin cierre x = a;")
        self.assertFalse(res.success)
        self.assertEqual(res.errors[0].phase, "LEXING")
        self.assertEqual(res.raw_lines, [])
        with self.assertRaises(LexicalError):
            Lexer("/* comentario sin cerrar").tokenize(raise_on_error=True)

    def test_edge_division_by_zero_variants(self) -> None:
        for zero_lit in ("0", "0.0", "0.00", "00", "00.000"):
            res = compile_source(f"x = a / {zero_lit};")
            self.assertFalse(res.success, f"División entre {zero_lit} debió rechazarse")
            self.assertEqual(res.errors[0].phase, "SEMANTIC")
            self.assertEqual(res.raw_lines, [])
            self.assertEqual(res.trace[-1].action, "ROLLBACK")

    # ---------------- Semántica, ámbitos, optimización y telemetría ----------------
    def test_strict_mode_declarations_and_scopes(self) -> None:
        program = """
        int a;
        int b;
        float x;
        a = 2;
        b = 3;
        {
            int c;
            c = 4;
            x = a + b * c;
        }
        """
        res = compile_source(program, strict_mode=True)
        self.assertTrue(res.success)
        self.assertEqual(len(res.errors), 0)
        names = [entry.name for entry in res.symbol_table]
        self.assertEqual(names, ["a", "b", "x", "c"])
        self.assertEqual(res.symbol_table[-1].scope_level, 1)

    def test_scope_shadowing_and_redeclaration(self) -> None:
        shadow_prog = """
        int a;
        a = 10;
        {
            float a;
            a = 2.5;
        }
        """
        res = compile_source(shadow_prog, strict_mode=True)
        self.assertTrue(res.success)
        self.assertEqual(len(res.symbol_table), 2)
        self.assertEqual(res.symbol_table[0].scope_id, "global")
        self.assertEqual(res.symbol_table[0].data_type, "int")
        self.assertEqual(res.symbol_table[1].scope_id, "block_1")
        self.assertEqual(res.symbol_table[1].data_type, "float")

        redecl_prog = "int a; int a;"
        res_bad = compile_source(redecl_prog, strict_mode=True)
        self.assertFalse(res_bad.success)
        self.assertEqual(res_bad.errors[0].phase, "SEMANTIC")
        self.assertEqual(res_bad.raw_lines, [])

    def test_strict_vs_compatible_narrowing_float_to_int(self) -> None:
        prog = "int x; x = 3.5;"
        res_strict = compile_source(prog, strict_mode=True)
        self.assertFalse(res_strict.success)
        self.assertEqual(res_strict.errors[0].phase, "SEMANTIC")
        self.assertEqual(res_strict.raw_lines, [])

        res_compat = compile_source(prog, strict_mode=False)
        self.assertTrue(res_compat.success)
        self.assertTrue(any("precisión" in w.message for w in res_compat.warnings))

    def test_strict_mode_rejects_undeclared_variable(self) -> None:
        res = compile_source("x = a + b;", strict_mode=True)
        self.assertFalse(res.success)
        self.assertEqual(res.errors[0].phase, "SEMANTIC")
        self.assertEqual(res.raw_lines, [])

    def test_optimizer_constant_folding_and_algebraic_identity(self) -> None:
        res = compile_source("x = a + 0 + 2 * 3;")
        self.assertTrue(res.success)
        self.assertEqual(
            res.raw_lines,
            ["t1 = a + 0", "t2 = 2 * 3", "t3 = t1 + t2", "x = t3"],
        )
        self.assertEqual(res.optimized_lines, ["x = a + 6"])

    def test_optimizer_multi_statement_reassignment_safety(self) -> None:
        prog = "a = 2; x = a + 1; a = 5; y = a + 1;"
        res = compile_source(prog)
        self.assertTrue(res.success)
        self.assertEqual(
            res.optimized_lines,
            ["a = 2", "x = a + 1", "a = 5", "y = a + 1"],
        )

    def test_optimizer_algebraic_identities_and_zero_div_folding_guard(self) -> None:
        res = compile_source("x = (a - a) + (b * 0) + (c / 1) + (0 / d);")
        self.assertTrue(res.success)
        self.assertEqual(res.optimized_lines, ["x = c"])

        res_div_zero_fold = compile_source("x = 5 / (2 - 2);")
        self.assertTrue(res_div_zero_fold.success)
        self.assertEqual(res_div_zero_fold.optimized_lines, ["x = 5 / 0"])

    def test_trace_json_export(self) -> None:
        res = compile_source("x = a + b * c;")
        self.assertTrue(res.success)
        assert res.tracer is not None
        exported = res.tracer.export_json()
        parsed = json.loads(exported)
        self.assertGreater(len(parsed), 10)
        required_keys = {
            "step_id",
            "phase",
            "action",
            "token_index",
            "current_token",
            "ll_stack",
            "call_frames",
            "production",
            "emitted_tac",
            "tac_buffer_snapshot",
            "symbol_table_snapshot",
            "message",
        }
        for step in parsed:
            self.assertEqual(set(step.keys()), required_keys)


def run_test_suite(verbosity: int = 2) -> bool:
    """Ejecuta toda la batería unittest y retorna True si todas las pruebas pasan."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCompilerPhase1)
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    ok = run_test_suite(verbosity=2)
    sys.exit(0 if ok else 1)
