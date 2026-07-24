# Pardus Panel

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![GTK 3](https://img.shields.io/badge/GTK-3-4A86CF.svg)](https://www.gtk.org/)

Pardus Panel, Pardus için GTK 3 ile geliştirilmiş bir sistem izleme ve yönetim uygulamasıdır. Sık kullanılan sistem araçlarını tek bir masaüstü arayüzünde toplar.

## Özellikler

- Çalışan süreçleri arama, sıralama ve sonlandırma
- CPU, bellek, disk ve ağ için canlı performans grafikleri
- Başlangıç uygulamalarını (XDG) yönetme
- systemd servislerini kontrol etme
- systemd günlüklerini (logs) detaylı filtreleme
- Güç profili ve batarya durumunu takip etme
- Sistem özetini görüntüleme
- Türkçe ve İngilizce dil desteği

## Gereksinimler

- Python 3.11+
- GTK 3
- PyGObject, pycairo, psutil, distro, systemd

Pardus üzerinde bağımlılıkları kurmak için:

```bash
sudo apt install dbus-user-session gir1.2-gtk-3.0 lxpolkit pciutils pkexec \
    python3 python3-cairo python3-distro python3-gi python3-gi-cairo \
    python3-psutil systemd
```

> **Not:** Ekran kartı bilgisi için `pciutils`, güç profili yönetimi için ise `power-profiles-daemon` paketi önerilir. Bunlar olmasa da uygulamanın diğer özellikleri sorunsuz çalışır.

## Çalıştırma

Kaynak koddan çalıştırmak için:

```bash
git clone https://github.com/abdmelihakdeniz/pardus-panel.git
cd pardus-panel
PYTHONPATH=src python3 -m pardus_panel
```

Paket olarak kurulduysa, uygulama menüsünden ya da terminalden başlatabilirsiniz:

```bash
pardus-panel
```

## Derleme

Gerekli derleme araçlarını kurun:

```bash
sudo apt install build-essential debhelper dh-python pybuild-plugin-pyproject \
    python3-all python3-setuptools python3-wheel
```

Paketi oluşturun:

```bash
make build
```

Oluşan `.deb` paketini kurmak veya kaldırmak için:

```bash
sudo apt install ../pardus-panel_1.0_all.deb
sudo apt remove pardus-panel
```

## Çeviri 

`.po` dosyalarını güncellemek için gettext kurup make komutunu çalıştırmanız yeterli:

```bash
sudo apt install gettext
make i18n
```

## Klasör Yapısı

```text
src/pardus_panel/
├── application/   Uygulama döngüsü
├── core/          Temel altyapı
├── features/      Süreç, servis, günlük, güç vb. modüller
├── gtk/           Arayüz sayfaları, grafikler vb.
├── data/          UI, CSS ve ikonlar
└── locales/       Derlenmiş çeviriler
po/                Çeviri dosyaları
debian/            Debian paketleme dosyaları
```

## Lisans

GPL-3.0-or-later
Detaylar için [LICENSE](LICENSE) dosyasına göz atabilirsiniz.

<sub>Abdurrahman Melih AKDENIZ - Mustafa GUNES - Furkan AYDIN | AI Assisted</sub>
