# Pardus Panel Mimari 

Pardus Panel Python 3.11+ GTK 3 PyGObject Cairo ve `psutil` kullanır Bazı
bilgileri de `/proc` `/sys` ve Linux komutlarından alır

## Uygulama nasıl çalışıyor

Genel akış şöyle

```text
Kullanıcı
   |
   v
GTK arayüzü
   |
   v
Sayfa kodu
   |
   v
Sistem özellikleri
   |
   v
psutil, /proc, /sys ve Linux komutları
```

Kod dört ana bölüme ayrılır

- `application/` Uygulamayı ve ana pencereyi açar
- `gtk/` Sayfaları ve GTK bileşenlerini yönetir
- `features/` Sistemden veri alır ve sistem işlemlerini yapar
- `core/` Arka plan işleri ve komut çalıştırma gibi ortak işleri yapar

En önemli kural şu `features/` içindeki kod GTKyı bilmemeli Sistemden veri
almalı ve sonucu geri vermeli Ekrana nasıl yazılacağına `gtk/` karar vermeli

## Çalıştırma sırası

1. `pardus-panel` komutu `pardus_panel.__main__:main` fonksiyonunu çalıştırır
2. `i18n.configure()` dil ve çeviri ayarlarını yapar
3. `PardusPanelApplication` oluşturulur
4. GTK ana döngüsü başlar
5. İlk açılışta CSS ve `MainWindow.ui` yüklenir
6. Bütün sayfalar oluşturulur ve `Gtk.Stack` içine eklenir
7. Soldaki menüden seçilen sayfa aktif edilir

Bütün sayfalar başta oluşturulur ama yalnız açık olan sayfa veri toplar
Süreçler sayfası 5 saniyede Performans sayfası 2 saniyede bir yenilenir Diğer
sayfalar açıldığında veya kullanıcı bir işlem yaptığında yenilenir

Uygulama kapanırken sayfaların `dispose()` metodu çağrılır Zamanlayıcılar
sinyaller ve çalışan komutlar temizlenir

Sayfa listesi `src/pardus_panel/application/app.py` içindeki `PAGES` sabitinde
bulunur

## Klasörler

```text
.
├── pyproject.toml Paket, sürüm ve bağımlılıklar
├── README.md Proje tanıtımı
├── ARCHITECTURE.md Bu dosya
├── Makefile Proje komutları
├── debian/ Debian paketleme dosyaları
├── po/ Çeviriler
└── src/pardus_panel/
    ├── __main__.py Başlangıç noktası
    ├── i18n.py Dil ayarları
    ├── application/ Ana uygulama
    ├── core/ Ortak araçlar
    ├── features/ Sistem verileri ve işlemleri
    ├── gtk/ Arayüz sayfaları
    └── data/
        ├── ui/ UI dosyaları
        ├── css/ CSS dosyaları
        ├── icons/ İkon
        ├── applications/ .desktop dosyası
        └── metainfo/ AppStream bilgisi
```

## Ortak araçlar

### `async_jobs.py`

Yavaş işleri arka planda çalıştırır Böylece pencere donmaz İş bitince sonuç
`GLib.idle_add` ile GTK ana döngüsüne gönderilir

### `refresh.py`

Aynı yenileme işinin üst üste çalışmasını engeller Bir yenileme devam ederken
yeni istek gelirse mevcut iş bitince bir kez daha yeniler

### `command.py`

`systemctl` ve `journalctl` gibi komutları çalıştırır Shell kullanmaz
Komutları argüman listesi olarak alır

```python
run_command(["journalctl", "--lines=300"])
```

Komutların süre sınırı vardır Uygulama kapanınca halen çalışan komutlar
sonlandırılır

### `lifecycle.py`

GTK sinyallerini takip eder Sayfa kapatılırken sinyal bağlantılarını temizler

### Diğerleri

- `formatting.py` Bayt sayılarını `MiB` ve `GiB` gibi okunabilir hale getirir
- `paths.py` Paket içindeki UI ve CSS dosyalarını bulur

## GTK sayfaları

UI dosyaları `src/pardus_panel/data/ui/` içindedir Bu dosyalardaki bileşenlere
`id` ile ulaşılır

Örnek

```python
view = builder.get_required("logs_view", Gtk.TreeView)
```

`logs_view` bulunamazsa veya yanlış GTK türündeyse açık bir hata oluşur Bu
yüzden UI dosyasındaki bir `id` değişince Python kodu da güncellenmelidir

Her sayfada şu üç üye bulunmalıdır

```python
page.root
page.set_active(active)
page.dispose()
```

- `root` Ana GTK bileşeni
- `set_active()` Sayfa açıldığında veya gizlendiğinde çağrılır
- `dispose()` Zamanlayıcı ve sinyal gibi kaynakları temizler

## Sayfalar

### Süreçler

- Sayfa `gtk/pages/processes.py`
- Veri `features/processes/`

Çalışan süreçler `psutil` ile alınır Arama PID süreç adı ve kullanıcı
alanlarında yapılır

Bir süreç kapatılmadan önce PID ve oluşturulma zamanı birlikte kontrol edilir
Böylece aynı PID başka bir sürece verilmişse yanlış süreç kapatılmaz Önce
normal kapatma denenir Süreç 2 saniyede kapanmazsa zorla kapatma denenir

### Performans

- Sayfa `gtk/pages/performance.py`
- Veri `features/performance/collector.py`

CPU bellek disk ağ sıcaklık ve frekans bilgileri çoğunlukla `psutil` ile
alınır Ağ hızı iki ölçüm arasındaki bayt farkından hesaplanır

Grafikler Cairo ile çizilir

### Başlangıç uygulamaları

- Sayfa `gtk/pages/autostart.py`
- Veri `features/autostart/`

Kullanıcı kayıtları `~/.config/autostart` altında bulunur Sistem kayıtları
genelde `/etc/xdg/autostart` altındadır Ortamda XDG dizinleri tanımlıysa onlar
kullanılır

Sistem dosyaları doğrudan değiştirilmez Gerektiğinde kullanıcı dizininde bir
kopya oluşturulur Dosyalar önce geçici bir ada yazılır sonra `os.replace()`
ile asıl yerine taşınır

### Servisler

- Sayfa `gtk/pages/services.py`
- Veri `features/services/repository.py`

Sistem ve kullanıcı servisleri `systemctl` ile yönetilir Desteklenen işlemler

- `start`
- `stop`
- `restart`
- `enable`
- `disable`

Kullanıcı servislerinde `systemctl --user` kullanılır Sistem servislerinde
komut `pkexec` üzerinden çalıştırılır Bu sırada polkit yetki penceresi
gösterebilir

### Sistem günlükleri

- Sayfa `gtk/pages/logs.py`
- Veri `features/logs/repository.py`

En yeni 300 kayıt `journalctl` üzerinden JSON olarak alınır Sistem ve kullanıcı
günlükleri ayrı seçilebilir Öncelik filtresi `journalctl` komutuna verilir
Metin araması Python tarafında kaynak ve mesaj alanlarında yapılır

Kullanıcının izni olmayan sistem kayıtları gösterilemez

### Güç

- Sayfa `gtk/pages/power.py`
- Veri `features/power/collector.py`

Batarya bilgisi `/sys/class/power_supply` ve `psutil` üzerinden alınır Güç profilleri
Pardusun de kullandığı `powerprofilesctl` ile okunur ve değiştirilir

### Sistem bilgisi

- Sayfa `gtk/pages/system_info.py`
- Veri `features/system_info/collector.py`

İşletim sistemi açılış türü makine adı masaüstü oturumu IP adresleri
kernel CPU bellek ve disk bilgileri toplanır Ekran kartı bilgisi için
gerekirse `lspci` kullanılır

## CSS ve çeviri

CSS dosyaları `src/pardus_panel/data/css/` içindedir

- `base.css` Genel görünüm
- `navigation.css` Sidebar menü
- `performance.css` Performans sayfası
- `tables.css` Tablo ve listeler

Python içindeki çevrilebilir yazılar `_()` ile işaretlenir UI dosyalarında
`translatable="yes"` kullanılır

Çeviri dosyaları

- `po/pardus-panel.pot` Kaynak metinler
- `po/tr.po` Türkçe çeviri

Çevirileri güncellemek için:

```bash
make i18n
```

## Proje komutları

```bash
make run # Uygulamayı çalıştır
make validate # Temel kontrolleri yap
make i18n # Çevirileri güncelle
make build # Debian paketi oluştur
make clean # Paketleme çıktılarını temizle
```
