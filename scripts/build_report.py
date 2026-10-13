"""Render the lab report from saved evidence; never runs or modifies the grader."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def table(headers: list[str], rows: list[list]) -> str:
    def line(cells: list) -> str:
        return "| " + " | ".join("—" if c is None else str(c) for c in cells) + " |"
    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(row) for row in rows)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    naive, resilient = load("reports/gameday/naive.json"), load("reports/gameday/resilient.json")
    cached = load("reports/cache/cached.json")["C1_faq_outage"]
    uncached = load("reports/cache/resilient.json")["C1_faq_outage"]
    workflow, slo = load("reports/workflows.json"), load("reports/slo.json")
    board, multi = load("reports/scoreboard.json"), load("reports/scoreboard_multiseed.json")

    def exp(label: str, scenario: str = "C1_faq_outage") -> dict:
        return load(f"reports/experiments/{label}_{scenario}.json")["metrics"]

    out = [f"""# Lab 25B — Report

**Họ tên / nhóm:** Nguyễn Nhân Sâm — **MSV:** 2A202602672  
**Commit:** `{args.code_commit}` (snapshot code/config được đánh giá; report được bổ sung ở commit kế tiếp).  
**Điểm tự động (`make grade`):** {board['summary']['automatic']} / 88.  
**Ngày chạy:** 13/10/2026; Python 3.12.14; mô phỏng local, thời gian ảo; không gọi API AI/payment thật.

84 điểm là toàn bộ điểm public có thể kiểm chứng: 4 điểm SLO hidden chưa có dữ liệu và 12 điểm report chấm tay chưa được chấm. `scoreboard_multiseed.json` cũng đạt {multi['summary']['automatic']}/88 trên seed 25, 26, 27; đây chưa phải kết quả băng ẩn của giảng viên. Full suite gồm test gốc và regression bổ sung đạt **99/99**; các test gốc, simulator, băng sự cố, services và grader được giữ nguyên. Ruff sạch, mypy sạch trên 7 module triển khai.

Tỷ lệ trong bảng dùng số từ 0 đến 1; chi phí là **đơn vị mô phỏng**, không phải USD. p95 chỉ tính lượt thành công. `recovery_s` là mốc bắt đầu cửa sổ 30 giây có >=95% logical call thành công sau restore; giá trị 0 không có nghĩa mọi request hoặc alpha hồi phục tức thì. Primary share đo attempt từ restore+60 giây tới hết băng.

## 1. Kết quả Game Day (naive vs của bạn)
"""
    ]
    keys = ["availability", "latency_p95_s", "amplification", "retry_ratio", "cost_per_good_turn", "recovery_s"]
    rows = []
    for scenario in naive:
        for name, data in [("naive", naive), ("resilient", resilient)]:
            m = data[scenario]
            rows.append([scenario[:2], name, *(m[k] for k in keys), "PASS" if m["pass"] else "FAIL"])
    out.append(table(["Băng", "Client", "availability", "p95 (s)", "amplification", "retry_ratio",
                      "cost/turn", "recovery (s)", "PASS?"], rows))
    out.append("\nNguồn: `reports/gameday/naive.json`, `resilient.json`, seed 25. Các băng public và ngưỡng giữ nguyên.")
    out.append(table(["Băng", "primary share sau restore", "retry-after violations", "400 retries",
                      "incompatible routes", "unneeded failovers"], [
        [key[:2], m["primary_share_after_restore"], m["retry_after_violations"], m["client_error_retries"],
         m["incompatible_routes"], m["unneeded_failovers"]] for key, m in resilient.items()
    ]))
    out.append(r"""
G5 availability thấp hơn vì request malformed không thể cứu bằng retry/failover: 0,8179 vẫn cao hơn ngưỡng 0,78. G2 p95 11,911 giây không phải check thất bại: giới hạn p95 <=10 giây nằm ở G4. Các check amplification và primary share bổ sung trong YAML cũng đã đạt.

## 2. Cấu hình client và lý do

Giữ toàn bộ giá trị `client:` của starter sau khi triển khai đúng logic: chúng đạt G1–G6 trên ba seed. Các lý do dưới đây là bằng chứng cấu hình phù hợp với các băng đã đo, không phải tuyên bố mỗi tham số đã được tối ưu độc lập.
"""
    )
    out.append(table(["Tham số", "Giá trị", "Lý do và bằng chứng"], [
        ["attempt_timeout_s", 8, "G6 availability 1,0; timeout 30 chỉ còn 0,9488, 107 lần GiveUp deadline"],
        ["max_attempts_per_provider", 2, "Một retry trước failover; G2 amplification 1,059; G3 retry ratio 0,034"],
        ["min_time_left_s", 1, "Không khởi động attempt vô nghĩa; test deadline và cancel permit đạt"],
        ["backoff_base_s / cap_s", "0,25 / 4", "Full jitter được test; G1 có 0 retry-after violations"],
        ["retry_budget_ratio", "0,1", "G3 retry ratio 0,034 <=0,10; thí nghiệm khi breaker sai còn 0,068 thay vì 0,159"],
        ["retry_budget_min_per_s / max_tokens", "0,5 / 20", "Có burst/refill cho traffic thấp; G2 retry ratio 0,008, không bùng retry"],
        ["quota_cooldown_s", 300, "Không lặp retry hết quota; G5 client_error_retries=0 và unneeded_failovers=0"],
        ["breaker.window_size / min_calls", "20 / 10", "Đủ mẫu trước trip; G2 recovery=0, amplification=1,059; test sliding window đạt"],
        ["breaker.failure_rate_threshold", "0,5", "G2/G6 tránh vùng hỏng; G6 availability=1,0 và primary share=1,0 sau restore"],
        ["breaker.slow_call_s / slow_rate_threshold", "5 / 0,6", "G4 p95=5,562 thay cho naive 13,764 dù chỉ có call chậm"],
        ["breaker.open_duration_s", 10, "Cho vùng giảm tải rồi probe; G2/G4/G6 đều đạt recovery/primary-share checks"],
        ["breaker.half_open_max_probes / half_open_successes", "2 / 2", "Giới hạn request thử phục hồi; test probe concurrent và stale generation đạt"],
    ]))
    out.append(r"""
Bảng quyết định `on_error`:

| Loại lỗi | Ghi breaker? | Retry cùng provider? | Failover? | Cooldown |
|---|---|---|---|---|
| Client error (400/401/403/404/422) | Release permit, không ghi sức khỏe | Không | Không: GiveUp client_error | Không |
| Quota exhausted | Release permit | Không | Ngay | 300 giây; không chờ quota |
| Rate limited | Release permit | Ưu tiên spillover; chỉ chờ ngắn khi không còn provider usable | Ngay | Ít nhất retry-after; wait tối đa 5 giây nếu đủ deadline |
| Overloaded/server/timeout | on_failure | Khi còn attempts, token, deadline và breaker permit | Khi retry không được phép | Breaker quản lý |

Cooldown dùng chung giữa các call và giữ loại lỗi gắn với expiry xa nhất, nên response rate limit đến muộn không biến quota thành thời gian chờ ngắn. Retry budget chỉ bị tiêu khi có permit và một retry sẽ được trả về. Thành công chậm vẫn ghi vào breaker; callback generation cũ bị bỏ qua; cancel giải phóng probe.

## 3. Ba thí nghiệm

Các thí nghiệm dùng helper `scripts/run_required_experiments.py`, seed simulator 25, seed client 1, bản sao config cho mỗi case. Không chỉnh client nộp bài hay băng chấm để làm thí nghiệm.

### 3.1 Retry budget là lớp phòng thủ cuối

Đặt `breaker.min_calls=1000000000`, `max_attempts_per_provider=5`; so sánh budget chuẩn với ratio=100, max_tokens=1e9, refill=1e6/s.
"""
    )
    rows = []
    for scenario in ("G2_overload_storm", "G3_brownout"):
        for label in ("normal", "broken_breaker_budget_on", "broken_breaker_budget_off"):
            m = exp(label, scenario)
            rows.append([scenario[:2], label, m["availability"], m["amplification"], m["retry_ratio"],
                         m["recovery_s"], m["latency_p95_s"]])
    out.append(table(["Băng", "Cấu hình", "availability", "amplification", "retry_ratio", "recovery (s)", "p95 (s)"], rows))
    out.append(r"""
Với breaker sai, tắt budget làm G2 amplification tăng 1,378 → 1,675 và recovery 0 → 25 giây; G3 retry ratio tăng 0,068 → 0,159. Breaker đúng giúp G2 amplification còn 1,059, nhưng budget vẫn cần: nó chặn retry trong khoảng thu mẫu trước trip hoặc khi breaker cấu hình sai. Breaker quyết định provider có khỏe không; budget giới hạn tải bổ sung toàn client, nên hai lớp xử lý hai nguyên nhân khác nhau. Ratio 0,1 không phải trần cứng mọi khoảng ngắn vì bucket khởi đầu có token và có refill theo thời gian.

### 3.2 Timeout 30 giây và survivorship bias
"""
    )
    rows = []
    for scenario in ("G6_provider_outage", "G4_slow_region"):
        for label in ("normal", "timeout30"):
            m = exp(label, scenario)
            rows.append([scenario[:2], label, m["availability"], m["latency_p95_s"],
                         json.dumps(m["give_up_reasons"], ensure_ascii=False)])
    out.append(table(["Băng", "Cấu hình", "availability", "p95 (s)", "give_up_reasons"], rows))
    out.append(r"""
G6 timeout 30 làm availability tụt 1,0 → 0,9488 trong khi p95 giảm 5,961 → 5,410: các lượt treo bị deadline loại khỏi tập tính p95, không phải hệ thống nhanh hơn. G4 gần như không đổi (5,562 → 5,608 giây; availability giữ 1,0) vì slow successes và breaker vẫn phát hiện vùng chậm trước khi timeout 30 có tác dụng. Timeout nên dựa trên p99 của attempt khi healthy và phần deadline còn lại dành cho các bước/failover; deadline user 30 giây không phải timeout phù hợp cho một attempt. Helper vẫn dùng `_send` để cap timeout theo deadline.

### 3.3 Bỏ lọc tool calling khỏi ladder
"""
    )
    m = exp("unfiltered", "G6_provider_outage")
    out.append(f"""
G6 chuẩn có **0 incompatible routes**, availability **1,0**. Subclass thí nghiệm cho phép tool call tới gamma-mini tạo **{m['incompatible_routes']} incompatible routes**, availability còn **{m['availability']}**, cost/good-turn **{m['cost_per_good_turn']}**. Với product manager: model dự phòng có thể trả lời văn bản nhưng không thể thực hiện bước công cụ mà sản phẩm cần; khách hàng nhận thất bại dù vẫn có một model online. Fallback phải giữ năng lực cần thiết của tác vụ, không chỉ chọn model rẻ.

## 4. Workflow hoàn tiền
"""
    )
    out.append(table(["Executor", "completion", "crashes", "duplicate refunds", "duplicate emails", "lost refunds",
                      "overpaid (cents)", "wasted LLM / crash"], [
        [name, m["completion_rate"], m["worker_crashes"], m["duplicate_refunds"], m["duplicate_emails"],
         m["lost_refunds"], m["overpaid_cents"], m["wasted_llm_per_crash"]] for name, m in workflow.items()
    ]))
    out.append(r"""
Nguồn: `reports/workflows.json`, 500 session, seed 25. Bản mới có 2500 checkpoint writes: năm bước cho mỗi session; restart bỏ qua bước đã hoàn tất.

Chỉ idempotency key tránh refund/email lặp nhưng không tránh tính lại classify/lookup/summary, làm tốn LLM và khó resume. Chỉ checkpoint không bảo vệ khoảng giữa payment đã thực thi và checkpoint chưa ghi: timeout hoặc crash ở đó khiến restart gọi payment lại. Vì vậy key phải ổn định theo session+step, còn checkpoint ghi sau response thành công; nếu ghi trước payment, crash có thể khiến restart bỏ qua refund chưa hề chạy. `WorkerCrash` truyền tới runner để tạo worker mới; key được length-prefix để tránh va chạm dấu phân cách và có namespace riêng cho checkpoint.

## 5. Alerting & error budget
"""
    )
    rows = []
    for n, b in zip(slo["naive"]["incidents"], slo["burnrate"]["incidents"]):
        def status(r: dict) -> str:
            if r["expect"] == "none":
                return "page nhầm" if r["paged"] else "không page"
            return r["expect"] if r["detected"] else "không phát hiện"
        rows.append([b["incident"], b["expect"], status(n), status(b), b.get("delay_min")])
    out.append(table(["Sự cố", "Mong đợi", "Naive alerter", "Burn-rate alerter", "Độ trễ mới (phút)"], rows))
    budget = slo["burnrate"]["budget"]
    out.append(f"""
Nguồn: `reports/slo.json`, `data/sli_30d.csv` (43.200 phút). Naive có 7 pages/0 tickets và 3 false pages; burn-rate có **3 pages/1 ticket/0 false pages**, mọi sự cố cần phát hiện đều trong thời hạn. Hai cửa sổ cùng đạt ngưỡng mới phát cảnh báo: page 14,4× (1h/5m), page 6× (6h/30m), ticket 1× (3d/6h); prefix sums giúp query mỗi cửa sổ O(1).

30 ngày có **{budget['requests']:,} requests**, **{budget['bad']:,} lỗi**, allowance **{budget['allowed_bad']:,}** và availability **{budget['availability']}**. Budget đã tiêu **{budget['budget_consumed'] * 100:.2f}%**, còn **{budget['budget_remaining'] * 100:.2f}%**: **không đóng băng release**. Quyết định freeze dùng consumption chưa làm tròn; số hiển thị làm tròn không được tạo freeze sớm khi còn một request allowance.

`small_bump` 20 phút ở 12% lỗi có burn rate xấp xỉ 24× trong cửa sổ ngắn, nhưng nếu phần còn lại bình thường thì cửa sổ 1h chỉ khoảng 8×, thấp hơn 14,4×; cửa sổ 6h chỉ khoảng 1,33×, thấp hơn 6×. Vì vậy không nên page chỉ từ ngưỡng 5 phút. Tính theo lượng request, không trung bình các tỷ lệ phút, để traffic ban đêm không gây page sai.

## 6. Postmortem — Băng G2 với client naive (blameless)

![Naive và resilient trên G2](gameday/G2_overload_storm.png)

**Tóm tắt:** Alpha mất 75% năng lực GPU tại t=120–300 giây. Retry chồng ba tầng giữ hàng đợi quá tải, biến sự cố provider ba phút thành thời gian gián đoạn kéo dài sau restore. Client mới giới hạn retry và dùng breaker/fallback, giữ availability 100% trên cùng băng seed 25.
"""
    )
    g2 = naive["G2_overload_storm"]
    failed = g2["turns"] - g2["good_turns"]
    out.append(f"""
**Ảnh hưởng:** {failed}/{g2['turns']} lượt user không thành công (**{failed / g2['turns'] * 100:.2f}%**); {g2['attempts']} attempt cho {g2['calls']} logical call, amplification {g2['amplification']}. Provider restore tại t=300 nhưng recovery metric chỉ đạt tại t=455, trễ **155 giây**; từ trigger tới mốc đó là **335 giây**, không đồng nghĩa mọi lượt trong khoảng đều thất bại. Giả sử traffic tháng đều 4 lượt/s và tháng chỉ có sự cố này: volume=10.368.000 lượt, error budget 99,5%=51.840 lượt; {failed} lượt lỗi tiêu **{failed / 51840 * 100:.4f}% budget tháng**. Đây là giả định impact cho G2, khác bộ SLI thực tế ở mục 5.

**Timeline:** attempts/s là bucket một giây; success ratio là tổng calls_ok / calls_done trong 10 giây kết thúc tại t, cùng cách rolling của hình. Số lấy trực tiếp từ `gameday/naive_G2_overload_storm_timeseries.csv`, không suy ra từ thời điểm sự cố.
"""
    )
    with Path("reports/gameday/naive_G2_overload_storm_timeseries.csv").open(encoding="utf-8") as stream:
        ts = [{key: int(value) for key, value in row.items()} for row in csv.DictReader(stream)]
    events = {
        110: "Trước sự cố", 120: "Trigger: năng lực alpha giảm 75%", 130: "Hàng đợi tăng trước timeout",
        150: "Retry storm; logical call bắt đầu thất bại", 200: "Vòng lặp quá tải duy trì",
        300: "Provider restore; client vẫn nghẹt", 350: "Chưa phục hồi dù đã restore 50 giây",
        400: "Retry tiếp tục lấp hàng đợi", 455: "Mốc recovery của cửa sổ 30 giây",
        480: "Tỷ lệ thành công 10 giây đã trở lại 100%",
    }
    rows = []
    for t, event in events.items():
        window = ts[max(0, t - 9):t + 1]
        ok, done = sum(r["calls_ok"] for r in window), sum(r["calls_done"] for r in window)
        rows.append([t, event, ts[t]["attempts_alpha"], f"{ok}/{done} = {ok / done:.4f}" if done else "không có call"])
    out.append(table(["t (giây ảo)", "Sự kiện", "alpha attempts/s", "Success ratio 10 giây"], rows))
    out.append(r"""
**Trigger vs root cause:** Trigger là mất năng lực GPU. Root cause phía hệ thống là retry ba tầng (tối đa 36 attempt/call), delay cố định, không budget/breaker/fallback; không phải hành vi của một cá nhân. Client timeout không hủy xử lý trên server, nên request đã bị bỏ vẫn chiếm slot và hàng đợi. Timeout → retry thêm → queue dài hơn → timeout nhiều hơn tạo vòng lặp metastable: restore GPU tại t=300 không xóa backlog và client vẫn tạo tải vượt năng lực.

**Điều giúp:** provider phục hồi năng lực, jitter/budget/breaker giới hạn tải, fallback giúp luồng mới tránh vùng bệnh. **Điều làm tệ hơn:** retry nhiều tầng, không tôn trọng retry-after và đánh giá dashboard chỉ bằng p95 các lượt thành công. Naive G2 có 28.381 retry-after violations; bản mới có 0. Blameless: đây là khoảng trống về chính sách retry và kiểm thử failure modes của hệ thống.

| # | Hành động | Loại | Owner | Cách kiểm chứng |
|---|---|---|---|---|
| 1 | Giữ một tầng retry, full jitter, budget toàn client | prevent | Nguyễn Nhân Sâm — client | G2 amplification <=1,6 và G3 retry ratio <=0,10 trên seed 25/26/27; test retry-after đạt |
| 2 | Theo dõi burn rate, provider timeout, breaker state và tỷ lệ stale | detect | Nguyễn Nhân Sâm — observability | SLO public 0 false page; provider_outage page trong <=8 phút; dashboard drill vẫn báo outage khi cache phục vụ |
| 3 | Breaker slow-call và fallback có kiểm tra capability, giới hạn probe | mitigate | Nguyễn Nhân Sâm — routing | G2 recovery <=30 giây; G4 p95 <=10 giây; G6 incompatible_routes=0 và primary share >=0,8 |
| 4 | Kiểm tra crash ngay sau payment và khóa idempotency ổn định | prevent | Nguyễn Nhân Sâm — workflow | 500 workflows: duplicate/lost refunds=0; completion >=0,99 |

Các gate mô phỏng trên đã chạy local; wiring CI cho provider metrics/drill ngoài mô phỏng là việc tiếp theo, chưa triển khai production.

## 7. Một điểm yếu còn lại

G2 vẫn có p95 **11,911 giây** dù availability 100% và amplification 1,059: các call đã vào alpha trước khi đủ mẫu trip có thể chờ tới timeout rồi mới failover. Trên seed 26 p95 là 11,421, seed 27 là 9,789. Bước cải thiện đề xuất là đo p99 attempt khi healthy, thử timeout/deadline allocation theo task và độ nhạy slow-call breaker trên nhiều biến thể cường độ; chưa đổi cấu hình chỉ để làm đẹp một seed vì có thể tăng timeout giả, chi phí hoặc failover không cần thiết. G6 cost/good-turn 2,196 cũng cao hơn naive 2,009, nhưng naive chỉ phục vụ thành công 51,7% lượt: không thể coi chi phí thấp của naive là chất lượng tương đương.

## 8. Cache (Part G)
"""
    )
    keys = ["availability", "faq_availability", "cache_hit_ratio", "stale_served", "wrong_answers", "outdated_answers", "cost_per_good_turn"]
    out.append(table(["Client", "availability", "faq_availability", "cache_hit_ratio", "stale_served", "wrong_answers",
                      "outdated_answers", "cost/turn", "PASS?"], [
        [name, *(m[k] for k in keys), "PASS" if m["pass"] else "FAIL"] for name, m in [
            ("resilient, không cache", uncached), ("cached", cached)
        ]
    ]))
    out.append(r"""
Nguồn: `reports/cache/*.json`, C1 seed 25. Bản không cache được dùng làm đối chứng nên dự kiến không đạt hai check cache. Starter cache (threshold 0,80 / TTL 600 / stale 0) có 181 wrong_answers do other_question, 80 outdated_answers và FAQ availability 0,8587; output giữ trong `reports/validation/cache_starter_config/`.

| Tham số cache | Giá trị | Lý do dựa trên số liệu |
|---|---|---|
| similarity_threshold | 0,92 | 0 wrong_answers, hit 0,652; threshold 0,80 ở cùng TTL/stale tạo 157 câu sai |
| ttl_s | 60 | Chỉ 3 câu outdated; TTL 300 tạo 95 câu outdated, vượt check <=15 |
| max_stale_s | 300 | 157 lượt stale; FAQ availability 0,9645; tắt stale còn 0,8733 |
| max_entries | 500 | Giữ giới hạn bộ nhớ với LRU; test eviction đạt; không tuyên bố 500 là dung lượng tối ưu |

### 8.1 Thí nghiệm ngưỡng similarity
"""
    )
    out.append(table(["Threshold", "hit ratio", "wrong_answers", "wrong_answers_by_reason", "FAQ availability", "cost/turn"], [
        [value, m["cache_hit_ratio"], m["wrong_answers"], json.dumps(m["wrong_answers_by_reason"]),
         m["faq_availability"], m["cost_per_good_turn"]]
        for value, m in [(v, exp(f"threshold_{v}")) for v in (0.8, 0.92, 0.97)]
    ]))
    out.append(r"""
Ở 0,80, cả 157 lỗi thuộc `other_question`; catalog có các cặp gần nhưng khác nghĩa như chính sách hoàn tiền/thời gian nhận tiền, đổi size/đổi màu và phí ship nội thành/đi tỉnh. Aggregate metric không ghi danh sách từng câu bị nhầm, nên không khẳng định cả 157 lỗi đều thuộc một cặp cụ thể. Ngưỡng 0,97 không có câu sai nhưng hit giảm 0,652 → 0,581 và cost tăng 0,915 → 0,964; 0,92 giữ đúng câu hỏi với hit cao hơn trong băng đã đo. Không suy diễn threshold này sẽ phù hợp mọi embedding model thực tế.

### 8.2 Thí nghiệm TTL
"""
    )
    out.append(table(["TTL (s)", "hit ratio", "outdated_answers", "wrong_answers", "FAQ availability", "cost/turn"], [
        [ttl, m["cache_hit_ratio"], m["outdated_answers"], m["wrong_answers"], m["faq_availability"], m["cost_per_good_turn"]]
        for ttl, m in [(v, exp(f"ttl_{v}")) for v in (30, 60, 300)]
    ]))
    out.append(r"""
Webhook invalidation xử lý thay đổi chính sách có thông báo tại t=150; nó không biết phí ship đổi âm thầm tại t=480. TTL buộc cache revalidate khi provider healthy nên giới hạn câu outdated do thay đổi không được thông báo: TTL 30 có 2 câu, 60 có 3, 300 có 95. TTL 60 cân bằng độ mới, hit và cost tốt hơn 30 trên băng này. Trong outage, stale window vẫn cho phép tuổi dài hơn TTL, nên không coi TTL là giới hạn tuyệt đối độ cũ của mọi câu trả lời trong mọi tình huống.

### 8.3 Thí nghiệm stale-if-error
"""
    )
    no_stale = exp("no_stale")
    out.append(table(["max_stale_s", "FAQ availability", "hit ratio", "stale_served", "wrong_answers", "outdated_answers"], [
        [v, m["faq_availability"], m["cache_hit_ratio"], m["stale_served"], m["wrong_answers"], m["outdated_answers"]]
        for v, m in [(0, no_stale), (300, cached)]
    ]))
    out.append(r"""
Không stale, FAQ availability chỉ 0,8733; có stale tăng tới 0,9645 mà vẫn 0 câu sai. Entry quá TTL được thử provider trước, chỉ dùng khi inner client GiveUp và lookup lại ở thời điểm đó. Invalidation xóa cả stale; prompt v2 không được đọc entry v1; câu hỏi cá nhân luôn bypass cache. TTL+max_stale là hạn cuối của entry, không được gia hạn chỉ vì cache hit.

**Vì sao không cache câu hỏi cá nhân kể cả theo user?** Trạng thái đơn, hoàn tiền và số điểm thay đổi nhanh theo giao dịch; cùng user và câu tương tự chưa chứng minh nội dung còn đúng hay cùng đơn hàng. Semantic similarity giữa đơn #123 và #124 có thể rất cao nhưng khác đối tượng. Lab quy định personal request không thuộc allowlist; production muốn cache phải thiết kế riêng exact entity key, quyền truy cập và invalidation theo giao dịch, chưa nằm trong bài này.

**Alert khi dashboard xanh nhờ cache:** Giữ SLI kết quả user để đo trải nghiệm, đồng thời theo dõi tỷ lệ provider errors/timeouts, breaker OPEN/HALF_OPEN, fallback rate, stale-served ratio và tuổi stale. C1 phục vụ 157 lượt stale che một phần provider outage; lỗi của attempt/provider vẫn phải được ghi dù user nhận Serve thành công. Các metric/alert này là đề xuất vận hành, không khẳng định đã kết nối hệ thống observability thật.

### Kiểm chứng nhiều seed và tái lập
"""
    )
    rows = []
    for seed in (25, 26, 27):
        m = load(f"reports/validation/seed-{seed}/cache/cached.json")["C1_faq_outage"]
        w = load(f"reports/validation/seed-{seed}/workflows.json")["yours"]
        g = load(f"reports/validation/seed-{seed}/gameday/resilient.json")
        rows.append([seed, f"{sum(x['pass'] for x in g.values())}/6", m["faq_availability"], m["cache_hit_ratio"],
                     m["wrong_answers"], m["outdated_answers"], w["completion_rate"], w["wasted_llm_per_crash"]])
    out.append(table(["Seed", "G1–G6 đạt", "FAQ availability", "cache hit", "wrong", "outdated", "workflow completion", "LLM/crash"], rows))
    out.append(r"""
Các lệnh tương đương Makefile, chạy từ root repo sau khi cài Python >=3.10:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,plot]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/run_gameday.py --client both
.\.venv\Scripts\python.exe scripts/run_gameday.py --scenarios configs/scenarios_cache.yaml --client resilient,cached --out reports/cache
.\.venv\Scripts\python.exe scripts/run_workflows.py --executor both
.\.venv\Scripts\python.exe scripts/run_slo.py --alerter both
.\.venv\Scripts\python.exe scripts/run_required_experiments.py
$env:MPLBACKEND = 'Agg'
.\.venv\Scripts\python.exe scripts/plot_timeseries.py --scenario G2_overload_storm
.\.venv\Scripts\python.exe scripts/grade.py --seeds 25,26,27 --out reports/scoreboard_multiseed.json
.\.venv\Scripts\python.exe scripts/grade.py
```

Trong phiên Codex này dùng `.venv-codex` với Python runtime đi kèm app vì `.venv` cũ trỏ tới Python311 không chạy được trong sandbox. `Agg` tạo PNG không cần Tk/Tcl. Artifact được giữ trong `reports/`; không dùng `make clean` trước khi nộp vì lệnh đó xóa JSON/CSV/hình. Exit code 0 của CLI chưa chứng minh băng pass; phải đọc `pass` và từng `checks` trong JSON.

**Ranh giới bàn giao:** code/report/test là kết quả local; GitHub chưa được push trong lượt thực hiện này, chưa xác minh repo public và chưa gửi link lớp. Remote hiện có tên `Track3-Day25-2A202602672-NguyenNhanSam`; đề yêu cầu tên `Track3-Day25-2A202602672-Nguyen-Nhan-Sam`, nên cần đổi tên remote trước khi nộp. Không có dữ liệu SLO ẩn để chấm 4 điểm cuối.
"""
    )
    Path("reports/REPORT.md").write_text("\n\n".join(out).strip() + "\n", encoding="utf-8")
    print("wrote reports/REPORT.md")


if __name__ == "__main__":
    main()
