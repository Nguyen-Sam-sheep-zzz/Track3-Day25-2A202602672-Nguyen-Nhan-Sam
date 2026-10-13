# Lab 25B Game Day Implementation Plan

**Trạng thái thực thi 13/10/2026:** đã hoàn thành code A/B/C/G/D/E, report F và kiểm chứng local Task 0–8. Full suite 99/99, grader public 84/88 trên seed 25/26/27 và trong môi trường sạch. Checklist ban đầu dưới đây giữ làm mô tả kế hoạch; kết quả thực tế xem `docs/COMPLETION.md`, `reports/REPORT.md` và `reports/validation/verification.json`. Đổi tên repo remote, push main và gửi link lớp chưa thực hiện.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thành A–G của Lab 25B, chứng minh bằng test và mô phỏng rằng ShopAgent chịu lỗi, không tạo retry storm, không hoàn tiền trùng và cache FAQ đúng; bàn giao báo cáo cùng artifact có thể tái lập.

**Architecture:** Simulator cung cấp thời gian ảo, request, provider và callback; code sinh viên chỉ quyết định `Send`, `GiveUp` hoặc `Serve`. `ResilientClient` ghép phân loại lỗi, retry budget, backoff, breaker và fallback; `CachingClient` bọc bên ngoài. Workflow và SLO là hai thành phần độc lập, dùng contracts có sẵn.

**Tech Stack:** Python >= 3.10, PyYAML, pytest; matplotlib để vẽ postmortem; PowerShell trên Windows. Không cần API key, model thật, Docker hay GPU.

**Spec:** `README.md`, `docs/RUBRIC.md`, `reports/REPORT_TEMPLATE.md`; API trong `src/gameday_lab/sim/contracts.py`; cách tính điểm trong `scripts/grade.py`.

## Global Constraints

- Python >= 3.10; SLO availability 99,5% / 30 ngày; deadline của lượt user là 30 giây.
- Dùng `now` và thời gian ảo; không dùng `time.time()` hoặc `time.sleep()` trong code sinh viên.
- Không sửa `src/gameday_lab/sim/`, `src/gameday_lab/naive_client.py`, `src/gameday_lab/workflows/services.py`, `src/gameday_lab/workflows/runner.py`, `src/gameday_lab/workflows/naive_executor.py`, `src/gameday_lab/slo/data.py`, `src/gameday_lab/slo/scoring.py`, `configs/scenarios.yaml`, `configs/scenarios_cache.yaml`, các test gốc.
- Chỉ hoàn thành các file có phần dành cho sinh viên; trong `configs/gameday.yaml` chỉ chỉnh `client:` và `cache:`. Có thể thêm helper/test riêng.
- Không hard-code thời điểm sự cố, tên băng hoặc tên tài liệu trong client/cache; không đọc state nội bộ simulator.
- Tool call chỉ gửi tới provider có `supports_tools=True`.
- Câu hỏi cá nhân không cache; scope cache phải có `prompt_version`; stale không được vượt invalidation.
- Không bắt `WorkerCrash`; checkpoint sau khi bước chạy thành công.
- Một băng chỉ có điểm nếu mọi check đạt trên mọi seed được chấm.
- Repo public; tên theo đề là `Track3-Day25-<MSV>-<Họ-Và-Tên>`; code nộp ở `main`; commit cả report, scoreboard và hình.
- Kế hoạch này chưa phải kết quả thực thi. Commit/push/publication/nộp lớp là các trạng thái riêng, cần quyền tương ứng khi thực hiện.

---

## 1. Tổng quan và trạng thái đã đọc

Bạn đóng vai on-call của ShopAgent, một agent CSKH hoàn tiền. Mỗi lượt thông thường gồm một call `tool`, thực thi tool, rồi một call `chat`. Bản `NaiveClient` retry ba tầng app × gateway × SDK, tối đa 36 attempt/call. Khi provider quá tải, client timeout nhưng provider vẫn xử lý request cũ, khiến retry tiếp tục lấp đầy hàng đợi ngay cả sau khi năng lực provider đã phục hồi.

Mục tiêu là thay client và chứng minh bằng số, không phải xây UI hay kết nối dịch vụ AI thật. Cache FAQ là phần bắt buộc, không phải bonus.

Trạng thái lúc lập kế hoạch ngày 13/10/2026:

- Nhánh hiện tại `main`; kiểm tra Git không liệt kê file thay đổi trước khi tạo kế hoạch này.
- Các điểm cần triển khai ở errors/retry/breaker/client/cache/executor/alerting vẫn `NotImplementedError`.
- `reports/` có template; chưa có `REPORT.md` và scoreboard trong danh sách file đã kiểm tra.
- `python` và `py` không có trên PATH của phiên sandbox hiện tại.
- Đã xác nhận runtime Python đi kèm app chạy được, phiên bản 3.12.14; runtime đó chưa có pytest, PyYAML hoặc matplotlib.
- Chưa cài dependency, chưa chạy test/baseline/grade. Không kết luận số test pass/fail từ việc đọc source.

Phân bổ điểm:

| Phần | Điểm | Sản phẩm |
|---|---:|---|
| A | 12 | Phân loại lỗi, full jitter, retry budget |
| B | 12 | Sliding-window circuit breaker |
| C | 30 | ResilientClient: unit test 6 + G1–G6 tổng 24 |
| G | 10 | SemanticCache + CachingClient: unit test 4 + C1 tổng 6 |
| D | 12 | Idempotency + checkpoint + resume |
| E | 12 | Alerting: unit test 4 + SLO public 4 + SLO hidden 4 |
| F | 12 | Report đầy đủ và postmortem G2 |

`grade.py` ghi `automatic_max=88`, nhưng khi không có `--hidden-slo`, 4 điểm SLO hidden để 0 và `pass=None`. Do đó **84/88 là mức tối đa tự kiểm chứng bằng dữ liệu public trong repo**, còn 4 điểm hidden và 12 điểm report do giảng viên đánh giá. Public pass không bảo đảm băng ẩn pass.

## 2. Bản đồ file và thứ tự

| File được triển khai | Trách nhiệm | Kiểm chứng |
|---|---|---|
| `src/gameday_lab/errors.py` | Chính sách theo loại lỗi | `tests/test_errors_retry.py` |
| `src/gameday_lab/retry.py` | Full jitter + token bucket | `tests/test_errors_retry.py` |
| `src/gameday_lab/breaker.py` | State machine + permit generation | `tests/test_breaker.py` |
| `src/gameday_lab/client.py` | Routing, cooldown, retry, deadline | `tests/test_client.py`, G1–G6 |
| `src/gameday_lab/cache.py` | Semantic lookup, TTL, invalidation, stale fallback | `tests/test_cache.py`, C1 |
| `src/gameday_lab/workflows/executor.py` | Exactly-once effects và resume | `tests/test_executor.py`, 500 workflows |
| `src/gameday_lab/slo/alerting.py` | Prefix sums, burn rate, error budget | `tests/test_alerting.py`, SLI 30 ngày |
| `configs/gameday.yaml` | Tham số `client:` và `cache:` | Băng public, nhiều seed, thí nghiệm |
| `scripts/run_required_experiments.py` (thêm) | Thí nghiệm report, không đổi code chấm | JSON riêng cho từng thí nghiệm |
| `reports/REPORT.md` (thêm) | Tổng hợp số liệu và postmortem | Đối chiếu rubric chấm tay |

Thứ tự: **môi trường/baseline → A → B → C → G → D → E → thí nghiệm/report → kiểm tra nộp bài**. Sau mỗi task báo ngắn: đã sửa gì, test/băng nào đạt, metric còn lệch, bước kế tiếp. Khi triển khai, đọc lại spec và skill executing-plans; thực hiện từng checkpoint trong phiên hiện tại là lựa chọn mặc định, chưa dispatch agent ở giai đoạn lập kế hoạch.

Đề thiết kế cho 4 giờ; với cài môi trường, tuning, thí nghiệm và báo cáo có bằng chứng, nên dành khoảng **6–8 giờ**, tùy số vòng tuning. Đây là ước lượng, không phải cam kết hoàn thành.

## Task 0: Chuẩn bị môi trường và lưu baseline (20–30 phút)

**Files:** tạo `.venv/` (đã được gitignore), output baseline trong `reports/gameday/`; không sửa simulator/test/config băng.

**Interfaces:** dùng các CLI có sẵn; tạo `naive.json` và timeseries CSV để Task F dùng.

- [ ] Xác nhận Python >= 3.10. Nếu user terminal có `py -3`, dùng launcher; nếu giống phiên hiện tại, dùng runtime đã xác minh:

```powershell
$labPython = 'C:\Users\SAM\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $labPython -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[dev,plot]'
& .\.venv\Scripts\python.exe -c 'import sys, yaml, pytest, matplotlib; print(sys.version)'
```

- [ ] Nếu pip không kết nối được, lưu đúng lỗi và xử lý quyền mạng/cached packages trước; không suy diễn rằng dependency đã cài.
- [ ] Chạy test starter để ghi nhận trạng thái ban đầu, rồi simulator sanity:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --tb=short
& .\.venv\Scripts\python.exe -m pytest tests/test_sim_sanity.py -q
& .\.venv\Scripts\python.exe scripts/run_gameday.py --client naive
```

- [ ] Giữ `reports/gameday/naive.json`, đặc biệt `naive_G2_overload_storm_timeseries.csv`. Test phần sinh viên thất bại do stub là dự kiến; sanity test cần pass để baseline đáng tin.
- [ ] Nếu Git gặp dubious ownership, dùng `git -c safe.directory=C:/Users/SAM/IdeaProjects/VinUniAIThucChien/Lap25/Track3-Day25-2A202602672-NguyenNhanSam ...` cho từng lệnh, không thay cấu hình global.

**Gate 0:** interpreter và dependency chạy; sanity pass; có baseline thực tế, chưa gắn kết quả giả định vào report.

## Task 1: Part A — chính sách lỗi và retry (25–35 phút)

**Files:** sửa `errors.py`, `retry.py` trong `src/gameday_lab/`; dùng test gốc `tests/test_errors_retry.py`.

**Interfaces:** `classify(err: ProviderError) -> ErrorKind`; `is_retryable`, `counts_toward_breaker`, `failover_helps` nhận `ErrorKind`, trả `bool`; `FullJitterBackoff.delay(retry_number, retry_after=None) -> float`; `RetryBudget.record_request(now)`; `try_acquire_retry(now) -> bool`.

- [ ] Chạy `tests/test_errors_retry.py` trước khi sửa để thấy failure từ stub.
- [ ] Triển khai classify theo đúng thứ tự: 0/408 → timeout; 429 + insufficient_quota → quota; 429 còn lại → rate limit; 503/529 → overload; 5xx còn lại → server; còn lại → client error.
- [ ] Áp dụng bảng chính sách dưới đây; phân biệt “có thể retry” với hành động client thực tế, vì 429 rate limit ưu tiên spillover.

| Loại | Retry cùng provider? | Đếm breaker? | Failover có ích? |
|---|---|---|---|
| Client error | Không | Không | Không |
| Quota exhausted | Không | Không | Có |
| Rate limited | Có sau retry-after | Không | Có |
| Overloaded/server/timeout | Có khi budget/deadline cho phép | Có | Có |

- [ ] Backoff dùng seeded RNG và công thức chính xác:

```python
if retry_number < 1:
    raise ValueError("retry_number must be >= 1")
if retry_after is not None:
    return retry_after + self.rng.uniform(0, self.base_s)
return self.rng.uniform(0, min(self.cap_s, self.base_s * 2 ** (retry_number - 1)))
```

- [ ] Token bucket nạp theo thời gian ảo, giới hạn `max_tokens`, thêm `ratio` cho mỗi logical call mới, chỉ trừ 1 khi cho phép retry. Token ban đầu và `min_per_s` tạo burst allowance; không diễn giải ratio như giới hạn tuyệt đối trong mọi khoảng ngắn.
- [ ] Chạy `& .\.venv\Scripts\python.exe -m pytest tests/test_errors_retry.py -q`.

**Gate A:** toàn bộ test A pass; không retry quota/client error; không retry sớm hơn retry-after.

## Task 2: Part B — circuit breaker (40–55 phút)

**Files:** sửa `src/gameday_lab/breaker.py`; test `tests/test_breaker.py`.

**Interfaces:** `allow(now) -> Permit | None`; `on_success(permit, now, latency_s)`; `on_failure(permit, now)`; `release(permit, now)`. Dùng `_move()` có sẵn để mọi transition cập nhật generation và log.

- [ ] Chạy test B trước khi sửa.
- [ ] `_record`: giữ đúng `window_size` kết quả cuối; chỉ xét tỷ lệ khi đủ `min_calls`; ưu tiên failure threshold, rồi slow-success threshold.
- [ ] `allow`: CLOSED cấp permit; OPEN từ chối tới hết cooldown; HALF_OPEN chỉ cấp tối đa `half_open_max_probes` permit đang bay.
- [ ] Mọi callback bỏ qua permit cũ:

```python
if permit.generation != self.generation:
    return
```

- [ ] Probe lỗi/chậm mở lại breaker; đủ probe thành công đóng breaker; `release` giải phóng probe mà không ghi nhận lỗi sức khỏe.
- [ ] Kiểm tra slow success và kết quả đến muộn riêng, rồi chạy `& .\.venv\Scripts\python.exe -m pytest tests/test_breaker.py -q`.

**Gate B:** toàn bộ test B pass; không có probe herd, không có kết quả thế hệ cũ đóng breaker mới.

## Task 3: Part C — ghép client và đạt G1–G6 (60–90 phút)

**Files:** sửa `src/gameday_lab/client.py`; tinh chỉnh riêng khối `client:` trong `configs/gameday.yaml`; test `tests/test_client.py`.

**Interfaces:** tuân theo `BaseClient` trong contracts; state mỗi call gồm `ladder`, `idx`, `tries`; permit đi qua `Send.tag` và `Attempt.tag`. Retry budget, breaker và cooldown là state dùng chung giữa các call trong một client.

- [ ] Chạy test C trước khi sửa. `ladder('tool')` phải giữ alpha/alpha-eu/beta; `ladder('chat')` giữ đủ bốn provider.
- [ ] `start` nạp budget một lần cho logical call, khởi tạo state và route; số `tries` phải đếm attempt được gửi trên provider hiện tại, kể cả lần đầu.
- [ ] `_route` kiểm tra cooldown ở thời điểm gửi `now + delay`; dùng helper `_send` có sẵn; khi bỏ provider reset tries/delay. Nếu hết ladder chỉ chờ cooldown rate limit ngắn <= 5 giây khi còn deadline, không chờ cooldown quota dài.
- [ ] `on_success` truyền latency vào breaker; `on_cancel` release permit.
- [ ] `on_error` áp dụng bảng sau:

| Loại | Breaker | Hành động |
|---|---|---|
| Client error | release | GiveUp ngay, không retry/failover |
| Quota exhausted | release | cooldown provider rồi failover ngay |
| Rate limited | release | cooldown ít nhất retry-after rồi failover ngay |
| Overloaded/server/timeout | on_failure | retry nếu còn tries, budget, deadline và permit; nếu không failover |

- [ ] Kiểm tra mọi `Send`: `now + delay_s + timeout_s <= call.deadline`; không tiêu token retry cho request không thực sự được phép gửi nếu tránh được.
- [ ] Chạy unit test C, sau đó so sánh:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_client.py -q
& .\.venv\Scripts\python.exe scripts/run_gameday.py --client both
```

- [ ] Tune theo check đang fail; chỉ đổi một nhóm tham số mỗi lần, lưu config và output riêng. Trước tiên kiểm tra lỗi logic; không dùng tuning để che sai classification/deadline/permit.

| Băng | Gate đầy đủ theo config public |
|---|---|
| G1 rate-limit spike | availability >= 98%; retry-after violations = 0; amplification <= 1,6 |
| G2 overload storm | availability >= 95%; amplification <= 1,6; recovery <= 30 giây; primary share sau restore >= 80% |
| G3 brownout | availability >= 98%; retry ratio <= 0,10; amplification <= 1,6 |
| G4 slow region | availability >= 97%; p95 <= 10 giây; primary share sau restore >= 80% |
| G5 malformed rồi quota | client error retries = 0; unneeded failovers <= 10; availability >= 78% |
| G6 outage | availability >= 95%; incompatible routes = 0; primary share sau restore >= 80% |

- [ ] Giữ primary là lựa chọn đầu khi healthy; quota trong G5 ảnh hưởng family A nhưng contract/test yêu cầu cooldown theo provider nhận lỗi, không tự thay đổi contract.

**Gate C:** unit test pass và 6/6 băng public pass; mỗi threshold có số đo, chưa khẳng định băng ẩn.

## Task 4: Part G — semantic cache và stale-if-error (45–65 phút)

**Files:** sửa `src/gameday_lab/cache.py`; tinh chỉnh riêng `cache:` trong config; test `tests/test_cache.py`.

**Interfaces:** `lookup(req: Request, now) -> CacheHit | None`; `store(req, answer, now)`; `invalidate(source, now) -> int`; `CachingClient` trả `Serve` khi dùng cache và chuyển callback tới inner client.

- [ ] Chạy test cache trước khi sửa; tests dùng fake inner client, không phụ thuộc simulator.
- [ ] Lookup loại personal request, xóa entry quá `ttl_s + max_stale_s`, lọc theo prompt version rồi chọn cosine cao nhất đủ threshold. Fresh khi age <= TTL; hit cập nhật LRU.
- [ ] Store chỉ FAQ không cá nhân; refresh entry tương tự trong cùng scope; vượt `max_entries` thì đuổi entry ít dùng nhất.
- [ ] Invalidation bỏ mọi entry chứa source được thông báo, kể cả entry stale; không hard-code source cụ thể.
- [ ] Wrapper: fresh hit → Serve; miss/stale → thử provider; success thông báo inner trước rồi store `call.answer`; GiveUp → lookup lại ngay thời điểm đó, rồi Serve nếu còn hit. Không giữ snapshot stale từ lúc start để vượt qua webhook xảy ra giữa chừng.
- [ ] Bắt đầu khảo sát threshold 0,92, TTL 60 giây, stale window 300 giây, max_entries 500. Đây là cấu hình thử, chưa là đáp án đã xác nhận; điều chỉnh bằng metric C1.

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_cache.py -q
& .\.venv\Scripts\python.exe scripts/run_gameday.py --scenarios configs/scenarios_cache.yaml --client resilient,cached --out reports/cache
```

- [ ] Đọc `wrong_answers_by_reason` trước khi tối ưu hit ratio/cost: `other_question`, `other_user`, `old_prompt`, `ignored_invalidation` phải bằng 0.

**Gate G:** unit test pass; C1 `wrong_answers=0`, `outdated_answers<=15`, `faq_availability>=93%`, `cache_hit_ratio>=50%`. Availability tổng khác FAQ availability; stale giữ trải nghiệm user nhưng cần theo dõi lỗi provider riêng.

## Task 5: Part D — workflow hoàn tiền exactly-once effects (30–45 phút)

**Files:** sửa `src/gameday_lab/workflows/executor.py`; dùng `tests/test_executor.py` và CLI workflow.

**Interfaces:** `idempotency_key(req: RefundRequest, step: str) -> str`; `checkpoint_key(req, step) -> str`; `_retry(fn: Callable[[], T]) -> T`; `run(req) -> dict[str, Any]`. Dùng `STEPS`, `_step`, `DurableStore.get/put` có sẵn.

- [ ] Chạy tests D trước khi sửa. Tạo key ổn định theo `(session_id, step)`, tách namespace cho idempotency/checkpoint; không dùng UUID/random/Python hash thay đổi giữa process.
- [ ] Ví dụ key có encoding không mơ hồ:

```python
import json

def idempotency_key(req: RefundRequest, step: str) -> str:
    return "idem:" + json.dumps([req.session_id, step], ensure_ascii=True, separators=(",", ":"))

def checkpoint_key(req: RefundRequest, step: str) -> str:
    return "checkpoint:" + json.dumps([req.session_id, step], ensure_ascii=True, separators=(",", ":"))
```

- [ ] `_retry` chỉ bắt `ServiceError` và `ServiceTimeout`, tối đa `max_attempts`, hết thì re-raise; không bắt WorkerCrash hoặc BaseException.
- [ ] Mỗi step: nếu checkpoint có thì load; nếu chưa có thì `_step`, sau thành công mới `store.put`, rồi cập nhật state. Giữ key/payload side effect giống nhau khi response mất hoặc worker restart.

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_executor.py -q
& .\.venv\Scripts\python.exe scripts/run_workflows.py --executor both --n 500 --seed 25
```

**Gate D:** 0 duplicate refunds, 0 duplicate emails, 0 lost refunds; completion >= 99%; wasted LLM/crash <= 0,6. Exactly-once effects dựa trên khả năng deduplicate của API mô phỏng; không suy diễn đã triển khai payment production.

## Task 6: Part E — alerting và error budget (30–45 phút)

**Files:** sửa `src/gameday_lab/slo/alerting.py`; dùng `tests/test_alerting.py`; đọc CSV/labels qua loader có sẵn.

**Interfaces:** `WindowSums(values)` với `sum(end_inclusive, length) -> int`; `burn_rate(total, bad, end, length) -> float`; `evaluate(total: list[int], bad: list[int]) -> list[AlertEvent]`; `error_budget_report(...) -> dict[str, float | bool]`.

- [ ] Chạy tests E trước khi sửa. Prefix sum để mỗi query O(1), cắt đầu window ở index 0:

```python
end = end_inclusive + 1
start = max(0, end - length)
return self.prefix[end] - self.prefix[start]
```

- [ ] Burn rate = `(bad_window / total_window) / (1 - slo)`, trả 0 khi không có traffic.
- [ ] Với mỗi rule, cả long và short window cùng >= threshold mới firing; một event cho một episode liên tục, end exclusive; sắp xếp theo start_min.
- [ ] Giữ rules: page 14,4× với 60/5 phút; page 6× với 360/30 phút; ticket 1× với 4320/360 phút.
- [ ] Budget theo lượng request: allowed_bad = 0,005 × tổng requests; consumed = bad/allowed; remaining = 1-consumed; freeze nếu hết budget. Giữ precision/rounding đúng docstring, không ép remaining âm thành 0.

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_alerting.py -q
& .\.venv\Scripts\python.exe scripts/run_slo.py --alerter both
```

**Gate E:** unit test và public SLO pass; page đúng hạn cho sự cố lớn, ticket slow leak, 0 false page cho blip; có budget report. Dữ liệu hidden chưa có thì ghi rõ chưa kiểm chứng.

## Task 7: Các thí nghiệm bắt buộc và report (60–90 phút)

**Files:** thêm `scripts/run_required_experiments.py`, `reports/experiments/`; tạo `reports/REPORT.md` từ template; tạo hình G2 bằng script có sẵn.

**Interfaces:** helper dùng `load_config`, `build_client`, `run_scenario`, `evaluate_checks`, metrics API công khai; mỗi case dùng `deepcopy(cfg)`; không thay config chuẩn hay code sinh viên cho thí nghiệm. File output gồm settings, seed, checks và metrics.

- [ ] Thêm helper theo cấu trúc dưới đây. Helper dùng chung code gốc; case bỏ tool filter dùng subclass riêng chỉ tồn tại trong helper, không sửa `ladder()` nộp bài.

```python
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameday_lab.client import ResilientClient
from gameday_lab.factory import build_client
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import evaluate_checks, run_scenario


class UnfilteredClient(ResilientClient):
    def ladder(self, task: str) -> list[str]:
        return list(self.order)


def run_case(label, scenario, *, client_name="resilient", patch=None, unfiltered=False):
    scenarios = "configs/scenarios_cache.yaml" if scenario == "C1_faq_outage" else "configs/scenarios.yaml"
    cfg = deepcopy(load_config("configs/gameday.yaml", scenarios))
    if patch:
        patch(cfg)
    client = (UnfilteredClient(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
              if unfiltered else build_client(client_name, cfg, seed=1))
    metrics = run_scenario(cfg, scenario, client, seed=25).metrics()
    checks = evaluate_checks(metrics, cfg.scenarios[scenario].checks)
    output = {"case": label, "scenario": scenario, "seed": 25,
              "client_rng_seed": 1, "client": cfg.client, "cache": cfg.cache,
              "metrics": metrics, "checks": checks, "pass": all(checks.values())}
    path = Path("reports/experiments") / f"{label}_{scenario}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")


def broken_breaker(cfg):
    cfg.client["breaker"]["min_calls"] = 1000000000
    cfg.client["max_attempts_per_provider"] = 5


def no_budget(cfg):
    broken_breaker(cfg)
    cfg.client.update(retry_budget_ratio=100, retry_budget_max_tokens=1e9,
                      retry_budget_min_per_s=1e6)


def timeout30(cfg):
    cfg.client["attempt_timeout_s"] = 30


def cache_patch(key, value):
    def apply(cfg):
        cfg.cache[key] = value
    return apply


def main():
    for scenario in ("G2_overload_storm", "G3_brownout"):
        run_case("normal", scenario)
        run_case("broken_breaker_budget_on", scenario, patch=broken_breaker)
        run_case("broken_breaker_budget_off", scenario, patch=no_budget)
    for scenario in ("G4_slow_region", "G6_provider_outage"):
        run_case("normal", scenario)
        run_case("timeout30", scenario, patch=timeout30)
    run_case("unfiltered", "G6_provider_outage", unfiltered=True)
    run_case("without_cache", "C1_faq_outage")
    run_case("selected_cache", "C1_faq_outage", client_name="cached")
    cfg = load_config("configs/gameday.yaml", "configs/scenarios_cache.yaml")
    for threshold in sorted({0.80, cfg.cache["similarity_threshold"], 0.97}):
        run_case(f"threshold_{threshold}", "C1_faq_outage", client_name="cached",
                 patch=cache_patch("similarity_threshold", threshold))
    for ttl in (30, 60, 300):
        run_case(f"ttl_{ttl}", "C1_faq_outage", client_name="cached", patch=cache_patch("ttl_s", ttl))
    run_case("no_stale", "C1_faq_outage", client_name="cached", patch=cache_patch("max_stale_s", 0))


if __name__ == "__main__":
    main()
```

- [ ] Chạy helper. Các biến thể cố ý làm yếu hệ thống có thể FAIL; đó là dữ liệu thí nghiệm, không thay scoreboard chuẩn.

```powershell
& .\.venv\Scripts\python.exe scripts/run_required_experiments.py
& .\.venv\Scripts\python.exe scripts/plot_timeseries.py --scenario G2_overload_storm
Copy-Item -LiteralPath reports/REPORT_TEMPLATE.md -Destination reports/REPORT.md
```

- [ ] Mục 1: đủ 12 hàng G1–G6 × naive/resilient; mục 2 giải thích các tham số chính bằng số từ băng.
- [ ] Mục 3: budget on/off khi breaker cấu hình sai; timeout 30 trên G6 và G4; bỏ tool filter trên G6. Với timeout, nhìn availability và give_up_reasons trước p95 vì p95 chỉ tính lượt thành công.
- [ ] Mục 4: bảng workflow hai executor; giải thích key tránh tác dụng lặp, checkpoint tránh lặp bước/cost, checkpoint trước payment có thể bỏ mất hoàn tiền.
- [ ] Mục 5: bảng đủ 7 incident; số budget và quyết định freeze; giải thích blip không đáng page.
- [ ] Mục 6: postmortem naive G2 gồm ảnh, >= 5 mốc timeline có attempts/s và success ratio từ CSV; trigger mất GPU khác root cause retry ba tầng; lý giải hàng đợi request đã timeout còn chạy sau restore; >= 3 action items có prevent/detect/mitigate, owner và cách đo.
- [ ] Khi tính impact theo error budget tháng, ghi rõ giả định volume tháng; không dùng denominator volume của riêng băng như volume 30 ngày. Với workload 4 lượt/s đều cả tháng, volume giả định = `4 * 30 * 86400`; budget = `0.005 * volume`; tỷ lệ tiêu budget của sự cố = số lượt thất bại / budget.
- [ ] Mục 7: một điểm yếu thực tế có bằng chứng, như cost khi beta gánh tải hoặc p95 trong quá tải; không dùng nhận định không đo.
- [ ] Mục 8: bảng no-cache/cached; đủ threshold/TTL/stale experiments; giải thích dữ liệu cá nhân thay đổi không nên semantic cache kể cả per-user; cảnh báo thêm trên provider errors/timeouts, breaker state và tỷ lệ stale để dashboard user không che outage.

**Gate F:** không còn ô trống trong 8 mục; mọi số có nguồn JSON/CSV; postmortem blameless; phân biệt kết quả chuẩn với biến thể thí nghiệm.

## Task 8: Kiểm tra cuối, tái lập và chuẩn bị nộp (25–40 phút)

**Files:** giữ reports chuẩn; tạo `reports/validation/seed-25/`, `seed-26/`, `seed-27/` và scoreboard nhiều seed. Không sửa dữ liệu/checker để đạt điểm.

- [ ] Chạy full suite:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check src tests scripts
```

- [ ] Nếu lint lỗi code cung cấp sẵn, ghi rõ và chỉ sửa file được phép; không chỉnh file bị cấm chỉ để lint xanh.
- [ ] Đánh giá nhiều seed và giữ evidence không ghi đè:

```powershell
foreach ($labSeed in @(25, 26, 27)) {
    & .\.venv\Scripts\python.exe scripts/run_gameday.py --client both --seed $labSeed --out "reports/validation/seed-$labSeed/gameday"
    & .\.venv\Scripts\python.exe scripts/run_gameday.py --scenarios configs/scenarios_cache.yaml --client resilient,cached --seed $labSeed --out "reports/validation/seed-$labSeed/cache"
    & .\.venv\Scripts\python.exe scripts/run_workflows.py --executor both --n 500 --seed $labSeed --out "reports/validation/seed-$labSeed/workflows.json"
}
& .\.venv\Scripts\python.exe scripts/grade.py --seeds 25,26,27 --out reports/scoreboard_multiseed.json
& .\.venv\Scripts\python.exe scripts/grade.py
```

- [ ] CLI có thể exit 0 dù có băng FAIL; kiểm tra trường `pass`, `checks` và `summary` trong JSON, không dùng exit code làm bằng chứng duy nhất.
- [ ] Chuẩn public mục tiêu 84/88 automatic; `slo_hidden.pass=None` được ghi rõ chưa chấm, không đổi file để lấy 4 điểm hidden.
- [ ] Dùng clean checkout/venv mới để xác minh `pip install -e '.[dev]'` và grade; plot dependency chỉ cần cho tạo hình, grader không cần tạo lại hình để chấm tự động.
- [ ] Đối chiếu diff: file bị cấm không thay đổi; chỉ `client:`/`cache:` đổi trong config; không thêm secret/venv; report/hình/scoreboard được track. Tránh `make clean` vì nó xóa evidence.
- [ ] Điền Nguyễn Nhân Sâm và MSV `2A202602672` theo thông tin repo; xác nhận lại tên có dấu khi bàn giao nếu user có cách viết khác. Tên repo theo đúng quy tắc README là `Track3-Day25-2A202602672-Nguyen-Nhan-Sam`; tên thư mục hiện tại chưa có dấu gạch giữa từng từ của họ tên, cần kiểm tra tên repo remote trước khi nộp.
- [ ] Hash trong report phải có ý nghĩa rõ: hash snapshot code/kết quả được đánh giá. Không cố ghi hash của chính commit đang chứa report vì tạo vòng tham chiếu; ghi hash code đã đánh giá trong report và kèm hash commit cuối ở thông tin nộp bài để truy xuất được cả hai.
- [ ] Bàn giao checklist ready/missing/risky, nhánh/SHA thực tế và link repo đã xác minh. Chỉ push `main`, đổi repo public hoặc gửi link lên kênh lớp khi đã được user cho phép; kế hoạch hiện tại không thực hiện các bước này.

**Gate cuối:** A/B/C/G/D/E tests pass; G1–G6 và C1 pass trên các seed kiểm tra; workflow/SLO public pass; 8 mục report đủ evidence; clean environment chạy grade; file bị cấm nguyên vẹn; tách rõ local completion, commit, push và submission.

## 3. Bảng phủ yêu cầu và checkpoint báo cáo

| Yêu cầu spec | Task | Bằng chứng cần có |
|---|---|---|
| Python, simulator baseline | 0 | sanity và naive JSON/CSV |
| Error taxonomy, jitter, retry-after, budget | 1 | tests A |
| Failure/slow sliding window, half-open, generation | 2 | tests B và transition log |
| Routing tương thích, deadline, recovery | 3 | tests C, đủ checks G1–G6 |
| Scope, privacy, TTL, LRU, source invalidation, stale | 4 | tests G, đủ checks C1 |
| Stable key, lost response, worker crash, checkpoint | 5 | tests D và workflow metrics |
| Multi-window burn rate, budget, freeze | 6 | tests E và public SLO |
| Client/cache thí nghiệm, cost, giải thích cấu hình | 7 | reports/experiments JSON và report |
| G2 postmortem có timeline/owners/blameless | 7 | CSV, PNG và mục 6 |
| Multiple seeds, sạch file cấm, clean install | 8 | multiseed scoreboard, diff, clean run |
| Repo public đúng tên, main, SHA, link lớp | 8 | kiểm tra remote và submission riêng khi được phép |

Mẫu báo sau mỗi bước: **“Bước [số] xong: [file/chức năng]. Kiểm chứng: [test hoặc metric thực tế]. Còn: [check thất bại hoặc chưa chạy]. Tiếp theo: [task].”**

Kế hoạch được đối chiếu với README, rubric, template report và grade.py. Điểm cần giữ khi thực thi là 84 điểm public so với 88 automatic, các check primary-share/amplification bổ sung trong YAML, và các thí nghiệm cache/report bắt buộc.
