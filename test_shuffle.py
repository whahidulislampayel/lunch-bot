import random
from shuffle import batch_sizes, make_batches

def test_sizes():
    assert batch_sizes(21, 5) == [5, 4, 4, 4, 4]
    assert batch_sizes(25, 5) == [5, 5, 5, 5, 5]
    assert batch_sizes(20, 5) == [5, 5, 5, 5]
    assert batch_sizes(6, 5) == [3, 3]
    assert batch_sizes(1, 5) == [1]
    assert batch_sizes(0, 5) == []

def test_pair_always_together_and_sizes_kept():
    for n in range(1, 31):
        for seed in range(300):
            rng = random.Random(seed)
            people = list(range(n))
            pair = (0, 1)
            b = make_batches(people, {}, pair, 5, 0.5, rng)
            assert [len(x) for x in b] == batch_sizes(n, 5)
            assert sorted(sum(b, [])) == people
            if n >= 2:
                assert any(0 in x and 1 in x for x in b), (n, seed, b)

def test_fairness_pushes_late_people_early():
    late_person, early_person = 100, 200
    people = list(range(20)) + [late_person, early_person]
    lat = {late_person: 1.0, early_person: 0.0}
    first_late = first_early = 0
    for seed in range(2000):
        b = make_batches(people, lat, (), 5, 0.5, random.Random(seed))
        first_late += late_person in b[0]
        first_early += early_person in b[0]
    assert first_late > first_early * 2

if __name__ == "__main__":
    test_sizes(); test_pair_always_together_and_sizes_kept(); test_fairness_pushes_late_people_early()
    print("all shuffle tests passed")
