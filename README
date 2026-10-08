# CNLTHD

CNLTHD là backend API cho hệ thống quản lý và đặt lịch dịch vụ tại tiệm tóc. Dự án giúp khách hàng tra cứu dịch vụ, chọn thợ và đặt lịch hẹn; đồng thời hỗ trợ thợ cắt tóc quản lý lịch làm việc và quản trị viên quản lý người dùng, dịch vụ, lịch hẹn.

Ứng dụng được xây dựng bằng FastAPI và SQLAlchemy 2 với cơ chế truy cập cơ sở dữ liệu bất đồng bộ, sử dụng PostgreSQL và hỗ trợ SQLite khi phát triển local. Repository hiện chứa backend và bộ kiểm thử API.

## Chức năng chính

- **Tài khoản và xác thực:** đăng ký, xác nhận đăng ký qua email, đăng nhập bằng JWT, làm mới token, đăng xuất, đăng xuất tất cả thiết bị và xem các phiên đăng nhập đang hoạt động.
- **Hồ sơ cá nhân:** xem và cập nhật thông tin, đổi mật khẩu, yêu cầu đặt lại mật khẩu qua email.
- **Danh mục dịch vụ:** tra cứu và lọc dịch vụ theo các tiêu chí; quản trị viên có thể tạo, cập nhật giá, thời lượng và trạng thái hoạt động của dịch vụ.
- **Thợ cắt tóc:** xem danh sách, thông tin thợ và quản lý lịch làm việc theo ngày trong tuần.
- **Đặt lịch:** chọn thợ, ngày giờ và nhiều dịch vụ trong một lịch hẹn; tính tổng tiền, thời gian kết thúc và lưu giá dịch vụ tại thời điểm đặt.
- **Quản lý lịch hẹn:** xem danh sách, chi tiết, lọc lịch hẹn, đổi lịch, hủy lịch và cập nhật trạng thái theo quyền truy cập. Các trạng thái gồm `pending`, `confirmed`, `completed`, `cancelled`.
- **Quản trị người dùng:** xem danh sách có phân trang và bộ lọc, tạo tài khoản và cập nhật thông tin, vai trò.

## Vai trò trong hệ thống

| Vai trò | Chức năng tiêu biểu |
| --- | --- |
| Khách hàng (`customer`) | Đặt lịch, xem và quản lý lịch hẹn của mình, cập nhật hồ sơ cá nhân. |
| Thợ cắt tóc (`barber`) | Xem lịch hẹn được phân công, cập nhật trạng thái lịch hẹn và quản lý lịch làm việc của mình. |
| Quản trị viên (`admin`) | Quản lý người dùng, dịch vụ, lịch làm việc của thợ và lịch hẹn trong hệ thống. |

## Công nghệ sử dụng

| Thành phần | Công nghệ |
| --- | --- |
| API | Python, FastAPI, Uvicorn |
| Cơ sở dữ liệu | SQLAlchemy 2 Async, PostgreSQL / SQLite |
| Kiểm tra dữ liệu và cấu hình | Pydantic, pydantic-settings |
| Xác thực | PyJWT, pwdlib với Argon2 |
| Lưu trữ tạm cho luồng xác thực | Redis, fastapi-redis-sdk |
| Email | Bird SDK và các mẫu email HTML |
| Kiểm thử | pytest, HTTPX, fakeredis, pytest-cov |
| Kiểm tra mã nguồn và CI | Ruff, GitHub Actions |
| Đóng gói | Docker, Docker Compose |

## Cấu trúc thư mục

```text
app/
├── main.py          # Khởi tạo ứng dụng, router và xử lý lỗi
├── dependencies.py  # Dependency cho xác thực, phân quyền và email
├── core/            # Cấu hình, model ORM, kết nối DB, bảo mật, email
├── routers/         # API xác thực và tra cứu dịch vụ, thợ cắt tóc
├── internal/        # API người dùng, quản trị, đặt lịch và lịch làm việc
├── schemas/         # Schema dữ liệu đầu vào và đầu ra
├── services/        # Xử lý nghiệp vụ và truy vấn dữ liệu
└── seeder.py        # Tạo dữ liệu mẫu
email_templates/     # Mẫu email xác nhận và đặt lại mật khẩu
tests/               # Bộ kiểm thử API
compose.yaml         # Cấu hình API và PostgreSQL
compose.dev.yaml     # Cấu hình phát triển có PostgreSQL và Redis
```

## Chạy trên máy local

Sử dụng Python 3.13 để đồng bộ với Dockerfile và CI. Chạy các lệnh từ thư mục gốc của dự án.

### 1. Cài đặt môi trường

```bash
python3.13 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Trên Windows PowerShell, kích hoạt môi trường bằng `venv\Scripts\Activate.ps1`. Nếu đã có `.env`, giữ lại cấu hình hiện tại và bổ sung những biến còn thiếu.

### 2. Cấu hình ứng dụng

Ứng dụng đọc cấu hình từ biến môi trường và file `.env`.

| Biến | Ý nghĩa |
| --- | --- |
| `APP_NAME` | Tên hiển thị trên tài liệu API. |
| `DATABASE_URL` | URL cơ sở dữ liệu; mẫu local là `sqlite:///./app.db`. |
| `SECRET_KEY` | Khóa ký JWT; tạo bằng `openssl rand -hex 32` và thay giá trị mẫu. |
| `ALGORITHM` | Thuật toán ký JWT, mặc định `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Thời hạn access token; `.env.example` đặt là 30 phút. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Thời hạn refresh token, mặc định 7 ngày. |
| `REDIS_URL` | URL Redis, ví dụ `redis://localhost:6379/0`. |
| `BIRD_API_KEY` | Khóa API phục vụ gửi email xác nhận và đặt lại mật khẩu. |
| `BASE_URL` | URL gốc dùng tạo liên kết trong email, mặc định `http://localhost:8000`. |

Để dùng PostgreSQL local, đặt `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/app`.

Các luồng gửi email cần `BIRD_API_KEY` hợp lệ và địa chỉ người gửi phù hợp trong `app/core/email.py`. Giá trị khóa mẫu không gửi được email thực tế.

### 3. Khởi động Redis và API

Nếu dùng Docker Compose, có thể khởi động riêng Redis:

```bash
docker compose -f compose.dev.yaml up -d redis
```

Nếu chọn PostgreSQL, khởi động cả hai dịch vụ bằng `docker compose -f compose.dev.yaml up -d db redis`.

Sau đó chạy API trong môi trường Python đã kích hoạt:

```bash
uvicorn app.main:app --reload
```

Ứng dụng tự tạo các bảng chưa tồn tại khi khởi động.

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Kiểm tra trạng thái: http://localhost:8000/health

### 4. Tạo dữ liệu mẫu (tùy chọn)

**Lệnh dưới đây xóa và tạo lại các bảng của ứng dụng trong cơ sở dữ liệu đang cấu hình trước khi thêm dữ liệu mẫu. Chỉ chạy trên cơ sở dữ liệu dành cho phát triển.**

```bash
python -m app.seeder
```

Dữ liệu mẫu gồm tài khoản cho ba vai trò, dịch vụ, lịch làm việc và một lịch hẹn. Thông tin tài khoản mẫu được khai báo trong `app/seeder.py`.

## Các nhóm API

| Đường dẫn | Mục đích |
| --- | --- |
| `/auth` | Đăng ký, xác nhận, đăng nhập, token, phiên đăng nhập và khôi phục mật khẩu. |
| `/users` | Hồ sơ và mật khẩu của người dùng hiện tại. |
| `/services` | Tra cứu dịch vụ công khai. |
| `/barbers` | Tra cứu thợ cắt tóc. |
| `/bookings` | Đặt lịch và quản lý lịch hẹn theo vai trò. |
| `/barber_schedules` | Quản lý lịch làm việc của thợ. |
| `/admin/users` | Quản trị người dùng. |
| `/admin/services` | Quản trị dịch vụ. |
| `/health` | Kiểm tra ứng dụng đang phản hồi. |

Xem phương thức HTTP, tham số và schema chi tiết tại Swagger UI. Các API yêu cầu đăng nhập sử dụng header `Authorization: Bearer <access_token>`.

## Kiểm thử và kiểm tra mã nguồn

```bash
python -m pip install -r requirements-test.txt -r requirements-lint.txt
python -m pytest tests -v
python -m ruff check app tests
```

Để tạo báo cáo độ bao phủ:

```bash
python -m pytest tests --cov=app --cov-report=term-missing --cov-report=html
```

Báo cáo HTML được tạo tại `htmlcov/index.html`. Bộ kiểm thử dùng SQLite trong bộ nhớ, Redis giả lập và email mock để kiểm tra API mà không cần gửi email thật.

GitHub Actions chạy lint, kiểm thử và build Docker image khi có push hoặc pull request.

## Ghi chú về Docker

Repository có Dockerfile và hai file Compose. `compose.dev.yaml` bổ sung Redis và chế độ tự tải lại mã nguồn; `compose.yaml` chỉ khai báo API và PostgreSQL.

Hiện Dockerfile chỉ sao chép thư mục `app/`, chưa bao gồm `email_templates/`; cấu hình Compose cũng chưa truyền các biến như `SECRET_KEY`, `BIRD_API_KEY` và `BASE_URL` vào container API. Cần bổ sung mẫu email và các biến cấu hình này khi chạy đầy đủ các luồng xác thực qua Docker.
