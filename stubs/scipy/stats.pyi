from typing import Optional

class Power_divergenceResult:  # noqa: N801
    @property
    def pvalue(self) -> float: ...

def chisquare(f_obs: list[int], f_exp: Optional[list[int]] = None) -> Power_divergenceResult: ...
