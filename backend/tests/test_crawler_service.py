"""
爬蟲服務單元測試
測試 parse_money() 與 calculate_high_win_rate() 函式
"""

from app.service.crawler_service import parse_money, calculate_high_win_rate


class TestParseMoney:
    """parse_money() 金額解析"""

    def test_simple_number(self):
        """純數字"""
        assert parse_money("1000") == 1000

    def test_with_commas(self):
        """帶千分位逗號"""
        assert parse_money("1,000,000") == 1000000

    def test_with_dollar_sign(self):
        """帶 $ 符號"""
        assert parse_money("$500") == 500

    def test_with_nt_prefix(self):
        """帶 NT$ 前綴"""
        assert parse_money("NT$1,000") == 1000

    def test_with_spaces(self):
        """帶空白"""
        assert parse_money(" 2,000 ") == 2000

    def test_empty_string(self):
        """空字串回傳 0"""
        assert parse_money("") == 0

    def test_zero(self):
        """零"""
        assert parse_money("0") == 0

    def test_large_number(self):
        """大數值不超過 SQLite 上限"""
        result = parse_money("10,000,000,000")
        assert result <= 2**63 - 1


class TestCalculateHighWinRate:
    """calculate_high_win_rate() 紅色警戒判定"""

    def test_high_win_rate_true(self):
        """銷售率 >= 80% 且頭獎未兌領 >= 1 → True"""
        details = {"頭獎未兌領張數": "2"}
        assert calculate_high_win_rate(details, 85.0) is True

    def test_low_sales_rate(self):
        """銷售率 < 80% → False"""
        details = {"頭獎未兌領張數": "3"}
        assert calculate_high_win_rate(details, 50.0) is False

    def test_no_unclaimed(self):
        """頭獎未兌領 = 0 → False"""
        details = {"頭獎未兌領張數": "0"}
        assert calculate_high_win_rate(details, 90.0) is False

    def test_missing_field(self):
        """缺少頭獎未兌領欄位 → False"""
        details = {}
        assert calculate_high_win_rate(details, 90.0) is False

    def test_edge_exact_80(self):
        """銷售率剛好 80% 且有未兌領 → True"""
        details = {"頭獎未兌領張數": "1"}
        assert calculate_high_win_rate(details, 80.0) is True
