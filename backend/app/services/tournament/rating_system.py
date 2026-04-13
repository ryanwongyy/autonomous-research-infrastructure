import trueskill
from dataclasses import dataclass

from app.config import settings


@dataclass
class RatingUpdate:
    mu: float
    sigma: float
    conservative_rating: float
    elo: float
    mu_change: float
    elo_change: float


class RatingSystem:
    def __init__(self):
        self.ts_env = trueskill.TrueSkill(
            mu=settings.trueskill_mu,
            sigma=settings.trueskill_sigma,
            beta=settings.trueskill_beta,
            tau=settings.trueskill_tau,
            draw_probability=settings.trueskill_draw_probability,
        )

    def create_rating(self) -> trueskill.Rating:
        return self.ts_env.create_rating()

    def conservative_rating(self, rating: trueskill.Rating) -> float:
        return rating.mu - 3 * rating.sigma

    def update_trueskill(
        self,
        winner_mu: float,
        winner_sigma: float,
        loser_mu: float,
        loser_sigma: float,
        drawn: bool = False,
    ) -> tuple[trueskill.Rating, trueskill.Rating]:
        winner = self.ts_env.create_rating(mu=winner_mu, sigma=winner_sigma)
        loser = self.ts_env.create_rating(mu=loser_mu, sigma=loser_sigma)
        new_winner, new_loser = self.ts_env.rate_1vs1(winner, loser, drawn=drawn)
        return new_winner, new_loser

    def update_elo(
        self,
        winner_elo: float,
        loser_elo: float,
        drawn: bool = False,
        k: float | None = None,
    ) -> tuple[float, float]:
        k = k or settings.elo_k_factor
        expected_winner = 1.0 / (1.0 + 10 ** ((loser_elo - winner_elo) / 400))
        expected_loser = 1.0 - expected_winner

        if drawn:
            score_winner = 0.5
            score_loser = 0.5
        else:
            score_winner = 1.0
            score_loser = 0.0

        new_winner_elo = winner_elo + k * (score_winner - expected_winner)
        new_loser_elo = loser_elo + k * (score_loser - expected_loser)
        return new_winner_elo, new_loser_elo

    def process_match(
        self,
        a_mu: float,
        a_sigma: float,
        a_elo: float,
        b_mu: float,
        b_sigma: float,
        b_elo: float,
        result: str,  # "a_wins", "b_wins", "draw"
    ) -> tuple[RatingUpdate, RatingUpdate]:
        if result == "a_wins":
            new_ts_a, new_ts_b = self.update_trueskill(a_mu, a_sigma, b_mu, b_sigma, drawn=False)
            new_elo_a, new_elo_b = self.update_elo(a_elo, b_elo, drawn=False)
        elif result == "b_wins":
            new_ts_b, new_ts_a = self.update_trueskill(b_mu, b_sigma, a_mu, a_sigma, drawn=False)
            new_elo_b, new_elo_a = self.update_elo(b_elo, a_elo, drawn=False)
        else:  # draw
            new_ts_a, new_ts_b = self.update_trueskill(a_mu, a_sigma, b_mu, b_sigma, drawn=True)
            new_elo_a, new_elo_b = self.update_elo(a_elo, b_elo, drawn=True)

        update_a = RatingUpdate(
            mu=new_ts_a.mu,
            sigma=new_ts_a.sigma,
            conservative_rating=self.conservative_rating(new_ts_a),
            elo=new_elo_a,
            mu_change=new_ts_a.mu - a_mu,
            elo_change=new_elo_a - a_elo,
        )
        update_b = RatingUpdate(
            mu=new_ts_b.mu,
            sigma=new_ts_b.sigma,
            conservative_rating=self.conservative_rating(new_ts_b),
            elo=new_elo_b,
            mu_change=new_ts_b.mu - b_mu,
            elo_change=new_elo_b - b_elo,
        )
        return update_a, update_b


rating_system = RatingSystem()
