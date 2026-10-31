


# CNLTHD API

CNLTHD là backend FastAPI dùng để quản lý dịch vụ và lịch hẹn của salon tóc.
Hệ thống hỗ trợ khách hàng đặt lịch, quản lý lịch làm việc của thợ cắt tóc và
quản trị người dùng, dịch vụ và lịch hẹn.

## Yêu cầu

- Docker Engine và Docker Compose v2 (`docker compose`)
- Python 3.13 nếu chạy API trực tiếp ngoài Docker
- k6 để kiểm thử tải (tùy chọn)

## Cấu hình

Tạo tệp biến môi trường cục bộ trước khi khởi động ứng dụng:

```bash
cp .env.example .env
```

Cập nhật `SECRET_KEY` và thông tin đăng nhập cơ sở dữ liệu trong `.env` khi
triển khai ngoài môi trường cục bộ. Không commit `.env` hoặc thông tin bí mật
của môi trường production vào hệ thống quản lý mã nguồn.

## Môi trường phát triển bằng Docker

Khởi động API, PostgreSQL và Redis:

```bash
docker compose -f compose.dev.yaml --env-file .env up --build
```

Mở terminal khác để tạo dữ liệu mẫu:

```bash
docker compose -f compose.dev.yaml --env-file .env exec api python -m app.seeder
```

API có thể truy cập tại `http://localhost:8000`. Tài liệu API tương tác có tại
`http://localhost:8000/docs`, còn OpenAPI schema có tại
`http://localhost:8000/openapi.json`. Kiểm tra trạng thái dịch vụ tại
`http://localhost:8000/health`.

Dừng các dịch vụ của môi trường phát triển:

```bash
docker compose -f compose.dev.yaml down
```

Chỉ sử dụng `docker compose down -v` khi muốn xóa volume PostgreSQL cục bộ.

## Môi trường phát triển bằng Python

Sử dụng cách này khi PostgreSQL và Redis đã chạy cục bộ hoặc đang chạy trong
Docker Compose:

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m script.migration
python -m app.seeder
uvicorn app.main:app --reload
```

## Kiểm thử và lint

Chạy bộ kiểm thử kèm báo cáo coverage:

```bash
python -m pytest --cov=./ tests/ --cov-report=html
```

Chạy công cụ lint đã được cấu hình:

```bash
ruff check .
```

Báo cáo coverage dạng HTML được tạo trong thư mục `htmlcov/`.

## Môi trường production

Tạo và kiểm tra `.env`, sau đó build và khởi động các dịch vụ production:

```bash
cp .env.example .env
docker compose -f compose.yaml --env-file .env up -d --build
```

Kiểm tra trạng thái và log của dịch vụ:

```bash
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs -f api
```

Chạy migration thủ công nếu cần:

```bash
docker compose -f compose.yaml --profile manual-only run --rm downgrade
```

Dừng các dịch vụ production mà không xóa volume cơ sở dữ liệu:

```bash
docker compose -f compose.yaml down
```

## Kiểm thử tải bằng k6

Chạy các kịch bản có sẵn trên API cục bộ:

```bash
k6 run k6/login-load.js
k6 run k6/read-load.js
```

Nếu chưa cài k6 cục bộ, có thể chạy k6 bằng Docker tại thư mục gốc của
repository:

```bash
docker run --rm -i --network host grafana/k6 run - < k6/login-load.js
docker run --rm -i --network host grafana/k6 run - < k6/read-load.js
```