from src import flip


def test_threshold_tiers_and_boundaries():
    # <= 10 -> 30%
    assert flip.threshold_for(3.50) == 0.30
    assert flip.threshold_for(10.0) == 0.30      # boundary: exactly 10 -> 30%
    # 10 < price <= 25 -> 25%
    assert flip.threshold_for(10.01) == 0.25
    assert flip.threshold_for(25.0) == 0.25      # boundary: exactly 25 -> 25%
    # price > 25 -> 22.5%
    assert flip.threshold_for(25.01) == 0.225
    assert flip.threshold_for(100.0) == 0.225
