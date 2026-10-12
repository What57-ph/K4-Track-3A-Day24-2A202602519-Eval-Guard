# Nhóm thực hiện K4 Track 3A

Tên nhóm: 2A202602519 (bài làm cá nhân).

Repo chung: https://github.com/What57-ph/K4-Track-3A-Day24-2A202602519-Eval-Guard

Trưởng nhóm/người nộp: Nguyễn Công Vinh — MSSV 2A202602519.

Ngày lab/deadline áp dụng: Chưa có thông báo lớp trong repository — cần nhóm bổ sung; múi giờ Asia/Ho_Chi_Minh (UTC+07:00).

Commit dùng để đối chiếu working tree: `b9f8d5b53bc4f94899aa30fdc52c30be0e96eb6d` (HEAD khi điền tài liệu; working tree có thể chứa thay đổi chưa commit).

## Thành viên và phân công

| STT | Họ và tên        | MSSV        | Vai trò / công việc thật                                                  | Bằng chứng                                                     |
| --: | ---------------- | ----------- | ------------------------------------------------------------------------- | -------------------------------------------------------------- |
|   1 | Nguyễn Công Vinh | 2A202602519 | Cá nhân thực hiện M1–M5, Phase A/B/C, tích hợp/chạy batch và soạn báo cáo | Người làm xác nhận; artifacts A/B/C; git author HEAD `b9f8d5b` |

Người tích hợp/chạy batch/nộp link: Nguyễn Công Vinh (người làm xác nhận); artifacts Phase A/B/C ghi `run_kind=live`.

## Môi trường và chuẩn bị trước lớp

OS/Python/compiler: Windows/PowerShell theo môi trường dự án; Python trong `.venv` là 3.12 theo `pyvenv.cfg`; Python hệ thống được phát hiện là 3.13.7. Bản Windows cụ thể/compiler chưa được ghi lại.

Virtualenv/dependencies/imports: `.venv` đã được tạo bằng Python 3.12. Lệnh test đã ghi nhận trong phiên làm việc: `python -m pytest tests/ -q` — 86 passed, 3 deselected. Đây là test offline, không chứng minh mọi dependency/model chạy live. Artifact live Phase C hiện có là bằng chứng runner guard đã thực thi trong lần ghi nhận đó.

Models/Qdrant/50 answers đã chuẩn bị: `artifacts/answers_50q.json` có 50/50 câu, metadata cho biết generation `gpt-4o-mini-2024-07-18`; 50 câu dùng `generation_mode=llm`. Artifact A live dùng evaluator `gpt-4o-mini` và `text-embedding-ada-002`; B live dùng judge `gpt-4o-mini`; C live ghi guard `gpt-4o-mini`. Qdrant endpoint/index, trạng thái chuẩn bị trước lớp và phiên bản runtime đầy đủ không được ghi trong artifact, nên không khẳng định các mục đó đã chuẩn bị từ trước.

## INDIVIDUAL

Một thành viên; người làm xác nhận tự thực hiện các đầu việc bên dưới và soạn báo cáo.

### Nguyễn Công Vinh-2A202602519

- Phần được giao và phần thực tế đã làm: Tự thực hiện M1–M5, Phase A/B/C, tích hợp pipeline, chạy các batch live và soạn báo cáo trong `doc/reports`.
- Bằng chứng: `artifacts/answers_50q.json`, `artifacts/ragas_50q.json`, `artifacts/judge_results.json`, `artifacts/guard_results.json`, ba báo cáo và git author HEAD.
- Cách kiểm tra: Artifacts ghi `run_kind=live`; `python scripts/check_lab.py` PASS toàn bộ với 0 failed checks. Log pytest đã ghi ở phần môi trường.
- Điều đã học: Đánh giá RAG cần xem riêng faithfulness, relevancy, precision và recall; judge cần kiểm tra position/verbosity và calibration; guard cần cả attack lẫn clean controls và latency đúng scope.
- Giới hạn/cách xử lý: Kết quả là một lần chạy trên các tập 50/5/10/20/8/4; judge có mẫu nhỏ và latency mới đo input layers. Giới hạn và cách kiểm chứng được ghi trong báo cáo.
- Nguồn/AI hỗ trợ nếu có: Trợ lý mã nguồn hỗ trợ tổng hợp số liệu artifact và soạn báo cáo trong phiên này; người làm đã rà soát và chịu trách nhiệm nội dung nộp.

## Cập nhật sau khi nộp

Không có cập nhật sau khi nộp
