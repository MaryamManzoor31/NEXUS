import itertools
from collections import defaultdict
from .models import *


def shared_counts(ds: Dataset):
    """number of students who selected both courses (unordered pair)"""
    # These counts help schedulers avoid clashes between popular course pairs.
    sh = defaultdict(int)
    for st in ds.students.values():
        for a, b in itertools.combinations(sorted(st.selections), 2):
            sh[(a, b)] += 1
    return sh


def starts_for(duration):
    """legal start slots: session must stay inside one day"""
    return [d * PERIODS + p for d in range(DAYS) for p in range(PERIODS - duration + 1)]


def sec_slots(ds, placement, sid):
    # Return None unless every session for the section has a placement.
    out = set()
    for k, spec in enumerate(ds.section_sessions(sid)):
        if (sid, k) not in placement:
            return None
        s = placement[(sid, k)][0]
        out |= set(range(s, s + spec.duration))
    return out
