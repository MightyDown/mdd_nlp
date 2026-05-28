from __future__ import annotations
from schema.player import Role, ROLE_DISPLAY_NAME, FACTION_GOAL


def build_role_instructions(role: Role) -> str:
    """构建角色 system instructions。"""
    name = ROLE_DISPLAY_NAME[role]

    if role == Role.WEREWOLF:
        return f"""你是{name}，属于狼人阵营。
你的目标：{FACTION_GOAL[role.faction]}

狼人规则：
- 夜晚你可以击杀一名玩家，你认识其他狼人同伴
- 白天你必须伪装成村民，参与讨论和投票
- 你的发言不能暴露你或同伴的狼人身份
- 投票时要尽量引导村民互相猜忌，保护自己和同伴

策略提示：
- 白天发言要装作在分析线索，不要沉默
- 可以适度质疑其他玩家，但不要太激进引人注意
- 投票时可以和同伴保持一致以增加对好人的票数压力
- 如果同伴被怀疑，要适当替其辩护但不能太明显"""
    else:
        return f"""你是{name}，属于好人阵营。
你的目标：{FACTION_GOAL[role.faction]}

村民规则：
- 你没有特殊能力，只能通过白天的发言和投票找出狼人
- 仔细分析每位玩家的发言，寻找矛盾和不自然之处
- 狼人会很活跃但可能前后矛盾，注意观察投票一致性

策略提示：
- 发言要表达你的推理，引用具体玩家的发言
- 投票时要说出你的理由，不要跟风盲投
- 如果某个玩家发言含糊、回避质疑，很可能是狼人
- 找到逻辑漏洞并指出，引导其他好人投票"""


def build_night_prompt(visible: dict) -> str:
    """构建狼人夜晚决策 prompt。"""
    if "teammate_proposal" in visible:
        proposal = visible["teammate_proposal"]
        return f"""你的狼人同伴提议击杀 {proposal['target_id']}。
理由：{proposal['reasoning']}

存活玩家：{visible['alive_players']}

请做出最终决定。你可以：
1. 同意同伴的提议
2. 否决并选择其他目标（说明理由）

以 JSON 格式返回：{{"target_id": "玩家ID", "reasoning": "你的理由"}}"""
    else:
        return f"""夜晚降临，你作为狼人需要选择今晚击杀的目标。

存活玩家（不含狼人同伴）：{[p for p in visible['alive_players'] if p not in visible.get('werewolf_teammates', [])]}

请选择你认为最合适的击杀目标并给出理由。
以 JSON 格式返回：{{"target_id": "玩家ID", "reasoning": "你的理由"}}"""


def build_speech_prompt(visible: dict) -> str:
    """构建白天发言 prompt。"""
    speeches = visible.get("speeches", {})
    history_str = ""
    if speeches:
        history_str = "\n已发言内容：\n" + "\n".join(f"{pid}: {text}" for pid, text in speeches.items())

    return f"""白天讨论阶段。你的身份是{ROLE_DISPLAY_NAME[Role(visible['my_role'])]}。

当前存活玩家：{visible['alive_players']}
已淘汰玩家：{visible.get('eliminated_players', [])}
{history_str}

请发表你的看法。要求：
1. 引用之前某位玩家的发言（如果已有发言）
2. 说出你的推理
3. 给出怀疑对象或信任对象

只返回发言文本，不需要 JSON。"""


def build_vote_prompt(visible: dict, candidates: list[str]) -> str:
    """构建投票 prompt。"""
    speeches = visible.get("speeches", {})
    history_str = ""
    if speeches:
        history_str = "\n发言记录：\n" + "\n".join(f"{pid}: {text}" for pid, text in speeches.items())

    candidates_str = ", ".join(candidates)

    return f"""投票阶段。根据刚才的发言，请投票放逐一名玩家。

{history_str}

可选投票目标：{candidates_str}

以 JSON 格式返回：{{"target_id": "玩家ID", "reason": "你的投票理由"}}"""
