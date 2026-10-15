# Hướng dẫn bộ cài NAC20 — Debian 12 amd64

**Công Ty TNHH TN20 · 20.com.vn**

Bộ cài dành cho mô hình **NAC20 trên VPS + Connector tại công ty + xác thực MAC qua switch/Wi-Fi**. Đây là bộ cài **online, bản preview**: có các gói `.deb` được biên dịch, cần Internet để tải phụ thuộc và ảnh dịch vụ. Chưa phải ISO offline hoặc bản đã nghiệm thu RADIUS/MAB trên thiết bị mạng thật.

## 1. Chuẩn bị hai máy riêng

| Thiết bị | Yêu cầu | Nhiệm vụ |
|---|---|---|
| VPS/máy chủ NAC20 | Debian 12 x86_64; 4 vCPU, RAM 16 GB, ổ đĩa 200 GB; systemd | Giao diện quản trị, cơ sở dữ liệu và chính sách |
| Máy Connector tại công ty | Debian 12 x86_64; tối thiểu 1 vCPU, RAM 2 GB, ổ đĩa 10 GB; systemd | Kết nối thiết bị mạng nội bộ với VPS |
| Switch/Wi-Fi/controller | Hỗ trợ RADIUS và MAC Authentication/MAB | Áp dụng quyết định cho phép/từ chối |

Dùng hệ điều hành mới, dành riêng cho NAC20. Không cài nhóm `server` và `connector` trên cùng máy. Không cần cài Connector trên từng laptop, camera hoặc máy in.

Tạo snapshot trước khi cài và giữ quyền truy cập console của VPS. Phần mềm nền tảng quản lý nhiều dịch vụ hệ thống; không dùng chung máy đang chạy website, cơ sở dữ liệu hoặc workload Docker khác.

## 2. Tải đúng tệp và kiểm tra SHA-256

Mở mục **Releases** của kho `lehuunghi/NAC`, chọn bản NAC20 dành cho Debian 12 amd64. Tải ba tệp vào cùng thư mục:

- `nac20-debian12-amd64-online.tar.gz`: toàn bộ bộ cài.
- `SHA256SUMS`: tổng kiểm tệp tải về.
- `BUILDINFO.json`: phiên bản, commit nguồn và danh sách gói.

Không dùng đường dẫn `releases/latest` để suy đoán bản preview: GitHub không coi prerelease là bản stable mới nhất. Chọn đúng bản phát hành hiển thị trên trang Releases.

Trên máy Linux đã tải tệp:

```bash
sha256sum --check --strict SHA256SUMS
tar -xzf nac20-debian12-amd64-online.tar.gz
cd nac20-debian12-amd64-online
cat BUILDINFO.json
```

Cả tệp nén và `BUILDINFO.json` phải được báo `OK`. Nếu lỗi tổng kiểm hoặc thiếu tệp, tải lại đúng bộ từ cùng bản phát hành; không sửa tay `SHA256SUMS` để vượt kiểm tra. SHA-256 xác nhận tệp khớp bản phát hành, không phải chữ ký GPG của nhà phát hành.

Nếu tải bằng máy Windows rồi chép qua SCP/SFTP, giữ nguyên tệp nén. Giải nén trên máy Linux đích để giữ quyền file và tránh chuyển nội dung script sang kiểu xuống dòng Windows.

## 3. Các tệp bên trong bộ cài

| Đường dẫn | Nội dung |
|---|---|
| `install.sh` | Cài mới hoặc kiểm tra bộ cài, chọn `server` hay `connector` |
| `server/` | Tám gói máy chủ và thành phần liên quan |
| `connector/` | Gói Connector từ xa |
| `connector-ad/` | Hai gói NTLM/AD tùy chọn, không tự cài cho xác thực MAC |
| `keys/` | Khóa công khai cho các kho phụ thuộc được trình cài dùng |
| `BUILDINFO.json` | Commit, phiên bản, tổng kiểm và phạm vi kiểm thử |
| `DEPENDENCY_SERIES` | Nhánh phiên bản phụ thuộc tương ứng |
| `SHA256SUMS` | Tổng kiểm các tệp bên trong bộ cài |
| `docs/NAC20_CAI_DAT.md` | Hướng dẫn triển khai NAC20 theo từng bước |

Tên gói, unit systemd và thư mục nội bộ được giữ để tương thích với nền tảng. Thương hiệu giao diện và bản dịch là NAC20. Không đổi tên package, unit hay thư mục `/usr/local/pf` theo cách thủ công.

## 4. Chuẩn bị DNS, giờ và kết nối mạng

Ví dụ địa chỉ, phải thay bằng giá trị thật của bạn:

| Hạng mục | Ví dụ |
|---|---|
| Tên miền quản trị | `nac20.20.com.vn` trỏ đến IP công khai của VPS |
| Connector trong công ty | `192.168.10.10`, đặt IP tĩnh hoặc DHCP reservation |
| Switch/Wi-Fi | `192.168.10.2` |
| Mạng quản trị thiết bị | `192.168.10.0/24` |

Kiểm tra trên VPS và máy Connector:

```bash
cat /etc/os-release
uname -m
free -h
df -h /
timedatectl status
```

Kết quả phải là Debian 12, `x86_64`, đủ tài nguyên và thời gian đồng bộ. Sau khi đã tạo DNS, kiểm tra:

```bash
getent ahostsv4 nac20.20.com.vn
```

VPS cần tải được các kho APT cấu hình bởi bộ cài và ảnh dịch vụ tại `ghcr.io`. Khi cài có thể cần nhiều dung lượng hơn kích thước tệp nén do giải nén và tải ảnh Docker.

| Luồng kết nối | Cổng |
|---|---|
| Máy quản trị → VPS | TCP 1443 |
| Connector → VPS | TCP 1443, kết nối chủ động ra ngoài |
| Switch/Wi-Fi → Connector | UDP 1812 xác thực; UDP 1813 accounting |
| Connector → thiết bị mạng | CoA/SNMP tùy model, CoA thường 3799 hoặc 1700 |
| Máy chủ/Connector → dịch vụ phụ thuộc | DNS và HTTP/HTTPS theo nguồn tải cần thiết |

Giới hạn nguồn truy cập quản trị phù hợp với hệ thống của bạn. Với mô hình Connector, không cần công khai RADIUS, SNMP, cơ sở dữ liệu hoặc cổng API nội bộ 9999 ra Internet. Không thay toàn bộ firewall hoặc gateway theo các IP ví dụ trong tài liệu.

## 5. Kiểm tra bộ cài trên VPS

Chạy trong thư mục đã giải nén trên **VPS**, chưa thực hiện cài dịch vụ:

```bash
bash install.sh server --check
```

Chế độ này kiểm tra Debian/kiến trúc, các tổng kiểm bên trong và metadata của gói. Nó **không** cài phụ thuộc, cấu hình firewall, chứng minh đủ RAM/disk hoặc kiểm thử thiết bị mạng. Không được coi thông báo thành công của `--check` là máy chủ NAC đã hoạt động.

## 6. Cài nhóm máy chủ trên VPS

Sau khi hoàn tất chuẩn bị:

```bash
sudo bash install.sh server --install
```

Trình cài sẽ kiểm tra bộ cài và quyền root, yêu cầu systemd, dừng nếu phát hiện NAC20/Connector đã cài hoặc cài dở, cấu hình nguồn APT có khóa công khai riêng, giải quyết phụ thuộc và cài các gói máy chủ. Script dành cho cài mới; không tự nâng cấp máy đang có NAC20.

Giữ phiên SSH và console dự phòng khi cài. Không khởi chạy hai trình cài đồng thời. Nếu APT bị gián đoạn, lưu lỗi và kiểm tra tình trạng gói trước khi thao tác tiếp; không dùng `--force-depends`, không xóa khóa APT khi một tiến trình cài khác còn chạy.

Kiểm tra sau khi lệnh hoàn tất:

```bash
dpkg-query -W packetfence packetfence-config packetfence-golang-daemon
locale -a | grep -i '^vi_VN'
sudo systemctl --failed
sudo ss -lnt | grep ':1443'
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
```

## 7. Cấu hình NAC20 lần đầu

Mở `https://TEN-MIEN-HOAC-IP-VPS:1443`. Với ví dụ DNS đã chuẩn bị, địa chỉ là `https://nac20.20.com.vn:1443`.

1. Chọn đúng interface quản trị và IP của VPS. Không đổi sang IP LAN của công ty hoặc đổi gateway đang phục vụ SSH.
2. Khai báo hostname `nac20`, domain `20.com.vn` nếu dùng đúng tên miền ví dụ; thay bằng miền thực tế nếu khác.
3. Khởi tạo cơ sở dữ liệu bằng trình cấu hình.
4. Tạo tài khoản quản trị riêng, mật khẩu mạnh; lưu thông tin khôi phục ở nơi quản lý mật khẩu của công ty. Không có tài khoản/mật khẩu dùng chung trong bộ cài.
5. Kiểm tra ngôn ngữ mặc định Tiếng Việt và thông tin NAC20.
6. Xác nhận, khởi động các dịch vụ và đăng nhập lại.
7. Sau khi cấu hình hoàn tất, tắt trình cấu hình trước khi bàn giao.

Cấu hình chứng thư TLS và chuỗi CA hợp lệ cho tên miền thật bằng cơ chế quản lý chứng thư của hệ thống, trước khi đưa vào vận hành và ghép Connector. Nếu trình duyệt báo lỗi chứng thư, đối chiếu DNS, SAN, chuỗi CA và giờ hệ thống. Không dùng việc bỏ xác minh TLS làm cấu hình nghiệm thu.

Từ máy Connector, sau khi đã cấu hình TLS tin cậy:

```bash
curl --head --connect-timeout 10 https://nac20.20.com.vn:1443/
openssl s_client -connect nac20.20.com.vn:1443 \
  -servername nac20.20.com.vn -verify_return_error </dev/null
```

## 8. Cài Connector trong mạng nội bộ

Trên **máy Debian 12 tại công ty**, chép cùng bộ cài, kiểm tra SHA-256, giải nén như bước 2. Chạy:

```bash
cd nac20-debian12-amd64-online
bash install.sh connector --check
sudo bash install.sh connector --install
```

Không chạy lựa chọn `server` trên máy này. Gói Connector được cài riêng; các gói AD/NTLM trong `connector-ad` không được tự cài chỉ để duyệt MAC.

## 9. Ghép nối Connector với VPS

Trên máy Connector:

```bash
sudo /usr/local/pfconnector-remote/bin/pfconnector-configure
```

1. Ghi lại Connector ID xuất hiện và giữ trình cấu hình đang chờ nhập khóa.
2. Trên NAC20, vào **Cấu hình → Cấu hình hệ thống → Bộ kết nối**; tạo Connector có cùng ID.
3. Tạo khóa ngẫu nhiên riêng, đặt mô tả chi nhánh và khai báo các CIDR thật phía công ty. Ví dụ mạng switch `192.168.10.0/24`; bổ sung mạng AD/DNS nếu cần. Không thay bằng `0.0.0.0/0`.
4. Trở lại terminal, nhập khóa và URL `https://nac20.20.com.vn:1443/api/v1/pfconnector/tunnel`, thay tên miền theo thực tế.
5. Chọn `y` khi được hỏi xác minh chứng thư TLS. Chứng thư máy chủ phải được Connector tin cậy.
6. Khởi động dịch vụ kết hợp và kiểm tra:

```bash
sudo chmod 600 /usr/local/pfconnector-remote/conf/pfconnector-client.env
sudo systemctl restart packetfence-pfconnector-remote-combined
sudo systemctl status packetfence-pfconnector-remote-combined --no-pager
sudo journalctl -u packetfence-pfconnector-remote-combined -n 50 --no-pager
```

NAC20 phải hiển thị Connector đã kết nối. Trình ghép nối nền tảng có thể in khóa ra terminal; không chia sẻ bản ghi chứa khóa. File `pfconnector-client.env` là cấu hình bí mật, không đưa lên GitHub hoặc dán vào yêu cầu hỗ trợ.

## 10. Bật xác thực MAC trên một cổng hoặc SSID thử nghiệm

1. Trên NAC20, thêm switch/Wi-Fi bằng IP quản trị thật; chọn đúng hãng/model hoặc driver tương thích.
2. Tạo vai trò như Nhân viên, Máy in, Camera. Nếu phân quyền bằng VLAN, tạo VLAN và trunk/uplink trên thiết bị mạng rồi ánh xạ vai trò tương ứng.
3. Trên switch/Wi-Fi, bật MAB/MAC Authentication cho một cổng hoặc SSID thử. Trỏ RADIUS Authentication đến IP Connector, ví dụ `192.168.10.10:1812`; Accounting UDP `1813`.
4. Với cơ chế Connector này, cấu hình khóa RADIUS theo giá trị `local_secret` của máy chủ mà nền tảng yêu cầu. Quản trị viên xem bảo mật tại `/usr/local/pf/conf/local_secret`; đây **khác** khóa ghép đường hầm ở bước 9. Không gửi khóa qua chat hoặc ghi vào tài liệu công khai.
5. Bật CoA/Disconnect nếu thiết bị hỗ trợ và cho phép Connector đến đúng cổng của model.
6. Thiết lập chỉ MAC được duyệt mới có quyền. Không bật tự đăng ký cho mọi MAC vừa xuất hiện.

Không có một bộ lệnh CLI dùng được cho mọi hãng. Xác định model và firmware trước khi cấu hình AAA/MAB/VLAN/CoA; không áp dụng một ví dụ Cisco lên thiết bị khác.

MAC có thể bị giả mạo. Máy dùng MAC riêng tư/ngẫu nhiên có thể được nhận diện bằng địa chỉ khác trên từng SSID; đăng ký đúng địa chỉ dùng trên mạng đó. MAB phù hợp cho danh sách thiết bị được quản lý, không thay thế mức xác thực của chứng thư 802.1X.

## 11. Đăng ký MAC được phê duyệt

Cách thủ công: vào **Thiết bị**, tạo MAC, đặt trạng thái đã đăng ký, gán vai trò và thời hạn truy cập nếu cần.

Với danh sách lớn, dùng API cục bộ trên **VPS**. Ví dụ dưới đây **thực sự đăng ký/cấp quyền**, không phải chạy thử. Thay các MAC và số `3` bằng ID vai trò đã tạo trên NAC20; `category_id` không phải VLAN ID.

```bash
sudo -i
cat > /root/nac20-macs.json <<'JSON'
{
  "ignoreUpdateIfExists": true,
  "items": [
    {"mac": "AA:BB:CC:11:22:33", "category_id": 3},
    {"mac": "AA:BB:CC:44:55:66", "category_id": 3}
  ]
}
JSON
chmod 600 /root/nac20-macs.json
jq . /root/nac20-macs.json
/usr/local/pf/sbin/pfperl-api get -M POST /api/v1/nodes/bulk_import \
  < /root/nac20-macs.json
```

Kiểm tra kết quả **từng MAC**, rồi xác nhận trạng thái/vai trò trên giao diện. `ignoreUpdateIfExists` bỏ qua MAC đã có, không tự thay đổi quyền của thiết bị cũ. HTTP thành công không bảo đảm mọi bản ghi đã thành công.

API gọi từ máy khác sử dụng `POST /api/v1/login` trên cổng quản trị, sau đó gửi `Authorization: Bearer TOKEN`. Giữ token ngoài mã nguồn và nhật ký công khai.

## 12. Kiểm thử trước khi triển khai rộng

- MAC đã duyệt: được chấp nhận, vào đúng VLAN/ACL và lấy đúng IP từ DHCP tại công ty.
- MAC chưa duyệt: bị từ chối, không chỉ hiển thị trạng thái khác trên NAC20.
- Thay đổi/thu hồi quyền: CoA hoặc xác thực lại thực sự làm thay đổi phiên truy cập.
- Mất đường hầm/Internet: thử trong môi trường riêng để biết hành vi thực tế; không giả định mọi phiên mới, portal hoặc AD đều hoạt động offline.
- Khởi động lại máy chủ/Connector: dịch vụ trở lại đúng trạng thái, không đổi thương hiệu hoặc ngôn ngữ.
- Sao lưu và khôi phục: kiểm chứng một bản sao lưu có thể khôi phục, không chỉ tạo được file xuất.

Chỉ chuyển dần từng nhóm cổng/SSID sang chính sách mới sau khi các thử nghiệm trên đạt.

## 13. Xử lý lỗi thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| `Requires Debian 12` hoặc sai kiến trúc | Dùng Debian 12 x86_64; không chạy bộ này trên Ubuntu hoặc ARM |
| Tổng kiểm lỗi | Tải lại đầy đủ ba tệp của cùng bản phát hành; không chỉnh SHA256SUMS |
| Phát hiện cài đặt cũ/cài dở | Dừng trình cài mới; sao lưu và kiểm tra quy trình phục hồi/nâng cấp |
| APT thiếu gói hoặc lỗi chữ ký | Kiểm tra DNS, giờ, nguồn APT, phiên bản trong BUILDINFO và kết nối HTTPS; không bỏ kiểm tra chữ ký |
| Không mở cổng 1443 | Kiểm tra `systemctl --failed`, `ss -lnt`, `docker ps`, firewall và DNS |
| Connector mất kết nối | Kiểm tra URL tunnel, ID, khóa, TCP 1443, TLS và giờ hai máy |
| Không có yêu cầu RADIUS | Kiểm tra IP Connector, MAB trên cổng/SSID, UDP 1812 và shared secret |
| Có RADIUS nhưng bị từ chối | Đối chiếu MAC thực tế, trạng thái đăng ký, hạn truy cập, vai trò và model NAS |
| Chấp nhận nhưng không có mạng | Kiểm tra VLAN/ACL, uplink, DHCP, gateway và DNS ở công ty |
| Không áp dụng quyền mới | Kiểm tra CoA/Disconnect và thời điểm xác thực lại của phiên hiện có |

Khi cần hỗ trợ, lưu commit/phiên bản gói, model/firmware, thời điểm lỗi và thông báo đã che dữ liệu nhạy cảm. Không gửi mật khẩu, token, shared secret hoặc toàn bộ tệp cấu hình chứa khóa.

## 14. Phạm vi bản preview và bảo trì

Bản phát hành ghi các kiểm tra đã chạy trong `BUILDINFO.json`: có gói Debian thật, chương trình Go/C dạng ELF, giao diện đã build, bản dịch Việt, tổng kiểm và kiểm tra giải quyết phụ thuộc trên Debian sạch. Các kiểm tra này chưa thay thế cài mới với systemd trên VPS, khôi phục đầy đủ hoặc nghiệm thu MAB với thiết bị thật.

Ảnh dịch vụ nền tảng được tải online từ registry ghi trong `BUILDINFO.json`, nhãn `latest`; đây chưa phải bộ runtime bất biến hoặc offline. Các gói chưa có chữ ký phát hành riêng của TN20; đối chiếu nguồn tải GitHub và SHA-256 được công bố.

Script không tự sửa firewall, bỏ TLS, xóa DNS hệ thống hoặc thay chính sách AppArmor. Đối chiếu yêu cầu tương thích của đúng bản nền tảng khi chuẩn bị máy chủ. Các maintainer script của gói nền tảng vẫn thực hiện cấu hình hệ thống cần thiết cho NAC, nên cần máy dành riêng và console khôi phục.

Đối với nâng cấp, dùng bộ gói tương thích đã thử và quy trình sao lưu/khôi phục riêng; không chạy lại trình cài mới trên hệ thống có dữ liệu. Theo dõi dung lượng đĩa, hạn chứng thư, nhật ký RADIUS và phiên bản phụ thuộc. Không xóa snapshot trước khi nghiệm thu hoạt động thực tế.
