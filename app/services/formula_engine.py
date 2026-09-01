"""
Safe formula evaluator using Python's ast module.
Supports: +, -, *, /, (), max(), min(), numeric literals, and variable references.
Rejects: imports, attribute access, function calls (except max/min), lambda, etc.
"""

import ast
import operator
from typing import Dict, Any, Union


class FormulaValidator(ast.NodeVisitor):
   """Validate formula AST while allowing only arithmetic and max()/min()."""

   _allowed_node_types = {
       ast.Expression,
       ast.Module,
       ast.Load,
       ast.Constant,
       ast.Name,
       ast.BinOp,
       ast.UnaryOp,
       ast.Call,
       ast.Add,
       ast.Sub,
       ast.Mult,
       ast.Div,
       ast.USub,
   }

   def __init__(self, allowed_variables):
       self.allowed_variables = set(allowed_variables)
       self.errors = []

   def visit_Constant(self, node):
       if isinstance(node.value, (int, float)):
           return
       self.errors.append(f"Unsupported constant type: {type(node.value).__name__}")

   def visit_Num(self, node):
       if isinstance(node.n, (int, float)):
           return
       self.errors.append(f"Unsupported constant type: {type(node.n).__name__}")

   def visit_Name(self, node):
       if node.id not in self.allowed_variables:
           self.errors.append(f"Undefined variable: {node.id}")

   def visit_BinOp(self, node):
       valid_ops = (ast.Add, ast.Sub, ast.Mult, ast.Div)
       if not isinstance(node.op, valid_ops):
           self.errors.append(f"Unsupported binary operation: {node.op.__class__.__name__}")
       self.generic_visit(node)

   def visit_UnaryOp(self, node):
       if not isinstance(node.op, ast.USub):
           self.errors.append(f"Unsupported unary operation: {node.op.__class__.__name__}")
       self.generic_visit(node)

   def visit_Call(self, node):
       if not isinstance(node.func, ast.Name):
           self.errors.append("Complex function calls not allowed")
           return

       func_name = node.func.id
       if func_name not in ("max", "min"):
           self.errors.append(f"Function call not allowed: {func_name}()")
           return

       if not node.args:
           self.errors.append(f"max()/min() requires comma-separated arguments, e.g., max(A, B)")
           return

       for arg in node.args:
           self.visit(arg)

       if node.keywords:
           self.errors.append("Keyword arguments are not allowed in max()/min()")

   def generic_visit(self, node):
       allowed_types = tuple(self._allowed_node_types)
       if not isinstance(node, allowed_types):
           self.errors.append(f"Unsupported syntax: {node.__class__.__name__}")
       super().generic_visit(node)


def validate_formula(formula_text: str, allowed_variable_names: list) -> tuple[bool, str]:
   """
   Validate a formula string before evaluation.

   - Simple arithmetic expressions without max()/min() must validate successfully.
   - Commas are only meaningful inside max()/min() argument lists.
   - If a malformed max()/min() call is present, a specific message is returned.
   """
   formula_text = (formula_text or '').strip()
   if not formula_text:
       return False, "Formula is required"

   try:
       tree = ast.parse(formula_text, mode='eval')
   except SyntaxError as e:
       if 'max(' in formula_text.lower() or 'min(' in formula_text.lower():
           return False, "max()/min() requires comma-separated arguments, e.g., max(A, B)"
       return False, f"Syntax error: {e.msg}"
   except Exception as e:
       return False, f"Parse error: {str(e)}"

   validator = FormulaValidator(allowed_variable_names)
   validator.visit(tree)

   if validator.errors:
       error_msg = "; ".join(validator.errors)
       return False, error_msg

   return True, ""


class FormulaEvaluator(ast.NodeVisitor):
   """Safely evaluate arithmetic expressions and max()/min() calls."""

   def __init__(self, variable_values: Dict[str, float]):
       self.variable_values = variable_values
       self.error = None

   def visit_Expression(self, node):
       return self.visit(node.body)

   def visit_Constant(self, node):
       if isinstance(node.value, (int, float)):
           return float(node.value)
       self.error = f"Unsupported constant type: {type(node.value).__name__}"
       return None

   def visit_Num(self, node):
       return float(node.n)

   def visit_Name(self, node):
       if node.id in self.variable_values:
           return self.variable_values[node.id]
       self.error = f"Missing variable value: {node.id}"
       return None

   def visit_BinOp(self, node):
       left = self.visit(node.left)
       if self.error or left is None:
           return None

       right = self.visit(node.right)
       if self.error or right is None:
           return None

       ops = {
           ast.Add: operator.add,
           ast.Sub: operator.sub,
           ast.Mult: operator.mul,
           ast.Div: operator.truediv,
       }

       op_func = ops.get(node.op.__class__)
       if not op_func:
           self.error = f"Unsupported binary operation: {node.op.__class__.__name__}"
           return None

       try:
           if isinstance(node.op, ast.Div) and right == 0:
               self.error = "Division by zero"
               return None
           return op_func(left, right)
       except Exception as e:
           self.error = f"Evaluation error: {str(e)}"
           return None

   def visit_UnaryOp(self, node):
       operand = self.visit(node.operand)
       if self.error or operand is None:
           return None

       if isinstance(node.op, ast.USub):
           return -operand

       self.error = f"Unsupported unary operation: {node.op.__class__.__name__}"
       return None

   def visit_Call(self, node):
       if not isinstance(node.func, ast.Name):
           self.error = "Complex function calls not allowed"
           return None

       func_name = node.func.id
       if func_name not in ("max", "min"):
           self.error = f"Function call not allowed: {func_name}()"
           return None

       if not node.args:
           self.error = f"{func_name}() requires comma-separated arguments, e.g., {func_name}(A, B)"
           return None

       args = []
       for arg in node.args:
           value = self.visit(arg)
           if self.error or value is None:
               return None
           args.append(value)

       try:
           func = max if func_name == "max" else min
           return func(args)
       except Exception as e:
           self.error = f"Error in {func_name}(): {str(e)}"
           return None


def evaluate_formula(formula_text: str, variable_values: Dict[str, float]) -> Union[float, None]:
   """
   Safely evaluates a formula using only arithmetic expressions and max()/min() calls.

   Examples:
       evaluate_formula("0.15*CAT1 + 0.15*CAT2 + 0.6*FAT", {"CAT1": 80, "CAT2": 85, "FAT": 90})
       evaluate_formula("0.05*GLA + max(0.6*F + 0.25*max(Qz1, Qz2), 0.4*F + 0.25*Qz1 + 0.3*Qz2)", {"GLA": 90, "F": 82, "Qz1": 75, "Qz2": 88})
   """
   try:
       tree = ast.parse(formula_text, mode='eval')
   except SyntaxError as e:
       raise ValueError(f"Formula syntax error: {e.msg}")
   except Exception as e:
       raise ValueError(f"Formula parse error: {str(e)}")

   evaluator = FormulaEvaluator(variable_values)
   result = evaluator.visit(tree)

   if evaluator.error:
       raise ValueError(evaluator.error)

   if result is None:
       raise ValueError("Formula evaluation returned no result")

   return float(result)
