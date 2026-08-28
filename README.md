# Dolap Kasası

Aile kıyafetlerini fotoğraflı katalogda yöneten, güçlü filtreleme ve fiziksel saklama birimi takibi sunan Türkçe, self-hosted Django uygulaması. Ürünün konumu yalnızca bağlı saklama biriminden türetilir; birimi taşımak tüm ürünlerin görünen konumunu anında değiştirir.

## Özellikler

- Ortak aile envanteri, Django kullanıcı girişi ve ayrı kişi kayıtları
- Hiyerarşik kategoriler, dinamik etiketler, yedi ürün durumu ve güvenli arşivleme
- Çoklu fotoğraf; EXIF yönü düzeltme, 1600 px WebP ve 400 px cover thumbnail
- 24 kayıtlık sayfalı, lazy-loading mağaza kataloğu; birleşebilir query-string filtreleri
- Kişi, kategori, iki renk, marka, ölçüler, kumaş, desen, fit, mevsim, durum, etiket, saklama birimi/türü ve metin araması
- Günlük kullanım için CRUD ekranları ve gelişmiş Django admin

## Gereksinimler ve kurulum

Docker Engine ve Docker Compose v2 gerekir.

```bash
cp .env.example .env                 # parolaları ve secret key'i değiştirin
docker compose up -d --build         # entrypoint migrate ve collectstatic çalıştırır
docker compose exec web python manage.py createsuperuser
```

Uygulama `http://localhost:8000`, admin `/admin/`, healthcheck `/health/` adresindedir. İlk veriler için:

```bash
docker compose exec web python manage.py seed_demo
```

Yerel geliştirme (PostgreSQL değişkenleri yoksa SQLite kullanılır):

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Test ve kalite

```bash
pytest
ruff check .
python manage.py makemigrations --check
python manage.py check --deploy
```

## İşletim ve güncelleme

```bash
docker compose logs -f web
docker compose exec web python manage.py migrate
docker compose pull && docker compose up -d --build
docker compose exec web python manage.py collectstatic --noinput
```

`media_data` işlenmiş WebP görselleri, `postgres_data` veritabanını kalıcı tutar. Büyük kaynak yükleme başarıyla işlenince tutulmaz.

## Yedekleme ve geri yükleme

Tam, tarih damgalı PostgreSQL + media + `.env` yedeği:

```bash
./scripts/backup.sh
./scripts/backup.sh backups/manuel
./scripts/restore.sh backups/20260801-120000
```

Tekil işlemler:

```bash
# PostgreSQL dump/restore
docker compose exec -T db pg_dump -U closet -d closet_vault -Fc > database.dump
docker compose exec -T db pg_restore -U closet -d closet_vault --clean --if-exists < database.dump
# Media arşivi (volume adını `docker volume ls` ile doğrulayın)
docker run --rm -v closet-vault_media_data:/data -v "$PWD":/backup alpine tar czf /backup/media.tar.gz -C /data .
```

Restore mevcut veritabanı ve mediayı **siler**; önce ayrıca yedek alın ve bakım penceresinde çalıştırın. `.env` dosyası hassastır, yedekleri şifreli ortamda saklayın.

## Varsayımlar ve sınırlamalar

- Giriş yapan herkes ortak envanteri düzenleyebilir; rol bazlı yetki ilk sürüm kapsamında değildir.
- Ürün adı teknik olarak gereklidir; hızlı tanıma ve erişilebilir fotoğraf alt metni için kullanıcı tarafından girilir.
- Dosyalar yerel Docker volume'da saklanır; S3/nesne depolama yoktur.
- Bootstrap ve HTMX CDN'den gelir; tamamen çevrimdışı kurulumda bunları statik olarak vendörlemek gerekir.
- Filtre değerleri tam eşleşir, serbest metin `icontains` kullanır. Çok büyük kataloglarda PostgreSQL trigram arama sonraki sürümde eklenebilir.
- Fotoğraf sırası veri modelinde ve admin'de düzenlenebilir; sürükle-bırak arayüzü yoktur.

## Sonraki sürüm önerileri

Nesne depolama, PostgreSQL trigram arama, çevrimdışı/PWA desteği, audit log, rol bazlı salt-okuma kullanıcıları ve sürükle-bırak fotoğraf sıralama. QR, yapay zekâ, laundry veya kombin özellikleri bilerek eklenmemiştir.

## Portable Backup (uygulama yedeği)

Portable Backup, PostgreSQL şemasına bağlı olmayan, sürümlenmiş bir Closet Vault veri aktarım formatıdır. Yetkili (`is_staff`) kullanıcı **Ayarlar → Yedekleme** ekranından **Tam Yedek Oluştur ve İndir** düğmesiyle tek bir ZIP indirebilir. ZIP içinde:

- `manifest.json`: format/uygulama sürümü, oluşturulma zamanı ve kayıt sayıları,
- `data.json`: kişiler, kategori hiyerarşisi, saklama birimleri, etiketler, ürünler, durumlar ve ilişkiler,
- `media/`: checksum ile doğrulanan ürün fotoğrafları

bulunur. `.env`, secret key, kullanıcı parolaları, session/cache tabloları ve database parolası portable ZIP'e dahil edilmez.

### Teknik PostgreSQL yedeğinden farkı

Yukarıdaki `scripts/backup.sh` yedeği PostgreSQL dump, media volume ve `.env` içerir; aynı kurulumun hızlı ve eksiksiz felaket kurtarması içindir. Portable ZIP ise mantıksal domain verilerini şemadan bağımsız referanslarla taşır ve özellikle **yeni/temiz Closet Vault kurulumuna aktarım** içindir. İki yöntem birbirinin yerine geçmez; düzenli olarak ikisini de alın.

### Temiz kuruluma restore

1. Hedef sürümü kurup migration'ları çalıştırın ve bir yönetici oluşturun; `seed_demo` çalıştırmayın.
2. Yönetici hesabıyla giriş yapıp **Ayarlar → Yedekleme** ekranını açın.
3. ZIP'i seçip **Yedeği Doğrula ve Önizle** düğmesine basın.
4. Manifest özetini ve uyarıyı kontrol edin, açık onay kutusunu işaretleyin.
5. **Yedekten Geri Yükle** düğmesine basın ve sonuç özetini kontrol edin.

Portable restore mevcut domain verilerinin üzerine sessizce yazmaz; kişi, kategori, saklama birimi, etiket, ürün veya fotoğraf varsa işlemi reddeder. Geçersiz ZIP, eksik/değiştirilmiş media, güvenli olmayan ZIP yolu, aşırı boyut/sıkıştırma oranı ve desteklenmeyen format sürümü veriye dokunulmadan reddedilir. Restore veritabanı transaction'ı içinde yapılır.

Her portable yedekte zorunlu `backup_format_version` bulunur. İlk format `1`'dir ve importer sürüm tabanlı adapter tablosu kullanır; gelecekte `import_v2(...)` gibi dönüştürücüler eklenebilir. Eski bir yedeği içe aktarmadan önce hedef Closet Vault sürümünün ilgili formatı desteklediğini doğrulayın.

Portable ZIP kişisel envanter, notlar ve fotoğraflar içerdiği için hassastır. Dosyayı şifreli ve erişimi kısıtlı bir konumda saklayın, birden fazla kopya tutun ve yedekleri periyodik olarak temiz bir test kurulumunda doğrulayın.
