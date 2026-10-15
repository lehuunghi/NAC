# NAC20 Security — quản lý và xử lý sự cố trong lab

Ngày 15/10/2026. Bổ sung trên nhánh `codex/nac20-security-foundation`.
Không deploy production, không gửi thông báo thật và không thực thi cách ly thiết bị
trong phiên triển khai này. Dữ liệu dashboard mẫu hoàn toàn tổng hợp.

## Phạm vi theo yêu cầu

| Chức năng | Đã có trong nhánh | Giới hạn còn lại |
|---|---|---|
| Quản lý thiết bị tập trung | Registry theo scope/MAC, tên, vendor của thiết bị mạng thực thi, VLAN gốc và cờ protected; nhập theo lô và hiển thị IP/người dùng hiện còn hiệu lực | Registry cục bộ, chưa đồng bộ trực tiếp PF; chưa có nhiều quản trị viên/RBAC hoặc lịch sử topology |
| Phát hiện từ Suricata | Nhận EVE alert, kiểm tra dữ liệu, chống trùng và giữ mức severity | Collector không tự tạo detection engine, vẫn cần sensor IDS thụ động; chưa chạy Suricata thật |
| Liên kết IP/MAC/người dùng | Đối chiếu binding theo thời gian, scope, MAC và username; bảo toàn bằng chứng lúc nhập | Username là dữ liệu phiên xuất sẵn, không xác minh danh tính người thao tác; không tự gán user hiện tại cho cảnh báo cũ |
| Dashboard sự cố | HTML xuất cục bộ có tab sự cố, thiết bị, kế hoạch cách ly/khôi phục, thông báo và audit; tìm kiếm, lọc trạng thái | Snapshot chỉ đọc, chưa phải route trong UI PacketFence, chưa tự cập nhật |
| Telegram/Email | Outbox chống trùng, xem trước, driver Telegram HTTPS và SMTP implicit TLS, trạng thái gửi/audit | Chỉ gửi khi vận hành chủ động gọi `dispatch --send`; chưa cấu hình hoặc gửi tới người nhận thật |
| VLAN thủ công/tự động có điều kiện | Tạo đề xuất thủ công hoặc đánh giá policy theo lô; rà soát và mô phỏng cách ly; kiểm tra lại binding/protected/VLAN | Không có adapter ghi lên mạng; tự động chỉ tạo đề xuất, chưa tự thực thi VLAN |
| Khôi phục/audit | Mô phỏng khôi phục theo VLAN gốc đã chụp; audit nguyên tử cho đề xuất, quyết định, inventory/registry và outbox; lifecycle event có bảng transitions | Không khẳng định thiết bị thật đã khôi phục; audit SQLite chưa chống sửa và actor chưa có xác thực |
| FortiGate/MikroTik/Ruijie | Ma trận tích hợp, registry và kế hoạch mô phỏng có vendor | Chưa chứng nhận model/firmware; Ruijie chưa thấy adapter có tên tương ứng trong repository |

## Kiến trúc và dữ liệu

```text
Sensor Suricata IDS ── EVE file ── Normalizer ── Security Events riêng
PF inventory/session export ── Interval resolver ── MAC + username evidence
Registry thiết bị ── Policy / Manual proposal ── Rà soát ── Mô phỏng / Khôi phục
Events ── Outbox ── Preview ── [chủ động --send] Telegram / Email
Store + Audit ── Xuất dashboard HTML chỉ đọc
```

`Store` nâng DB Security schema 1 lên 2, giữ events và bindings; sao lưu DB thử nghiệm
trước khi nâng cấp. Schema 2 thêm username trong khóa binding để các phiên trùng IP/MAC
nhưng khác người dùng không bị bỏ qua. Nếu nhiều username trùng thời gian, user là
`ambiguous`; một MAC vẫn có thể resolved. Thiếu username là `unresolved`, không đoán.

Các bảng vận hành bổ sung: `assets`, `action_plans`, `outbox`, `audit`. Không đụng
schema MySQL hay dữ liệu PacketFence. Các sự kiện schema cũ không có user evidence
vẫn đọc được nhưng không đủ điều kiện tự động tạo đề xuất. Replay không tự cập nhật
evidence cũ. Registry giữ VLAN quan sát gốc; mô phỏng không thay đổi registry thành
VLAN cách ly để tránh nhầm là trạng thái mạng thật.

## Quy trình lab

Từ thư mục repository, dùng Python 3.10+:

```sh
python3 addons/nac20-security/demo.py --out work/security-dashboard-demo.html
python3 -m unittest discover -s addons/nac20-security -v
```

Lệnh demo dùng DB trong bộ nhớ, không mạng, không credential, không dữ liệu thật.
Mở HTML trong trình duyệt. Có dữ liệu của ba vendor để rà soát giao diện; đây không
phải bằng chứng đã kết nối hay điều khiển thiết bị các hãng đó.

Với DB lab đã nhập EVE theo [README module](../addons/nac20-security/README.md):

```sh
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor lab-import assets --scope lab --file addons/nac20-security/examples/assets.json
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor lab-import inventory --scope lab --file addons/nac20-security/examples/inventory.json
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor lab-admin dashboard --out work/security-lab/dashboard.html
```

Nhập inventory có username **trước** EVE để lưu bằng chứng user vào sự kiện. File
mẫu có thời gian cố định, chỉ để thử ingest; các đề xuất đòi dữ liệu mới. Với quy trình
đề xuất, dùng sự kiện lab mới và binding thời gian còn hiệu lực. `vendor` trong assets
là vendor của hạ tầng dự kiến thực thi NAC cho máy đó, không phải hãng sản xuất laptop.

### Đề xuất cách ly và khôi phục

```sh
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor analyst plan --event EVENT_ID --endpoint src --vlan 999 --reason "Rà soát cảnh báo lab"
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor reviewer decide PLAN_ID simulate
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor reviewer decide PLAN_ID restore
```

Có thể `decide PLAN_ID reject` để từ chối đề xuất. `simulate` yêu cầu actor khác người
đề xuất và thực hiện trong 5 phút; label actor ở CLI không phải cơ chế phân quyền
hay phê duyệt production. Trạng thái luôn ghi rõ `simulated_quarantined` hoặc
`simulated_restored`. Chỉ một plan hoạt động cho mỗi scope/MAC, tránh chồng lấn.

Đề xuất thủ công yêu cầu sự kiện không đóng, trong 300 giây, endpoint resolved,
binding hiện tại khớp MAC, thiết bị có registry và `protected=false`, VLAN 1–4094 và
khác VLAN gốc. Khi mô phỏng, kiểm tra lại binding, protection, thời gian và VLAN gốc.
Khôi phục chỉ theo trạng thái mô phỏng hợp lệ và VLAN gốc được lưu; không gửi CoA.

### Điều kiện tự động

`examples/policy.json` mặc định `enabled=false`. Sao chép và chỉnh policy lab nếu
muốn kiểm thử đề xuất tự động; không bật bản mẫu thành mặc định của repository.

```sh
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor lab-policy evaluate --policy work/lab-policy.json --endpoint src --vlan 999
```

Mỗi lần chạy xét tối đa 1.000 sự kiện gần nhất. Policy cần allowlist scope, sensor,
signature ID; ngưỡng severity (số nhỏ hơn là nghiêm trọng hơn), max age, cooldown và
quota đề xuất mỗi giờ. Cần user resolved và user hiện tại khớp bằng chứng sự kiện.
Các điều kiện thủ công vẫn áp dụng. Endpoint cần được chọn rõ ràng theo rule, không
suy ra “nguồn luôn nhiễm”. Quota hiện tính trên toàn DB để bảo thủ; mọi plan đều tính,
kể cả đã từ chối/khôi phục. Trùng plan hoặc không đủ điều kiện được đếm skipped.
Đây là đánh giá một lượt có giới hạn, chưa phải daemon hay tự động thực thi.

### Telegram và Email

```sh
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor analyst notify-active --channel telegram
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor analyst notify-active --channel email
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor analyst snapshot
python3 addons/nac20-security/security_ops.py --db work/security-lab/security.db --actor analyst dispatch NOTIFICATION_ID
```

`notify-active` xếp hàng tối đa 1.000 sự kiện gần nhất chưa đóng. Khóa event/channel
ngăn lặp; `notify --event EVENT_ID --channel ...` xếp hàng một sự kiện. `dispatch`
không có `--send` chỉ xem trước. Không tự gửi sau khi ingest.

Để vận hành chức năng gửi sau khi có phê duyệt/người nhận được xác nhận, cấu hình
biến môi trường trong tài khoản dịch vụ, không commit secret:

| Kênh | Biến cấu hình |
|---|---|
| Telegram | `NAC20_TELEGRAM_TOKEN`, `NAC20_TELEGRAM_CHAT_ID` |
| Email | `NAC20_SMTP_HOST`, `NAC20_SMTP_PORT` (mặc định 465), `NAC20_SMTP_FROM`, `NAC20_SMTP_TO`, `NAC20_SMTP_USER`, `NAC20_SMTP_PASSWORD` |

Sau đó người vận hành gọi `dispatch NOTIFICATION_ID --send` cho từng bản tin đã xem.
Telegram dùng [Bot API sendMessage](https://core.telegram.org/bots/api#sendmessage),
plain text, không parse HTML; không cho đổi endpoint hoặc redirect. Email dùng
SMTP_SSL xác minh chứng thư, không fallback plaintext/STARTTLS; máy chủ chỉ hỗ trợ
587 cần adapter riêng sau này. Thời gian chờ 10 giây. Chữ ký cảnh báo vẫn có thể
chứa dữ liệu nhạy cảm; rà soát nội dung xem trước. Không đưa trường IP/MAC/user hoặc
payload trực tiếp vào bản tin mặc định.

Outbox ghi `sending` trước I/O; thành công là `sent`. Lỗi là `uncertain`, không lưu
exception/secret và không tự thử lại vì máy chủ có thể đã nhận. Nếu tiến trình chết,
bản ghi có thể còn `sending`. Cần kiểm tra ở kênh nhận trước khi xây cơ chế gửi lại;
chưa hỗ trợ lệnh resend. `sent` nghĩa transport chấp nhận, không chứng minh người
nhận đã đọc. Chưa có end-to-end delivery receipt hay routing nhiều người nhận.

## Tích hợp hạ tầng

```text
Internet ── FortiGate hoặc MikroTik (gateway/firewall)
                         │
                  Switch/AP truy cập ── máy người dùng
                    │           │
             RADIUS/Accounting  SPAN/TAP ── Suricata IDS
                    │                        │
                  PacketFence          NAC20 Security
             (quyền truy cập/VLAN)     (quan sát/đề xuất)
```

Thiết bị cấp quyền truy cập có thể khác gateway. Việc cách ly VLAN chỉ khả thi nếu
switch/AP, chế độ xác thực và topology hỗ trợ thực thi tương ứng; gateway không
tự đổi VLAN trên mọi switch phía sau nó. Không áp dụng cấu hình chung cho mọi model.

| Hạ tầng | Bằng chứng hiện hữu | Cần xác nhận trong lab |
|---|---|---|
| FortiGate | `lib/pf/Switch/Fortinet/FortiGate.pm` mô tả web auth/802.1X/VPN và role-based enforcement; có giới hạn không deauth web auth. `docs/installation/firewall/fortigate.asciidoc` có SSO, tài liệu IDS có DHCP parser | Model/FortiOS, dùng gateway hay NAS thực thi, RADIUS accounting, phương thức đổi quyền/reauth và khôi phục. SSO không đồng nghĩa đổi VLAN trên switch |
| MikroTik | `lib/pf/Switch/Mikrotik.pm`; `docs/network/networkdevice/mikrotik.asciidoc` có RouterOS/802.1X và RADIUS disconnect | Model/RouterOS, wired/wireless/CAPsMAN, bridge/VLAN filtering, khả năng dynamic VLAN, accounting/reauth và giới hạn mode |
| Ruijie | Chưa tìm thấy module tên Ruijie trong `lib/pf/Switch` ở mốc kiểm tra | Model switch/AP/controller, firmware, 802.1X/MAB, VLAN RADIUS, CoA/disconnect; kiểm tra generic profile hoặc viết adapter có test. Không giả nhận chứng nhận tương thích |

Tham khảo [hướng dẫn thiết bị PacketFence](https://www.packetfence.org/doc/PacketFence_Network_Devices_Configuration_Guide.html)
và tài liệu đúng model. Chỉ bổ sung adapter ghi sau khi chốt topology, role/VLAN
mapping, tài khoản tối thiểu, rollback và phê duyệt tác động thật. Không cần đặt
Suricata inline hoặc sửa đường RADIUS/DHCP hiện có cho phần thu thập này.

## Kiểm chứng và phần phải làm tiếp

Bộ test Python gồm nền tảng, migration schema 1→2, user conflict, asset batch
atomicity, inventory/audit rollback, proposal/restore, revalidation, policy quota/
cooldown, outbox dedup, transport mock Telegram/SMTP TLS và escape dữ liệu HTML.
Dashboard được kiểm tra bằng trình duyệt headless: counters, các tab, tìm user,
lọc trạng thái, audit sự kiện, màn hình nhỏ và lỗi JavaScript.

Chưa có API/RBAC, dashboard live trong PacketFence, exporter phiên xác thực trực
tiếp, thu EVE liên tục/retention, notification daemon hay adapter đổi VLAN thật.
Audit hiện có thể bị sửa bởi người có quyền DB; label CLI không chứng minh danh
tính và không thay thế phê duyệt tổ chức. Các lệnh CLI nền tảng có thể bỏ qua audit
vận hành mới; dùng entry point `security_ops.py inventory` cho import có audit.
Giữ lab trên tài khoản/thư mục riêng, không công khai dashboard chứa dữ liệu thật.

Bước tiếp theo cần model/firmware của ba hãng, sơ đồ gateway/switch/AP, nguồn user
(802.1X/AD/RADIUS/VPN), VLAN cách ly/khôi phục, quy tắc bảo vệ thiết bị và người
nhận thông báo. Chưa cần gửi credential trong chat; cấu hình secret ngoài repository.
