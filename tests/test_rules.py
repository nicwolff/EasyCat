"""Tests for rules engine."""

from datetime import datetime
from decimal import Decimal

from easycat.db.models import PatternType, Rule
from easycat.rules import RuleMatch, RulesEngine, create_rule_from_transaction


def make_rule(
    id: int,
    name: str,
    pattern: str,
    pattern_type: PatternType,
    category_id: int = 1,
    priority: int = 0,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    is_active: bool = True,
) -> Rule:
    """Helper to create test rules."""
    return Rule(
        id=id,
        name=name,
        pattern=pattern,
        pattern_type=pattern_type,
        category_id=category_id,
        min_amount=min_amount,
        max_amount=max_amount,
        priority=priority,
        is_active=is_active,
        created_at=datetime.now(),
    )


class TestRuleMatch:
    """Tests for RuleMatch dataclass."""

    def test_rule_match_creation(self):
        """Test creating a RuleMatch."""
        rule = make_rule(1, "Test", "AMAZON", PatternType.CONTAINS)
        match = RuleMatch(rule=rule, matched_text="AMAZON", category_id=1)
        assert match.rule == rule
        assert match.matched_text == "AMAZON"
        assert match.category_id == 1


class TestRulesEngine:
    """Tests for RulesEngine."""

    def test_init_sorts_by_priority(self):
        """Test that rules are sorted by priority on init."""
        rules = [
            make_rule(1, "Low", "A", PatternType.CONTAINS, priority=1),
            make_rule(2, "High", "B", PatternType.CONTAINS, priority=10),
            make_rule(3, "Med", "C", PatternType.CONTAINS, priority=5),
        ]
        engine = RulesEngine(rules)
        assert engine.rules[0].name == "High"
        assert engine.rules[1].name == "Med"
        assert engine.rules[2].name == "Low"

    def test_find_match_contains(self):
        """Test finding a match with CONTAINS pattern."""
        rules = [
            make_rule(1, "Amazon", "AMAZON", PatternType.CONTAINS, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMAZON MKTPLACE PMTS", None, Decimal("50.00"))
        assert match is not None
        assert match.category_id == 5
        assert match.matched_text == "AMAZON"

    def test_find_match_contains_case_insensitive(self):
        """Test that CONTAINS matching is case insensitive."""
        rules = [
            make_rule(1, "Amazon", "amazon", PatternType.CONTAINS, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMAZON.COM", None, Decimal("50.00"))
        assert match is not None

    def test_find_match_exact(self):
        """Test finding a match with EXACT pattern."""
        rules = [
            make_rule(1, "Specific", "EXACT VENDOR", PatternType.EXACT, category_id=3),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("EXACT VENDOR", None, Decimal("100.00"))
        assert match is not None
        assert match.matched_text == "EXACT VENDOR"

    def test_find_match_exact_case_insensitive(self):
        """Test that EXACT matching is case insensitive."""
        rules = [
            make_rule(1, "Specific", "exact vendor", PatternType.EXACT, category_id=3),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("EXACT VENDOR", None, Decimal("100.00"))
        assert match is not None

    def test_find_match_exact_no_partial(self):
        """Test that EXACT pattern doesn't match partial text."""
        rules = [
            make_rule(1, "Specific", "VENDOR", PatternType.EXACT, category_id=3),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("VENDOR NAME", None, Decimal("100.00"))
        assert match is None

    def test_find_match_regex(self):
        """Test finding a match with REGEX pattern."""
        rules = [
            make_rule(1, "Amazon Pattern", r"AMZN.*MKTPLACE", PatternType.REGEX, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMZN PRIME MKTPLACE", None, Decimal("50.00"))
        assert match is not None
        assert "AMZN" in match.matched_text

    def test_find_match_regex_case_insensitive(self):
        """Test that REGEX matching is case insensitive."""
        rules = [
            make_rule(1, "Pattern", r"amazon", PatternType.REGEX, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMAZON.COM", None, Decimal("50.00"))
        assert match is not None

    def test_find_match_invalid_regex(self):
        """Test handling of invalid regex patterns."""
        rules = [
            make_rule(1, "Bad Regex", r"[invalid(", PatternType.REGEX, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("some text", None, Decimal("50.00"))
        assert match is None

    def test_find_match_respects_priority(self):
        """Test that higher priority rules match first."""
        rules = [
            make_rule(1, "Low", "AMAZON", PatternType.CONTAINS, category_id=1, priority=1),
            make_rule(2, "High", "AMAZON", PatternType.CONTAINS, category_id=2, priority=10),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMAZON", None, Decimal("50.00"))
        assert match.category_id == 2

    def test_find_match_skips_inactive(self):
        """Test that inactive rules are skipped."""
        rules = [
            make_rule(
                1,
                "Inactive",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=1,
                is_active=False,
                priority=10,
            ),
            make_rule(
                2,
                "Active",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=2,
                is_active=True,
                priority=1,
            ),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMAZON", None, Decimal("50.00"))
        assert match.category_id == 2

    def test_find_match_vendor_name(self):
        """Test matching against vendor name."""
        rules = [
            make_rule(1, "Amazon", "Amazon", PatternType.CONTAINS, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("Some purchase", "Amazon", Decimal("50.00"))
        assert match is not None
        assert match.category_id == 5

    def test_find_match_no_vendor_name(self):
        """Test matching when vendor name is None."""
        rules = [
            make_rule(1, "Test", "TEST", PatternType.CONTAINS, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("TEST PURCHASE", None, Decimal("50.00"))
        assert match is not None

    def test_find_match_no_match(self):
        """Test when no rules match."""
        rules = [
            make_rule(1, "Amazon", "AMAZON", PatternType.CONTAINS, category_id=5),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("WALMART", None, Decimal("50.00"))
        assert match is None

    def test_find_match_min_amount(self):
        """Test min_amount constraint."""
        rules = [
            make_rule(
                1,
                "Big Purchase",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=5,
                min_amount=Decimal("100.00"),
            ),
        ]
        engine = RulesEngine(rules)
        match_small = engine.find_match("AMAZON", None, Decimal("50.00"))
        assert match_small is None
        match_big = engine.find_match("AMAZON", None, Decimal("150.00"))
        assert match_big is not None

    def test_find_match_max_amount(self):
        """Test max_amount constraint."""
        rules = [
            make_rule(
                1,
                "Small Purchase",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=5,
                max_amount=Decimal("100.00"),
            ),
        ]
        engine = RulesEngine(rules)
        match_small = engine.find_match("AMAZON", None, Decimal("50.00"))
        assert match_small is not None
        match_big = engine.find_match("AMAZON", None, Decimal("150.00"))
        assert match_big is None

    def test_find_match_amount_range(self):
        """Test both min and max amount constraints."""
        rules = [
            make_rule(
                1,
                "Medium Purchase",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=5,
                min_amount=Decimal("50.00"),
                max_amount=Decimal("200.00"),
            ),
        ]
        engine = RulesEngine(rules)
        match_too_small = engine.find_match("AMAZON", None, Decimal("25.00"))
        assert match_too_small is None
        match_ok = engine.find_match("AMAZON", None, Decimal("100.00"))
        assert match_ok is not None
        match_too_big = engine.find_match("AMAZON", None, Decimal("300.00"))
        assert match_too_big is None

    def test_find_match_negative_amount(self):
        """Test that amount comparison uses absolute value."""
        rules = [
            make_rule(
                1,
                "Refund",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=5,
                min_amount=Decimal("50.00"),
            ),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("AMAZON REFUND", None, Decimal("-75.00"))
        assert match is not None

    def test_find_all_matches(self):
        """Test finding all matching rules."""
        rules = [
            make_rule(1, "Amazon", "AMAZON", PatternType.CONTAINS, category_id=1, priority=10),
            make_rule(2, "Online", "AMAZON", PatternType.CONTAINS, category_id=2, priority=5),
            make_rule(3, "Other", "WALMART", PatternType.CONTAINS, category_id=3, priority=1),
        ]
        engine = RulesEngine(rules)
        matches = engine.find_all_matches("AMAZON", None, Decimal("50.00"))
        assert len(matches) == 2
        assert matches[0].category_id == 1
        assert matches[1].category_id == 2

    def test_find_all_matches_empty(self):
        """Test find_all_matches returns empty list when no match."""
        rules = [
            make_rule(1, "Amazon", "AMAZON", PatternType.CONTAINS, category_id=1),
        ]
        engine = RulesEngine(rules)
        matches = engine.find_all_matches("WALMART", None, Decimal("50.00"))
        assert matches == []

    def test_find_all_matches_skips_inactive(self):
        """Test that find_all_matches skips inactive rules."""
        rules = [
            make_rule(1, "Active", "AMAZON", PatternType.CONTAINS, category_id=1, is_active=True),
            make_rule(
                2, "Inactive", "AMAZON", PatternType.CONTAINS, category_id=2, is_active=False
            ),
        ]
        engine = RulesEngine(rules)
        matches = engine.find_all_matches("AMAZON", None, Decimal("50.00"))
        assert len(matches) == 1
        assert matches[0].category_id == 1

    def test_find_all_matches_skips_out_of_range(self):
        """Test that find_all_matches skips rules with out-of-range amounts."""
        rules = [
            make_rule(
                1,
                "Small",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=1,
                max_amount=Decimal("100.00"),
            ),
            make_rule(
                2,
                "Big",
                "AMAZON",
                PatternType.CONTAINS,
                category_id=2,
                min_amount=Decimal("100.00"),
            ),
        ]
        engine = RulesEngine(rules)
        matches = engine.find_all_matches("AMAZON", None, Decimal("50.00"))
        assert len(matches) == 1
        assert matches[0].category_id == 1

    def test_regex_no_match(self):
        """Test regex pattern that doesn't match returns None."""
        rules = [
            make_rule(1, "Pattern", r"xyz\d+", PatternType.REGEX, category_id=1),
        ]
        engine = RulesEngine(rules)
        match = engine.find_match("no numbers here", None, Decimal("50.00"))
        assert match is None

    def test_regex_with_invalid_pattern_skips(self):
        """Test that invalid regex patterns are skipped in matching."""
        rules = [
            make_rule(1, "Invalid", r"[bad(", PatternType.REGEX, category_id=1),
            make_rule(2, "Valid", "TEXT", PatternType.CONTAINS, category_id=2),
        ]
        engine = RulesEngine(rules)
        matches = engine.find_all_matches("TEXT", None, Decimal("50.00"))
        assert len(matches) == 1
        assert matches[0].category_id == 2

    def test_check_pattern_invalid_regex_only(self):
        """Test _check_pattern with only an invalid regex rule."""
        rules = [
            make_rule(1, "Invalid", r"[bad(", PatternType.REGEX, category_id=1),
        ]
        engine = RulesEngine(rules)
        result = engine._check_pattern(rules[0], "any text")
        assert result is None

    def test_add_rule(self):
        """Test adding a rule to the engine."""
        engine = RulesEngine([])
        rule = make_rule(1, "New", "TEST", PatternType.CONTAINS, category_id=1)
        engine.add_rule(rule)
        assert len(engine.rules) == 1
        match = engine.find_match("TEST", None, Decimal("50.00"))
        assert match is not None

    def test_add_rule_maintains_priority(self):
        """Test that add_rule maintains priority order."""
        rules = [
            make_rule(1, "High", "A", PatternType.CONTAINS, priority=10),
        ]
        engine = RulesEngine(rules)
        engine.add_rule(make_rule(2, "Higher", "B", PatternType.CONTAINS, priority=20))
        engine.add_rule(make_rule(3, "Low", "C", PatternType.CONTAINS, priority=1))
        assert engine.rules[0].priority == 20
        assert engine.rules[1].priority == 10
        assert engine.rules[2].priority == 1

    def test_add_rule_regex(self):
        """Test adding a regex rule compiles the pattern."""
        engine = RulesEngine([])
        rule = make_rule(1, "Regex", r"test.*pattern", PatternType.REGEX)
        engine.add_rule(rule)
        match = engine.find_match("test some pattern", None, Decimal("50.00"))
        assert match is not None

    def test_add_rule_invalid_regex(self):
        """Test adding an invalid regex rule."""
        engine = RulesEngine([])
        rule = make_rule(1, "Bad", r"[invalid(", PatternType.REGEX)
        engine.add_rule(rule)
        assert len(engine.rules) == 1
        match = engine.find_match("[invalid(", None, Decimal("50.00"))
        assert match is None

    def test_remove_rule(self):
        """Test removing a rule from the engine."""
        rules = [
            make_rule(1, "Keep", "A", PatternType.CONTAINS),
            make_rule(2, "Remove", "B", PatternType.CONTAINS),
        ]
        engine = RulesEngine(rules)
        engine.remove_rule(2)
        assert len(engine.rules) == 1
        assert engine.rules[0].name == "Keep"

    def test_remove_rule_nonexistent(self):
        """Test removing a nonexistent rule does nothing."""
        rules = [make_rule(1, "Keep", "A", PatternType.CONTAINS)]
        engine = RulesEngine(rules)
        engine.remove_rule(999)
        assert len(engine.rules) == 1

    def test_update_rules(self):
        """Test replacing all rules."""
        initial_rules = [
            make_rule(1, "Old", "A", PatternType.CONTAINS),
        ]
        engine = RulesEngine(initial_rules)
        new_rules = [
            make_rule(2, "New1", "B", PatternType.CONTAINS, priority=10),
            make_rule(3, "New2", "C", PatternType.CONTAINS, priority=5),
        ]
        engine.update_rules(new_rules)
        assert len(engine.rules) == 2
        assert engine.rules[0].name == "New1"
        assert engine.rules[1].name == "New2"

    def test_rules_property_returns_copy(self):
        """Test that rules property returns a copy."""
        rules = [make_rule(1, "Test", "A", PatternType.CONTAINS)]
        engine = RulesEngine(rules)
        returned_rules = engine.rules
        returned_rules.clear()
        assert len(engine.rules) == 1

    def test_empty_engine(self):
        """Test engine with no rules."""
        engine = RulesEngine([])
        match = engine.find_match("anything", None, Decimal("50.00"))
        assert match is None
        matches = engine.find_all_matches("anything", None, Decimal("50.00"))
        assert matches == []


class TestCreateRuleFromTransaction:
    """Tests for create_rule_from_transaction helper."""

    def test_create_rule_basic(self):
        """Test creating a basic rule."""
        rule = create_rule_from_transaction(
            name="Amazon Rule",
            pattern="AMAZON",
            pattern_type=PatternType.CONTAINS,
            category_id=5,
        )
        assert rule.id is None
        assert rule.name == "Amazon Rule"
        assert rule.pattern == "AMAZON"
        assert rule.pattern_type == PatternType.CONTAINS
        assert rule.category_id == 5
        assert rule.is_active is True
        assert rule.priority == 0
        assert rule.min_amount is None
        assert rule.max_amount is None

    def test_create_rule_with_amounts(self):
        """Test creating a rule with amount constraints."""
        rule = create_rule_from_transaction(
            name="Big Amazon",
            pattern="AMAZON",
            pattern_type=PatternType.CONTAINS,
            category_id=5,
            priority=10,
            min_amount=Decimal("100.00"),
            max_amount=Decimal("500.00"),
        )
        assert rule.min_amount == Decimal("100.00")
        assert rule.max_amount == Decimal("500.00")
        assert rule.priority == 10

    def test_create_rule_created_at(self):
        """Test that created_at is set to current time."""
        before = datetime.now()
        rule = create_rule_from_transaction(
            name="Test",
            pattern="TEST",
            pattern_type=PatternType.CONTAINS,
            category_id=1,
        )
        after = datetime.now()
        assert before <= rule.created_at <= after
