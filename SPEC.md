# Codex Proje Talimatı — Kıyafet Envanter ve Saklama Sistemi

## Rolün

Kıdemli bir full-stack geliştirici ve yazılım mimarı gibi çalış. Aşağıdaki gereksinimlere göre çalışan, Docker ile kurulabilen, self-hosted bir web uygulaması geliştir.

Projeyi yalnızca iskelet olarak bırakma. Çalışan kod, veritabanı migration'ları, testler, Docker kurulumu, örnek veriler ve README hazırla.

## Projenin amacı

Aile üyelerinin kıyafet, ayakkabı ve aksesuarlarını fotoğraflı bir katalog içinde yönetmesini sağlamak.

Uygulamanın temel değeri:

- Ürünleri mağaza kataloğu gibi görüntülemek
- Güçlü filtrelerle aranan ürünü bulmak
- Bir ürünün hangi vakum poşetinde, valizde veya saklama biriminde olduğunu görmek
- Saklama biriminin fiziksel konumunu yönetmek
- Bir saklama birimi taşındığında içindeki ürünlerin konumunu otomatik olarak yeni konumdan göstermek

Bu bir kombin, çamaşır takibi veya yapay zekâ uygulaması değildir. İlk sürümde ana odak envanter, fotoğraf, filtreleme ve saklama birimi yönetimidir.

---

# 1. Teknoloji seçimi

Aşağıdaki teknolojileri kullan:

- Backend: Python 3.12+
- Framework: Django 5+
- Arayüz: Django Templates + HTMX
- CSS: Bootstrap 5 veya sade, mobil uyumlu bir CSS yaklaşımı
- Veritabanı: PostgreSQL
- Fotoğraf işleme: Pillow
- Dağıtım: Docker Compose
- Web sunucusu: Gunicorn
- Statik dosyalar: WhiteNoise
- Test: pytest + pytest-django
- Kod kalitesi: Ruff
- Ortam değişkenleri: `.env`

Ayrı bir React/Vue frontend oluşturma. Uygulama sade, hızlı ve ev sunucusunda düşük kaynakla çalışabilir olmalı.

---

# 2. Kullanıcı yapısı

Uygulama aile içinde kullanılacak.

İlk sürümde:

- Django kullanıcı girişi olsun.
- Tüm giriş yapmış kullanıcılar aynı aile envanterini görebilsin.
- Karmaşık yetkilendirme gerekmiyor.
- Admin kullanıcı yeni kullanıcı oluşturabilsin.
- Ürünlerde ürünün kime ait olduğunu belirten ayrı bir `Person` alanı olsun.

Örnek kişiler:

- Ben
- Eşim
- Çocuk
- Ortak

`Person`, Django giriş kullanıcısıyla aynı olmak zorunda değildir.

---

# 3. Temel domain modeli

## 3.1 Person

Alanlar:

- `id`
- `name`
- `is_active`
- `created_at`
- `updated_at`

## 3.2 Category

Hiyerarşik kategori desteği olsun.

Alanlar:

- `id`
- `name`
- `parent`
- `is_active`
- `sort_order`

Örnek:

- Üst Giyim
  - Tişört
  - Gömlek
  - Kazak
  - Sweatshirt
- Alt Giyim
  - Pantolon
  - Jean
  - Şort
- Dış Giyim
  - Mont
  - Ceket
  - Kaban
- Ayakkabı
- Aksesuar
  - Çanta
  - Saat
  - Gözlük
  - Kemer
  - Takı

Çorap, boxer ve atlet ilk sürümde kapsam dışı olabilir.

## 3.3 StorageUnit

Bu kavram Türkçe arayüzde **Saklama Birimi** olarak gösterilsin.

Saklama birimi örnekleri:

- Vakum poşeti
- Valiz
- Raf
- Çekmece
- Askılık bölümü
- Diğer

Kutu özel ve zorunlu bir kavram değildir.

Alanlar:

- `id`
- `name`
- `unit_type`
- `location_text`
- `description`
- `is_active`
- `created_at`
- `updated_at`

Örnek:

- Ad: Vakum Poşeti 3
- Tür: Vakum poşeti
- Konum: Yatak odası dolabı, ikinci raf
- Açıklama: Kışlık kadın üst giyim

QR kod ilk sürümde yapılmayacak. Model gelecekte eklenebilir olacak şekilde tasarlanabilir ancak mevcut kullanıcı arayüzünde QR özelliği bulunmasın.

## 3.4 Item

Her fiziksel kıyafet, ayakkabı veya aksesuar bir `Item` kaydıdır.

Alanlar:

- `id`
- `name`
- `person`
- `category`
- `storage_unit`
- `brand`
- `model`
- `primary_color`
- `secondary_color`
- `size`
- `waist_size`
- `inseam_size`
- `shoe_size`
- `material`
- `pattern`
- `fit`
- `season`
- `status`
- `notes`
- `created_at`
- `updated_at`
- `archived_at`

Önemli mimari kural:

- Üründe ayrı `location`, `wardrobe` veya `shelf` alanı tutulmayacak.
- Ürün yalnızca bir `StorageUnit` seçer.
- Ürünün fiziksel konumu, bağlı olduğu saklama biriminin `location_text` alanından türetilir.
- Bir ürün aynı anda en fazla bir aktif saklama birimine bağlıdır.
- Bir saklama biriminde birden fazla ürün bulunabilir.

İlişki:

`StorageUnit 1 -> N Item`

Örnek:

- Siyah mont -> Vakum Poşeti 3
- Vakum Poşeti 3 -> Yatak odası dolabı, ikinci raf

Ürün detayında şu şekilde göster:

- Saklama birimi: Vakum Poşeti 3
- Fiziksel konum: Yatak odası dolabı, ikinci raf

## 3.5 Item status

Aşağıdaki durumları destekle:

- `ACTIVE` — Envanterde
- `TO_SELL` — Satılacak
- `TO_DONATE` — Bağışlanacak
- `SOLD` — Satıldı
- `DONATED` — Bağışlandı
- `ARCHIVED` — Arşivlendi
- `LOST` — Kayıp

Varsayılan durum `ACTIVE` olsun.

Silme ile arşivleme ayrı işlemler olsun:

- Arşivlenen ürün normal katalogda görünmesin.
- Kalıcı silme yalnızca açık onay ile yapılsın.
- Normal kullanıcı akışında arşivleme tercih edilsin.

Laundry status bulunmayacak.

## 3.6 Tag

Dinamik etiket sistemi oluştur.

Alanlar:

- `id`
- `name`
- `slug`
- `created_at`

Item ile many-to-many ilişki kur.

Örnek etiketler:

- Favori
- İş kıyafeti
- Düğün
- Türkiye seyahati
- Kış tatili
- Zayıflayınca denenecek
- Pahalı
- Nadiren kullanılan

Kullanıcı arayüzünden yeni etiket oluşturulabilsin.

## 3.7 Photo

Bir üründe birden fazla fotoğraf bulunabilsin.

Alanlar:

- `id`
- `item`
- `image`
- `thumbnail`
- `is_cover`
- `sort_order`
- `created_at`

Kurallar:

- İlk eklenen fotoğraf otomatik olarak ana fotoğraf (`is_cover=True`) olsun.
- Bir üründe yalnızca bir ana fotoğraf bulunabilsin.
- Kullanıcı daha sonra başka bir fotoğrafı ana fotoğraf yapabilsin.
- Ana fotoğraf değiştirildiğinde yeni ana fotoğraf için thumbnail bulunmasını garanti et.
- Ana olmayan fotoğraflar için thumbnail zorunlu değildir.
- Fotoğraf sıralaması desteklensin.

---

# 4. Fotoğraf işleme

Kullanıcı fotoğrafları telefon tarayıcısından çekecek veya galeriden seçecek.

Native mobil uygulama yapılmayacak. Mobil uyumlu web uygulaması yeterlidir.

Fotoğraf yüklenirken sunucu otomatik olarak:

1. EXIF orientation bilgisini uygulasın.
2. Fotoğrafı doğru yönde fiziksel olarak döndürsün.
3. Ana/ek fotoğrafın uzun kenarını en fazla 1600 piksele düşürsün.
4. En-boy oranını korusun.
5. WebP formatında yaklaşık %80 kaliteyle kaydetsin.
6. Ana fotoğraf için uzun kenarı yaklaşık 400 piksel olan thumbnail oluştursun.
7. Yüklenen büyük orijinal dosyayı başarılı işleme sonrasında saklamasın.
8. Hata olursa yarım dosya ve bozuk veritabanı kaydı bırakmasın.

Fotoğraf kareye zorla kırpılmamalı. Katalog kartında CSS `object-fit: cover` kullanılabilir.

Ana katalog yalnızca thumbnail yüklemeli.

Ürün detay sayfası optimize edilmiş 1600 px sürümü kullanmalı.

Fotoğraflarda HTML native lazy loading kullan:

```html
<img loading="lazy">
```

Katalogda tüm kayıtları ve görselleri bir anda yükleme.

---

# 5. Ürün ekleme akışı

Ürünler tek tek eklenecek. Toplu import gerekmiyor.

Hızlı ürün ekleme formunda şu alanlar doğrudan görünsün:

Zorunlu:

- En az bir fotoğraf
- Kişi
- Kategori
- Ana renk
- Saklama birimi

Opsiyonel ama hızlı formda görünür:

- Marka
- Beden

Ayrıntılı alanlar açılır/kapanır bir bölümde olsun:

- Model
- İkincil renk
- Bel ölçüsü
- Paça uzunluğu
- Ayakkabı numarası
- Kumaş
- Desen
- Fit
- Mevsim
- Durum
- Etiketler
- Notlar
- Ek fotoğraflar

Butonlar:

- Kaydet
- Kaydet ve sonraki ürünü ekle

`Kaydet ve sonraki ürünü ekle` seçildiğinde:

- Son seçilen kişi korunmalı
- Son seçilen saklama birimi korunmalı
- İstenirse son kategori de korunabilir
- Yeni ürün formu temizlenerek açılmalı
- Önceki ürünün fotoğraf ve özel alanları taşınmamalı

---

# 6. Saklama birimi akışları

## 6.1 Saklama birimi oluşturma

Kullanıcı şunları girebilsin:

- Ad
- Tür
- Fiziksel konum
- Açıklama

## 6.2 Bir poşetin içindekileri görmek

Saklama birimi detay sayfasında:

- Saklama biriminin adı
- Türü
- Fiziksel konumu
- Açıklaması
- İçindeki ürün sayısı
- İçindeki ürünlerin fotoğraflı katalog görünümü

bulunsun.

## 6.3 Ürünü başka poşete koymak

Ürün detay veya düzenleme sayfasında yalnızca saklama birimi değiştirilsin.

Örnek:

- Eski: Vakum Poşeti 3
- Yeni: Vakum Poşeti 7

Kullanıcı ayrıca lokasyon seçmesin.

Ürünün yeni fiziksel konumu otomatik olarak Vakum Poşeti 7'nin konumundan gösterilsin.

## 6.4 Saklama birimini taşımak

Örnek:

- Vakum Poşeti 3
- Eski konum: Yatak odası dolabı, ikinci raf
- Yeni konum: Balkon dolabı, üst raf

Sadece `StorageUnit.location_text` değişsin.

İçindeki Item kayıtlarında toplu location güncellemesi yapılmasın; çünkü ürünlerde location tutulmuyor.

Bu nedenle tüm ürünler otomatik olarak yeni konumda görünmelidir.

Location history gerekli değildir.

---

# 7. Ana katalog

Ana sayfa mağaza ürün listeleme ekranına benzesin.

Her kartta:

- Ana fotoğraf thumbnail'i
- Ürün adı
- Kişi
- Kategori
- Ana renk
- Marka
- Beden
- Saklama birimi adı

gösterilebilir.

Karttan ürün detayına geçilebilsin.

Mobil görünüm öncelikli tasarla.

Katalog özellikleri:

- Lazy-loaded thumbnails
- Sayfalama veya “daha fazla yükle”
- İlk yüklemede örneğin 24 ürün
- Arşivlenen ve aktif olmayan ürünleri varsayılan olarak gizle
- Filtreler temizlenebilsin
- Aktif filtreler kullanıcıya gösterilsin
- Filtre sonucu sayısı gösterilsin
- Filtreler query string içinde tutulabilsin
- Sayfa yenilendiğinde filtreler kaybolmasın

---

# 8. Filtreleme ve arama

Bu projenin en önemli özelliği güçlü filtreleme sistemidir.

Aşağıdaki filtreleri destekle:

- Kişi
- Kategori
- Alt kategori
- Ana renk
- İkincil renk
- Marka
- Beden
- Bel ölçüsü
- Paça uzunluğu
- Ayakkabı numarası
- Kumaş
- Desen
- Fit
- Mevsim
- Durum
- Etiket
- Saklama birimi
- Saklama birimi türü
- Serbest metin araması

Serbest metin araması şu alanlarda çalışsın:

- Ürün adı
- Marka
- Model
- Notlar
- Saklama birimi adı
- Saklama birimi fiziksel konumu

Birden fazla filtre birlikte çalışabilsin.

Örnek:

- Kişi: Eşim
- Kategori: Mont
- Renk: Siyah
- Saklama birimi: Vakum Poşeti 3

Filtre sorguları PostgreSQL üzerinde verimli çalışmalı.

Gerekli indeksleri ekle.

N+1 sorgularını önlemek için `select_related` ve `prefetch_related` kullan.

---

# 9. Ürün detay ekranı

Gösterilecek bilgiler:

- Tüm fotoğraflar
- Ana fotoğraf
- Ürün adı
- Kişi
- Kategori
- Marka
- Model
- Ana ve ikincil renk
- Beden bilgileri
- Kumaş
- Desen
- Fit
- Mevsim
- Durum
- Etiketler
- Notlar
- Saklama birimi
- Saklama biriminin fiziksel konumu
- Oluşturulma ve güncellenme tarihleri

İşlemler:

- Düzenle
- Ana fotoğrafı değiştir
- Fotoğraf ekle/sil
- Saklama birimini değiştir
- Arşivle
- Durum değiştir
- Kalıcı sil

---

# 10. Yönetim ekranları

Aşağıdakiler için CRUD ekranları oluştur:

- Kişiler
- Kategoriler
- Saklama birimleri
- Etiketler

Django admin de kullanılabilir durumda olsun ancak günlük kullanım için normal web ekranları oluştur.

---

# 11. İlk sürümde yapılmayacaklar

Aşağıdakileri uygulama:

- Yapay zekâ
- Kombin önerileri
- Hava durumu entegrasyonu
- Kullanım sayısı
- Bugün ne giydim takibi
- Laundry status
- Location history
- QR kod
- Native mobil uygulama
- Toplu ürün importu
- Barkod sistemi
- Body profile otomasyonu
- Çorap, boxer ve atlet stok yönetimi

Kod yapısını gelecekte genişlemeye engel olmayacak şekilde kur ancak şu anda bu özellikleri ekleyip kapsamı büyütme.

---

# 12. Docker ve kurulum

Aşağıdaki dosyaları hazırla:

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- PostgreSQL servisi
- Uygulama servisi
- Persistent media volume
- Persistent PostgreSQL volume
- Migration çalıştırma mekanizması
- Static collection
- Healthcheck
- Başlangıç yönetici hesabı oluşturma talimatı

Komutlar mümkün olduğunca sade olsun:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

README içinde:

- Gereksinimler
- Kurulum
- Güncelleme
- Yedekleme
- Geri yükleme
- Log görüntüleme
- Migration
- Admin oluşturma
- Media klasörü
- PostgreSQL yedeği

anlatılsın.

---

# 13. Yedekleme

README'de aşağıdakiler için çalışan komutlar ver:

- PostgreSQL dump
- PostgreSQL restore
- Media dosyalarının yedeği
- Tam uygulama yedeği

Mümkünse `scripts/backup.sh` ve `scripts/restore.sh` ekle.

Script'ler:

- `.env` değerlerini kullansın
- Hata durumunda durmalı
- Tarih damgalı yedek oluştursun
- PostgreSQL ve media dosyalarını kapsasın

---

# 14. Testler

En az şu testleri yaz:

## Model testleri

- Bir üründe yalnızca bir cover photo olabilir
- İlk fotoğraf otomatik cover olur
- StorageUnit ile Item ilişkisi doğru çalışır
- Arşivleme normal listeden ürünü çıkarır
- Tag many-to-many ilişkisi çalışır

## Fotoğraf testleri

- Büyük fotoğraf 1600 px sınırına küçültülür
- Oran korunur
- Cover için thumbnail üretilir
- EXIF orientation uygulanır
- Orijinal büyük dosya saklanmaz
- Hatalı dosya güvenli biçimde reddedilir

## Filtre testleri

- Kişiye göre filtre
- Kategoriye göre filtre
- Renge göre filtre
- Saklama birimine göre filtre
- Tag filtreleme
- Birleşik filtreler
- Arşivlerin varsayılan olarak gizlenmesi

## Akış testleri

- Ürün oluşturma
- Kaydet ve sonraki ürüne geç
- Ürünü başka saklama birimine taşıma
- Saklama biriminin konumunu değiştirme
- Ürün detayında yeni konumun otomatik görünmesi

---

# 15. Örnek veriler

Bir Django management command hazırla:

```bash
python manage.py seed_demo
```

Şunları oluştursun:

Kişiler:

- Ben
- Eşim
- Ortak

Saklama birimleri:

- Vakum Poşeti 1
- Vakum Poşeti 2
- Vakum Poşeti 3
- Büyük Siyah Valiz
- Yatak Odası Dolabı 2. Raf

Örnek kategoriler ve birkaç örnek ürün oluştur.

Demo fotoğrafları telif sorunu yaratmayacak basit placeholder görseller olabilir.

---

# 16. Kullanıcı deneyimi ilkeleri

- Arayüz Türkçe olsun.
- Kod, model ve değişken isimleri İngilizce olabilir.
- Mobil tarayıcıda kolay kullanılmalı.
- Form kontrolleri büyük ve dokunmatik kullanıma uygun olmalı.
- Filtre bölümü mobilde açılır/kapanır olabilir.
- Ürün ekleme süreci kısa olmalı.
- Opsiyonel alanlar kullanıcıyı boğmamalı.
- Hata mesajları anlaşılır olmalı.
- Silme ve arşivleme açıkça ayrılmalı.
- Uygulama düşük kaynaklı ev sunucusunda çalışabilmeli.

---

# 17. Beklenen repository yapısı

Yaklaşık olarak:

```text
wardrobe-inventory/
├── config/
├── inventory/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── filters.py
│   ├── services/
│   │   └── image_processing.py
│   ├── management/
│   │   └── commands/
│   │       └── seed_demo.py
│   ├── templates/
│   ├── static/
│   ├── migrations/
│   └── tests/
├── templates/
├── static/
├── media/
├── scripts/
│   ├── backup.sh
│   └── restore.sh
├── Dockerfile
├── docker-compose.yml
├── requirements.txt veya pyproject.toml
├── .env.example
├── manage.py
└── README.md
```

Daha iyi bir yapı öneriyorsan kullanabilirsin ancak gereksiz mikroservis veya aşırı soyutlama yapma.

---

# 18. Geliştirme yöntemi

Projeyi aşamalı geliştir ancak sonunda çalışan bütün repository'yi teslim et.

Önerilen sıra:

1. Django/PostgreSQL/Docker iskeleti
2. Modeller ve migration'lar
3. Kişi, kategori ve saklama birimi CRUD
4. Item CRUD
5. Çoklu fotoğraf ve image processing
6. Katalog
7. Filtreleme
8. Arşivleme, durum ve etiketler
9. Mobil arayüz iyileştirmeleri
10. Testler
11. Seed command
12. Backup/restore
13. README

Her aşamada:

- Testleri çalıştır
- Migration'ları kontrol et
- Lint hatalarını düzelt
- Kırık route veya template bırakma

---

# 19. Teslimat kriterleri

Proje aşağıdaki durumda tamamlanmış kabul edilir:

- `docker compose up -d --build` ile başlıyor
- PostgreSQL bağlantısı çalışıyor
- Migration'lar hatasız
- Giriş yapılabiliyor
- Ürün eklenebiliyor
- Telefonda fotoğraf yüklenebiliyor
- Fotoğraf otomatik optimize ediliyor
- Thumbnail oluşturuluyor
- Katalog hızlı açılıyor
- Lazy loading çalışıyor
- Birden fazla filtre birlikte çalışıyor
- Saklama birimine göre filtre yapılabiliyor
- Bir poşetin içindeki tüm ürünler görülebiliyor
- Ürün başka poşete taşınabiliyor
- Poşet konumu değiştirilince ürün detayındaki konum otomatik değişiyor
- Arşivleme çalışıyor
- Dinamik etiket oluşturulabiliyor
- Testler geçiyor
- README ile sıfırdan kurulum yapılabiliyor
- Yedekleme ve geri yükleme adımları belgelenmiş

---

# 20. Codex'ten beklenen ilk çıktı

Önce kısa bir uygulama planı ve kesin repository yapısını göster.

Ardından doğrudan projeyi oluştur.

Gereksiz açıklamalarla durma ve her dosya için onay isteme. Makul teknik kararları kendin ver.

Bir belirsizlik projenin temel davranışını ciddi biçimde değiştirmiyorsa varsayım yap, README içinde belirt ve geliştirmeye devam et.

Sonunda şu bilgileri ver:

1. Oluşturulan ana özellikler
2. Kurulum komutları
3. Test komutu
4. Demo veri komutu
5. Varsayımlar
6. Bilinen sınırlamalar
7. Sonraki sürüm için öneriler
