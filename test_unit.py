"""
单元测试
测试 validators, symbols, config 解析
不依赖 FXCM API（可离线运行）
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# symbols.py 测试
# ──────────────────────────────────────────────────────────────

from symbols import (
    tv_to_fxcm, fxcm_to_tv, normalize_symbol,
    is_valid_symbol, format_for_display,
)


class TestSymbols:
    def test_tv_to_fxcm_with_slash(self):
        assert tv_to_fxcm("EUR/USD") == "EUR/USD"

    def test_tv_to_fxcm_empty(self):
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            tv_to_fxcm("")

    def test_tv_to_fxcm_with_spaces(self):
        assert tv_to_fxcm("  EUR/USD  ") == "EUR/USD"

    def test_fxcm_to_tv(self):
        assert fxcm_to_tv("EUR/USD") == "EUR/USD"

    def test_normalize_symbol(self):
        assert normalize_symbol("  eur/usd  ") == "EUR/USD"
        assert normalize_symbol("NATGAS") == "NATGAS"

    def test_is_valid_symbol_true(self):
        assert is_valid_symbol("EUR/USD") is True
        assert is_valid_symbol("GBP/USD") is True
        assert is_valid_symbol("XAU/USD") is True
        assert is_valid_symbol("NATGAS") is True
        assert is_valid_symbol("GER30") is True

    def test_is_valid_symbol_false(self):
        assert is_valid_symbol("") is False
        assert is_valid_symbol("   ") is False
        assert is_valid_symbol("EUR") is False       # 无 /
        assert is_valid_symbol("EUR//USD") is False  # 多斜杠
        assert is_valid_symbol("12/USD") is False    # 含数字
        assert is_valid_symbol("EU/RSD1") is False    # 含数字

    def test_format_for_display(self):
        assert format_for_display("eur/usd") == "EUR/USD"
        assert format_for_display("XAU/USD") == "XAU/USD"


# ──────────────────────────────────────────────────────────────
# config.py 测试
# ──────────────────────────────────────────────────────────────

class TestConfigEnvOverride:
    """测试环境变量覆盖 config.json 的行为"""

    def test_config_loads_with_env_vars(self, monkeypatch, tmp_path):
        """环境变量提供所有敏感字段时，即使 config.json 缺失也能加载"""
        # 清除任何已存在的单例
        from config import Config
        Config._instance = None

        monkeypatch.setenv("FXCM_USERNAME", "test_user")
        monkeypatch.setenv("FXCM_PASSWORD", "test_pass")
        monkeypatch.setenv("WEBHOOK_TOKEN", "test_token")

        # 创建空 config.json
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({}))

        # 临时替换路径
        import config as config_module
        old_path = config_module.CONFIG_FILE
        config_module.CONFIG_FILE = cfg_file

        try:
            cfg = Config()
            assert cfg.fxcm_username == "test_user"
            assert cfg.fxcm_password == "test_pass"
            assert cfg.webhook_token == "test_token"
        finally:
            config_module.CONFIG_FILE = old_path
            Config._instance = None

    def test_config_missing_credentials_raises(self, monkeypatch, tmp_path):
        """缺少凭据时抛出 ValueError"""
        from config import Config
        Config._instance = None

        # 不设置任何环境变量
        monkeypatch.delenv("FXCM_USERNAME", raising=False)
        monkeypatch.delenv("FXCM_PASSWORD", raising=False)
        monkeypatch.delenv("WEBHOOK_TOKEN", raising=False)

        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({}))

        import config as config_module
        old_path = config_module.CONFIG_FILE
        config_module.CONFIG_FILE = cfg_file

        try:
            with pytest.raises(ValueError, match="FXCM_USERNAME"):
                Config()
        finally:
            config_module.CONFIG_FILE = old_path
            Config._instance = None


# ──────────────────────────────────────────────────────────────
# validators.py 测试（mock config）
# ──────────────────────────────────────────────────────────────

class MockConfig:
    webhook_token = "secret_token"

class TestValidators:
    """测试请求验证，需要 mock config"""

    def test_verify_token_correct(self, monkeypatch):
        import validators
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())
        assert validators.verify_token("secret_token") is True

    def test_verify_token_wrong(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())
        with pytest.raises(ValidationError):
            validators.verify_token("wrong_token")

    def test_verify_token_empty(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())
        with pytest.raises(ValidationError):
            validators.verify_token("")

    def test_validate_minimal_valid(self, monkeypatch):
        """必填字段齐全的最简合法请求"""
        import validators
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {
            "symbol": "EUR/USD",
            "direction": "BUY",
            "amount": 10000,
            "token": "secret_token",
        }
        result = validators._validate_json(data)
        assert result["symbol"] == "EUR/USD"
        assert result["direction"] == "BUY"
        assert result["amount"] == 10000
        assert result["order_type"] == "MARKET"  # 默认值
        assert result["rate"] is None

    def test_validate_all_fields(self, monkeypatch):
        """所有字段都提供的完整请求"""
        import validators
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {
            "symbol": "EUR/USD",
            "direction": "SELL",
            "amount": 5000,
            "order_type": "LIMIT",
            "rate": 1.0850,
            "stop_rate": 1.0800,
            "limit_rate": 1.0900,
            "token": "secret_token",
        }
        result = validators._validate_json(data)
        assert result["order_type"] == "LIMIT"
        assert result["rate"] == 1.0850
        assert result["stop_rate"] == 1.0800
        assert result["limit_rate"] == 1.0900

    def test_validate_missing_symbol(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"direction": "BUY", "amount": 10000, "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "MISSING_FIELD"
        assert exc_info.value.field == "symbol"

    def test_validate_missing_amount(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"symbol": "EUR/USD", "direction": "BUY", "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "MISSING_FIELD"
        assert exc_info.value.field == "amount"

    def test_validate_invalid_direction(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"symbol": "EUR/USD", "direction": "HOLD", "amount": 10000, "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "INVALID_DIRECTION"

    def test_validate_negative_amount(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"symbol": "EUR/USD", "direction": "BUY", "amount": -100, "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "INVALID_AMOUNT"

    def test_validate_invalid_order_type(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"symbol": "EUR/USD", "direction": "BUY", "amount": 10000,
                "order_type": "FOK", "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "INVALID_ORDER_TYPE"

    def test_validate_invalid_rate(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"symbol": "EUR/USD", "direction": "BUY", "amount": 10000,
                "order_type": "LIMIT", "rate": -1.0, "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "INVALID_RATE"

    def test_validate_amount_as_string_fails(self, monkeypatch):
        import validators
        from validators import ValidationError
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())

        data = {"symbol": "EUR/USD", "direction": "BUY", "amount": "ten thousand",
                "token": "secret_token"}
        with pytest.raises(ValidationError) as exc_info:
            validators._validate_json(data)
        assert exc_info.value.code == "INVALID_AMOUNT"

    def test_validate_direction_case_insensitive(self, monkeypatch):
        """direction 大小写不敏感"""
        import validators
        monkeypatch.setattr("validators.get_config", lambda: MockConfig())
        dir_map = {"B": "BUY", "S": "SELL"}

        for direction in ["buy", "B", "Buy", "sell", "S", "Sell"]:
            data = {"symbol": "EUR/USD", "direction": direction,
                    "amount": 10000, "token": "secret_token"}
            result = validators._validate_json(data)
            expected = dir_map.get(direction.upper()) or direction.upper()
            assert result["direction"] == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
