<!-- Generated from the About page content. Run node addons/dev-helpers/generate-nac20-installation-guide.cjs to update. -->

# Cài đặt NAC20 từ đầu

**NAC20 · Công Ty TNHH TN20 · 20.com.vn**

Triển khai máy chủ trên VPS, kết nối mạng nội bộ và xác thực thiết bị bằng địa chỉ MAC.

> **Chuẩn bị bộ cài trước khi bắt đầu:** Lấy bộ cài từ bản phát hành NAC20 thành công trong mục Releases của kho lehuunghi/NAC; kiểm tra BUILDINFO.json và SHA256SUMS. Bộ cài Debian 12 hiện được thiết kế theo dạng online: cần Internet để tải phụ thuộc và ảnh dịch vụ. Chỉ tải mã nguồn hoặc chạy npm build chưa tạo thành một máy chủ NAC hoạt động. Nếu chưa có bản phát hành thành công, cần chờ quy trình đóng gói hoàn tất.

Các lệnh Linux dưới đây dành cho Debian 12 x86_64. Đọc nhãn để chạy đúng máy: VPS, máy Connector hoặc máy đóng gói. Tên miền, IP, MAC và ID vai trò đều là ví dụ cần thay bằng giá trị của bạn.

## Mô hình triển khai

Thiết bị người dùng → Switch / Wi-Fi nội bộ → Connector tại công ty → NAC20 trên VPS

## Yêu cầu hệ thống

| Hạng mục | Nội dung |
|---|---|
| Máy chủ NAC20 | Debian 12 x86_64; 4 vCPU, RAM 16 GB, ổ đĩa 200 GB theo mức tối thiểu của nền tảng. Dùng VPS hoặc máy ảo riêng. |
| Máy Connector | Một máy Debian 12 x86_64 trong mạng công ty; tối thiểu 1 vCPU, RAM 2 GB, ổ đĩa 10 GB. Không cần cài trên từng máy người dùng. |
| Thiết bị mạng | Switch hoặc Wi-Fi/controller hỗ trợ RADIUS và xác thực MAC (MAB). Phân VLAN, ACL và CoA tùy khả năng của model và phiên bản firmware. |
| DNS và chứng thư | Tên miền quản trị trỏ về VPS; chứng thư TLS hợp lệ cho tên miền đó. Đồng bộ giờ trên VPS và Connector. |
| Bộ cài | Gói máy chủ, gói Connector và các phụ thuộc cùng phiên bản; cấu hình nguồn APT đã xác minh. Không trộn các nhánh hoặc phiên bản nền tảng. |

## Địa chỉ ví dụ

| Hạng mục | Nội dung |
|---|---|
| Tên miền NAC20 | nac20.20.com.vn → IP công khai của VPS |
| Connector trong LAN | 192.168.10.10, địa chỉ tĩnh hoặc DHCP reservation |
| Switch / Wi-Fi | 192.168.10.2, phải liên lạc được với Connector |
| Mạng phía công ty | 192.168.10.0/24; khai báo đúng các mạng quản trị thiết bị, AD và DNS cần đi qua Connector |

## Các cổng mạng

| Hạng mục | Nội dung |
|---|---|
| Quản trị và đường hầm | TCP 1443 trên VPS: cho phép máy quản trị và Connector truy cập; Connector chủ động mở kết nối ra Internet. |
| Xác thực RADIUS | UDP 1812 từ switch/Wi-Fi tới IP Connector trong LAN. |
| Ghi nhận phiên RADIUS | UDP 1813 từ switch/Wi-Fi tới IP Connector trong LAN. |
| Đổi quyền / ngắt kết nối | CoA thường dùng UDP 3799 hoặc 1700 tùy hãng; SNMP và ACL cũng phụ thuộc thiết bị. Cấu hình theo model, không mở hàng loạt ra Internet. |
| Cổng đăng ký và API | HTTP/HTTPS cho cổng đăng ký tùy phương án. API của giao diện dùng /api/v1 trên cổng quản trị; cổng API nội bộ 9999 không cần công khai chỉ để đăng ký MAC. |

## 1. Chuẩn bị VPS và địa chỉ mạng

Thực hiện trên VPS Debian 12 mới, trước khi cài dịch vụ NAC20.

Tạo snapshot của VPS, ghi lại IP, cổng SSH và cách truy cập console của nhà cung cấp. Chuẩn bị tên miền và các địa chỉ ví dụ ở trên. Nếu máy đang chạy web, cơ sở dữ liệu hoặc dịch vụ mạng khác, dùng VPS riêng vì NAC20 quản lý nhiều dịch vụ hệ thống.

Đăng nhập SSH bằng tài khoản quản trị và chạy sudo -i để vào shell root trước khi dùng các lệnh cài đặt dưới đây. Đối với máy Connector, cũng dùng shell quản trị riêng trên đúng máy đó.

**VPS — kiểm tra hệ điều hành và cập nhật gói**

```bash
cat /etc/os-release
uname -m
free -h
df -h /
apt-get update
apt-get install ca-certificates curl gnupg git locales-all jq
timedatectl status
getent ahostsv4 nac20.20.com.vn
```

1. Tạo bản ghi DNS A cho nac20.20.com.vn trỏ đến IPv4 của VPS. Chỉ tạo AAAA nếu đã cấu hình IPv6 hoạt động.
2. Giữ firewall quản trị của nhà cung cấp và bảo đảm SSH vẫn truy cập được. Chưa bật MAB trên toàn bộ mạng đang vận hành.
3. Đăng nhập SSH bằng tài khoản quản trị, vào shell root bằng sudo -i. Các khối lệnh cài đặt tiếp theo giả định đang ở shell root.

**Kết quả cần đạt:** Hệ điều hành là Debian 12, kiến trúc x86_64, DNS trả về đúng VPS và thời gian đã đồng bộ. Nếu nâng cấp kernel, khởi động lại rồi cài bộ headers khớp kernel trước khi xử lý các phụ thuộc DKMS.

## 2. Chuẩn bị bộ cài NAC20 đúng phiên bản

Phân biệt mã nguồn, môi trường đóng gói và gói có thể cài lên VPS.

Trong mục Releases của kho lehuunghi/NAC, chọn bản NAC20 dành cho Debian 12 amd64 và tải nac20-debian12-amd64-online.tar.gz cùng SHA256SUMS. Chọn đúng trạng thái preview hoặc bản nghiệm thu theo môi trường của bạn. Không có lệnh apt install nac20 từ một kho APT riêng tại 20.com.vn.

Bên trong bộ cài có thư mục server, connector, nhóm connector-ad tùy chọn, install.sh và BUILDINFO.json ghi phiên bản cùng commit nguồn. Chạy chế độ --check trước khi --install. Không cài nhóm server và connector trên cùng một máy.

Nếu chưa có bản phát hành thành công, cần hoàn tất quy trình đóng gói trước khi cài. Gói tải từ nguồn nền tảng khác không tự chứa các thay đổi NAC20 trong kho này. Phần lấy mã nguồn bên dưới dành cho người đóng gói, không cần chạy khi đã có bộ cài.

**Máy đóng gói — lấy mã nguồn, không phải lệnh cài NAC20**

```bash
git clone --branch main --single-branch https://github.com/lehuunghi/NAC.git nac20-src
cd nac20-src
git rev-parse HEAD
cat conf/pf-release
head -n 1 debian/changelog
```

1. Ghi lại mã commit; đối chiếu phiên bản trong conf/pf-release, debian/changelog và các gói phụ thuộc. Nhánh main có thể đang theo phiên bản phát triển.
2. Trong kho có môi trường Docker đóng gói Debian tại containers/pfbuild-bookworm và quy trình make build_deb. Việc chạy riêng Dockerfile mới tạo môi trường build, chưa tạo bộ cài hoàn chỉnh.
3. Quy trình phát hành cần biên dịch giao diện, các thành phần Go và tài nguyên cần thiết, đóng gói các dịch vụ liên quan, rồi thử cài mới trên Debian 12. Không sao chép đè một vài thư mục vào máy đang chạy để thay cho quy trình này.
4. Chuẩn bị riêng thư mục gói server và connector; kèm danh sách phiên bản và mã SHA-256 từ bên phát hành. Cấu hình các nguồn APT phụ thuộc đã xác minh trước bước 3.

**Kết quả cần đạt:** Có bộ gói server và Connector tương thích cùng phiên bản NAC20, cùng thông tin kiểm tra nguồn gốc; không chỉ một thư mục git clone.

## 3. Cài gói máy chủ và kiểm tra tiếng Việt

Thực hiện trên VPS sau khi có bộ .deb được nghiệm thu.

Đặt các gói chỉ dành cho máy chủ vào /opt/nac20-packages/server. Không để các gói Connector từ xa trong thư mục này. Kiểm tra tên, phiên bản, kiến trúc và tổng kiểm theo danh sách của bên phát hành trước khi cài.

Tên gói, dịch vụ và thư mục nội bộ vẫn dùng các định danh nền tảng để tương thích. Giao diện sản phẩm là NAC20; không tự đổi tên file .deb, unit systemd hoặc thư mục /usr/local/pf.

**VPS — cách cài bằng bộ cài online đã tải về**

```bash
tar -xzf nac20-debian12-amd64-online.tar.gz
cd nac20-debian12-amd64-online
bash install.sh server --check
sudo bash install.sh server --install
```

**VPS — kiểm tra và cài các gói server đã được cung cấp**

```bash
find /opt/nac20-packages/server -maxdepth 1 -name '*.deb' -print
for package in /opt/nac20-packages/server/*.deb; do
  dpkg-deb --field "$package" Package Version Architecture
done
apt-get update
apt-get install /opt/nac20-packages/server/*.deb
```

**VPS — xác nhận cài đặt và bộ dịch**

```bash
dpkg-query -W packetfence
locale -a | grep -i '^vi_VN'
test -s /usr/local/pf/conf/locale/vi/LC_MESSAGES/packetfence.mo && echo 'Da co bo dich cong dang ky'
test -s /usr/local/pf/html/pfappserver/root/dist/index.html && echo 'Da co giao dien quan tri'
ss -lnt | grep ':1443'
```

1. Nếu APT báo thiếu phụ thuộc, kiểm tra nguồn gói và phiên bản yêu cầu; không ép cài bằng --force-depends hoặc ghép các gói khác nhánh.
2. Nếu chưa thấy locale tiếng Việt dù đã có locales-all, kiểm tra lại gói locale trên hệ điều hành. Nếu thiếu file .mo hoặc dist/index.html, sửa bộ đóng gói trước khi nghiệm thu.
3. Kiểm tra các yêu cầu tương thích hệ điều hành của đúng bản phát hành, bao gồm AppArmor và quản lý DNS. Không chạy lệnh xóa resolv.conf hoặc tắt firewall theo một hướng dẫn khác khi chưa xác định tác động trên VPS này.

**Kết quả cần đạt:** Gói cài không còn lỗi phụ thuộc; có giao diện đã build và bộ dịch tiếng Việt; cổng trình cấu hình 1443 sẵn sàng.

## 4. Hoàn tất trình cấu hình lần đầu

Mở https://nac20.20.com.vn:1443 bằng trình duyệt quản trị.

Ở mô hình VPS + Connector, không kéo interface LAN hoặc VLAN tại công ty lên VPS bằng cách đổi IP trên trình cấu hình. Các mạng công ty sẽ được khai báo qua Connector ở bước 6.

1. Cấu hình interface quản trị theo IP thực tế của VPS. Không thay IP, gateway hoặc interface đang giữ phiên SSH nếu chưa có đường console dự phòng.
2. Trong cấu hình chung, đặt hostname là nac20, domain là 20.com.vn và ngôn ngữ mặc định là Tiếng Việt. Không nhập cả FQDN vào ô hostname nếu ô domain được khai báo riêng.
3. Khởi tạo cơ sở dữ liệu theo trình cấu hình. Tạo tài khoản quản trị riêng, mật khẩu mạnh và lưu thông tin khôi phục ở nơi quản lý mật khẩu của công ty.
4. Nếu cần nhận diện loại thiết bị, cấu hình dịch vụ nhận diện tương ứng. Việc chỉ duyệt danh sách MAC không đòi hỏi phải bật tự động cấp quyền cho thiết bị mới.
5. Xác nhận và khởi động các dịch vụ từ trình cấu hình. Đăng nhập lại, kiểm tra thương hiệu NAC20 và tiếng Việt; tắt trình cấu hình sau khi đã hoàn tất.

**Kết quả cần đạt:** Đăng nhập được giao diện quản trị; cơ sở dữ liệu và dịch vụ RADIUS hoạt động; không còn trình cấu hình mở khi bàn giao.

## 5. Hoàn thiện TLS và giới hạn cổng truy cập

Chuẩn bị kết nối tin cậy trước khi ghép Connector.

**Máy quản trị hoặc Connector — thử TLS và cổng quản trị**

```bash
curl --head --connect-timeout 10 https://nac20.20.com.vn:1443/
openssl s_client -connect nac20.20.com.vn:1443 -servername nac20.20.com.vn -verify_return_error </dev/null
```

1. Cài chứng thư TLS và chuỗi chứng thư đầy đủ cho nac20.20.com.vn bằng cơ chế quản lý chứng thư của hệ thống. Đối chiếu đúng tên miền và gia hạn định kỳ.
2. Tại firewall VPS, cho phép TCP 1443 từ máy quản trị và địa chỉ ra Internet của chi nhánh/Connector theo chính sách của bạn. Nếu chi nhánh dùng IP động, thiết kế quy tắc truy cập phù hợp thay vì giả định IP cố định.
3. Giữ cổng SSH theo cấu hình hiện có và hạn chế nguồn truy cập. Không cần công khai cơ sở dữ liệu, SNMP hoặc RADIUS ra Internet cho mô hình Connector.
4. Nếu có cảnh báo chứng thư trên trình duyệt hoặc Connector, sửa DNS, chuỗi CA hoặc thời gian hệ thống; không dùng việc bỏ kiểm tra TLS làm cấu hình bàn giao.

**Kết quả cần đạt:** Kết nối đến đúng VPS, xác minh được chứng thư TLS và không phải dùng tùy chọn bỏ kiểm tra chứng thư.

## 6. Cài Connector tại công ty và ghép với VPS

Thực hiện trên máy Debian 12 trong LAN, không cài trên từng thiết bị.

Đặt IP tĩnh hoặc DHCP reservation cho máy Connector, ví dụ 192.168.10.10. Máy phải truy cập được switch/Wi-Fi trong LAN và mở kết nối ra tên miền VPS trên TCP 1443. Cài gói Connector cùng phiên bản với máy chủ. Nếu dùng bộ cài online, chạy bash install.sh connector --check rồi sudo bash install.sh connector --install trên máy Connector; không chạy lựa chọn server tại đây. Phần lệnh APT bên dưới chỉ áp dụng cho cách cài gói thủ công đã chuẩn bị đầy đủ phụ thuộc.

Trình ghép nối hiện có thể in khóa chia sẻ ra terminal. Chạy trong phiên quản trị riêng, không ghi hình hoặc sao chép đầu ra chứa khóa vào hệ thống hỗ trợ. Không đưa nội dung file pfconnector-client.env vào Git.

**Máy Connector — cài gói và bắt đầu ghép nối**

```bash
apt-get update
apt-get install /opt/nac20-packages/connector/*.deb
/usr/local/pfconnector-remote/bin/pfconnector-configure
```

1. Ghi lại Connector ID xuất hiện trên terminal; giữ trình cấu hình chờ nhập khóa.
2. Trên NAC20: vào Cấu hình → Cấu hình hệ thống → Bộ kết nối; tạo Connector có cùng ID, mô tả chi nhánh và một khóa ngẫu nhiên riêng.
3. Khai báo đúng các CIDR phía công ty, ví dụ 192.168.10.0/24. Bổ sung mạng quản trị switch, máy chủ AD hoặc DNS nếu chúng nằm ở subnet khác. Không dùng 0.0.0.0/0 để thay cho việc xác định mạng cần truy cập.
4. Trở lại terminal, nhập khóa và địa chỉ https://nac20.20.com.vn:1443/api/v1/pfconnector/tunnel. Chọn y khi được hỏi xác minh chứng thư TLS; chứng thư phải được tin cậy.
5. Nếu dùng AD/LDAP nội bộ, khai báo thêm ánh xạ miền và DNS trong các tab của Bộ kết nối. Chỉ dùng danh sách MAC thì chưa cần tích hợp AD.

**Máy Connector — khởi động lại và xem trạng thái**

```bash
chmod 600 /usr/local/pfconnector-remote/conf/pfconnector-client.env
systemctl restart packetfence-pfconnector-remote-combined
systemctl status packetfence-pfconnector-remote-combined --no-pager
journalctl -u packetfence-pfconnector-remote-combined -n 50 --no-pager
```

**Kết quả cần đạt:** Connector hiện trạng thái kết nối trên NAC20. Nếu mất kết nối, kiểm tra DNS, giờ, TLS, khóa, firewall và dịch vụ; chưa bật xác thực lên các cổng sản xuất.

## 7. Cấu hình xác thực MAC trên switch hoặc Wi-Fi

Làm thử trên một cổng mạng hoặc một SSID trước khi mở rộng.

Không có một bộ lệnh CLI dùng được cho mọi switch hoặc Wi-Fi. Cần đối chiếu hãng, model và firmware trước khi áp dụng AAA, MAB, VLAN hoặc CoA. Connector hỗ trợ Web Authentication nhưng tài liệu hiện tại không hỗ trợ VLAN đăng ký/cách ly theo cách triển khai cổng đó.

MAC có thể bị giả mạo. Điện thoại hoặc laptop dùng MAC riêng tư có thể xuất hiện với MAC khác trên từng mạng; đăng ký đúng MAC của SSID cần quản lý. Với thiết bị cần xác thực mạnh hơn, cân nhắc 802.1X và chứng thư số.

1. Trên NAC20, thêm switch/Wi-Fi bằng IP quản trị thực tế, đúng hãng/model hoặc loại driver tương thích.
2. Tạo vai trò như Nhân viên, Máy in hoặc Camera. Nếu dùng VLAN, tạo VLAN và đường uplink/trunk tương ứng trên thiết bị mạng rồi ánh xạ vai trò sang VLAN đó.
3. Trên thiết bị mạng, bật MAB/MAC Authentication trên cổng hoặc SSID thử nghiệm. Đặt RADIUS Authentication về 192.168.10.10 cổng UDP 1812, Accounting cổng UDP 1813.
4. Cấu hình shared secret RADIUS theo cơ chế Connector. Trong luồng này, tài liệu nền tảng yêu cầu dùng giá trị local_secret của máy chủ cho cấu hình NAS; quản trị viên đọc bảo mật tại /usr/local/pf/conf/local_secret và nhập đúng ở hai phía. Đây không phải khóa ghép đường hầm của bước 6.
5. Nếu thiết bị hỗ trợ, cấu hình CoA/Disconnect và cho phép Connector truy cập cổng CoA tương ứng để áp dụng lại quyền. Kiểm tra cổng theo model thay vì mặc định mọi hãng đều dùng 3799.
6. Thiết lập chính sách chỉ cho MAC đã duyệt được phép truy cập. Không tự đăng ký mọi MAC vừa phát hiện. Ban đầu đặt MAC lạ bị từ chối, chưa mở quy trình khách hoặc cổng tự đăng ký.

**Kết quả cần đạt:** Switch/Wi-Fi gửi được yêu cầu RADIUS qua Connector và NAC20 nhìn thấy đúng MAC, đúng NAS và đúng cổng hoặc SSID thử nghiệm.

## 8. Đăng ký MAC thủ công hoặc hàng loạt qua API

Chỉ thêm thiết bị được phê duyệt vào danh sách cho phép.

Cách thủ công: mở Thiết bị, tạo bản ghi MAC, đặt trạng thái đã đăng ký, chọn vai trò và thời hạn truy cập phù hợp. Đối với danh sách lớn, dùng API nhập hàng loạt.

Ví dụ bên dưới chạy trực tiếp trên VPS bằng công cụ API cục bộ, cần quyền quản trị máy chủ. Thay MAC ví dụ và category_id bằng ID vai trò thật. category_id là ID vai trò, không phải số VLAN. Endpoint bulk_import thực hiện đăng ký thiết bị mới; đây là thao tác cấp quyền thực tế, không chỉ là xem trước.

**VPS — tạo danh sách MAC đã duyệt và nhập qua API cục bộ**

```bash
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

1. Đối chiếu category_id với vai trò đã tạo trên giao diện trước khi chạy; số 3 chỉ là ví dụ, không mặc định là Nhân viên.
2. ignoreUpdateIfExists bỏ qua MAC đã tồn tại. Muốn đổi quyền cho thiết bị cũ, duyệt danh sách thay đổi rồi dùng chức năng gán vai trò hoặc API bulk_apply_role.
3. Kiểm tra status và message của từng phần tử trả về; HTTP thành công không bảo đảm mọi MAC đã được nhập. Mở lại danh sách Thiết bị để xác nhận trạng thái và vai trò.
4. Nếu gọi API từ máy khác, đăng nhập POST /api/v1/login trên cổng quản trị đã cấu hình để lấy token; gửi Authorization: Bearer TOKEN cho các yêu cầu tiếp theo. Giữ token trong môi trường chạy, không ghi vào mã nguồn.

**Kết quả cần đạt:** Các MAC được duyệt có bản ghi đã đăng ký và vai trò chính xác; MAC khác vẫn không được tự động cấp quyền.

## 9. Kiểm thử, bàn giao và xử lý sự cố

Chỉ mở rộng triển khai sau khi thử đầy đủ trên cổng hoặc SSID riêng.

1. Thử một MAC trong danh sách: xác thực thành công, vào đúng VLAN/ACL và nhận IP từ DHCP của mạng tương ứng.
2. Thử một MAC chưa duyệt: yêu cầu bị từ chối theo chính sách. Không chỉ kiểm tra thông báo trên giao diện; kiểm tra thiết bị có thực sự bị chặn truy cập hay không.
3. Thay đổi hoặc thu hồi quyền một MAC thử nghiệm rồi yêu cầu đánh giá lại truy cập. Xác nhận CoA/Disconnect hoạt động; nếu chưa có CoA, thiết bị có thể giữ phiên cũ tới khi xác thực lại.
4. Ngắt đường Internet hoặc đường hầm trong môi trường thử nghiệm để xác định hành vi thực tế. Không giả định mọi kiểu xác thực, phiên mới, portal hoặc AD đều hoạt động offline.
5. Sao lưu cấu hình và dữ liệu theo cơ chế xuất/nhập của hệ thống; bảo quản khóa, chứng thư và bản sao lưu riêng. Thử khôi phục trước khi coi bản sao lưu là sử dụng được.
6. Ghi lại commit/bản gói đã cài, phiên bản firmware thiết bị, các vai trò, ánh xạ VLAN, IP Connector và chính sách cho MAC lạ. Theo dõi dung lượng đĩa, nhật ký RADIUS và thời hạn chứng thư.

**Kết quả cần đạt:** Đã kiểm chứng cả cho phép và từ chối, đổi quyền, mất kết nối và khôi phục. Chưa kiểm thử trên Linux thực tế thì không coi việc build giao diện là nghiệm thu toàn hệ thống.

## Kiểm tra khi gặp lỗi

| Hạng mục | Nội dung |
|---|---|
| Không mở được giao diện | Kiểm tra DNS, TCP 1443, firewall phía VPS, dịch vụ và ss -lnt. Xác minh đúng IP và chứng thư; không đổi sang bỏ kiểm tra TLS để che lỗi. |
| Connector chưa kết nối | Kiểm tra URL /api/v1/pfconnector/tunnel, Connector ID, khóa, giờ hệ thống, CA và quyền truy cập TCP 1443 từ LAN. |
| Không có yêu cầu RADIUS | Kiểm tra MAB đã bật trên cổng/SSID; IP Connector, UDP 1812, shared secret và đường mạng giữa NAS với Connector. |
| Có yêu cầu nhưng bị từ chối | Đối chiếu MAC thực tế, trạng thái đăng ký, thời hạn, vai trò, driver của NAS và chính sách xác thực trong nhật ký RADIUS. |
| Được cho phép nhưng không vào mạng | Kiểm tra VLAN/ACL trả về, VLAN trên uplink, DHCP, gateway và DNS tại công ty. RADIUS chấp nhận không thay thế cấu hình mạng dữ liệu. |
| Không thấy giao diện NAC20 hoặc tiếng Việt | Kiểm tra bộ gói có đúng commit NAC20, dist được đóng gói, vi_VN có trên OS, file vi.po/packetfence.mo đã được cài và tùy chọn ngôn ngữ người dùng. |
