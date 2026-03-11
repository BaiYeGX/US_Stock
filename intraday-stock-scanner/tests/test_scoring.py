from app.scoring.intraday_score import compute_ias
from app.scoring.premarket_score import compute_pms


def test_pms_and_ias():
    pools = {"gap": [1,2,3], "pm_dollar_vol": [1,2,3], "atr": [2,3,4], "prev_day_trend": [10,20,30]}
    pms = compute_pms(2,2,3,20,50,pools)
    assert pms > 0
    ipools = {"rs_benchmark":[0,1,2], "rs_sector":[0,1,2], "rvol":[1,2,3], "atr20":[2,3,4], "spread":[0.02,0.05,0.1], "dollar5m":[1,2,3]}
    ias = compute_ias(80,1,1,2,3,0.05,2,"trend_up","long",80,ipools)
    assert ias > 70
