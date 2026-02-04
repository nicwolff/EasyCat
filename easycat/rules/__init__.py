"""Rules engine for transaction auto-categorization."""

import re
from dataclasses import dataclass
from decimal import Decimal

from easycat.db.models import PatternType, Rule


@dataclass
class RuleMatch:
    """Result of a rule matching a transaction."""

    rule: Rule
    matched_text: str
    category_id: int


class RulesEngine:
    """Engine for matching transactions against categorization rules."""

    def __init__(self, rules: list[Rule]):
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        self._compiled_patterns: dict[int, re.Pattern | None] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        for rule in self._rules:
            if rule.pattern_type == PatternType.REGEX:
                try:
                    self._compiled_patterns[rule.id] = re.compile(rule.pattern, re.IGNORECASE)
                except re.error:
                    self._compiled_patterns[rule.id] = None
            else:
                self._compiled_patterns[rule.id] = None

    def find_match(
        self,
        description: str,
        vendor_name: str | None,
        amount: Decimal,
    ) -> RuleMatch | None:
        """Find the first matching rule for a transaction."""
        for rule in self._rules:
            if not rule.is_active:
                continue
            if not self._amount_in_range(amount, rule):
                continue
            matched_text = self._match_pattern(rule, description, vendor_name)
            if matched_text is not None:
                return RuleMatch(
                    rule=rule,
                    matched_text=matched_text,
                    category_id=rule.category_id,
                )
        return None

    def find_all_matches(
        self,
        description: str,
        vendor_name: str | None,
        amount: Decimal,
    ) -> list[RuleMatch]:
        """Find all matching rules for a transaction (in priority order)."""
        matches = []
        for rule in self._rules:
            if not rule.is_active:
                continue
            if not self._amount_in_range(amount, rule):
                continue
            matched_text = self._match_pattern(rule, description, vendor_name)
            if matched_text is not None:
                matches.append(
                    RuleMatch(
                        rule=rule,
                        matched_text=matched_text,
                        category_id=rule.category_id,
                    )
                )
        return matches

    def _amount_in_range(self, amount: Decimal, rule: Rule) -> bool:
        """Check if amount is within rule's min/max constraints."""
        abs_amount = abs(amount)
        if rule.min_amount is not None and abs_amount < rule.min_amount:
            return False
        return rule.max_amount is None or abs_amount <= rule.max_amount

    def _match_pattern(
        self,
        rule: Rule,
        description: str,
        vendor_name: str | None,
    ) -> str | None:
        """Check if rule pattern matches description or vendor name."""
        texts_to_check = [description]
        if vendor_name:
            texts_to_check.append(vendor_name)
        for text in texts_to_check:
            match_result = self._check_pattern(rule, text)
            if match_result is not None:
                return match_result
        return None

    def _check_pattern(self, rule: Rule, text: str) -> str | None:
        """Check if pattern matches text based on pattern type."""
        if rule.pattern_type == PatternType.EXACT:
            if text.upper() == rule.pattern.upper():
                return text
        elif rule.pattern_type == PatternType.CONTAINS:
            if rule.pattern.upper() in text.upper():
                return rule.pattern
        else:  # PatternType.REGEX
            compiled = self._compiled_patterns.get(rule.id)
            if compiled:
                match = compiled.search(text)
                if match:
                    return match.group(0)
        return None

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        if rule.pattern_type == PatternType.REGEX:
            try:
                self._compiled_patterns[rule.id] = re.compile(rule.pattern, re.IGNORECASE)
            except re.error:
                self._compiled_patterns[rule.id] = None
        else:
            self._compiled_patterns[rule.id] = None

    def remove_rule(self, rule_id: int) -> None:
        """Remove a rule from the engine."""
        self._rules = [r for r in self._rules if r.id != rule_id]
        self._compiled_patterns.pop(rule_id, None)

    def update_rules(self, rules: list[Rule]) -> None:
        """Replace all rules with a new set."""
        self._rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        self._compiled_patterns.clear()
        self._compile_patterns()

    @property
    def rules(self) -> list[Rule]:
        """Get all rules in priority order."""
        return self._rules.copy()


def create_rule_from_transaction(
    name: str,
    pattern: str,
    pattern_type: PatternType,
    category_id: int,
    priority: int = 0,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> Rule:
    """Helper to create a new rule from a categorized transaction."""
    from datetime import datetime

    return Rule(
        id=None,
        name=name,
        pattern=pattern,
        pattern_type=pattern_type,
        category_id=category_id,
        min_amount=min_amount,
        max_amount=max_amount,
        priority=priority,
        is_active=True,
        created_at=datetime.now(),
    )
