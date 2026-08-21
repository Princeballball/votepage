# 正式環境部署

## 1. 安裝套件

部署平台的 build command：

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
```

## 2. 啟動服務

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

也可以讓支援 `Procfile` 的平台直接讀取專案內的啟動設定。

## 3. 必填環境變數

依照 `.env.example` 在部署平台後台設定：

- `DJANGO_SECRET_KEY`：至少 50 字元的隨機密鑰，不可提交到 Git。
- `DJANGO_ALLOWED_HOSTS`：只填網域，不含 `https://`。
- `DJANGO_CSRF_TRUSTED_ORIGINS`：完整 HTTPS 網址。
- `DJANGO_DEBUG=false`

產生密鑰：

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 4. HTTPS

正式環境預設會：

- 將 HTTP 重新導向 HTTPS。
- 只透過 HTTPS 傳送 session 與 CSRF cookie。
- 啟用一年 HSTS。

請先確認部署平台已提供有效 HTTPS 憑證。若第一次部署尚未設定 TLS，可暫時設定：

```text
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SECURE_HSTS_SECONDS=0
```

HTTPS 正常後應立即恢復安全設定。

## 5. SQLite 資料保存

目前使用 SQLite。若部署平台的檔案系統會在重新部署後清空，必須掛載永久磁碟，並把 `SQLITE_PATH` 指向該磁碟，例如：

```text
SQLITE_PATH=/persistent-storage/db.sqlite3
```

正式開放前也應設定資料庫備份。多台應用伺服器或流量增加後，建議改用 PostgreSQL。
