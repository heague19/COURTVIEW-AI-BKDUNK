"""
run_all_tests.py

Core Foundation 전체 테스트 스위트
- 모든 테스트 자동 탐색 및 실행
- 모듈별/타입별 결과 집계
- 상세 보고서 생성

Usage:
    python run_all_tests.py              # 모든 테스트 실행
    python run_all_tests.py --unit       # 단위 테스트만
    python run_all_tests.py --perf       # 성능 테스트만
    python run_all_tests.py --integration # 통합 테스트만
    python run_all_tests.py --module config  # 특정 모듈만

Author: COURTVIEW Team
Version: 1.0.0
"""

import sys
import time
import subprocess
import io
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, field

# Windows 콘솔 UTF-8 설정
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass  # 이미 래핑된 경우 무시


# ==================== 테스트 결과 데이터 클래스 ====================
@dataclass
class TestFileResult:
    """개별 테스트 파일 결과"""
    file_path: Path
    module_name: str
    test_type: str  # unit, performance, integration
    passed: int
    failed: int
    duration: float
    exit_code: int
    output: str = ""


@dataclass
class TestSummary:
    """전체 테스트 요약"""
    total_files: int = 0
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_duration: float = 0.0
    results: List[TestFileResult] = field(default_factory=list)

    def add_result(self, result: TestFileResult) -> None:
        """결과 추가"""
        self.total_files += 1
        self.total_tests += result.passed + result.failed
        self.total_passed += result.passed
        self.total_failed += result.failed
        self.total_duration += result.duration
        self.results.append(result)

    @property
    def pass_rate(self) -> float:
        """통과율 (%)"""
        if self.total_tests == 0:
            return 0.0
        return (self.total_passed / self.total_tests) * 100


# ==================== 테스트 러너 ====================
class TestRunner:
    """테스트 실행 및 관리"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "tests"
        self.summary = TestSummary()

    def find_test_files(
        self,
        test_type: str = None,
        module_name: str = None
    ) -> List[Tuple[Path, str, str]]:
        """
        테스트 파일 탐색

        Args:
            test_type: "unit", "performance", "integration" 중 하나 (None이면 전체)
            module_name: 특정 모듈만 (None이면 전체)

        Returns:
            (파일 경로, 모듈명, 테스트 타입) 튜플 리스트
        """
        test_files = []

        # core_foundation 하위 탐색
        core_foundation_tests = self.tests_dir / "core_foundation"

        if not core_foundation_tests.exists():
            return test_files

        # 모듈별 탐색
        for module_dir in sorted(core_foundation_tests.iterdir()):
            if not module_dir.is_dir():
                continue

            module = module_dir.name

            # 특정 모듈만 필터링
            if module_name and module != module_name:
                continue

            # unit, performance, integration 폴더 탐색
            for type_dir in ["unit", "performance", "integration"]:
                type_path = module_dir / type_dir

                # 특정 타입만 필터링
                if test_type and type_dir != test_type:
                    continue

                if not type_path.exists():
                    continue

                # test_*.py 파일 찾기
                for test_file in sorted(type_path.glob("test_*.py")):
                    test_files.append((test_file, module, type_dir))

        return test_files

    def run_test_file(self, test_file: Path, module_name: str, test_type: str) -> TestFileResult:
        """
        개별 테스트 파일 실행

        Args:
            test_file: 테스트 파일 경로
            module_name: 모듈 이름
            test_type: 테스트 타입

        Returns:
            TestFileResult
        """
        print(f"  실행: {test_file.name} ", end="", flush=True)

        start_time = time.time()

        try:
            # 테스트 실행
            result = subprocess.run(
                [sys.executable, str(test_file)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=120  # 2분 타임아웃
            )

            duration = time.time() - start_time
            exit_code = result.returncode

            # 출력에서 결과 파싱
            output = result.stdout + result.stderr
            passed, failed = self._parse_test_output(output)

            # 결과 표시
            if exit_code == 0:
                print(f"✅ {passed}/{passed+failed} ({duration:.1f}s)")
            else:
                print(f"❌ {passed}/{passed+failed} ({duration:.1f}s)")

            return TestFileResult(
                file_path=test_file,
                module_name=module_name,
                test_type=test_type,
                passed=passed,
                failed=failed,
                duration=duration,
                exit_code=exit_code,
                output=output
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏱️ TIMEOUT ({duration:.1f}s)")

            return TestFileResult(
                file_path=test_file,
                module_name=module_name,
                test_type=test_type,
                passed=0,
                failed=1,
                duration=duration,
                exit_code=1,
                output="Test timeout"
            )

        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 ERROR ({str(e)})")

            return TestFileResult(
                file_path=test_file,
                module_name=module_name,
                test_type=test_type,
                passed=0,
                failed=1,
                duration=duration,
                exit_code=1,
                output=str(e)
            )

    def _parse_test_output(self, output: str) -> Tuple[int, int]:
        """
        테스트 출력에서 통과/실패 수 파싱

        Returns:
            (passed, failed) 튜플
        """
        passed = 0
        failed = 0

        for line in output.split('\n'):
            # "테스트 결과: X/Y 통과" 패턴
            if "통과" in line and "/" in line:
                try:
                    parts = line.split(":")[-1].strip()
                    if "/" in parts:
                        passed_str = parts.split("/")[0].strip()
                        passed = int(passed_str)

                        # 실패 수 추출
                        if "실패" in output:
                            for fail_line in output.split('\n'):
                                if "실패한 테스트:" in fail_line:
                                    # 다음 줄부터 실패 목록
                                    fail_count = 0
                                    idx = output.split('\n').index(fail_line) + 1
                                    for i in range(idx, len(output.split('\n'))):
                                        if output.split('\n')[i].strip().startswith("-"):
                                            fail_count += 1
                                        elif output.split('\n')[i].strip().startswith("="):
                                            break
                                    failed = fail_count
                                    break
                        break
                except (ValueError, IndexError):
                    pass

            # "성능 테스트 결과: X/Y 통과" 패턴
            if "성능 테스트 결과" in line and "/" in line:
                try:
                    parts = line.split(":")[-1].strip()
                    if "/" in parts:
                        passed_str = parts.split("/")[0].strip()
                        total_str = parts.split("/")[1].split()[0].strip()
                        passed = int(passed_str)
                        total = int(total_str)
                        failed = total - passed
                        break
                except (ValueError, IndexError):
                    pass

        return passed, failed

    def run_all_tests(
        self,
        test_type: str = None,
        module_name: str = None
    ) -> TestSummary:
        """
        모든 테스트 실행

        Args:
            test_type: 테스트 타입 필터
            module_name: 모듈 필터

        Returns:
            TestSummary
        """
        test_files = self.find_test_files(test_type, module_name)

        if not test_files:
            print("❌ 테스트 파일을 찾을 수 없습니다.")
            return self.summary

        print(f"\n📋 총 {len(test_files)}개 테스트 파일 발견\n")

        # 타입별로 그룹화
        by_type = {}
        for file, module, ttype in test_files:
            if ttype not in by_type:
                by_type[ttype] = []
            by_type[ttype].append((file, module, ttype))

        # 순서: unit → performance → integration
        for ttype in ["unit", "performance", "integration"]:
            if ttype not in by_type:
                continue

            print(f"\n{'='*60}")
            print(f"🧪 {ttype.upper()} 테스트")
            print(f"{'='*60}\n")

            for file, module, _ in by_type[ttype]:
                result = self.run_test_file(file, module, ttype)
                self.summary.add_result(result)

        return self.summary

    def print_summary(self) -> None:
        """테스트 요약 출력"""
        print(f"\n\n{'='*70}")
        print("📊 Core Foundation 테스트 결과 요약")
        print(f"{'='*70}\n")

        # 모듈별 요약
        by_module = {}
        for result in self.summary.results:
            module = result.module_name
            if module not in by_module:
                by_module[module] = {"passed": 0, "failed": 0, "duration": 0.0}

            by_module[module]["passed"] += result.passed
            by_module[module]["failed"] += result.failed
            by_module[module]["duration"] += result.duration

        print("📦 모듈별 결과:")
        for module in sorted(by_module.keys()):
            stats = by_module[module]
            total = stats["passed"] + stats["failed"]
            rate = (stats["passed"] / total * 100) if total > 0 else 0

            status = "✅" if stats["failed"] == 0 else "⚠️"
            print(f"  {status} {module:15s}: {stats['passed']:3d}/{total:3d} ({rate:5.1f}%) - {stats['duration']:6.1f}s")

        # 타입별 요약
        print(f"\n🔬 타입별 결과:")
        by_type = {}
        for result in self.summary.results:
            ttype = result.test_type
            if ttype not in by_type:
                by_type[ttype] = {"passed": 0, "failed": 0}

            by_type[ttype]["passed"] += result.passed
            by_type[ttype]["failed"] += result.failed

        for ttype in ["unit", "performance", "integration"]:
            if ttype not in by_type:
                continue

            stats = by_type[ttype]
            total = stats["passed"] + stats["failed"]
            rate = (stats["passed"] / total * 100) if total > 0 else 0

            status = "✅" if stats["failed"] == 0 else "⚠️"
            print(f"  {status} {ttype:15s}: {stats['passed']:3d}/{total:3d} ({rate:5.1f}%)")

        # 전체 요약
        print(f"\n{'─'*70}")
        print(f"📈 전체 결과:")
        print(f"  • 테스트 파일:  {self.summary.total_files}개")
        print(f"  • 총 테스트:    {self.summary.total_tests}개")
        print(f"  • 통과:         {self.summary.total_passed}개")
        print(f"  • 실패:         {self.summary.total_failed}개")
        print(f"  • 통과율:       {self.summary.pass_rate:.1f}%")
        print(f"  • 총 실행시간:  {self.summary.total_duration:.1f}초")

        # 실패한 테스트 상세
        if self.summary.total_failed > 0:
            print(f"\n❌ 실패한 테스트:")
            for result in self.summary.results:
                if result.failed > 0:
                    print(f"  • {result.module_name}/{result.test_type}/{result.file_path.name}")
                    print(f"    ({result.passed}/{result.passed + result.failed} 통과)")

        print(f"\n{'='*70}")

        # 최종 상태
        if self.summary.total_failed == 0:
            print("✅ 모든 테스트 통과!")
        else:
            print(f"⚠️  {self.summary.total_failed}개 테스트 실패")

        print(f"{'='*70}\n")


# ==================== 메인 ====================
def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Core Foundation 전체 테스트 스위트")
    parser.add_argument("--unit", action="store_true", help="단위 테스트만 실행")
    parser.add_argument("--perf", "--performance", action="store_true", help="성능 테스트만 실행")
    parser.add_argument("--integration", action="store_true", help="통합 테스트만 실행")
    parser.add_argument("--module", type=str, help="특정 모듈만 실행 (예: config)")

    # 실행 모드
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dev-mode", action="store_true",
                           help="개발 모드: 성능 실패를 경고로 처리")
    mode_group.add_argument("--ci-mode", action="store_true",
                           help="CI 모드: 기능 테스트만 필수")
    mode_group.add_argument("--strict", action="store_true",
                           help="엄격 모드: 모든 테스트 필수 (기본값)")

    args = parser.parse_args()

    # 프로젝트 루트
    project_root = Path(__file__).resolve().parent

    # 테스트 타입 결정
    test_type = None
    if args.unit:
        test_type = "unit"
    elif args.perf:
        test_type = "performance"
    elif args.integration:
        test_type = "integration"

    print("=" * 70)
    print("🧪 COURTVIEW Core Foundation 테스트 스위트")
    print("=" * 70)

    # 실행 모드 표시
    if args.dev_mode:
        print("🔧 실행 모드: 개발 모드 (성능 실패는 경고)")
    elif args.ci_mode:
        print("🤖 실행 모드: CI 모드 (기능 테스트만 필수)")
    elif args.strict:
        print("⚡ 실행 모드: 엄격 모드 (모든 테스트 필수)")
    else:
        print("📋 실행 모드: 표준 모드")

    if test_type:
        print(f"📌 필터: {test_type} 테스트만")
    if args.module:
        print(f"📌 필터: {args.module} 모듈만")

    # 테스트 실행
    runner = TestRunner(project_root)
    start_time = time.time()

    summary = runner.run_all_tests(test_type, args.module)

    elapsed = time.time() - start_time

    # 요약 출력
    runner.print_summary()

    # Exit code 결정 (모드에 따라)
    exit_code = 0

    if args.dev_mode:
        # 개발 모드: 성능 테스트 실패 무시
        perf_failures = sum(1 for r in summary.results
                           if r.test_type == "performance" and r.failed > 0)
        critical_failures = summary.total_failed - sum(r.failed for r in summary.results
                                                       if r.test_type == "performance")
        if critical_failures > 0:
            exit_code = 1
        elif perf_failures > 0:
            print(f"\n💡 개발 모드: {perf_failures}개 성능 테스트 실패는 무시됩니다.")

    elif args.ci_mode:
        # CI 모드: 단위 테스트와 통합 테스트만 체크
        critical_failures = sum(r.failed for r in summary.results
                               if r.test_type in ["unit", "integration"])
        if critical_failures > 0:
            exit_code = 1
        else:
            perf_failures = sum(r.failed for r in summary.results
                               if r.test_type == "performance")
            if perf_failures > 0:
                print(f"\n💡 CI 모드: {perf_failures}개 성능 테스트 실패는 무시됩니다.")

    else:
        # 표준/엄격 모드: 모든 실패 체크
        exit_code = 0 if summary.total_failed == 0 else 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
