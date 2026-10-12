# Phân tích lỗi Phase A

Nhóm: 2A202602519

Người phụ trách: Nguyễn Công Vinh — MSSV 2A202602519

Nguồn: `artifacts/ragas_50q.json`; run timestamp: `2026-10-12T10:22:59.932141+00:00` (17:22:59, UTC+07:00).  
Generation mode: 50/50 câu dùng `llm`, không có fallback trong answers.  
Models generation/evaluator: `gpt-4o-mini-2024-07-18`; evaluator gồm `gpt-4o-mini` và `text-embedding-ada-002` (metadata m4).

## Điểm theo distribution

| Metric            | factual (20) | multi_hop (20) | adversarial (10) |
| ----------------- | -----------: | -------------: | ---------------: |
| faithfulness      |       0.9000 |         0.5803 |           0.8667 |
| answer_relevancy  |       0.7995 |         0.8032 |           0.7694 |
| context_precision |       0.9500 |         0.9750 |           0.9667 |
| context_recall    |       1.0000 |         0.8875 |           0.7167 |
| avg_score         |       0.9124 |         0.8115 |           0.8299 |

## Bottom 10 và nguyên nhân

Các điểm và chẩn đoán dưới đây được giữ theo `bottom_10` của artifact; nhận xét nguyên nhân là giả thuyết dựa trên answer và metrics, không coi riêng điểm RAGAS là bằng chứng nguyên nhân.

| Rank |  ID | Distribution |    Avg | Worst metric   | Chẩn đoán / hướng xử lý                                                                                                                                                                            |
| ---: | --: | ------------ | -----: | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|    1 |  33 | multi_hop    | 0.3750 | faithfulness   | Answer “Không tìm thấy” dù precision=1.00; recall=0.50 cho thấy vừa abstain vừa có thể thiếu evidence. Kiểm tra truy vấn tổ hợp phụ cấp + phép năm, tăng recall rồi chỉ trả lời từ nguồn tìm được. |
|    2 |  50 | adversarial  | 0.4167 | faithfulness   | Answer “Không tìm thấy”; precision=1.00, recall=0.67. Kiểm tra truy hồi câu hỏi VPN cá nhân/WFH và chính sách cấm cụ thể; không tự suy diễn từ câu hỏi.                                            |
|    3 |   9 | factual      | 0.5000 | faithfulness   | Abstain dù context recall=1.00 và precision=1.00. Context có thông tin nghỉ khi nam nhân viên có vợ sinh con; đây là lỗi sử dụng evidence/generation rõ hơn lỗi retrieval.                         |
|    4 |  31 | multi_hop    | 0.6200 | faithfulness   | Answer tính trần khách sạn 2.400.000 VNĐ, nhưng faithfulness=0.00 và recall=0.67. Đối chiếu mức trần theo đêm, số đêm hợp lệ và đúng phiên bản nguồn trước khi kết luận lỗi số học.                |
|    5 |  38 | multi_hop    | 0.6796 | faithfulness   | Answer nhân 200 USD/đêm × 3 đêm ra 600 USD; recall=1.00 nhưng faithfulness=0.00. Rà soát điều kiện giới hạn số đêm/phiên bản trong context và buộc câu trả lời nêu phép tính có căn cứ.            |
|    6 |  24 | multi_hop    | 0.6822 | faithfulness   | Answer tính phí 200.000 VNĐ bằng 20 ngày; faithfulness=0.00 trong khi recall=1.00. Kiểm tra quy tắc ngày miễn phí/quá hạn và mẫu số tính phí; không chỉ làm tăng retrieval.                        |
|    7 |  21 | multi_hop    | 0.7771 | context_recall | Answer nêu 18 ngày phép nhưng thiếu khoảng lương được hỏi; recall=0.50. Thêm truy vấn/chunk lương Senior vào kết quả và kiểm tra đủ mọi phần câu hỏi trước khi trả lời.                            |
|    8 |  32 | multi_hop    | 0.7883 | faithfulness   | Answer khẳng định đào tạo bắt buộc và diễn giải điều kiện; faithfulness=0.333, recall=1.00. Rà soát câu chữ bắt buộc/phạm vi thời gian trong nguồn và tránh thêm lý do không có căn cứ.            |
|    9 |  34 | multi_hop    | 0.7969 | faithfulness   | So sánh ngưỡng duyệt 4 và 7 triệu; faithfulness=0.667, recall=0.667. Bảo đảm context chứa đầy đủ cả hai ngưỡng và không khẳng định thiếu người phê duyệt.                                          |
|   10 |  29 | multi_hop    | 0.8011 | faithfulness   | Answer đúng hai người phê duyệt và phí 80.000 VNĐ theo 15 ngày quá hạn; faithfulness=0.333 dù recall=1.00. Kiểm tra từng bước tính phí và phân biệt 30 ngày từ lúc tạm ứng với 15 ngày quá hạn.    |

Đối chiếu đại diện: ID 9 có context nêu nam giới được nghỉ 5 ngày làm việc liên tục khi sinh con, nhưng câu trả lời lại từ chối “Không tìm thấy”; retrieval đã có evidence theo recall/precision, nên ưu tiên sửa context assembly/prompt hoặc nhánh abstention. ID 33 vừa abstain vừa chỉ đạt recall 0.50 ở câu hỏi cần ghép hai thuộc tính; cần cải thiện query/chunk coverage trước. Các ID 31, 38, 24 và 29 có câu trả lời tính toán nhưng điểm faithfulness thấp; cần đối chiếu điều kiện, phép tính và phiên bản tài liệu gốc thay vì mặc định lỗi do retrieval. ID 21 là trường hợp thiếu một vế câu hỏi (khoảng lương), phù hợp hơn với lỗi coverage. Không có bằng chứng từ bảng này để quy lỗi cho version conflict cụ thể; phải kiểm tra context/reference nguyên bản trước khi gán nguyên nhân.

## Matrix và nhóm yếu nhất

| Worst metric      | factual | multi_hop | adversarial | Tổng |
| ----------------- | ------: | --------: | ----------: | ---: |
| faithfulness      |       3 |        13 |           2 |   18 |
| answer_relevancy  |      16 |         4 |           1 |   21 |
| context_precision |       1 |         0 |           0 |    1 |
| context_recall    |       0 |         3 |           7 |   10 |
| Tổng              |      20 |        20 |          10 |   50 |

Nhóm yếu theo **mean** thấp nhất là `multi_hop`: 0.8115 (factual 0.9124; adversarial 0.8299). Metric có nhiều câu mang điểm thấp nhất nhất là `answer_relevancy` với 21/50; tuy vậy faithfulness là điểm trung bình thấp nhất của nhóm multi_hop (0.5803), nên ưu tiên xử lý cả câu trả lời không bám evidence và lỗi trả lời thiếu/abstain. Không chọn nhóm theo tổng số câu, vì sample sizes khác nhau.

Kế hoạch kiểm chứng: (1) đo recall@k trên các câu 33, 21, 34 và 50 sau thay đổi query/chunking; (2) kiểm tra answer và các context gốc cho nhóm tính toán 24/29/31/38; (3) sửa prompt/logic abstention để dùng evidence sẵn có như ID 9 và đánh giá lại đủ 50 câu bằng cùng evaluator; (4) so sánh metric theo distribution và giữ nguyên dataset/reference. Dùng artifact mới, không sửa answers hoặc ground truth để tăng điểm.

## Bẫy adversarial và giới hạn

Adversarial có faithfulness 0.8667, relevancy 0.7694, precision 0.9667 và recall 0.7167; thấp hơn factual ở relevancy/recall nhưng không thấp nhất về avg_score. Trong bottom 10 có ID 50 (câu hỏi VPN cá nhân), answer abstain và recall 0.67. Điều này gợi ý cần kiểm tra truy hồi chính sách VPN, nhưng điểm thấp không chứng minh pipeline đã nhận diện đúng một bẫy hay hiểu chính sách. Bản đo có 50 câu (20/20/10), một lượt live, generation `gpt-4o-mini-2024-07-18` và evaluator `gpt-4o-mini` + `text-embedding-ada-002`; kết quả có thể dao động theo model/evaluator. RAGAS là tín hiệu sàng lọc, cần review context, answer và reference trước khi quy kết nguyên nhân.
