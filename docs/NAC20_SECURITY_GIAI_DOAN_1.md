# NAC20 Security — kiểm toán và triển khai nền tảng phương án A

Ngày 15/10/2026. Mốc kiểm toán: `9464658bc1c92d0926155f71d7a0ac740a8d3d30`
trên `main`; nhánh làm việc `codex/nac20-security-foundation`.

## Cơ sở và phạm vi

Yêu cầu: xây Security Events, Device Inventory/Resolver, tích hợp Suricata không
phá PacketFence; có test và tài liệu; không deploy production hoặc tự động cách ly.
Chat tham chiếu chỉ trả mã tham chiếu nội dung, nên chưa xác minh được toàn văn
thiết kế A trước đó. Tài liệu này ghi rõ cách diễn giải để rà soát: NAC quan sát và
cảnh báo qua IDS thụ động, giữ PacketFence là chủ thể thực thi NAC. Không chuyển
NAC20 thành firewall Internet/antivirus endpoint. Chưa tuyên bố đáp ứng đầy đủ bản
thiết kế không truy xuất được.

Kiểm toán tĩnh tập trung vào đường Security Events, Suricata, mô hình IP/MAC,
API, đóng gói và CI liên quan; không phải pentest hay chứng nhận an toàn toàn bộ
kho mã. Không sử dụng credential hoặc truy cập máy chủ/thiết bị thật.

## Kiến trúc hiện hữu và phát hiện

| Thành phần/bằng chứng trong repository | Kết luận và tác động |
|---|---|
| `README.md`, `lib/pf`, `go`, `html/pfappserver`, `db` | Fork PacketFence: lõi Perl, dịch vụ/parser Go, UI quản trị, DB MySQL. Thương hiệu NAC20 giữ tên/giao thức nội bộ PF. Cần bổ sung có ranh giới để không gây xung đột nâng cấp. |
| `go/detectparser/parser.go`, `snort.go` | Loại parser `suricata` đang dùng `NewSnortParser`, đọc định dạng văn bản Snort bằng regex; không phải parser EVE alert JSON tổng quát. Giữ nguyên để tương thích. |
| `go/detectparser/suricata_md5.go` | Parser MD5 đọc định dạng riêng, gọi `/api/v1/ip4logs/ip2mac/` rồi phát `trigger_security_event`. Không nối EVE mới vào đường này trong chế độ quan sát. |
| `lib/pf/security_event.pm::security_event_trigger` | Hàm có thể tạo sự kiện và dẫn tới thay đổi VLAN theo chính sách. Security Events PF mang ý nghĩa vận hành, không nên dùng như kho alert thụ động mặc định. Đây là rủi ro tích hợp, không phải lỗ hổng mới được khẳng định. |
| `lib/pf/api.pm::event_add` | Đường `event_add` cũng tra IP/MAC và gọi `security_event_trigger`; vì vậy chỉ tránh parser MD5 là chưa đủ. Collector mới không gọi cả hai đường này. |
| `db/pf-schema-15.0.sql`: `node`, `ip4log`, `ip4log_history` | Inventory/IP history đã tồn tại. `ip4log` dùng IP làm khóa chính, có thời gian bắt đầu/kết thúc và zero-date. Đối chiếu sự kiện cũ với IP hiện tại có thể sai khi DHCP đổi chủ; cần interval có timezone và scope rõ. |
| `docs/api/spec/static/paths/security_events.yaml` và schema liên quan | API Security Events có sẵn; chưa thêm route trùng hoặc sửa ý nghĩa dữ liệu PF. Kho alert mới hiện chỉ có CLI cục bộ. |
| `t/venom/test_suites/security_event_suricata`, `t/unittest/security_events.t` | Đã có test đường xử lý PF; cần giữ và bổ sung bộ test observe-only tách riêng. Chưa chạy bộ PF vì môi trường hiện tại thiếu Linux/services tương ứng. |
| `packaging/debian12/build.sh`, `.github/workflows/nac20-publish.yml` | Quy trình đóng gói và phát hành có sẵn. Không sửa/kích hoạt installer hoặc workflow release. Bộ thu thập mới chưa được cài thành dịch vụ. |
| `docs/NAC20_SAAS_DAC_TA.md` | SaaS nhiều công ty là đặc tả đề xuất. `scope` trong module mới chỉ phân vùng đối chiếu địa chỉ, không thay thế isolation/RBAC tenant. |

Không sửa parser cũ, schema MySQL, route API, UI, policy engine, queue, cấu hình
RADIUS/DHCP hoặc dịch vụ PF. Các phát hiện trên dẫn đến kiến trúc module độc lập
ở `addons/nac20-security`, DB SQLite riêng có schema version 1 và chỉ mục thời gian.

## Kết quả triển khai

- Chuẩn hóa alert EVE, kiểm tra trường bắt buộc, timestamp UTC, IPv4/IPv6 và kiểu
  dữ liệu; giới hạn dòng và bỏ trường payload nhạy cảm.
- Lưu sự kiện bền vững, chống trùng khi replay, xuất JSON qua CLI; có trạng thái
  open/acknowledged/closed và audit transaction cho chuyển trạng thái.
- Nhập inventory snapshot nguyên tử theo scope; resolver theo khoảng thời gian,
  giữ trạng thái resolved/unresolved/ambiguous, enrich riêng nguồn và đích.
- CLI nhập EVE từ file chỉ đọc, thống kê accepted/duplicate/ignored/rejected/
  incomplete; không có khả năng tác động thiết bị hoặc mạng.
- Fixture lab, test độc lập và workflow CI chỉ đọc quyền repository, không deploy.

Hướng dẫn chạy, hợp đồng dữ liệu và giới hạn chi tiết nằm trong
[README module](../addons/nac20-security/README.md).

## Kiểm chứng và giới hạn nghiệm thu

10 test Python stdlib đã chạy thành công trên Windows với Python runtime đi kèm:
chuẩn hóa/privacy, chống trùng/phân vùng sensor-scope, hết hạn/conflict inventory,
DHCP đổi chủ/IPv6, atomic snapshot, enrichment không thay đổi khi replay, input sai,
oversized/partial JSONL, lifecycle audit/rollback và persistence/CLI.
CI cấu hình chạy lại trên Ubuntu với Python 3.10/3.12; kết quả CI cần kiểm tra riêng
sau khi đẩy nhánh. Không suy từ unit test ra khả năng tương thích production.

Chưa có Suricata binary/traffic replay thật, Debian lab, dịch vụ PF, cơ sở dữ liệu
PF hoặc switch thử nghiệm tại phiên làm việc. Chưa xác minh hiệu năng, resource
isolation, installer, UI hay regression toàn bộ PacketFence. Không khẳng định có
phát hiện/chặn virus thực tế từ fixture tổng hợp. Không deploy hoặc cách ly thiết bị.

## Lộ trình tiếp theo và điều kiện đi tiếp

1. Đối chiếu toàn văn thiết kế A; thống nhất nguồn inventory, timezone, TTL, scope
   và topology SPAN/TAP; chọn lab độc lập và giới hạn tài nguyên.
2. Xây exporter chỉ đọc có xác thực; kiểm tra DHCP churn, IP trùng giữa site, NAT,
   stale bindings và IPv6 bằng dữ liệu PacketFence trong lab.
3. Chạy Suricata IDS thật với PCAP an toàn, kiểm tra EVE thực tế, rotation/restart,
   load/disk-full, retention và không ảnh hưởng RADIUS/DHCP/UI; sau đó đóng gói
   collector và nối dashboard/RBAC/notification.
4. Thiết kế workflow đề xuất cách ly có phê duyệt, protected devices, rate limit,
   audit và rollback. Chỉ xây/kích hoạt enforcement trên thiết bị thật sau phê duyệt
   riêng và nghiệm thu môi trường thử nghiệm. Không thực hiện bước này trong PR.

Rollback phần bổ sung hiện tại: dừng chạy CLI, bỏ module/nhánh nếu cần; không có
migration PF hay thay đổi network để hoàn tác. Dữ liệu Security lab được quản lý
riêng theo chính sách lưu trữ của đơn vị.
