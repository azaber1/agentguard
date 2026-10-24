"""AgentGuard testing engine.

Pure Python: the sandbox, scenario library, agent adapters, deterministic
policy engine and scoring. Nothing in this package performs real side effects;
the only network I/O is the HTTP agent adapter calling the customer's agent.
"""
