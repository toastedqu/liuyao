from __future__ import annotations

from dataclasses import dataclass

from pydantic import JsonValue

from app.rules.models import FactLayer, RuleFact, RuleStatus


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    id: str
    name: str
    fact_types: frozenset[str]
    layer: FactLayer
    status: RuleStatus
    source_ids: tuple[str, ...]
    premise: str
    conclusion: str
    priority: int = 0
    exceptions: tuple[str, ...] = ()
    implemented: bool = True
    limitation: str | None = None


def _rule(
    id: str,
    name: str,
    fact_types: tuple[str, ...],
    layer: FactLayer,
    status: RuleStatus,
    source_ids: tuple[str, ...],
    premise: str,
    conclusion: str,
    *,
    priority: int = 0,
    exceptions: tuple[str, ...] = (),
    implemented: bool = True,
    limitation: str | None = None,
) -> RuleDefinition:
    return RuleDefinition(
        id=id,
        name=name,
        fact_types=frozenset(fact_types),
        layer=layer,
        status=status,
        source_ids=source_ids,
        premise=premise,
        conclusion=conclusion,
        priority=priority,
        exceptions=exceptions,
        implemented=implemented,
        limitation=limitation,
    )


RULES: tuple[RuleDefinition, ...] = (
    _rule(
        "ZSBY-008-USEFUL-MAPPING",
        "用神映射",
        ("USEFUL_GOD",),
        FactLayer.DERIVED,
        RuleStatus.AUTHORITATIVE,
        (
            "008_用神章:p0001",
            "008_用神章:p0002",
            "008_用神章:p0003",
            "008_用神章:p0004",
            "008_用神章:p0005",
            "008_用神章:p0006",
            "008_用神章:p0007",
            "031_各门类题头总注章:p0010",
            "035_飞伏神章:p0003",
            "035_飞伏神章:p0007",
            "035_飞伏神章:p0013",
            "035_飞伏神章:p0017",
            "041_天时章:p0002",
            "041_天时章:p0003",
            "041_天时章:p0005",
        ),
        "所占对象的语义已经明确。",
        "按原文映射为世爻、应爻或一种六亲。",
        exceptions=("姐丈、妹夫取世爻；表兄弟取应爻。",),
    ),
    _rule(
        "ZSBY-009-GOD-ROLES",
        "元神忌神仇神",
        ("YUAN_GOD", "TABOO_GOD", "ENEMY_GOD"),
        FactLayer.DERIVED,
        RuleStatus.AUTHORITATIVE,
        ("009_用神、元神、忌神、仇神章:p0001",),
        "用神五行已经确定。",
        "生用神者为元神，克用神者为忌神，克元神且生忌神者为仇神。",
    ),
    _rule(
        "ZSBY-014-LINE-ELEMENT-RELATION",
        "爻间五行生克",
        (
            "LINE_ELEMENT_RELATION",
            "MOVING_GENERATES_USEFUL",
            "MOVING_OVERCOMES_USEFUL",
        ),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("014_动静生克章:p0001", "014_动静生克章:p0004"),
        "比较两爻五行及动静状态。",
        "记录生、克、受生、受克或比和；效力另行求值。",
        exceptions=("静爻之间及动静之间的作用力不同，不得仅凭结构关系断吉凶。",),
    ),
    _rule(
        "ZSBY-015-CHANGED-LINE-RELATION",
        "动变生克冲合",
        (
            "CHANGED_ELEMENT_RELATION",
            "RETURN_GENERATE",
            "RETURN_OVERCOME",
            "RETURN_CLASH",
            "RETURN_COMBINE",
        ),
        FactLayer.RAW,
        RuleStatus.AUTHORITATIVE,
        (
            "015_动变生克冲合章:p0001",
            "015_动变生克冲合章:p0003",
            "015_动变生克冲合章:p0004",
        ),
        "本位爻发动并产生变爻。",
        "变爻只生克冲合本位动爻；日月可以作用于变爻。",
    ),
    _rule(
        "ZSBY-016-SEASONAL-STRENGTH",
        "四时旺相休囚",
        (
            "SEASONAL_STRENGTH",
            "CHANGED_SEASONAL_STRENGTH",
            "HIDDEN_SEASONAL_STRENGTH",
        ),
        FactLayer.DERIVED,
        RuleStatus.AUTHORITATIVE,
        tuple(f"016_四时旺相章:p{index:04d}" for index in range(1, 9)),
        "月建和爻支五行已知。",
        "按十二月建确定月建、旺、相、余气或休囚。",
    ),
    _rule(
        "ZSBY-018-DAY-ACTION",
        "日辰作用",
        ("DAY_RELATION", "CHANGED_DAY_RELATION", "HIDDEN_DAY_RELATION", "DAY_BREAK"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        tuple(f"018_日辰章:p{index:04d}" for index in range(2, 10)),
        "日辰与爻支、五行已知。",
        "记录日辰生克比扶、冲合及墓绝等作用。",
        exceptions=("日辰作用须与月建、动爻及生克多少合看。",),
    ),
    _rule(
        "ZSBY-019-SIX-GOD",
        "六神附和",
        ("SIX_GOD",),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("019_六神章:p0002", "019_六神章:p0003"),
        "六神已经按日干布于六爻。",
        "六神只能附和既有五行吉凶；青龙不能救凶，白虎螣蛇不能害吉。",
        exceptions=("玄武、朱雀只记录事象，不得独立决定吉凶。",),
    ),
    _rule(
        "ZSBY-019-SIX-GOD-CATEGORY",
        "六神门类加权",
        (),
        FactLayer.EFFECTIVE,
        RuleStatus.CONDITIONAL,
        ("019_六神章:p0003",),
        "所占属于家宅或坟茔。",
        "原文只说尤不可少，未给确定加权判据。",
        implemented=False,
        limitation="六神在家宅、坟茔中的特殊加权原文未给确定判据，暂不量化",
    ),
    _rule(
        "ZSBY-020-COMBINE",
        "六合与爻合",
        (
            "LINE_COMBINE",
            "BRANCH_COMBINE_PAIR",
            "MONTH_COMBINE",
            "DAY_COMBINE",
            "PRIMARY_SIX_HARMONY",
            "CHANGED_SIX_HARMONY",
            "CLASH_TO_HARMONY",
        ),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        (
            "020_六合章:p0001",
            "020_六合章:p0003",
            "020_六合章:p0004",
            "020_六合章:p0005",
            "020_六合章:p0006",
            "020_六合章:p0007",
            "020_六合章:p0008",
            "020_六合章:p0009",
            "020_六合章:p0010",
            "020_六合章:p0019",
            "020_六合章:p0022",
            "020_六合章:p0026",
        ),
        "出现六合支对、日月合爻、爻与爻合、动化合或六合卦。",
        "先记录合的结构，再按动静、有气无气和生克求值。",
        exceptions=("用神失陷无济；子丑等合在无生扶而受克时言克不言合。",),
    ),
    _rule(
        "ZSBY-021-THREE-HARMONY",
        "三合局",
        (
            "THREE_HARMONY",
            "THREE_HARMONY_PENDING",
            "THREE_HARMONY_EFFECT",
            "THREE_HARMONY_WORLD_EFFECT",
        ),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        tuple(f"021_三合章:p{index:04d}" for index in range(1, 11) if index != 2),
        "卦中动爻、变爻、暗动及日月形成三合支组。",
        "区分已成局、虚一待用、空破待实和入墓待冲。",
        exceptions=("成局本身不等于吉，须看局与用神、世爻的生克关系。",),
    ),
    _rule(
        "ZSBY-022-CLASH",
        "六冲与爻冲",
        (
            "LINE_CLASH",
            "BRANCH_CLASH_PAIR",
            "PRIMARY_SIX_CLASH",
            "CHANGED_SIX_CLASH",
        ),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        (
            "022_六冲章:p0001",
            "022_六冲章:p0003",
            "022_六冲章:p0004",
            "022_六冲章:p0005",
            "022_六冲章:p0008",
        ),
        "出现六冲支对、日月冲爻、动化冲或六冲卦。",
        "记录冲的结构；旺衰、动静和所占吉凶决定效力。",
    ),
    _rule(
        "ZSBY-023-PUNISHMENT",
        "三刑",
        ("LINE_PUNISHMENT", "BRANCH_PUNISHMENT_PAIR"),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("023_三刑章:p0001",),
        "出现三刑或自刑支组。",
        "记录刑的结构，不得脱离用神休囚和其他克害单独断凶。",
    ),
    _rule(
        "ZSBY-024-HARM-DISCARDED",
        "六害",
        ("LINE_HARM",),
        FactLayer.RAW,
        RuleStatus.DISCARDED,
        ("024_六害章:p0001",),
        "出现六害支对。",
        "只记录结构，预测权重恒为零。",
    ),
    _rule(
        "ZSBY-025-DARK-MOVEMENT",
        "暗动",
        ("DARK_MOVEMENT", "DARK_MOVEMENT_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        ("025_暗动章:p0001",),
        "旺相静爻受日辰冲。",
        "该爻转为暗动；吉凶取决于其对用神的角色和作用。",
    ),
    _rule(
        "ZSBY-026-MOVING-DAY-CLASH",
        "动散",
        ("MOVING_DAY_CLASH", "MOVING_DAY_CLASH_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        ("026_动散章:p0001",),
        "动爻受日辰冲或动爻相冲。",
        "旺相有气者不散；休囚者仅极少数可能散。",
    ),
    _rule(
        "ZSBY-027-HEXAGRAM-CHANGE",
        "卦变生克墓绝",
        ("HEXAGRAM_CHANGE_RELATION", "HEXAGRAM_CHANGE_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        (
            "027_卦变生克墓绝章:p0001",
            "027_卦变生克墓绝章:p0003",
            "027_卦变生克墓绝章:p0005",
            "027_卦变生克墓绝章:p0007",
            "027_卦变生克墓绝章:p0009",
        ),
        "主卦与变卦的宫五行已知且确有动爻。",
        "记录卦化生、化克、化比和或化去；原文未给出卦化墓绝的可执行判据，代码不臆造。",
        implemented=True,
    ),
    _rule(
        "ZSBY-027-HEXAGRAM-CHANGE-TOMB-EXTINCTION",
        "卦化墓绝",
        (),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        ("027_卦变生克墓绝章:p0025",),
        "主卦变卦形成所谓卦化墓或卦化绝。",
        "原书按语明确指出变墓变绝未论，不能臆造宫卦判据。",
        implemented=False,
        limitation="卦化墓、卦化绝原文未给可执行判据，系统不臆造",
    ),
    _rule(
        "ZSBY-028-REVERSE-CHANT",
        "反吟",
        ("REVERSE_CHANT", "REVERSE_CHANT_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        tuple(f"028_反伏章:p{index:04d}" for index in range(1, 9) if index != 5),
        "内卦、外卦或全卦动变后逐爻相冲。",
        "记录相应范围的反吟；成败仍取决于用神旺衰与回头冲克。",
    ),
    _rule(
        "ZSBY-028-REPEATED-CHANT",
        "伏吟",
        ("REPEATED_CHANT", "REPEATED_CHANT_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        ("028_反伏章:p0014", "028_反伏章:p0015", "028_反伏章:p0017"),
        "内卦、外卦或全卦发动而变后地支不变。",
        "记录相应范围的伏吟；效力仍取决于用神旺衰。",
    ),
    _rule(
        "ZSBY-029-VOID",
        ("旬空"),
        (
            "旬空",
            "CHANGED_VOID",
            "HIDDEN_VOID",
            "VOID_EFFECT",
            "CHANGED_VOID_EFFECT",
        ),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        tuple(f"029_旬空章:p{index:04d}" for index in range(1, 7)),
        "爻支属于当旬空亡。",
        "先记录旬空，再区分旺不为空、动不为空、真空及待填实。",
        exceptions=("原书遇疑要求再占，单卦规则并非总能唯一裁决。",),
    ),
    _rule(
        "ZSBY-030-LIFE-STAGE",
        "生旺墓绝",
        (
            "LIFE_STAGE",
            "CHANGED_LIFE_STAGE",
            "HIDDEN_LIFE_STAGE",
            "DYNAMIC_LIFE_STAGE",
            "LIFE_STAGE_EFFECT",
            "CHANGED_LIFE_STAGE_EFFECT",
            "DYNAMIC_LIFE_STAGE_EFFECT",
        ),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        tuple(f"030_生旺墓绝章:p{index:04d}" for index in range(2, 8)),
        "主事爻与日、动爻或本位变爻形成长生、帝旺、墓、绝。",
        "先记录结构，再按旺衰、生扶、刑克决定是否有效。",
        exceptions=("旺相受生时可论生不论墓绝；烈火煎金等可论克不论生。",),
    ),
    _rule(
        "ZSBY-031-CHANGED-OMEN",
        "用神化吉化凶",
        ("CHANGED_TO_OFFICIAL", "CHANGED_TO_OFFICIAL_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        (
            "031_各门类题头总注章:p0003",
            "031_各门类题头总注章:p0004",
            "031_各门类题头总注章:p0011",
        ),
        "用神或元神发动并化出官鬼。",
        "化鬼通常为化凶；若同时构成明确回头生则保留冲突，不把六亲名称凌驾于五行生克。",
    ),
    _rule(
        "ZSBY-031-YEAR-COMMAND",
        "太岁背景",
        ("YEAR_COMMAND",),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("031_各门类题头总注章:p0005",),
        "已知起卦当年的地支。",
        "只记录当年太岁；不据术语定义自行增加吉凶作用力。",
    ),
    _rule(
        "ZSBY-031-YEAR-COMMAND-EFFECT",
        "太岁作用力",
        (),
        FactLayer.EFFECTIVE,
        RuleStatus.CONDITIONAL,
        (
            "031_各门类题头总注章:p0005",
            "031_各门类题头总注章:p0006",
            "031_各门类题头总注章:p0007",
        ),
        "太岁、岁五、五位术语已经定义。",
        "本章没有给出太岁独立生克世用的确定效力判据。",
        implemented=False,
        limitation="太岁作用力原文仅定义术语、未给确定效力判据，暂不独立定吉凶",
    ),
    _rule(
        "ZSBY-033-WANDERING-RETURNING",
        "游魂归魂",
        ("WANDERING_SOUL", "RETURNING_SOUL"),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("033_归魂游魂章:p0001", "033_归魂游魂章:p0002"),
        "主卦属于八宫游魂或归魂位。",
        "只记录卦型，须结合用神及所占事项解释。",
    ),
    _rule(
        "ZSBY-034-MONTH-BREAK",
        "月破",
        (
            "MONTH_BREAK",
            "CHANGED_MONTH_BREAK",
            "HIDDEN_MONTH_BREAK",
            "MONTH_BREAK_EFFECT",
            "CHANGED_MONTH_BREAK_EFFECT",
        ),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        (
            "034_月破章:p0001",
            "034_月破章:p0002",
            "034_月破章:p0003",
            "034_月破章:p0004",
        ),
        "爻支受月建冲。",
        "先记录月破，再区分动而有用、出月填实及静而无助之到底破。",
    ),
    _rule(
        "ZSBY-035-HIDDEN-RELATION",
        "飞伏关系",
        ("FLYING_HIDDEN_RELATION",),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("035_飞伏神章:p0004", "035_飞伏神章:p0008"),
        "用神不上卦并伏于本宫首卦对应爻位。",
        "记录飞来生伏、飞来克伏、伏去生飞、伏来克飞或比和。",
    ),
    _rule(
        "ZSBY-035-HIDDEN-EFFECT",
        "伏神有用无用",
        ("HIDDEN_SPIRIT_EFFECT",),
        FactLayer.EFFECTIVE,
        RuleStatus.CONDITIONAL,
        (
            "035_飞伏神章:p0010",
            "035_飞伏神章:p0011",
            "035_飞伏神章:p0012",
            "035_飞伏神章:p0014",
            "035_飞伏神章:p0015",
            "035_飞伏神章:p0016",
        ),
        "伏神、飞神、日月及动爻的旺衰空破生克已知。",
        "按六种有用、五种无用条件形成显式效力结论。",
        implemented=True,
    ),
    _rule(
        "ZSBY-036-ADVANCE",
        "进神",
        ("ADVANCE", "ADVANCE_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        (
            "036_进神退神章:p0001",
            "036_进神退神章:p0002",
            "036_进神退神章:p0004",
            "036_进神退神章:p0008",
            "036_进神退神章:p0009",
        ),
        "动爻化为对应进神地支。",
        "记录化进及待时条件；吉凶取决于该爻喜忌。",
    ),
    _rule(
        "ZSBY-036-RETREAT",
        "退神",
        ("RETREAT", "RETREAT_EFFECT"),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        (
            "036_进神退神章:p0001",
            "036_进神退神章:p0003",
            "036_进神退神章:p0005",
            "036_进神退神章:p0010",
            "036_进神退神章:p0011",
        ),
        "动爻化为对应退神地支。",
        "记录化退及近远、待时条件；吉凶取决于该爻喜忌。",
    ),
    _rule(
        "ZSBY-037-GHOST-TOMB",
        "随鬼入墓",
        ("GHOST_TOMB",),
        FactLayer.EFFECTIVE,
        RuleStatus.CONDITIONAL,
        ("037_随鬼入墓章:p0004",),
        "自占取世爻、代占取用神，目标入日墓、动墓或化墓。",
        "只有休囚无气时形成凶危；旺而有扶仍可解救。",
        implemented=True,
    ),
    _rule(
        "ZSBY-038-SOLE-MOVING",
        "独发独静",
        ("SINGLE_MOVING", "SINGLE_STATIC"),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        ("038_独发章:p0001",),
        "六爻中仅一爻动，或仅一爻静。",
        "只记录结构，不得舍用神而据此独断祸福与应期。",
    ),
    _rule(
        "ZSBY-039-DOUBLE-PRESENT",
        "用神两现",
        ("USEFUL_GOD_MULTIPLE",),
        FactLayer.DERIVED,
        RuleStatus.CONDITIONAL,
        ("039_两现章:p0001", "039_两现章:p0002"),
        "同一种用神六亲在卦中出现两处或以上。",
        "以古法旺相、动、不破、不空、不伤的顺序选主用爻；"
        "同时保留空破爻可能应于填实的反例边界，完全同等时不臆定。",
    ),
    _rule(
        "ZSBY-040-STAR",
        "四个有效星煞",
        (
            "STAR_NOBLE",
            "STAR_LU",
            "STAR_HORSE",
            "STAR_HAPPINESS",
        ),
        FactLayer.RAW,
        RuleStatus.CONDITIONAL,
        (
            "040_星煞章:p0001",
            "040_星煞章:p0003",
            "040_星煞章:p0005",
            "040_星煞章:p0007",
            "040_星煞章:p0008",
            "040_星煞章:p0009",
        ),
        "贵人、禄神、驿马或天喜按日干、日支、月建命中爻支。",
        "只在用神旺而有扶时作为有利辅证；用神失陷则虽有如无。",
    ),
    _rule(
        "ZSBY-040-STAR-DISCARDED",
        "其余星煞删弃",
        (),
        FactLayer.RAW,
        RuleStatus.DISCARDED,
        ("040_星煞章:p0010", "040_星煞章:p0011"),
        "命中丧门、大杀及其余星煞。",
        "原书认为往往全无应验，系统不生成预测事实。",
    ),
)


RULES_BY_ID = {rule.id: rule for rule in RULES}
if len(RULES_BY_ID) != len(RULES):
    raise RuntimeError("规则注册表存在重复 rule_id")


def get_rule(rule_id: str) -> RuleDefinition:
    try:
        return RULES_BY_ID[rule_id]
    except KeyError as exc:
        raise ValueError(f"未注册的规则：{rule_id}") from exc


def make_fact(
    rule_id: str,
    *,
    id: str,
    type: str,
    value: JsonValue,
    line: int | None = None,
    related_lines: tuple[int, ...] = (),
    evidence: dict[str, JsonValue] | None = None,
    source_id: str | None = None,
    source_ids: tuple[str, ...] | None = None,
    layer: FactLayer | None = None,
) -> RuleFact:
    rule = get_rule(rule_id)
    if type not in rule.fact_types:
        raise ValueError(f"规则 {rule_id} 不允许产生事实类型 {type}")
    resolved_sources = source_ids or ((source_id,) if source_id else rule.source_ids)
    unknown_sources = set(resolved_sources) - set(rule.source_ids)
    if unknown_sources:
        raise ValueError(
            f"规则 {rule_id} 使用了未登记出处：{', '.join(sorted(unknown_sources))}"
        )
    return RuleFact(
        id=id,
        type=type,
        layer=layer or rule.layer,
        rule_id=rule.id,
        line=line,
        related_lines=related_lines,
        value=value,
        evidence=evidence or {},
        source_ids=resolved_sources,
        rule_source=resolved_sources[0],
    )


def unimplemented_rule_descriptions() -> tuple[str, ...]:
    return tuple(
        rule.limitation or f"{rule.name}尚未实现"
        for rule in RULES
        if not rule.implemented
    )
