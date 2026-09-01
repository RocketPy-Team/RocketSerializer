"""Pure-Python re-implementation of OpenRocket's zero-lift drag build-up.

Computes the drag coefficient of a rocket directly from its .ork design file --
no OpenRocket JVM and no saved simulation required.  The physics is an exact
port of OpenRocket 24.12's ``BarrowmanDragCalculator`` and its per-component
calculators (skin friction, nose/transition pressure drag, base drag, fin
leading/trailing-edge drag, launch-lug and rail-button parasitic drag,
per-component CD overrides, and the CD -> axial-CD conversion).

Usage::

    from rocketserializer.dragmodel import load_rocket, DragBuildup

    rocket = load_rocket("rocket.ork")
    buildup = DragBuildup(rocket)
    result = buildup.evaluate(mach=0.8, reynolds=5.2e6, aoa=0.0)
    # result.cd, result.friction, result.pressure, result.base, result.cd_axial

    machs, cds = buildup.drag_curve()   # Cd(Mach) at sea-level ISA, AoA = 0
"""

from .buildup import DragBuildup, DragResult
from .components import Rocket, load_rocket

__all__ = ["DragBuildup", "DragResult", "Rocket", "load_rocket"]
