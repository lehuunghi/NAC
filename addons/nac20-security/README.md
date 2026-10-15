# NAC20 Security — nền tảng giai đoạn 1

Đây là công cụ thử nghiệm **observe-only**, Python 3.10+ chỉ dùng thư viện chuẩn.
Nhận tệp Suricata EVE JSONL và bản xuất inventory, lưu SQLite riêng, tra cứu sự kiện
và ghi nhận trạng thái xử lý. Không có API mạng, lệnh thực thi, thông tin đăng nhập
PacketFence, thay đổi VLAN, CoA, firewall hoặc đường gọi hàng đợi PacketFence.
Chưa được nối vào installer hay dịch vụ đang chạy. Không tương đương antivirus/IPS.

## Chạy thử bằng dữ liệu giả

Từ thư mục repository, trên máy thử nghiệm có Python:

```sh
mkdir -p work/security-lab
python3 addons/nac20-security/nac20_security.py --db work/security-lab/security.db inventory --scope lab --file addons/nac20-security/examples/inventory.json
python3 addons/nac20-security/nac20_security.py --db work/security-lab/security.db ingest --scope lab --sensor lab-sensor-01 --file addons/nac20-security/examples/eve.json
python3 addons/nac20-security/nac20_security.py --db work/security-lab/security.db events --limit 20
```

Lần ingest đầu trả `inserted=1`, lần tiếp theo `duplicate=1`. Sự kiện có nguồn
`02:00:00:00:00:01`, đích `unresolved`. Ví dụ dùng địa chỉ và chữ ký giả để kiểm thử,
không khẳng định phát hiện được mã độc.

Đánh dấu đã xem hoặc đóng, dùng `event_id` từ lệnh `events`:

```sh
python3 addons/nac20-security/nac20_security.py --db work/security-lab/security.db status EVENT_ID acknowledged --actor lab-admin
python3 addons/nac20-security/nac20_security.py --db work/security-lab/security.db status EVENT_ID closed --actor lab-admin
python3 -m unittest discover -s addons/nac20-security -v
```

`open → acknowledged → closed` hoặc `open → closed`; không mở lại. Lưu người thao tác,
thời điểm và trạng thái cũ/mới trong `transitions`, cùng transaction với cập nhật.
`actor` là nhãn do người chạy cung cấp, **chưa phải danh tính được xác thực**.
Quyền truy cập hiện dựa vào tài khoản hệ điều hành và quyền tệp.

## Hợp đồng inventory và resolver

Mỗi binding gồm `ip`, MAC unicast, `valid_from`, `valid_until`, cả hai có múi giờ.
Khoảng hiệu lực là `[valid_from, valid_until)`. Lệnh inventory thay thế nguyên tử
toàn bộ binding của một `scope`; tệp `[]` chủ động xóa scope đó. Scope khác được giữ.
Scope biểu diễn một miền địa chỉ mạng không chồng lấn; dùng scope riêng cho tenant,
site hoặc VRF có IP trùng nhau. Đây là phân vùng tra cứu, chưa phải hàng rào phân quyền SaaS.

Resolver tra theo scope + IP + **thời điểm sự kiện**, hỗ trợ IPv4/IPv6. Một MAC duy
nhất được trả về `resolved`; nhiều MAC là `ambiguous`; không có bằng chứng là
`unresolved`. Không suy luận MAC từ IP public, từ ethernet header của gateway, hoặc
từ IP hiện tại cho sự kiện quá khứ. NAT không có mapping phù hợp vẫn unresolved.
Cả hai đầu được đối chiếu riêng; không tự kết luận đầu nào là thiết bị nhiễm.

PacketFence có `node`, `ip4log`, `ip4log_history`; xem báo cáo kiểm toán. Giai đoạn này
chỉ nhận **bản xuất đã được quản trị viên chuẩn hóa** sang hợp đồng trên. Không gọi
API PacketFence hoặc kết nối SQL trực tiếp. Khi làm exporter ở bước sau, cần xác nhận
múi giờ máy chủ, lịch sử DHCP, nguồn dữ liệu và thời hạn quan sát. Giá trị kết thúc
`0000-00-00 00:00:00` của PF không phải timestamp hợp lệ; không đổi thành vô hạn.
Phải giới hạn bằng thời điểm quan sát đã xác nhận, hoặc bỏ qua binding thiếu bằng chứng.

## Đường tích hợp Suricata thụ động

```text
SPAN/TAP trong lab → Suricata IDS → bản sao eve.json chỉ đọc
                                     ↓
inventory xuất sẵn → resolver → normalizer → SQLite riêng → CLI JSON
```

EVE chứa nhiều loại bản ghi; module chỉ nhận `event_type=alert`. Tham khảo
[tài liệu EVE chính thức](https://docs.suricata.io/en/latest/output/eve/eve-json-output.html).
Với sensor lab độc lập, bật EVE file JSON không prefix và loại `alert` trong cấu hình
Suricata hiện hữu. Không thay thế toàn bộ cấu hình sensor bằng ví dụ trong tài liệu.
Giữ sensor ở chế độ IDS trên cổng mirror, không dùng NFQUEUE/inline bridge hoặc
bật chế độ chặn. Chưa cài/chạy Suricata hay sửa interface trên máy thật trong thay đổi này.

Nhập một bản sao ổn định của EVE bằng lệnh ingest. Một lần chạy đọc đến EOF;
không tail liên tục, chưa quản lý checkpoint/rotation. Có thể replay cùng tệp sau
khi khởi động lại: SHA-256 của sự kiện chuẩn hóa (gồm scope/sensor/thời điểm/flow
và các trường alert được giữ) là khóa chống trùng. Không chứa kết quả resolver
trong khóa; replay giữ nguyên bằng chứng enrichment lúc nhập đầu tiên. Hai bản
ghi có toàn bộ trường chuẩn hóa giống nhau sẽ được gộp, không phải bộ đếm packet.
Khi rotation, nhập riêng từng tệp đã đóng; chưa hỗ trợ file nén.

Giới hạn một dòng 256 KiB; dòng quá lớn hoặc JSON/alert sai được đếm `rejected`,
không lưu nội dung lỗi. Dòng cuối thiếu newline được đếm `incomplete`, chờ replay
khi đã ghi xong. Bản ghi không phải alert được đếm `ignored`. Mã thoát: 0 thành
công, 2 có rejected/incomplete, 1 lỗi vận hành; argparse cũng trả 2 cho tham số sai.
DB lỗi dừng cả lần chạy, không nuốt lỗi thành bản ghi bị từ chối. Các bản ghi đã
commit trước đó được giữ và replay sẽ bỏ trùng.

Không lưu payload, HTTP body, thông tin xác thực hoặc nguyên văn EVE. IP/MAC và
chữ ký vẫn là dữ liệu cần bảo vệ. Dùng thư mục riêng chỉ tài khoản thử nghiệm được
truy cập (Linux: `umask 077` trước khi chạy), không chạy root. Không trỏ vào DB PF.
Chưa có retention tự động, backup, giới hạn dung lượng DB hoặc quota tổng tệp;
theo dõi dung lượng, chỉ dùng tập dữ liệu lab có giới hạn. Ngừng nhập và lưu trữ/xóa
DB thử nghiệm theo quy trình của đơn vị khi kết thúc; không xóa log gốc PacketFence.

## Các phần chưa triển khai

- Exporter/API đọc inventory trực tiếp từ PacketFence có xác thực, TTL và lịch sử.
- Daemon thu log liên tục, checkpoint, rotation, backpressure, health/metrics và retention.
- REST API/RBAC, giao diện Security dashboard, thông báo email/webhook, tìm kiếm phân trang.
- Rule correlation, threat intelligence, malware file scanning và chính sách risk score.
- Workflow đề xuất/phê duyệt cách ly, rollback, protected devices và enforcement adapter.
- Gói Debian/systemd và kiểm thử end-to-end trên PacketFence, Suricata, switch thật.

Những phần này cần được thiết kế/kiểm chứng tiếp; **không có công tắc bật enforcement**
trong module hiện tại. Báo cáo kiến trúc, kiểm toán và lộ trình ở
[NAC20_SECURITY_GIAI_DOAN_1.md](../../docs/NAC20_SECURITY_GIAI_DOAN_1.md).
