# NAC20

**Nền tảng kiểm soát truy cập mạng của Công Ty TNHH TN20**
Tên miền: **20.com.vn**

NAC20 quản lý việc kết nối vào mạng có dây và không dây, xác thực người dùng, đăng ký thiết bị và xử lý các sự kiện bảo mật. Hệ thống hỗ trợ 802.1X, cổng đăng ký truy cập, phân quyền theo vai trò và cách ly thiết bị theo chính sách.

## Giao diện

- Tiếng Việt là ngôn ngữ mặc định của giao diện quản trị và cổng đăng ký truy cập.
- Trang tổng quan cung cấp tìm kiếm chức năng, truy cập nhanh và cấu hình hệ thống.
- Thương hiệu hiển thị là NAC20, với thông tin Công Ty TNHH TN20 và 20.com.vn.
- Các nút, biểu tượng và liên kết mở tài liệu trợ giúp đã được loại bỏ khỏi giao diện quản trị.

## Triển khai

Đây là hệ thống máy chủ Linux, không phải ứng dụng chỉ cần mở một trang HTML. Hãy xây dựng gói cài đặt bằng quy trình trong kho mã nguồn và kiểm tra trên môi trường thử nghiệm trước khi đưa vào vận hành.

Máy chủ phải có locale `vi_VN.UTF-8`. Trên Debian, bật `vi_VN.UTF-8 UTF-8` trong `/etc/locale.gen` rồi chạy `locale-gen`. Trên hệ thống dùng glibc có thể chạy `localedef -i vi_VN -f UTF-8 vi_VN.UTF-8`. Chạy `make translation` để biên dịch bộ dịch cổng đăng ký; bản dịch quản trị được đóng gói cùng giao diện.

Cấu hình mặc định dùng tên máy chủ `nac20`, tên miền `20.com.vn` và chuyển hướng sau đăng ký đến `https://20.com.vn/`. Quản trị viên phải cấu hình DNS và chứng thư TLS phù hợp với môi trường thực tế.

## Bản dịch

Bộ dịch tiếng Việt bao phủ ba danh mục thông báo của giao diện quản trị, API và cổng đăng ký. Các thuật ngữ chính được hiệu chỉnh thủ công; các mô tả kỹ thuật còn lại được dịch với sự hỗ trợ của mô hình dịch máy cục bộ Argos Translate. Cần rà soát câu chữ kỹ thuật trong quá trình nghiệm thu. Các biến chèn, thẻ HTML và khóa cấu hình được bảo toàn.

## Giấy phép và tương thích

Giấy phép GNU GPL và các thông báo bản quyền gốc được giữ nguyên trong `COPYING` và mã nguồn. Các tên gói, dịch vụ, thư mục, lớp và giao thức nội bộ tương thích với nền tảng gốc được giữ để không làm hỏng cài đặt hoặc nâng cấp. Đổi thương hiệu giao diện không thay đổi các quyền theo giấy phép.
