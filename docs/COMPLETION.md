# Lab 25B — Bàn giao local ngày 13/10/2026

**Sinh viên:** Nguyễn Nhân Sâm — 2A202602672.  
**Nhánh:** `feature/lab25b-completion`.  
**Snapshot code đã đánh giá:** commit `27f907f` (full hash trong đầu `reports/REPORT.md`).

## Checkpoint

| Bước | Trạng thái | Bằng chứng |
|---|---|---|
| 0. Môi trường/baseline | Xong | Python 3.12.14; starter 76 fail / 6 pass; naive 0/6 băng |
| A. Error/retry | Xong | 21/21 test gốc |
| B. Breaker | Xong | 13/13 test gốc |
| C. Client | Xong | 11/11 test gốc; G1–G6 pass trên seed 25/26/27 |
| G. Cache | Xong | 17/17 test gốc; C1 pass trên seed 25/26/27 |
| D. Workflow | Xong | 7/7 test gốc; 500 workflows/seed, 0 duplicate/lost refunds, 100% completion |
| E. SLO | Xong public | 7/7 test gốc; 3 pages/1 ticket/0 false pages; hidden chưa có |
| F. Report | Xong local | 8 mục, đủ thí nghiệm, G2 PNG và 10 mốc timeline có số từ CSV |
| 8. Kiểm tra cuối | Xong local | Full 99/99; Ruff sạch; mypy 7 module sạch; môi trường mới cũng 99/99 và 84/88 |
| Công bố/nộp | Chưa thực hiện | Chưa push/merge main, chưa đổi tên/xác minh public repo, chưa gửi link lớp |

Report chi tiết: [`reports/REPORT.md`](../reports/REPORT.md). Scoreboard chuẩn: [`reports/scoreboard.json`](../reports/scoreboard.json), nhiều seed: [`reports/scoreboard_multiseed.json`](../reports/scoreboard_multiseed.json). Thí nghiệm cố ý tắt lớp bảo vệ có thể FAIL; đó là dữ liệu đối chứng, không phải kết quả cấu hình nộp bài.

## Sẵn sàng / còn thiếu / giới hạn

- **Sẵn sàng local:** code, cấu hình, report, hình, JSON/CSV; các file bị cấm giữ nguyên (22 SHA-256 đối chiếu trước/sau).
- **Còn chưa chấm:** 4 điểm SLO hidden và 12 điểm report. 84/88 là tối đa public, không phải điểm cuối 100.
- **Trước khi nộp:** repo remote hiện tên `Track3-Day25-2A202602672-NguyenNhanSam`; quy tắc đề cần `Track3-Day25-2A202602672-Nguyen-Nhan-Sam`. Cần đổi tên/xác minh public, đưa snapshot hoàn chỉnh lên `main` và nộp link khi user cho phép.
- **Giới hạn kỹ thuật đã ghi report:** G2 p95 seed 25 là 11,911 giây; provider all-down vẫn làm một phần FAQ cá nhân và tool workflow thất bại; băng ẩn chưa kiểm chứng.
- **Review độc lập:** đã sửa và kiểm tra lại cooldown quota bị rate limit đến muộn ghi đè, và freeze sớm do làm tròn budget. Có regression tests riêng; không sửa test gốc.

## Chạy lại trong phiên hiện tại

`.venv` cũ trỏ tới Python311 không chạy trong sandbox; `.venv-codex` đã cài đầy đủ dependency và được gitignore.

```powershell
& .\.venv-codex\Scripts\python.exe -m pytest -q
& .\.venv-codex\Scripts\python.exe scripts/grade.py
& .\.venv-codex\Scripts\python.exe scripts/grade.py --seeds 25,26,27 --out reports/scoreboard_multiseed.json
& .\.venv-codex\Scripts\python.exe -m ruff check src tests scripts
```

Tái tạo report dùng hash code đang được đánh giá; không dùng hash commit report thay thế hash code nếu muốn tái lập đúng snapshot:

```powershell
& .\.venv-codex\Scripts\python.exe scripts/run_required_experiments.py
$labCodeSha = git rev-parse 27f907f
& .\.venv-codex\Scripts\python.exe scripts/build_report.py --code-commit $labCodeSha
```

Bản sao môi trường sạch đã được cài bằng `pip install -e ".[dev]"`, chạy đủ 99 test và grader single/multiseed. Evidence ở `reports/validation/clean_tests.txt` và `clean_scoreboard*.json`. Dùng `MPLBACKEND=Agg` khi vẽ ở môi trường không có Tk/Tcl. Tránh `make clean` trước khi nộp vì nó xóa evidence.
