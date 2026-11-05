"""SIH26141 backend package root.

Milestone 1 added ``backend.quantum``: the verified quantum core.
Milestone 2 adds ``backend.protocol``: the reference prototype QDS protocol
engine built on top of it.

Dependency direction is strictly one way::

    backend.protocol  ->  backend.quantum

``backend.quantum`` imports nothing from ``backend.protocol``. No attack,
noise, detection, security, API or frontend subpackage exists yet; those are
later milestones.
"""
