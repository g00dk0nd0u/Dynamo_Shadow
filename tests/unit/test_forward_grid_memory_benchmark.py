import pytest

from tools import benchmark_forward_grid_memory as benchmark


def test_current_grid_shares_y_coordinate_within_each_row():
    grid = benchmark._current_grid(12)

    assert grid[0]["y_m"] is grid[1]["y_m"]
    assert grid[1]["y_m"] is grid[2]["y_m"]
    assert grid[2]["y_m"] is not grid[3]["y_m"]


def test_contour_benchmark_rejects_prime_count_collapsing_to_one_dimension():
    with pytest.raises(ValueError, match="two-dimensional factorization"):
        benchmark.measure_contours(101)
