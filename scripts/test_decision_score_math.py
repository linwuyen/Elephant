#!/usr/bin/env python3
from build_decision_scores import WEIGHTS, real_yoy


def close(a, b, eps=1e-10):
    assert a is not None
    assert abs(a - b) <= eps, (a, b)


def main():
    close(real_yoy(10.0, 5.0), (1.10 / 1.05 - 1.0) * 100.0)
    close(real_yoy(0.0, 2.0), (1.0 / 1.02 - 1.0) * 100.0)
    close(real_yoy(-5.0, 3.0), (0.95 / 1.03 - 1.0) * 100.0)
    assert real_yoy(None, 2.0) is None
    assert real_yoy(10.0, None) is None
    assert real_yoy(10.0, -100.0) is None

    financial = WEIGHTS['financial']
    close(sum(financial.values()), 1.0)
    assert financial['exchange_rate'] == 0.0
    close(financial['m1b'], 5 / 17)
    close(financial['m2'], 4 / 17)
    close(financial['credit'], 5 / 17)
    close(financial['interest_rate'], 3 / 17)
    print('DECISION SCORE MATH TEST PASS')


if __name__ == '__main__':
    main()
