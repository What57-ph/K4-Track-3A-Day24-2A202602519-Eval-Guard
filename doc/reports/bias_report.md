# Đánh giá LLM Judge Phase B

Nhóm: 2A202602519

Người phụ trách: Nguyễn Công Vinh — MSSV 2A202602519

Nguồn: `artifacts/judge_results.json`; run timestamp: `2026-10-12T10:24:45.167098+00:00` (17:24:45, UTC+07:00).  
Models generation/judge: `gpt-4o-mini-2024-07-18` / `gpt-4o-mini`.

## Năm cặp A/B và hai lượt

Nguồn A/B/reference lần lượt là `artifacts/answers_50q.json:answer`, `fixtures/human_labels_10q.json:model_answer`, `fixtures/test_set_50q.json:ground_truth`. Giữ nguyên năm ID 1, 5, 12, 21, 41.

|  ID | Candidate A vs B (tóm tắt)                                                         | Winner lượt 1 | Winner lượt 2 quy về A/B gốc | Final | Nhất quán | Điểm (lượt 1; lượt 2) và ghi chú                                                   |
| --: | ---------------------------------------------------------------------------------- | ------------- | ---------------------------- | ----- | --------- | ---------------------------------------------------------------------------------- |
|   1 | A: 3 ngày làm việc; B: 3 ngày có lương                                             | B             | B                            | B     | Có        | A/B .8/1.0; .8/1.0. B nêu rõ nghỉ có lương.                                        |
|   5 | A: CEO duyệt; B: giám đốc phòng ban duyệt                                          | A             | A                            | A     | Có        | 1.0/0.0; 1.0/0.0. A khớp ngưỡng mua trên 50 triệu.                                 |
|  12 | A: nêu điều kiện chính thức từ 6 tháng và 1 tháng lương; B: chỉ nêu 1 tháng lương  | A             | tie                          | tie   | Không     | 1.0/.7; 1.0/1.0. Lượt đầu xem điều kiện là cần thiết, lượt sau coi hai câu đều đủ. |
|  21 | A: 18 ngày phép, chưa trả lời khoảng lương; B: 18 ngày và lương Senior 20–35 triệu | A             | B                            | tie   | Không     | 1.0/.8; .8/1.0. Đổi lượt làm winner đổi; câu hỏi có hai ý nên cần xét độ đầy đủ.   |
|  41 | A: 15 ngày theo v2024; B: 12 ngày theo v2023                                       | A             | A                            | A     | Có        | 1.0/0.0; 1.0/0.0. A dùng phiên bản hiện hành.                                      |

Position inconsistency: 2/5 = 0.40. Verbosity win rate: 3/3 = 1.00 trong ba cặp decisive; trong đó A dài hơn và thắng ở 2 cặp, B dài hơn và thắng ở 1 cặp. Hai lượt không nhất quán là ID 12 và 21. Ở ID 12, judge thay đổi từ A sang tie sau khi đổi vị trí; ở ID 21, winner thay từ A sang B, phản ánh đánh giá không ổn định về độ đầy đủ. Kết quả độ dài chỉ là tương quan trên ba quyết định, không chứng minh độ dài gây ra lựa chọn.

## Calibration đúng model_answer

Các dòng dưới giữ nguyên `model_answer` trong `fixtures/human_labels_10q.json`; nhãn judge được chấm riêng trước khi so với nhãn human.

|  ID | Model answer gốc                                                                   | Judge | Human | Đồng ý | Reasoning judge (tóm tắt)                           |
| --: | ---------------------------------------------------------------------------------- | ----: | ----: | ------ | --------------------------------------------------- |
|   1 | Nhân viên được nghỉ 3 ngày làm việc có lương khi kết hôn.                          |     1 |     1 | Có     | Đúng số ngày, lương và điều kiện theo reference.    |
|   5 | Cần Giám đốc phòng ban phê duyệt.                                                  |     0 |     0 | Có     | Sai cấp phê duyệt; cần Tổng Giám đốc.               |
|  12 | Nhân viên được thưởng Tết tối thiểu 1 tháng lương.                                 |     1 |     1 | Có     | Đúng theo reference, judge xem là đủ ý.             |
|  21 | Được nghỉ 18 ngày phép (15 cơ bản + 3 thâm niên). Lương Senior từ 20 đến 35 triệu. |     1 |     1 | Có     | Khớp số ngày phép và khoảng lương.                  |
|  23 | Hoàn trả 25 triệu vì chưa đủ 1 năm cam kết.                                        |     1 |     1 | Có     | Đúng chi phí phải hoàn trả và lý do.                |
|  29 | Trưởng phòng phê duyệt. Phạt 2% tháng trên 8 triệu.                                |     0 |     0 | Có     | Thiếu Kế toán trưởng và áp dụng sai khoảng quá hạn. |
|  33 | Phép: 19 ngày. Phụ cấp: 1.500.000 VNĐ/tháng.                                       |     1 |     1 | Có     | Hai giá trị khớp reference.                         |
|  41 | Nhân viên được nghỉ 12 ngày phép năm.                                              |     0 |     0 | Có     | Dùng chính sách v2023 thay cho v2024 (15 ngày).     |
|  46 | Nhân viên thử việc không được nghỉ phép năm và phải xin nghỉ không lương nếu cần.  |     1 |     1 | Có     | Đúng điều kiện nghỉ phép của nhân viên thử việc.    |
|  50 | Được, miễn là đảm bảo kết nối an toàn.                                             |     0 |     0 | Có     | Sai vì chính sách cấm VPN cá nhân.                  |

Cohen’s κ = 1.00. Observed agreement = 10/10 = 1.00. Chance agreement = (6×6 + 4×4)/10² = 0.52; κ = (1.00−0.52)/(1−0.52) = 1.00. Nhãn judge và human đều có 6 số 1, 4 số 0 và trùng toàn bộ trong mẫu này.

## Giới hạn và cách dùng judge

Judge là `gpt-4o-mini`; pairwise chỉ có 5 cặp, còn calibration có 10 nhãn, nên κ hoàn hảo trên mẫu nhỏ không chứng minh judge không thiên lệch hoặc sẽ khái quát tốt. Hai cặp đổi quyết định sau khi đảo vị trí; ID 21 đặc biệt cần đọc câu hỏi hai vế và hai answer. Để kiểm tra ổn định, mở rộng các cặp được chọn trước khi xem kết quả, giữ hai thứ tự và reference cố định, đồng thời nhờ người đánh giá độc lập phân xử các disagreement. Không dùng winner làm nhãn đúng tuyệt đối; binary calibration cũng chỉ đo mức đồng ý trên 10 ví dụ đã chọn.
