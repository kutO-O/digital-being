"""
Digital Being — Evolution Sandbox
Stage 30: Safe testing environment for generated code.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("digital_being.evolution_sandbox")

class EvolutionSandbox:
    """
    Safe sandbox for testing generated code.
    
    Features:
    - Isolated execution
    - Resource limits
    - Automated testing
    - Performance measurement
    - Rollback support
    """
    
    # Resource limits
    MAX_EXECUTION_TIME = 5.0  # seconds
    MAX_MEMORY_MB = 100  # megabytes
    
    def __init__(self, state_path: Path, sandbox_dir: Path) -> None:
        self._state_path = state_path / "evolution_sandbox.json"
        self._sandbox_dir = sandbox_dir
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        self._state = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "total_execution_time": 0.0,
            "test_history": [],
        }
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load sandbox state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info("EvolutionSandbox: loaded state")
            except Exception as e:
                log.error(f"EvolutionSandbox: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save sandbox state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"EvolutionSandbox: failed to save state: {e}")
    
    def test_module(
        self,
        module_code: str,
        module_name: str,
        test_cases: list[dict] | None = None
    ) -> dict:
        """
        Test generated module in sandbox.
        
        Args:
            module_code: Module code to test
            module_name: Module name
            test_cases: Optional test cases to run
        
        Returns:
            Test results
        """
        start_time = time.time()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            dir=self._sandbox_dir,
            delete=False,
            encoding='utf-8'
        ) as f:
            temp_path = Path(f.name)
            f.write(module_code)
        
        try:
            # Test syntax by importing
            result = self._test_import(temp_path, module_name)
            
            if not result["success"]:
                return self._record_test_result(
                    module_name=module_name,
                    passed=False,
                    error=result["error"],
                    execution_time=time.time() - start_time
                )
            
            # Run test cases if provided
            if test_cases:
                test_results = self._run_test_cases(temp_path, module_name, test_cases)
                
                return self._record_test_result(
                    module_name=module_name,
                    passed=test_results["all_passed"],
                    test_cases=test_results["results"],
                    execution_time=time.time() - start_time
                )
            
            # Basic test passed
            return self._record_test_result(
                module_name=module_name,
                passed=True,
                execution_time=time.time() - start_time
            )
        
        finally:
            # Cleanup
            try:
                temp_path.unlink()
            except Exception as e:
                log.warning(f"Failed to cleanup temp file: {e}")
    
    def _test_import(self, module_path: Path, module_name: str) -> dict:
        """
        Test if module can be imported.
        
        Args:
            module_path: Path to module file
            module_name: Module name
        
        Returns:
            Test result
        """
        test_code = f'''
import sys
sys.path.insert(0, "{module_path.parent}")
try:
    import {module_path.stem}
    print("IMPORT_SUCCESS")
except Exception as e:
    print(f"IMPORT_ERROR: {{e}}")
'''
        
        try:
            result = subprocess.run(
                ['python', '-c', test_code],
                capture_output=True,
                text=True,
                timeout=self.MAX_EXECUTION_TIME
            )
            
            if "IMPORT_SUCCESS" in result.stdout:
                return {"success": True, "error": None}
            else:
                error = result.stdout.strip() or result.stderr.strip()
                return {"success": False, "error": error}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Import timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_test_cases(
        self,
        module_path: Path,
        module_name: str,
        test_cases: list[dict]
    ) -> dict:
        """
        Run test cases on module.
        
        Args:
            module_path: Path to module
            module_name: Module name
            test_cases: Test cases to run
        
        Returns:
            Test results
        """
        results = []
        all_passed = True
        
        for i, test_case in enumerate(test_cases):
            test_name = test_case.get("name", f"test_{i}")
            test_input = test_case.get("input", None)
            expected_output = test_case.get("expected", None)
            
            # Generate test code
            test_code = self._generate_test_code(
                module_path,
                module_name,
                test_input,
                expected_output
            )
            
            try:
                result = subprocess.run(
                    ['python', '-c', test_code],
                    capture_output=True,
                    text=True,
                    timeout=self.MAX_EXECUTION_TIME
                )
                
                passed = "TEST_PASSED" in result.stdout
                error = None if passed else result.stdout.strip() or result.stderr.strip()
                
                results.append({
                    "name": test_name,
                    "passed": passed,
                    "error": error
                })
                
                if not passed:
                    all_passed = False
            
            except subprocess.TimeoutExpired:
                results.append({
                    "name": test_name,
                    "passed": False,
                    "error": "Test timeout"
                })
                all_passed = False
            
            except Exception as e:
                results.append({
                    "name": test_name,
                    "passed": False,
                    "error": str(e)
                })
                all_passed = False
        
        return {
            "all_passed": all_passed,
            "results": results
        }
    
    def _generate_test_code(
        self,
        module_path: Path,
        module_name: str,
        test_input: Any,
        expected_output: Any
    ) -> str:
        """
        Generate test code for a test case.
        
        Args:
            module_path: Path to module
            module_name: Module name  
            test_input: Test input
            expected_output: Expected output
        
        Returns:
            Test code
        """
        return f'''
import sys
sys.path.insert(0, "{module_path.parent}")

try:
    from {module_path.stem} import *
    
    # Run test
    result = process({repr(test_input)})
    expected = {repr(expected_output)}
    
    if result == expected:
        print("TEST_PASSED")
    else:
        print(f"TEST_FAILED: expected {{expected}}, got {{result}}")
except Exception as e:
    print(f"TEST_ERROR: {{e}}")
'''
    
    def _record_test_result(
        self,
        module_name: str,
        passed: bool,
        error: str | None = None,
        test_cases: list[dict] | None = None,
        execution_time: float = 0.0
    ) -> dict:
        """
        Record test result.
        
        Args:
            module_name: Module name
            passed: Whether test passed
            error: Error message if failed
            test_cases: Individual test case results
            execution_time: Total execution time
        
        Returns:
            Test result dict
        """
        result = {
            "module_name": module_name,
            "passed": passed,
            "error": error,
            "test_cases": test_cases,
            "execution_time": execution_time,
            "timestamp": time.time()
        }
        
        # Update state
        self._state["tests_run"] += 1
        if passed:
            self._state["tests_passed"] += 1
        else:
            self._state["tests_failed"] += 1
        
        self._state["total_execution_time"] += execution_time
        
        # Keep recent history (last 100)
        self._state["test_history"].append({
            "module": module_name,
            "passed": passed,
            "timestamp": time.time()
        })
        if len(self._state["test_history"]) > 100:
            self._state["test_history"] = self._state["test_history"][-100:]
        
        self._save_state()
        
        log.info(
            f"EvolutionSandbox: test {'PASSED' if passed else 'FAILED'} for {module_name} "
            f"in {execution_time:.2f}s"
        )
        
        return result
    
    def benchmark_performance(
        self,
        module_code: str,
        module_name: str,
        benchmark_input: Any,
        iterations: int = 10
    ) -> dict:
        """
        Benchmark module performance.
        
        Args:
            module_code: Module code
            module_name: Module name
            benchmark_input: Input for benchmark
            iterations: Number of iterations
        
        Returns:
            Benchmark results
        """
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            dir=self._sandbox_dir,
            delete=False,
            encoding='utf-8'
        ) as f:
            temp_path = Path(f.name)
            f.write(module_code)
        
        try:
            benchmark_code = f'''
import sys
import time
sys.path.insert(0, "{temp_path.parent}")

from {temp_path.stem} import *

times = []
for i in range({iterations}):
    start = time.time()
    process({repr(benchmark_input)})
    times.append(time.time() - start)

avg_time = sum(times) / len(times)
min_time = min(times)
max_time = max(times)

print(f"AVG:{{avg_time:.6f}} MIN:{{min_time:.6f}} MAX:{{max_time:.6f}}")
'''
            
            result = subprocess.run(
                ['python', '-c', benchmark_code],
                capture_output=True,
                text=True,
                timeout=self.MAX_EXECUTION_TIME * iterations
            )
            
            # Parse results
            output = result.stdout.strip()
            if "AVG:" in output:
                parts = output.split()
                avg = float(parts[0].split(":")[1])
                min_t = float(parts[1].split(":")[1])
                max_t = float(parts[2].split(":")[1])
                
                return {
                    "success": True,
                    "avg_time": avg,
                    "min_time": min_t,
                    "max_time": max_t,
                    "iterations": iterations
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to parse benchmark results"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        
        finally:
            try:
                temp_path.unlink()
            except:
                pass
    
    def get_stats(self) -> dict:
        """Get sandbox statistics."""
        pass_rate = 0.0
        if self._state["tests_run"] > 0:
            pass_rate = self._state["tests_passed"] / self._state["tests_run"]
        
        avg_execution = 0.0
        if self._state["tests_run"] > 0:
            avg_execution = self._state["total_execution_time"] / self._state["tests_run"]
        
        return {
            "tests_run": self._state["tests_run"],
            "tests_passed": self._state["tests_passed"],
            "tests_failed": self._state["tests_failed"],
            "pass_rate": pass_rate,
            "avg_execution_time": avg_execution,
            "recent_tests": len(self._state["test_history"])
        }
