# Blueprint CI/CD cho RAG và guardrails

Nhóm: 2A202602519
Người phụ trách: Nguyễn Công Vinh — MSSV 2A202602519

Đây là **đề xuất CI/CD**, không phải workflow đã được triển khai/chạy.  
Nguồn: `artifacts/ragas_50q.json`, `artifacts/judge_results.json`, `artifacts/guard_results.json`, `artifacts/extended_latency.json`.  
Run timestamp: A `2026-10-12T10:22:59.932141+00:00`; B `2026-10-12T10:24:45.167098+00:00`; C `2026-10-12T10:25:56.996605+00:00`; latency `2026-10-12T11:25:49.648234+00:00`. Guard model: `gpt-4o-mini`. Models generation/evaluator/judge: `gpt-4o-mini-2024-07-18` / `gpt-4o-mini` + `text-embedding-ada-002` / `gpt-4o-mini`.

## Kiến trúc và failure action

Luồng dự kiến: request → Presidio PII scan/anonymize → NeMo input rail → truy vấn RAG (retrieve/rerank/enrich/generate) → NeMo output rail → response. Nếu Presidio phát hiện PII hoặc input rail từ chối thì dừng request và trả thông báo phù hợp; không chuyển prompt bị chặn vào RAG. Output rail không an toàn thì thay bằng câu từ chối, không trả nguyên answer. Lỗi dịch vụ/timeout ở các lớp bảo vệ nên fail closed đối với dữ liệu nhạy cảm, ghi mã lỗi để vận hành và không ghi raw PII/prompt bí mật vào log. Secrets/API keys lưu trong biến môi trường hoặc secret store của CI, không commit vào repo. Fallback RAG chỉ được phép khi nguồn và phiên bản đủ rõ; khi evidence thiếu hoặc xung đột thì nêu không đủ căn cứ thay vì bịa nội dung.

Đây là mô tả kiến trúc đề xuất. Artifact C chứng minh các bộ input/output đã được chạy qua guard trong lần đo này; không chứng minh có dịch vụ triển khai, log redaction, secret store hay CI workflow đang hoạt động.

## Phạm vi và số đo latency

Đo Task 12 có scope `input_layers_sequential`: Presidio rồi NeMo input, không short-circuit. Có 20 mẫu timed, 2 lượt warm-up, engine được tạo trước đo; percentile nội suy tuyến tính (`linear`) từ raw samples. `input_guard_ms` là tổng hai lớp trên từng sample.

| Layer / scope                      |  P50 ms |  P95 ms |  P99 ms | Tình trạng                             |
| ---------------------------------- | ------: | ------: | ------: | -------------------------------------- |
| Presidio                           |   5.688 |   7.364 |   7.432 | Đo trong 20 mẫu                        |
| NeMo input                         |   0.027 |   0.037 |   0.041 | Đo trong 20 mẫu                        |
| Input guard sequential             |   5.714 |   7.401 |   7.474 | Đo tổng từng sample; đạt target 500 ms |
| RAG (retrieve/rerank/generate)      | 929.698 | 1494.574 | 1551.760 | Đo live, 20 request được phép          |
| NeMo output rail                   | 715.993 | 865.816 | 898.743 | Đo live, 20 request được phép          |
| Full request (được phép)           | 2372.378 | 2907.003 | 2967.351 | Đo live từ input đến response          |
| PII short-circuit request          | 7.141 | 8.148 | 9.360 | Đo live, 20 mẫu                         |

Task 12 input target là 500 ms; `latency_budget_ok=true` (P95 7.401 ms). Phép đo live bổ sung được ghi trong `artifacts/extended_latency.json` (2026-10-12): 20 mẫu timed sau 2 warm-up cho mỗi luồng, percentile tuyến tính. Full allowed request P95 là 2907.003 ms; đây là số end-to-end thực đo, không phải tổng percentile các layer. PII short-circuit P95 là 8.148 ms. RAG đo gồm hybrid retrieval, reranking và live answer generation trên raw M1 chunks, không có M5 ingestion enrichment. Chạy benchmark dùng `_HashingEncoder` và `_LexicalReranker` do dense model/cross-encoder không khả dụng; kết quả vì vậy mô tả cấu hình fallback này, không phải cấu hình encoder/reranker dense dự kiến. Index là in-memory; persistent Qdrant không bị thay đổi.

Trong clean control của benchmark, 2/24 lần thử (gồm 2 warm-up và 22 lượt kiểm tra) bị NeMo input rail chặn, FPR 8.33%; cả hai là ID 107. PII preflight phát hiện 4/5 fixture và bỏ sót ID 5. Đây là các cảnh báo về chất lượng guard trong phép đo này; không suy rộng thành tỷ lệ production. Số đo có 20 mẫu, nên phù hợp để bổ sung báo cáo lab, chưa đủ để xác lập SLO ổn định. Không áp target 500 ms của Task 12 lên full request; nếu sau này đặt SLO end-to-end thì cần ngưỡng riêng và benchmark dài hơn với cold/warm state, tải đồng thời và cấu hình retrieval mong muốn.

## CI gates đề xuất

- Phase A: faithfulness trung bình ≥0.75 và avg_score ≥0.65 trên đủ 50 câu; hiện faithfulness trung bình theo 50 câu xấp xỉ 0.7655, avg_score xấp xỉ 0.8555. `multi_hop` thấp nhất về avg_score (0.8115), faithfulness 0.5803.
- Phase C: attacks ≥18/20 cho gate đề xuất; clean phải 8/8 allowed (FPR=0); output cases phải đúng 4/4. Kết quả hiện tại lần lượt 20/20, 8/8, 4/4.
- Không áp điều kiện P95 <500 ms cho full request; target 500 ms hiện chỉ thuộc input layers. Full request đã được đo riêng với P95 2907.003 ms trong benchmark bổ sung.

Ngưỡng lab bắt buộc cho attacks vẫn là 15/20; 18/20 là mục tiêu bonus/CI đề xuất. Cách triển khai: job CI cài dependencies đã khóa, chạy unit tests offline, rồi chạy checker artifact; chạy live A/B/C chỉ trong job được bật rõ ràng với secret/API budget. Runner phải trả exit code khác 0 khi schema/provenance hoặc ngưỡng CI fail. Không có bằng chứng workflow này đã được cấu hình trong repo.

## Monitoring và cải tiến

Theo dõi metric theo bản phát hành: RAGAS 4 metric và avg_score trên 50 câu cố định; attack pass rate, clean false-positive rate, output pass rate; P50/P95/P99 theo từng layer; timeout/error rate; judge position inconsistency và calibration. Gửi cảnh báo khi Phase A dưới gate, clean control bị block, attack pass dưới ngưỡng, output case sai, hoặc latency vượt ngân sách; lấy mẫu lại trước khi kết luận drift. Lưu question ID, model IDs, source hashes và quyết định guard; redact PII khỏi telemetry. Người phụ trách cần được nhóm chỉ định; hiện chưa có thông tin owner trong repo.

RAGAS mean trên 50 câu: faithfulness 0.7654, answer_relevancy 0.7950, context_precision 0.9633, context_recall 0.8983, avg_score 0.8555 (trung bình bốn metric; không trọng số). Worst distribution theo avg_score: `multi_hop` 0.8115.  
Cohen’s κ Phase B: 1.00 (10 nhãn).  
Phase C run: attacks 20/20, clean 8/8 allowed (FPR=0.00), output cases 4/4. Extended-latency benchmark riêng có clean-control FPR 8.33%; hai lần chạy khác nhau, nên cần giữ cả hai kết quả và điều tra ID 107.

Các cải tiến kiểm chứng được: (1) review ID 9 vì answer abstain dù recall=1.00; (2) cải thiện coverage multi-hop cho ID 33 và 21 rồi đo lại recall; (3) audit phép tính/policy evidence ở ID 24, 29, 31, 38 để xử lý faithfulness thấp; (4) giữ clean controls 8/8 và bổ sung tình huống PII hợp lệ/biên để theo dõi false positives; (5) mở rộng cặp pairwise và calibration trước khi kết luận judge ổn định, vì hiện chỉ có 5 cặp/10 nhãn và 2/5 cặp đổi quyết định khi đảo thứ tự. Các báo cáo là ảnh chụp của một lần chạy và không chứng minh CI hoặc production monitoring đã được triển khai.
