"""System Usability Scale (Brooke, 1996): 10 тверджень, відповіді 1-5.

Запуск: uv run python -m eval.sus eval/sus_responses.csv   (формат: eval/sus_example.csv)
CSV: respondent,q1,...,q10
"""
import csv
import statistics
import sys


def sus_score(answers: list[int]) -> float:
    """Непарні твердження позитивні (відповідь - 1), парні негативні (5 - відповідь)."""
    if len(answers) != 10 or not all(1 <= a <= 5 for a in answers):
        raise ValueError("SUS needs 10 answers in range 1..5")
    total = sum(a - 1 if i % 2 == 0 else 5 - a for i, a in enumerate(answers))
    return total * 2.5


def main(path: str) -> None:
    scores = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            score = sus_score([int(row[f"q{i}"]) for i in range(1, 11)])
            scores.append(score)
            print(f"{row['respondent']}: {score:.1f}")
    if not scores:
        raise SystemExit("У файлі немає відповідей")
    print(f"\nSUS mean = {statistics.mean(scores):.1f}, n = {len(scores)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Використання: python -m eval.sus <файл.csv>")
    main(sys.argv[1])
