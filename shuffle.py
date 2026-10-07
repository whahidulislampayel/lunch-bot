"""Builds the day's lunch batches.

Rules:
  * Batches hold at most `max_size` people and are balanced (21 people -> 5/4/4/4/4).
  * The shuffle is weighted: people who ate in late batches recently tend to go earlier.
  * The pair (two people who must always eat together) is treated as one unit,
    so they always land in the same batch.
"""
import math
import random


def batch_sizes(n: int, max_size: int) -> list[int]:
    """Split n people into the fewest batches of at most max_size, as evenly as possible."""
    if n <= 0:
        return []
    k = math.ceil(n / max_size)
    base, extra = divmod(n, k)
    return [base + 1 if i < extra else base for i in range(k)]


def make_batches(people, lateness, pair, max_size=5, strength=0.5, rng=random):
    """
    people:    list of user ids eating today
    lateness:  {user_id: 0.0 (always early) .. 1.0 (always last)}; missing -> 0.5
    pair:      ids that must stay together (only enforced if both are present)
    strength:  0 = pure random, higher = stronger push toward fairness
    returns:   list of batches, each a list of user ids, in serving order
    """
    people = list(dict.fromkeys(people))  # drop duplicates, keep order
    pair_here = [p for p in pair if p in people]

    units = []
    if len(pair_here) == 2:
        units.append(tuple(pair_here))
        singles = [p for p in people if p not in pair_here]
    else:
        singles = people
    units += [(p,) for p in singles]

    def sort_key(unit):
        late = sum(lateness.get(p, 0.5) for p in unit) / len(unit)
        return rng.random() - strength * late

    queue = sorted(units, key=sort_key)
    sizes = batch_sizes(len(people), max_size)
    batches = [[] for _ in sizes]

    for batch, cap in zip(batches, sizes):
        while len(batch) < cap and queue:
            room = cap - len(batch)
            idx = next((j for j, u in enumerate(queue) if len(u) <= room), None)
            if idx is None:
                # Only the pair is left and just 1 seat remains here:
                # bump one person to the next batch so the pair fits together.
                bumped = batch.pop()
                queue.insert(1, (bumped,))
                continue
            batch.extend(queue.pop(idx))
    return batches
