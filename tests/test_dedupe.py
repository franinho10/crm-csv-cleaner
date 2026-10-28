from itertools import permutations

from crm_csv_cleaner.dedupe import group_by_keys

P1 = ("telefono", "+34600000001")
E1 = ("email", "b@example.com")
E2 = ("email", "z@example.org")


def test_transitive_chain_is_one_person():
    # A y B comparten teléfono; B y C comparten email -> A, B y C son la misma persona.
    assert group_by_keys([{P1}, {P1, E1}, {E1}, {E2}]) == [[0, 1, 2], [3]]


def test_link_that_appears_last_joins_earlier_groups():
    assert group_by_keys([{P1}, {E1}, {P1, E1}]) == [[0, 1, 2]]


def test_items_without_keys_are_singletons():
    assert group_by_keys([set(), set(), {P1}]) == [[0], [1], [2]]
    assert group_by_keys([]) == []


def test_grouping_does_not_depend_on_order():
    items = [{"a"}, {"a", "b"}, {"b"}, {"c"}, {"c", "d"}, {"e"}]
    expected = {frozenset({0, 1, 2}), frozenset({3, 4}), frozenset({5})}
    for perm in permutations(range(len(items))):
        groups = group_by_keys([items[i] for i in perm])
        assert {frozenset(perm[i] for i in g) for g in groups} == expected
