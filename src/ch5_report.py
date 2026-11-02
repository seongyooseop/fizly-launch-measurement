"""Chapter 5: the readout for FIZLY and its agency, and the reusable playbook.

Reads every chapter's output and writes the readout in English and Korean
(the advertiser's team reads Korean; regional colleagues read English). The
wording follows the numbers: each recommendation is chosen by comparing an
estimate and its interval with break-even, not written in advance.

One lab-only check uses the truth: what halving sustain video after the
flight would really have cost. It is labelled as such.

Writes outputs/ch5_report.json, docs/advertiser_readout.md and docs/advertiser_readout_ko.md
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from world import LAUNCH_FLIGHT, World, actual_plan

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
# Sales here are shelf (sell-out) value. FIZLY keeps roughly 60% of shelf price
# after the retailer's margin and about half of that after cost of goods:
# an assumed 30% contribution per won of shelf sales, to be confirmed by FIZLY.
MARGIN = 0.30
ONLINE_MARGIN = 0.45  # own mall and marketplace: no retailer cut, marketplace fee instead (assumed)


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def model_sustain_return():
    """Calibrated MMM: sales lost per won saved if sustain video (after the
    flight) were halved, over weeks 91-104."""
    from ch4_mmm import MEDIA, contributions, weekly
    df = weekly()
    d = dict(np.load(ROOT / "models" / "ch4_calibrated.npz"))
    sp = {c: df[c].to_numpy() for c in MEDIA}
    cut = {c: v.copy() for c, v in sp.items()}
    m = (df.week > LAUNCH_FLIGHT[1]).to_numpy()
    cut["video_zero"][m] *= 0.5
    loss = contributions(sp, d)[:, m, :].sum((1, 2)) - contributions(cut, d)[:, m, :].sum((1, 2))
    saved = sp["video_zero"][m].sum() - cut["video_zero"][m].sum()
    q = np.quantile(loss / saved, [0.05, 0.5, 0.95])
    return {"median": float(q[1]), "ci90": [float(q[0]), float(q[2])]}


def cost_of_halving_video():
    """Lab check: halve short video after the flight (weeks 91-104). Uses the true world."""
    media = json.loads((ROOT / "data" / "media_plan.json").read_text(encoding="utf-8"))
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))
    w = World()
    geos = w.geo_ids
    dark = np.array([g in media["go_dark"] for g in geos])
    rival = [geos.index(g) for g in eff["rival_regions"]]
    base = actual_plan(w, go_dark=dark, competitor_geos=rival)
    cut = base.copy()
    m = w.week > LAUNCH_FLIGHT[1]
    cut.spend["short_video"][m] *= 0.5
    o1, _ = w.simulate(base)
    o2, _ = w.simulate(cut)
    post = o1.week > LAUNCH_FLIGHT[1]
    saved = base.spend["short_video"][m].sum() - cut.spend["short_video"][m].sum()
    lost = ((o1.offline_rev + o1.online_rev)[post].sum() - (o2.offline_rev + o2.online_rev)[post].sum())
    return {"spend_saved_m": saved / 1e6, "sales_lost_m": lost / 1e6, "true_return": lost / saved}


def main():
    bl, cl, geo, mmm = j("ch1_brand_lift.json"), j("ch2_conversion_lift.json"), j("ch3_offline.json"), j("ch4_mmm.json")
    c, g = cl["readout"], geo["readout"]
    cal = mmm["models"]["calibrated"]["roi"]
    both = cal["video_combined"]
    rec, aw = bl["readout"]["ad_recall"], bl["readout"]["awareness"]
    cd = rec["creative_diff"]
    ratio = c["attributed_roas"] / c["iroas_online"]
    halving = cost_of_halving_video()
    sustain = model_sustain_return()
    be, be_on = 1 / MARGIN, 1 / ONLINE_MARGIN
    halving["contribution_lost_m"] = halving["sales_lost_m"] * MARGIN
    gw, gc = g["flagged_dropped"]["total"], g["with_cooldown"]["total"]
    tr = geo["tracker"]

    # ---- decisions, chosen by the numbers
    video_pays = both["median"] >= be
    video_sure = both["ci90"][0] >= be
    s_ratio = sustain["median"] / be
    sustain_call = "down" if sustain["ci90"][1] < be else ("up" if sustain["ci90"][0] > be else "edge")
    cut = {ch: cal[ch]["ci90"][1] < be_on for ch in ["search", "retail_media", "social"]}

    # ---- English
    if video_pays:
        v_en = (f"The launch video pays back. Short video and online video together returned about {both['median']:.1f} won of shelf sales "
                f"per won over the half year (90% interval {both['ci90'][0]:.1f}-{both['ci90'][1]:.1f}), most of it in stores. At an assumed "
                f"{100 * MARGIN:.0f}% contribution on shelf sales, break-even is {be:.1f}"
                + (", and even the low end of the interval clears it." if video_sure else
                   "; the middle of the interval clears it, the low end does not."))
    else:
        v_en = (f"Video drives sales but has not paid back yet: {both['median']:.1f} won of shelf sales per won over the half year "
                f"against a break-even of {be:.1f} at {100 * MARGIN:.0f}% contribution.")
    s_en = {"down": f"Sustain video after the flight is past the point of profit: its last won returns about {sustain['median']:.1f} "
                    f"(90%: {sustain['ci90'][0]:.1f}-{sustain['ci90'][1]:.1f}) against {be:.1f}. Step it down and measure it.",
            "edge": f"Sustain video after the flight sits near the edge: its last won returns about {sustain['median']:.1f} "
                    f"(90%: {sustain['ci90'][0]:.1f}-{sustain['ci90'][1]:.1f}) against a break-even of {be:.1f}. Hold the weight and "
                    f"find the edge with a step-down test.",
            "up": f"Sustain video has room to grow: its last won returns about {sustain['median']:.1f} "
                  f"(90%: {sustain['ci90'][0]:.1f}-{sustain['ci90'][1]:.1f}) against {be:.1f}. Add weight in a test before adding it everywhere."}[sustain_call]
    bottom_en = [v_en, s_en,
                 f"Do not judge video on online numbers. The platform credits {ratio:.1f} times the online orders video adds, and video's "
                 f"online return alone is {c['iroas_online']:.2f}: about {100 * (1 - c['iroas_online'] / both['median']):.0f}% of what video earns "
                 f"is in stores and in the weeks after a flight, where no pixel looks.",
                 f"Scale creative A. Opening on the product in the first second lifted ad recall {100 * cd['diff']:+.1f}pp more than "
                 f"the lifestyle opening (95% CI {100 * cd['lo']:+.1f} to {100 * cd['hi']:+.1f}).",
                 f"Search and retail media look best in platform reports and are the weakest lines. The model puts them at "
                 f"{cal['search']['median']:.1f} and {cal['retail_media']['median']:.1f}, with intervals topping out at "
                 f"{cal['search']['ci90'][1]:.2f} and {cal['retail_media']['ci90'][1]:.2f}"
                 + (f", under the online break-even of {be_on:.2f} even at the top. Cut both 30% and confirm with holdout tests."
                    if cut["search"] and cut["retail_media"] else f"; test them before moving budget.")]
    measured_en = [
        {"question": "Did the launch video build awareness among people it reached?", "method": "Brand lift survey, 20% holdout",
         "answer": f"Ad recall {100 * rec['lift']:+.1f}pp, awareness {100 * aw['lift']:+.1f}pp ({100 * aw['weighted']['lift']:+.1f}pp across everyone reached)",
         "confidence": "High for recall and awareness; consideration and intent directional only"},
        {"question": "How many online orders did video add?", "method": "Conversion lift, 10% user holdout",
         "answer": f"{c['incr_orders']:,.0f} orders in six weeks; online return {c['iroas_online']:.2f} per won",
         "confidence": f"High (95% CI {c['iroas_lo']:.2f}-{c['iroas_hi']:.2f}); confirmed by the geo test's online part"},
        {"question": "With store sales, what did video return in the test weeks?", "method": "Geo test, 12 regions dark for 6 weeks",
         "answer": f"{gw['iroas']:.2f} in the window, {gc['iroas']:.2f} with a two-week cooldown",
         "confidence": "Medium: wide interval; a short window understates a launch"},
        {"question": "Over the half year, what does video return?", "method": "MMM calibrated to the geo test",
         "answer": f"{both['median']:.2f} for both video channels together", "confidence": "Medium-high on the total; low on the split between the two video channels"},
        {"question": "Is awareness growing in the market?", "method": "Independent tracker, monthly",
         "answer": f"From {100 * tr[1]['estimate']:.0f}% at launch to {100 * tr[-1]['estimate']:.0f}% by week 103",
         "confidence": "Level only: a monthly wave of 1,000 cannot say what caused a change under 5.7pp"},
    ]
    sustain_action_en = {"down": "Step down 30% in a geo test", "edge": "Hold; step-down test on short video (-30% in matched regions, Q1)",
                         "up": "Add 30% in matched regions first"}[sustain_call]
    rec_en = [
        {"line": "Launch flight (next launch)", "action": "Same approach; judge it on half-year sales against break-even, not on a six-week read",
         "why": f"Half-year return {both['median']:.1f} vs break-even {be:.1f}; the six-week read was {gw['iroas']:.1f}"},
        {"line": "Sustain video (short + online)", "action": sustain_action_en + "; keep alternating heavy and light blocks",
         "why": f"Marginal return about {sustain['median']:.1f} vs break-even {be:.1f}"},
        {"line": "Online bidding targets", "action": f"Divide platform-reported ROAS by {ratio:.1f}", "why": "Conversion lift measured how much of the credit is real"},
        {"line": "Creative", "action": "Shift weight to product-first openings (A)", "why": "Brand lift, pre-registered metric"},
        {"line": "Retail media", "action": "Cut 30%; holdout test in Q2" if cut["retail_media"] else "Hold; holdout test in Q2",
         "why": f"Model {cal['retail_media']['median']:.2f} [{cal['retail_media']['ci90'][0]:.2f}, {cal['retail_media']['ci90'][1]:.2f}] vs online break-even {be_on:.2f}"},
        {"line": "Search", "action": "Cut generic terms 30%; brand-term test in Q3" if cut["search"] else "Hold; brand-term test in Q3",
         "why": f"Model {cal['search']['median']:.2f} [{cal['search']['ci90'][0]:.2f}, {cal['search']['ci90'][1]:.2f}]; much of its credit is searches the video created"},
        {"line": "Social", "action": "Cut 30%" if cut["social"] else "Hold flat",
         "why": f"Model interval {cal['social']['ci90'][0]:.2f}-{cal['social']['ci90'][1]:.2f}" + ("" if cut["social"] else " reaches past break-even: unclear")},
    ]
    agenda_en = [
        {"quarter": "Q1 2027", "question": "How much sustain short video does Zero need, and what does short video alone return over months?",
         "study": "Geo test on short video only (online video unchanged): -30% in matched regions for 12 weeks, stores + online, "
                  "read at week 12 and again at week 20 to catch carry-over", "decides": "Sustain weight, and the split the model cannot make"},
        {"quarter": "Q2 2027", "question": "Does retail media add sales or collect buyers who would come anyway?",
         "study": "Audience holdout on the marketplace (or regions)", "decides": "Retail media budget"},
        {"quarter": "Q3 2027", "question": "How much of search is protecting the brand name vs new demand?",
         "study": "Geo test pausing brand-term search", "decides": "Search split between brand and generic terms"},
        {"quarter": "Q4 2027", "question": "Is the model still right, and does a new creative beat A?",
         "study": "Recalibrate the MMM with Q1-Q3 tests; brand lift with a 30% holdout; tracker boost sample of heavy platform users",
         "decides": "2028 budget and creative"},
    ]
    not_sure_en = [
        f"The contribution margins: {100 * MARGIN:.0f}% of shelf sales and {100 * ONLINE_MARGIN:.0f}% online are our assumptions; "
        f"at 25-40% on shelf sales, break-even runs from 4.0 to 2.5.",
        "How the video return splits between short video and online video: they build the same awareness and no test so far "
        "separated them. The Q1 test moves short video alone for long enough to see carry-over.",
        f"The model's marginal return for sustain video ({sustain['median']:.1f}): in this lab the model runs high on it; the Q1 test measures it directly.",
        "Returns beyond week 104: the model assumes awareness keeps fading at the rate it learned.",
    ]
    asks_en = [
        "Region-level sell-out panel every Monday (the geo test cannot run on national totals).",
        "Server-side purchase events, so more than 75% of online orders match: a better match rate narrows every online read.",
        "Tell the agency about local competitor launches and retailer promotions during tests; that is the only reliable way to drop a contaminated region.",
        "Agree the rules before each test (metrics, holdouts, read dates) and do not ask for early reads.",
    ]

    # ---- Korean (for FIZLY's team; same numbers, same decisions)
    if video_pays:
        v_ko = (f"출시 영상은 이익으로 본전을 넘었습니다. 숏폼 영상과 온라인 영상을 합쳐 광고비 1원당 매장 판매가 기준 매출 약 "
                f"{both['median']:.1f}원을 반년 동안 만들었고(90% 구간 {both['ci90'][0]:.1f}~{both['ci90'][1]:.1f}), 대부분은 매장에서 나왔습니다. "
                f"공헌이익률을 판매가의 {100 * MARGIN:.0f}%로 가정하면 손익분기는 {be:.1f}원"
                + ("이고, 구간의 아래쪽 끝도 이를 넘습니다." if video_sure else "입니다. 구간 가운데는 넘지만 아래쪽 끝은 넘지 못합니다."))
    else:
        v_ko = (f"영상은 매출을 만들지만 아직 이익으로 본전을 넘지 못했습니다. 반년 매출은 광고비 1원당 {both['median']:.1f}원이고, "
                f"공헌이익률 {100 * MARGIN:.0f}% 기준 손익분기는 {be:.1f}원입니다.")
    s_ko = {"down": f"출시 후 유지 기간 영상은 이익이 나는 선을 넘었습니다. 마지막 1원이 약 {sustain['median']:.1f}원"
                    f"(90%: {sustain['ci90'][0]:.1f}~{sustain['ci90'][1]:.1f})으로 손익분기 {be:.1f}원보다 낮습니다. 줄이고, 줄인 효과를 측정하십시오.",
            "edge": f"출시 후 유지 기간 영상은 손익분기 근처에 있습니다. 마지막 1원이 약 {sustain['median']:.1f}원"
                    f"(90%: {sustain['ci90'][0]:.1f}~{sustain['ci90'][1]:.1f})이고 손익분기는 {be:.1f}원입니다. 지금 비중을 유지하면서 "
                    f"줄이는 지역 실험으로 경계를 찾는 것을 권합니다.",
            "up": f"유지 기간 영상은 더 늘릴 여지가 있습니다. 마지막 1원이 약 {sustain['median']:.1f}원으로 손익분기 {be:.1f}원보다 높습니다. "
                  f"전국에 늘리기 전에 일부 지역에서 먼저 늘려 확인하십시오."}[sustain_call]
    bottom_ko = [v_ko, s_ko,
                 f"영상을 온라인 숫자로 판단하지 마십시오. 플랫폼은 영상이 실제로 늘린 온라인 주문의 {ratio:.1f}배를 자기 몫으로 잡고, "
                 f"영상의 온라인 수익만 보면 {c['iroas_online']:.2f}원입니다. 영상이 버는 돈의 약 {100 * (1 - c['iroas_online'] / both['median']):.0f}%는 "
                 f"픽셀이 보지 못하는 매장과 집행이 끝난 뒤의 몇 주에서 나옵니다.",
                 f"소재 A를 늘리십시오. 첫 1초에 제품을 보여준 소재가 라이프스타일로 시작한 소재보다 광고 회상을 "
                 f"{100 * cd['diff']:+.1f}%p 더 올렸습니다(95% 구간 {100 * cd['lo']:+.1f}~{100 * cd['hi']:+.1f}%p).",
                 f"검색과 리테일 미디어는 플랫폼 보고에서는 가장 좋아 보이지만 실제로는 가장 약합니다. 모델 추정은 각각 "
                 f"{cal['search']['median']:.1f}원, {cal['retail_media']['median']:.1f}원이고 구간 위쪽 끝도 {cal['search']['ci90'][1]:.2f}원, "
                 f"{cal['retail_media']['ci90'][1]:.2f}원"
                 + (f"으로 온라인 손익분기 {be_on:.2f}원보다 낮습니다. 둘 다 30% 줄이고 홀드아웃 테스트로 확인하십시오."
                    if cut["search"] and cut["retail_media"] else "입니다. 예산을 옮기기 전에 테스트하십시오.")]
    measured_ko = [
        {"question": "출시 영상이 도달한 사람들의 인지도를 올렸나?", "method": "브랜드 리프트 설문, 20% 홀드아웃",
         "answer": f"광고 회상 {100 * rec['lift']:+.1f}%p, 인지 {100 * aw['lift']:+.1f}%p(도달자 전체 기준 {100 * aw['weighted']['lift']:+.1f}%p)",
         "confidence": "회상·인지는 높음. 고려·구매 의향은 방향성만"},
        {"question": "영상이 온라인 주문을 얼마나 늘렸나?", "method": "전환 리프트, 사용자 10% 홀드아웃",
         "answer": f"6주간 {c['incr_orders']:,.0f}건, 온라인 수익 광고비 1원당 {c['iroas_online']:.2f}원",
         "confidence": f"높음(95% 구간 {c['iroas_lo']:.2f}~{c['iroas_hi']:.2f}), 지역 실험의 온라인 결과와 일치"},
        {"question": "매장까지 포함하면 실험 기간에 얼마를 벌었나?", "method": "지역 실험, 12개 지역 6주 소등",
         "answer": f"실험 기간 {gw['iroas']:.2f}원, 2주 쿨다운 포함 {gc['iroas']:.2f}원",
         "confidence": "중간. 구간이 넓고, 짧은 창은 출시 효과를 과소평가"},
        {"question": "반년 동안 영상은 얼마를 벌었나?", "method": "지역 실험으로 보정한 MMM",
         "answer": f"두 영상 채널 합산 {both['median']:.2f}원", "confidence": "합계는 중상, 두 채널 간 배분은 낮음"},
        {"question": "시장 전체 인지도는 오르고 있나?", "method": "독립 조사 회사의 월간 트래커",
         "answer": f"출시 시점 {100 * tr[1]['estimate']:.0f}% → 103주 {100 * tr[-1]['estimate']:.0f}%",
         "confidence": "수준만 보여줌. 웨이브당 1,000명으로는 5.7%p 미만의 변화 원인을 말할 수 없음"},
    ]
    sustain_action_ko = {"down": "지역 실험으로 30% 축소", "edge": "유지, Q1 숏폼 매칭 지역 30% 축소 실험", "up": "매칭 지역에서 먼저 30% 증액"}[sustain_call]
    rec_ko = [
        {"line": "출시 집행(다음 출시)", "action": "같은 방식. 6주 결과가 아니라 반년 매출을 손익분기와 비교해 판단",
         "why": f"반년 수익 {both['median']:.1f}원 vs 손익분기 {be:.1f}원, 6주 결과는 {gw['iroas']:.1f}원"},
        {"line": "유지 기간 영상(숏폼+온라인)", "action": sustain_action_ko + ", 격주 강약 운영 유지",
         "why": f"한계 수익 약 {sustain['median']:.1f}원 vs 손익분기 {be:.1f}원"},
        {"line": "온라인 입찰 목표", "action": f"플랫폼 보고 ROAS를 {ratio:.1f}로 나눠 사용", "why": "전환 리프트로 실제 몫을 측정"},
        {"line": "소재", "action": "제품을 먼저 보여주는 소재(A) 비중 확대", "why": "사전에 정한 지표의 브랜드 리프트 결과"},
        {"line": "리테일 미디어", "action": "30% 축소, Q2 홀드아웃 테스트" if cut["retail_media"] else "유지, Q2 홀드아웃 테스트",
         "why": f"모델 {cal['retail_media']['median']:.2f} [{cal['retail_media']['ci90'][0]:.2f}, {cal['retail_media']['ci90'][1]:.2f}] vs 온라인 손익분기 {be_on:.2f}"},
        {"line": "검색", "action": "일반 키워드 30% 축소, Q3 브랜드 키워드 테스트" if cut["search"] else "유지, Q3 브랜드 키워드 테스트",
         "why": f"모델 {cal['search']['median']:.2f} [{cal['search']['ci90'][0]:.2f}, {cal['search']['ci90'][1]:.2f}], 성과의 상당 부분이 영상이 만든 검색"},
        {"line": "소셜", "action": "30% 축소" if cut["social"] else "유지",
         "why": f"모델 구간 {cal['social']['ci90'][0]:.2f}~{cal['social']['ci90'][1]:.2f}" + ("" if cut["social"] else ", 손익분기를 걸쳐 있어 판단 보류")},
    ]
    agenda_ko = [
        {"quarter": "2027 Q1", "question": "유지 기간 숏폼 영상이 얼마나 필요하고, 숏폼만의 수개월 효과는 얼마인가?",
         "study": "숏폼만 움직이는 지역 실험(온라인 영상은 그대로): 매칭 지역 30% 축소 12주, 매장+온라인, 12주 차와 이월 효과를 보는 20주 차에 두 번 판독",
         "decides": "유지 비중, 모델이 가르지 못한 두 영상 채널 몫"},
        {"quarter": "2027 Q2", "question": "리테일 미디어는 매출을 늘리나, 어차피 살 사람을 모으나?", "study": "마켓플레이스 오디언스(또는 지역) 홀드아웃", "decides": "리테일 미디어 예산"},
        {"quarter": "2027 Q3", "question": "검색은 브랜드명을 지키는 몫과 새 수요 몫이 각각 얼마인가?", "study": "브랜드 키워드 중단 지역 실험", "decides": "브랜드·일반 키워드 배분"},
        {"quarter": "2027 Q4", "question": "모델이 여전히 맞나, 새 소재가 A를 이기나?", "study": "Q1~Q3 실험으로 MMM 재보정, 30% 홀드아웃 브랜드 리프트, 헤비 유저 보강 트래커", "decides": "2028 예산과 소재"},
    ]
    not_sure_ko = [
        f"공헌이익률(매장 판매가의 {100 * MARGIN:.0f}%, 온라인 {100 * ONLINE_MARGIN:.0f}%)은 가정입니다. 매장 기준 25~40%라면 손익분기는 4.0~2.5원입니다.",
        "영상 효과가 숏폼과 온라인 영상 사이에 어떻게 나뉘는지는 아직 모릅니다. 둘이 같은 인지도를 쌓고, 지금까지 이를 가른 실험이 없었습니다. Q1 실험이 숏폼만 충분히 오래 움직여 이월 효과까지 봅니다.",
        f"유지 영상의 한계 수익({sustain['median']:.1f}원)은 모델이 높게 보는 경향이 있습니다. Q1 실험이 직접 측정합니다.",
        "104주 이후의 수익은 모델이 학습한 속도로 인지도가 줄어든다고 가정한 값입니다.",
    ]
    asks_ko = [
        "매주 월요일 지역 단위 셀아웃 패널 데이터 공유(전국 합계로는 지역 실험을 할 수 없습니다).",
        "서버 측 구매 이벤트 연동으로 온라인 주문 매칭률을 75% 이상으로: 매칭률이 오르면 모든 온라인 측정이 정밀해집니다.",
        "실험 기간 중 지역 경쟁사 출시나 유통사 프로모션을 대행사에 알려 주십시오. 오염된 지역을 빼는 유일하게 믿을 만한 방법입니다.",
        "실험마다 규칙(지표, 홀드아웃, 판독일)을 미리 합의하고 중간 판독을 요청하지 않기.",
    ]

    playbook = {
        "title": "Launch measurement playbook (reusable for the next launch)",
        "steps": [
            {"when": "4 weeks before launch", "what": "One-page plan: questions, KPIs, studies, read dates, success thresholds (chapter 0)"},
            {"when": "2 weeks before", "what": "Designs from history: brand lift holdout by answers needed, conversion lift holdout by detectable lift, geo regions by detectable return and sales at risk"},
            {"when": "Weeks 1-4", "what": "Brand lift on recall and awareness; creative compared only on those"},
            {"when": "Weeks 5-10", "what": "Conversion lift and geo test in the same flight (holdout users in campaign regions, video off in 12 regions); cooldown read two weeks later"},
            {"when": "Week 12", "what": "Readout: one question per decision, with the number that answers it (chapter 4)"},
            {"when": "Every quarter", "what": "Recalibrate the model with the newest experiment; one new test per quarter"},
        ],
        "cost": {"geo_sales_given_up_m": gw["iroas"] * geo["withheld_m"], "geo_video_withheld_m": geo["withheld_m"],
                 "conversion_holdout_online_sales_m": cl["holdout"] * c["incr_orders"] / (1 - cl["holdout"]) * cl["aov"] / 1e6},
        "value_lab_check": halving,
        "reusable": ["Chapter 0 plan template", "Design scripts (holdout and region sizing from the advertiser's own history)",
                     "In-flight A/A check for geo tests", "Readout table: question, number, what it does not count",
                     "Program view: which study each advertiser tier can read"],
    }
    out = {"bottom_line": bottom_en, "measured": measured_en, "recommendation": rec_en, "agenda": agenda_en,
           "asks": asks_en, "not_sure": not_sure_en,
           "ko": {"bottom_line": bottom_ko, "measured": measured_ko, "recommendation": rec_ko, "agenda": agenda_ko,
                  "asks": asks_ko, "not_sure": not_sure_ko},
           "playbook": playbook, "platform_correction": ratio, "margin": MARGIN, "online_margin": ONLINE_MARGIN,
           "breakeven": be, "breakeven_online": be_on, "sustain_marginal": sustain, "sustain_call": sustain_call,
           "video_pays": video_pays}
    (OUT / "ch5_report.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    def md(lang, d, title, heads, note):
        h = heads
        lines = [f"# {title}", "", f"*{note}*", "", f"## {h[0]}", ""] + [f"- {b}" for b in d["bottom_line"]]
        lines += ["", f"## {h[1]}", "", f"| {' | '.join(h[2])} |", "|---|---|---|---|"]
        lines += [f"| {m['question']} | {m['method']} | {m['answer']} | {m['confidence']} |" for m in d["measured"]]
        lines += ["", f"## {h[3]}", "", f"| {' | '.join(h[4])} |", "|---|---|---|"]
        lines += [f"| {r['line']} | {r['action']} | {r['why']} |" for r in d["recommendation"]]
        lines += ["", f"## {h[5]}", "", f"| {' | '.join(h[6])} |", "|---|---|---|---|"]
        lines += [f"| {a['quarter']} | {a['question']} | {a['study']} | {a['decides']} |" for a in d["agenda"]]
        lines += ["", f"## {h[7]}", ""] + [f"- {x}" for x in d["not_sure"]]
        lines += ["", f"## {h[8]}", ""] + [f"- {x}" for x in d["asks"]]
        return "\n".join(lines) + "\n"

    en = md("en", out, "FIZLY Zero launch: measurement readout",
            ["Bottom line", "What we measured", ["Question", "Method", "Answer", "Confidence"], "Recommendation for the first half of 2027",
             ["Line", "Action", "Why"], "Learning agenda for 2027", ["Quarter", "Question", "Study", "Decides"],
             "What we are not sure about", "What we need from you"], "Synthetic data. FIZLY is a fictional brand.")
    en += (f"\n## Was measuring worth it?\n\nMeasuring cost about {playbook['cost']['geo_sales_given_up_m']:.0f}M KRW of sales in the go-dark "
           f"regions and about {playbook['cost']['conversion_holdout_online_sales_m']:.0f}M KRW of online sales in the holdout. "
           f"Lab check (uses the simulated truth): halving sustain video would save {halving['spend_saved_m']:.0f}M KRW of media and lose "
           f"{halving['sales_lost_m']:.0f}M KRW of shelf sales by week 104, a true return of {halving['true_return']:.1f} per won "
           f"(the model said {sustain['median']:.1f}).\n")
    ko = md("ko", out["ko"], "FIZLY 제로 출시 측정 보고서",
            ["핵심 결론", "측정한 것", ["질문", "방법", "답", "신뢰도"], "2027 상반기 권고", ["항목", "실행", "근거"],
             "2027 학습 아젠다", ["분기", "질문", "실험", "결정할 것"], "확실하지 않은 것", "요청 사항"],
            "가상 데이터입니다. FIZLY는 가상의 브랜드입니다. 금액은 매장 판매가 기준 매출이며, 'n원'은 광고비 1원당 매출입니다.")
    (ROOT / "docs" / "advertiser_readout.md").write_text(en, encoding="utf-8")
    (ROOT / "docs" / "advertiser_readout_ko.md").write_text(ko, encoding="utf-8")
    print("\n".join(bottom_en))
    print(f"sustain call: {sustain_call}; model {sustain['median']:.2f} {np.round(sustain['ci90'], 2)}; "
          f"true return of the halved sustain {halving['true_return']:.2f}")


if __name__ == "__main__":
    main()
