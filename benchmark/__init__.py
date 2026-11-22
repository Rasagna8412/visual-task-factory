"""Visual Task Factory - Benchmark Module"""
from .vlm_client import VLMClient, VLMResponse, get_vlm_client
from .evaluator import BenchmarkEvaluator, run_benchmark
from .report_generator import ReportGenerator, generate_benchmark_reports
from .dashboard_builder import DashboardBuilder, build_dashboard

__all__ = [
    "VLMClient",
    "VLMResponse",
    "get_vlm_client",
    "BenchmarkEvaluator",
    "run_benchmark",
    "ReportGenerator",
    "generate_benchmark_reports",
    "DashboardBuilder",
    "build_dashboard",
]
