"""Engine 层单元测试 — state.py + rules.py + AgentProxy，不依赖 LLM。"""
from __future__ import annotations
import pytest
from schema.player import Role, Faction
from schema.state import Phase
from schema.actions import NightAction, Vote
from engine.state import (
    create_game, transition_phase, apply_kill, apply_day_death,
    apply_elimination, record_votes, record_speech, advance_round,
    get_visible_state, set_winner,
)
from engine.rules import check_win, tally_votes, get_alive_players, get_werewolves
from engine.game import AgentProxy, _to_night_action, _to_vote


# ---- helpers ----

def make_state(werewolf_ids=("p1", "p2"), villager_ids=("p3", "p4", "p5", "p6")):
    pids = list(werewolf_ids + villager_ids)
    return create_game("test", pids, list(werewolf_ids))


# ---- rules.py: check_win ----

class TestWinCheck:
    def test_no_winner_initially(self):
        assert check_win(make_state()) is None

    def test_villager_win_all_wolves_dead(self):
        state = make_state(werewolf_ids=(), villager_ids=("p1", "p2"))
        assert check_win(state) == "villager"

    def test_werewolf_win_by_equal(self):
        state = make_state(werewolf_ids=("p1", "p2"), villager_ids=("p3", "p4"))
        assert check_win(state) == "werewolf"

    def test_werewolf_win_by_outnumber(self):
        state = make_state(werewolf_ids=("p1", "p2", "p3"), villager_ids=("p4", "p5"))
        assert check_win(state) == "werewolf"

    def test_no_winner_mid_game(self):
        state = make_state(werewolf_ids=("p1", "p2"), villager_ids=("p3", "p4", "p5"))
        assert check_win(state) is None


# ---- rules.py: tally_votes ----

class TestTallyVotes:
    def test_clear_winner(self):
        state = make_state()
        state.votes = {"p1": "p3", "p2": "p3", "p5": "p6"}
        assert tally_votes(state) == "p3"

    def test_tie_returns_none(self):
        state = make_state()
        state.votes = {"p1": "p3", "p2": "p4"}
        assert tally_votes(state) is None

    def test_no_votes(self):
        assert tally_votes(make_state()) is None

    def test_unanimous(self):
        state = make_state()
        state.votes = {"p1": "p3", "p2": "p3", "p3": "p5", "p5": "p3", "p6": "p3"}
        assert tally_votes(state) == "p3"

    def test_three_way_tie(self):
        state = make_state()
        state.votes = {"p1": "p3", "p2": "p4", "p5": "p6"}
        assert tally_votes(state) is None


# ---- rules.py: get_alive_players / get_werewolves ----

class TestGetPlayers:
    def test_get_alive_players(self):
        state = make_state()
        alive = get_alive_players(state)
        assert len(alive) == 6

    def test_get_alive_players_after_kill(self):
        state = make_state()
        state = apply_kill(state, "p3")
        state = apply_day_death(state)
        alive = get_alive_players(state)
        assert len(alive) == 5
        assert "p3" not in [p.id for p in alive]

    def test_get_werewolves(self):
        state = make_state()
        wolves = get_werewolves(state)
        assert {w.id for w in wolves} == {"p1", "p2"}

    def test_get_werewolves_dead_not_counted(self):
        state = make_state()
        state = apply_kill(state, "p1")
        state = apply_day_death(state)
        wolves = get_werewolves(state)
        assert [w.id for w in wolves] == ["p2"]


# ---- state.py: create_game ----

class TestCreateGame:
    def test_initial_state(self):
        state = create_game("g1", ["p1", "p2", "p3"], ["p1"])
        assert state.game_id == "g1"
        assert state.phase == Phase.NIGHT
        assert state.round == 1
        assert state.winner is None

    def test_role_assignment(self):
        state = create_game("g1", ["p1", "p2", "p3", "p4"], ["p1", "p3"])
        roles = {p.id: p.role for p in state.players}
        assert roles["p1"] == Role.WEREWOLF
        assert roles["p3"] == Role.WEREWOLF
        assert roles["p2"] == Role.VILLAGER
        assert roles["p4"] == Role.VILLAGER


# ---- state.py: transition_phase ----

class TestTransitionPhase:
    def test_night_to_day_speech(self):
        state = make_state()
        state = transition_phase(state, Phase.DAY_SPEECH)
        assert state.phase == Phase.DAY_SPEECH

    def test_to_ended(self):
        state = make_state()
        state = transition_phase(state, Phase.ENDED)
        assert state.phase == Phase.ENDED


# ---- state.py: apply_kill / apply_day_death ----

class TestKillFlow:
    def test_apply_kill_sets_target(self):
        state = apply_kill(make_state(), "p3")
        assert state.night_kill_target == "p3"

    def test_apply_day_death_marks_dead(self):
        state = make_state()
        state = apply_kill(state, "p3")
        state = apply_day_death(state)
        p3 = next(p for p in state.players if p.id == "p3")
        assert not p3.alive
        assert "p3" in state.eliminated_players
        assert state.night_kill_target is None

    def test_apply_day_death_no_kill_target(self):
        state = make_state()
        new_state = apply_day_death(state)
        assert new_state == state


# ---- state.py: apply_elimination ----

class TestApplyElimination:
    def test_player_dies(self):
        state = make_state()
        state = apply_elimination(state, "p3")
        p3 = next(p for p in state.players if p.id == "p3")
        assert not p3.alive
        assert "p3" in state.eliminated_players

    def test_clears_votes(self):
        state = make_state()
        state = record_votes(state, {"p1": "p3"}, {"p1": "reason"})
        state = apply_elimination(state, "p3")
        assert state.votes == {}
        assert state.vote_reasons == {}


# ---- state.py: record_votes / record_speech / advance_round ----

class TestRecording:
    def test_record_votes(self):
        state = make_state()
        state = record_votes(state, {"p1": "p3"}, {"p1": "suspicious"})
        assert state.votes == {"p1": "p3"}
        assert state.vote_reasons == {"p1": "suspicious"}

    def test_record_speech(self):
        state = make_state()
        state = record_speech(state, "p1", "hello")
        assert state.speeches == {"p1": "hello"}

    def test_record_multiple_speeches(self):
        state = make_state()
        state = record_speech(state, "p1", "a")
        state = record_speech(state, "p2", "b")
        assert state.speeches == {"p1": "a", "p2": "b"}

    def test_advance_round(self):
        state = make_state()
        state = record_speech(state, "p1", "x")
        state = record_votes(state, {"p1": "p3"}, {"p1": "r"})
        state = advance_round(state)
        assert state.round == 2
        assert state.speeches == {}
        assert state.votes == {}
        assert state.vote_reasons == {}


# ---- state.py: set_winner ----

class TestSetWinner:
    def test_sets_winner_and_ends(self):
        state = make_state()
        state = set_winner(state, "werewolf")
        assert state.winner == "werewolf"
        assert state.phase == Phase.ENDED


# ---- state.py: get_visible_state (信息隔离) ----

class TestVisibleState:
    def test_werewolf_sees_teammates(self):
        state = make_state()
        visible = get_visible_state(state, "p1")
        assert "werewolf_teammates" in visible
        assert "p2" in visible["werewolf_teammates"]
        assert "p1" not in visible["werewolf_teammates"]

    def test_villager_sees_no_teammates(self):
        state = make_state()
        visible = get_visible_state(state, "p3")
        assert "werewolf_teammates" not in visible

    def test_both_see_public_info(self):
        state = make_state()
        w_visible = get_visible_state(state, "p1")
        v_visible = get_visible_state(state, "p3")
        assert w_visible["my_id"] == "p1"
        assert v_visible["my_id"] == "p3"
        assert w_visible["alive_players"] == v_visible["alive_players"]

    def test_speeches_visible_in_day(self):
        state = make_state()
        state = transition_phase(state, Phase.DAY_SPEECH)
        state = record_speech(state, "p1", "hello")
        visible = get_visible_state(state, "p3")
        assert "speeches" in visible
        assert visible["speeches"] == {"p1": "hello"}

    def test_speeches_not_visible_at_night(self):
        state = make_state()
        state = record_speech(state, "p1", "hello")
        visible = get_visible_state(state, "p3")
        assert "speeches" not in visible

    def test_villager_sees_own_role(self):
        state = make_state()
        visible = get_visible_state(state, "p3")
        assert visible["my_role"] == "villager"

    def test_werewolf_sees_own_role(self):
        state = make_state()
        visible = get_visible_state(state, "p1")
        assert visible["my_role"] == "werewolf"


# ---- game.py: AgentProxy ----

class TestAgentProxy:
    @pytest.mark.asyncio
    async def test_night_act_returns_none_for_villager(self):
        proxy = AgentProxy(player_id="p1", on_night=None, on_speech=lambda v: "ok", on_vote=lambda v, c: Vote(voter_id="p1", target_id="p2"))
        assert await proxy.night_act({}, ["p1", "p2"]) is None

    @pytest.mark.asyncio
    async def test_vote_from_dict(self):
        async def mock_vote(visible, candidates):
            return {"voter_id": "p1", "target_id": "p2", "reason": "sus"}
        proxy = AgentProxy(player_id="p1", on_night=None, on_speech=lambda v: "ok", on_vote=mock_vote)
        result = await proxy.vote({}, ["p1", "p2"])
        assert isinstance(result, Vote)
        assert result.target_id == "p2"

    @pytest.mark.asyncio
    async def test_vote_from_object(self):
        async def mock_vote(visible, candidates):
            return Vote(voter_id="p1", target_id="p2", reason="sus")
        proxy = AgentProxy(player_id="p1", on_night=None, on_speech=lambda v: "ok", on_vote=mock_vote)
        result = await proxy.vote({}, ["p1", "p2"])
        assert isinstance(result, Vote)
        assert result.target_id == "p2"

    @pytest.mark.asyncio
    async def test_speak_returns_string(self):
        async def mock_speak(visible):
            return "hello world"
        proxy = AgentProxy(player_id="p1", on_night=None, on_speech=mock_speak, on_vote=lambda v, c: Vote(voter_id="p1", target_id="p2"))
        result = await proxy.speak({})
        assert result == "hello world"


class TestConversion:
    def test_to_night_action_from_dict(self):
        raw = {"actor_id": "p1", "action_type": "kill", "target_id": "p3", "reasoning": "test"}
        action = _to_night_action(raw)
        assert isinstance(action, NightAction)
        assert action.target_id == "p3"

    def test_to_night_action_from_object(self):
        obj = NightAction(actor_id="p1", action_type="kill", target_id="p3")
        assert _to_night_action(obj) is obj

    def test_to_vote_from_dict(self):
        raw = {"voter_id": "p1", "target_id": "p2", "reason": "sus"}
        vote = _to_vote(raw)
        assert isinstance(vote, Vote)
        assert vote.target_id == "p2"

    def test_to_vote_from_object(self):
        obj = Vote(voter_id="p1", target_id="p2")
        assert _to_vote(obj) is obj
