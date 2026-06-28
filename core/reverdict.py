from core.verdict import compute_verdict


def reverdict_from_raw(raw: dict) -> dict:
    return compute_verdict(
        raw["meta"], raw["spectral"], raw["integrity"],
        raw["loudness"], raw["vinyl"],
    )
