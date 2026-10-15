# Bộ cài NAC20 — Debian 12 amd64

Công Ty TNHH TN20 · 20.com.vn

Đây là **bộ cài online, bản preview**: chứa gói `.deb` máy chủ và Connector được dựng từ commit ghi trong `BUILDINFO.json`. Cần Internet để APT cài phụ thuộc và Docker tải ảnh dịch vụ. Đây chưa phải ISO offline hay bản đã nghiệm thu toàn bộ chức năng trên thiết bị mạng.

## Cài máy chủ trên VPS riêng

Yêu cầu Debian 12 x86_64, 4 vCPU, RAM 16 GB, ổ đĩa 200 GB và systemd. Dùng hệ điều hành mới; sao lưu/snapshot trước khi cài. Không dùng chung máy với dịch vụ web hoặc cơ sở dữ liệu đang vận hành.

```bash
tar -xzf nac20-debian12-amd64-online.tar.gz
cd nac20-debian12-amd64-online
bash install.sh server --check
sudo bash install.sh server --install
```

Mở `https://TEN-MIEN-HOAC-IP-VPS:1443`, hoàn tất cấu hình mạng, cơ sở dữ liệu và tài khoản quản trị. Cấu hình DNS/TLS cho tên miền thật; ví dụ `nac20.20.com.vn` chỉ dùng khi DNS và chứng thư tương ứng đã được chuẩn bị. Không có tài khoản/mật khẩu quản trị dùng chung trong bộ cài.

## Cài Connector trong mạng nội bộ

Dùng **máy Debian 12 khác** trong mạng công ty, tối thiểu 1 vCPU, RAM 2 GB và ổ đĩa 10 GB. Không cài Connector từ xa trên cùng máy chủ NAC20.

```bash
tar -xzf nac20-debian12-amd64-online.tar.gz
cd nac20-debian12-amd64-online
bash install.sh connector --check
sudo bash install.sh connector --install
sudo /usr/local/pfconnector-remote/bin/pfconnector-configure
sudo systemctl restart packetfence-pfconnector-remote-combined
```

Ghép Connector ID và khóa với máy chủ, dùng URL `https://TEN-MIEN-VPS:1443/api/v1/pfconnector/tunnel`, bật xác minh TLS. Xem hướng dẫn tiếng Việt tại `docs/NAC20_CAI_DAT.md`. Nhóm `connector-ad` chứa gói NTLM/AD tùy chọn, không cài mặc định cho xác thực MAC.

## Kiểm tra và giới hạn bản phát hành

- Kiểm tra SHA-256 của tệp tải về theo bản phát hành GitHub và `SHA256SUMS`; bộ cài tự đối chiếu các tệp bên trong trước khi cài.
- `BUILDINFO.json` ghi commit, phiên bản, môi trường dựng và tổng kiểm từng gói. Các tên package/dịch vụ nội bộ được giữ để tương thích.
- Bộ cài đóng gói giao diện NAC20 đã biên dịch, bản dịch tiếng Việt và các chương trình Go/C; cấu hình gắn giao diện từ máy chủ vào container để không trở lại giao diện gốc.
- Phụ thuộc hệ điều hành, Docker và các ảnh dịch vụ nền tảng vẫn được tải online. Ảnh dịch vụ dùng nhãn `latest`; đây chưa phải bộ runtime bất biến được đóng gói offline.
- Chưa xác nhận cài mới/khôi phục đầy đủ với systemd trên VPS hoặc xác thực MAB với switch/Wi-Fi thật. Kiểm thử môi trường riêng trước khi đưa vào vận hành.
- Không tự tắt firewall, bỏ kiểm tra TLS hoặc đổi cấu hình AppArmor bằng script này. Đối chiếu yêu cầu tương thích của nền tảng và giữ console khôi phục khi chuẩn bị máy chủ.
- Script dành cho cài mới và sẽ dừng nếu phát hiện NAC20/Connector đã cài; không dùng thay quy trình nâng cấp và sao lưu.
