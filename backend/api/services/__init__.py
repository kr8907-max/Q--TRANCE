"""Service layer.

One module per concern. Each translates a typed request into calls on the M1-M6
packages and returns plain dictionaries that the route binds to a response model.
No domain logic lives here: no hashing, no teleportation, no transcript
validation, no detection rule, no threshold arithmetic and no security
interpretation is implemented in this package.
"""
