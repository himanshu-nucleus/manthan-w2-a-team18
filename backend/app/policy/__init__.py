"""Policy engine: rules are rows in ``policy_rules``; each ``rule_type`` has one evaluator.

To add a rule type: subclass ``RuleType`` in ``rules.py``, decorate it with
``@register``, then insert a ``policy_rules`` row that uses it. The engine core
does not change.
"""
