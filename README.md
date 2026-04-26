

# EzAccess Cloudflare Scanner

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-brightgreen.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

**High-Performance VLESS/VMess Endpoint Scanner for Cloudflare CDN IPs**

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [How It Works](#how-it-works) • [Configuration](#configuration) • [Troubleshooting](#troubleshooting)

</div>

---

## 📋 Overview

**EzAccess Cloudflare Scanner** is a powerful multi-threaded network diagnostic tool that scans Cloudflare CDN IP ranges to find the fastest, most reliable endpoints for your VLESS/VMess proxy configurations. It performs comprehensive latency, bandwidth, and geolocation analysis to identify optimal server connections.

Designed specifically for the Iranian and international internet freedom community, this tool automates the tedious process of manually testing hundreds of Cloudflare IPs to find ones that work best with your specific configuration.

### 🎯 What It Tests

- **Ping Latency** – ICMP round-trip time for each endpoint
- **Download Speed** – Real download throughput via SOCKS5 proxy
- **Upload Speed** – Real upload throughput to Cloudflare test endpoints
- **Colo Location** – Cloudflare data center identification
- **TLS Handshake** – Optional pre-filter to eliminate dead IPs immediately

---

## ✨ Features

### Core Capabilities

- 🚀 **Multi-Threaded Scanning** – Configurable worker pool (1-64 threads) for parallel testing
- 🔒 **Full Protocol Support** – VLESS and VMess with WebSocket, gRPC, and XHTTP transports
- 🎯 **Smart Scoring** – Composite scoring algorithm balancing speed, latency, and reliability
- 📊 **Real-Time Dashboard** – Live top-10 leaderboard with dynamic updates
- 🧵 **Safe Process Management** – Clean Xray core lifecycle with process tree cleanup
- ⚡ **TLS Pre-Filtering** – Optional fast TCP/TLS handshake test to skip dead IPs early
- 🎲 **IP Range Shuffling** – Randomize scan order to avoid rate limiting
- 📁 **CIDR/Range/Auto-Expand** – Supports single IPs, CIDR notation, ranges, and mixed input files

### Advanced Features

- 🔄 **Real-Time GOOD Pool Export** – Automatically save qualifying results to file during scan
- 📤 **v2rayN URI Export** – Generate top-N v2rayN-compatible VLESS/VMess links
- ⚙️ **Flexible Classification** – Configurable GOOD/DL-only/UL-only/Below thresholds
- 🎨 **Dark Theme UI** – Modern gradient-based interface with adaptive font scaling
- 🔧 **Custom Upload URL** – Point to your own upload test endpoint
- 📈 **Live Progress Tracking** – Real-time percentage, pool stats, and status updates

---

## 🛠️ Installation

### Prerequisites

- **Windows** (10/11 recommended)
- **Python 3.8+** (64-bit)
- **Xray Core** (`xray.exe`) – Download from [XTLS/Xray-core](https://github.com/XTLS/Xray-core/releases)
- **curl** – Included with Windows 10+ or install manually

### Step-by-Step Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YourUsername/EzAccess-Cloudflare-Scanner.git
   cd EzAccess-Cloudflare-Scanner
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   *Required: PySide6*

3. **Download Xray Core**
   - Visit [Xray-core releases](https://github.com/XTLS/Xray-core/releases)
   - Download `Xray-windows-64.zip`
   - Extract `xray.exe` to the same folder as `main.py`

4. **Verify Installation**
   ```bash
   python main.py
   ```

---

## 🚀 Usage

### Quick Start

1. **Launch the application**
   ```bash
   python main.py
   ```

2. **Configure Xray path** – Point to your `xray.exe` (defaults to `./xray.exe`)

3. **Paste your configuration URI**
   ```
   vless://YOUR-UUID@yourdomain.com:443?security=tls&sni=yourdomain.com&type=ws&path=%2F#YourConfig
   ```
   or
   ```
   vmess://BASE64_ENCODED_CONFIG
   ```

4. **Set IP targets** – Default is `188.114.96.0/20` (Cloudflare's standard range)
   - Single IP: `1.1.1.1`
   - CIDR Range: `188.114.96.0/20`
   - IP Range: `1.1.1.1-1.1.1.255`
   - Import from file containing mixed formats

5. **Click "Start Scan"** and watch the results populate in real-time!

### Advanced Usage

#### Custom IP Targeting
```text
188.114.96.0/20
162.159.192.0/18
1.1.1.1-1.1.1.255
# Lines starting with # are ignored
```

#### File-Based Target Import
Create a `.txt` file with any combination of the formats above. Use the "Import targets from file" button.

#### Relaxed Mode
Enable "Relaxed GOOD" to treat DL-only or UL-only results as valid GOOD entries for your pool.

---

## ⚙️ Configuration Reference

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| **Workers** | 6 | 1-64 | Number of concurrent scanning threads |
| **SOCKS Base Port** | 19080 | 1024-65500 | Starting port for SOCKS5 proxies (each worker gets base+wid) |
| **DL Bytes** | 20,000,000 | 100K-200M | Bytes to download for speed test |
| **UL Bytes** | 3,000,000 | 100K-50M | Bytes to upload for speed test |
| **Min DL (Mbps)** | 10.0 | 0-10000 | Minimum download speed to qualify as GOOD |
| **Min UL (Mbps)** | 2.0 | 0-10000 | Minimum upload speed to qualify as GOOD |
| **Limit** | 254 | 0-10M | Max IPs to scan (0 = unlimited) |
| **Upload URL** | Cloudflare | any HTTP(S) | Custom endpoint for upload testing |

### Scoring Algorithm

```
Score = (Download × 0.75) + (Upload × 0.25) - (Ping / 50)
```

For DL-only or UL-only results:
```
Score = (Available Speed × 0.7) - (Ping / 60)
```

---

## 🏗️ Architecture

### Component Overview

```
┌─────────────────────┐
│   MainWindow (UI)   │
│  - Real-time updates│
│  - Top 10 dashboard │
│  - Result table     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Scanner Workers   │
│  - Thread pool      │
│  - IP queue         │
│  - Result queue     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Xray Core (SOCKS) │
│  - Per-worker proxy │
│  - Dynamic config   │
│  - Clean lifecycle  │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Network Tests     │
│  - Ping (ICMP)      │
│  - Download (curl)  │
│  - Upload (curl)    │
│  - Colo (trace)     │
└─────────────────────┘
```

### Lifecycle of a Scan

1. **IP Pool Generation** – Parse targets, expand ranges, shuffle
2. **Worker Distribution** – IPs pushed to FIFO queue consumed by threads
3. **Per-IP Pipeline**:
   ```
   Ping Test → [TLS Pre-Filter] → Xray Config Generation → 
   Proxy Start → Download Test → Upload Test → Colo Lookup → 
   Score Calculation → Result Dispatch → Proxy Cleanup
   ```
4. **Real-Time Processing** – Results streamed to UI, GOOD pool updated live
5. **Graceful Shutdown** – `Stop Safely` kills all subprocesses cleanly

---

## 📊 Understanding Results

### Status Classifications

| Status | Criteria | Icon |
|--------|----------|------|
| **GOOD** | DL ≥ threshold AND UL ≥ threshold | 🚀 |
| **DL-only** | Only download test succeeded | ⚡ |
| **UL-only** | Only upload test succeeded | ⚡ |
| **Below** | Both tests completed but below thresholds | 🌐 |

### Score Interpretation

- **> 25** – Excellent, high-speed endpoint (🚀)
- **15-25** – Good, reliable performance (⚡)  
- **< 15** – Acceptable, usable speeds (🌐)

---

## 📁 Output Formats

### Real-Time GOOD Pool
```
1.1.1.1	GOOD	ping=45ms	dl=85.23	ul=23.45	colo=LAX	score=78.92
188.114.97.2	GOOD	ping=32ms	dl=92.11	ul=18.67	colo=CDG	score=85.34
```

### v2rayN Export
```
vless://uuid@1.1.1.1:443?security=tls&type=ws&path=%2F#Config-score-78.92-GOOD
vmess://eyJhZGQiOiIxLjEuMS4xIiwgInBzIjogIkNvbmZpZy0xLjEuMS4xLXNjb3JlLTc4LjkyLUdPT0QiLCAuLi59
```

---

## 🔧 Troubleshooting

### Common Issues

**"xray.exe not found"**
- Ensure `xray.exe` is in the same directory as `main.py`
- Use "Browse xray.exe" to explicitly set the path

**"No results showing"**
- Check that your URI has `security=tls` – most Cloudflare IPs require TLS
- Increase worker count for faster processing
- Verify the IP range is valid Cloudflare CDN

**"All results are Below threshold"**
- Lower minimum DL/UL thresholds
- Check your internet connection
- Try different Cloudflare IP ranges

**"curl not found"**
- Install curl or add to PATH
- Ensure you're using PowerShell or CMD where curl is available

**Process cleanup issues**
- Use "Stop Safely" button (not window close) for clean termination
- If Xray processes persist, manually run: `taskkill /F /IM xray.exe`

---

## 🤝 Contributing

Contributions are welcome! Areas that need attention:

- **Linux/macOS support** – Platform-specific command adaptations
- **Additional protocols** – Shadowsocks, Trojan, Hysteria2
- **Performance optimizations** – Faster parallel testing
- **UI improvements** – Additional visualizations, export formats
- **Bugs/Issues** – Report through GitHub Issues

---

## 📝 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This tool is designed for network testing and optimization purposes only. Users are responsible for ensuring compliance with their local laws and regulations regarding proxy tools and network scanning. The developers assume no liability for misuse or any damages resulting from the use of this software.

---

## 🙏 Acknowledgments

- **XTLS/Xray-core** – Powerful proxy platform
- **Cloudflare** – CDN infrastructure and speed test endpoints
- **Community** – Iranian network freedom advocates for testing and feedback

---

<div align="center">

**Programmed By MacanDev**  
📢 **Telegram Channel:** [@EzAccess1](https://t.me/EzAccess1)

**If this tool helps you, star the repo! ⭐**

</div>

---

# EzAccess Cloudflare Scanner

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-brightgreen.svg)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg)

**اسکنر حرفه‌ای VLESS/VMess برای IP های کلودفلر**

[ویژگی‌ها](#ویژگیها) • [نصب](#نصب) • [روش استفاده](#روش-استفاده) • [نحوه کار](#نحوه-کار) • [تنظیمات](#تنظیمات) • [رفع اشکال](#رفع-اشکال)

</div>

---

## 📋 معرفی

**EzAccess Cloudflare Scanner** یک ابزار قدرتمند شبکه‌ای چندنخی است که رنج‌های IP کلودفلر را اسکن می‌کند تا سریع‌ترین و پایدارترین IP ها را برای کانفیگ‌های VLESS/VMess شما پیدا کند. این ابزار تست‌های جامع تأخیر، پهنای باند و موقعیت جغرافیایی را برای شناسایی بهترین نقاط اتصال انجام می‌دهد.

این ابزار که به طور ویژه برای جامعه اینترنت ایران و مدافعان آزادی اینترنت طراحی شده، فرآیند خسته‌کننده تست دستی صدها IP کلودفلر را خودکار می‌کند تا IP هایی را پیدا کند که بهترین عملکرد را با کانفیگ خاص شما دارند.

### 🎯 چه چیزهایی تست می‌شود

- **تأخیر (Ping)** – زمان رفت و برگشت ICMP برای هر IP
- **سرعت دانلود** – توان عملیاتی واقعی دانلود از طریق پروکسی SOCKS5
- **سرعت آپلود** – توان عملیاتی واقعی آپلود به نقاط تست کلودفلر
- **موقعیت Colo** – شناسایی دیتاسنتر کلودفلر
- **TLS Handshake** – فیلتر اولیه اختیاری برای حذف سریع IP های مرده

---

## ✨ ویژگی‌ها

### قابلیت‌های اصلی

- 🚀 **اسکن چندنخی** – استخر کاری قابل تنظیم (1-64 نخ) برای تست موازی
- 🔒 **پشتیبانی کامل از پروتکل‌ها** – VLESS و VMess با انتقال WebSocket، gRPC و XHTTP
- 🎯 **امتیازدهی هوشمند** – الگوریتم امتیازدهی ترکیبی با توازن سرعت، تأخیر و پایداری
- 📊 **داشبورد زنده** – جدول ۱۰ تای برتر با به‌روزرسانی پویا
- 🧵 **مدیریت امن فرآیندها** – چرخه حیات تمیز Xray با پاکسازی درختی فرآیندها
- ⚡ **پیش‌فیلتر TLS** – تست سریع TCP/TLS Handshake اختیاری برای رد کردن زودهنگام IP های مرده
- 🎲 **شافل رنج IP** – تصادفی‌سازی ترتیب اسکن برای جلوگیری از محدودیت نرخ
- 📁 **پشتیبانی از CIDR/رنج/Auto-Expand** – پشتیبانی از IP تکی، نت‌های CIDR، رنج‌ها و فایل‌های ورودی ترکیبی

### قابلیت‌های پیشرفته

- 🔄 **خروجی زنده استخر GOOD** – ذخیره خودکار نتایج واجد شرایط در فایل حین اسکن
- 📤 **خروجی v2rayN URI** – تولید لینک‌های VLESS/VMess سازگار با v2rayN برای N تای برتر
- ⚙️ **طبقه‌بندی انعطاف‌پذیر** – آستانه‌های قابل تنظیم GOOD/DL-only/UL-only/Below
- 🎨 **رابط کاربری دارک مود** – رابط مدرن مبتنی بر گرادینت با مقیاس‌دهی تطبیقی فونت
- 🔧 **URL آپلود سفارشی** – اشاره به نقطه پایانی آپلود دلخواه
- 📈 **ردیابی زنده پیشرفت** – درصد لحظه‌ای، آمار استخر و به‌روزرسانی وضعیت

---

## 🛠️ نصب

### پیش‌نیازها

- **ویندوز** (10 یا 11 پیشنهاد می‌شود)
- **Python 3.8+** (64 بیتی)
- **Xray Core** (`xray.exe`) – دانلود از [XTLS/Xray-core](https://github.com/XTLS/Xray-core/releases)
- **curl** – در ویندوز 10+ موجود است یا به صورت دستی نصب کنید

### مراحل نصب گام به گام

1. **کلون کردن مخزن**
   ```bash
   git clone https://github.com/YourUsername/EzAccess-Cloudflare-Scanner.git
   cd EzAccess-Cloudflare-Scanner
   ```

2. **نصب وابستگی‌های پایتون**
   ```bash
   pip install -r requirements.txt
   ```
   *نیازمندی: PySide6*

3. **دانلود Xray Core**
   - به [صفحه انتشار Xray-core](https://github.com/XTLS/Xray-core/releases) مراجعه کنید
   - فایل `Xray-windows-64.zip` را دانلود کنید
   - فایل `xray.exe` را در همان پوشه `main.py` استخراج کنید

4. **تأیید نصب**
   ```bash
   python main.py
   ```

---

## 🚀 روش استفاده

### شروع سریع

1. **اجرای برنامه**
   ```bash
   python main.py
   ```

2. **تنظیم مسیر Xray** – به `xray.exe` خود اشاره کنید (پیش‌فرض: `./xray.exe`)

3. **چسباندن URI کانفیگ**
   ```
   vless://YOUR-UUID@yourdomain.com:443?security=tls&sni=yourdomain.com&type=ws&path=%2F#YourConfig
   ```
   یا
   ```
   vmess://BASE64_ENCODED_CONFIG
   ```

4. **تنظیم IP های هدف** – پیش‌فرض `188.114.96.0/20` (رنج استاندارد کلودفلر)
   - IP تکی: `1.1.1.1`
   - رنج CIDR: `188.114.96.0/20`
   - بازه IP: `1.1.1.1-1.1.1.255`
   - وارد کردن از فایل حاوی فرمت‌های ترکیبی

5. **کلیک روی "Start Scan"** و مشاهده نتایج به صورت زنده!

### استفاده پیشرفته

#### هدف‌گیری IP سفارشی
```text
188.114.96.0/20
162.159.192.0/18
1.1.1.1-1.1.1.255
# خطوطی که با # شروع می‌شوند نادیده گرفته می‌شوند
```

#### ورودی مبتنی بر فایل
یک فایل `.txt` با هر ترکیبی از فرمت‌های بالا ایجاد کنید. از دکمه "Import targets from file" استفاده کنید.

#### حالت Relaxed
گزینه "Relaxed GOOD" را فعال کنید تا نتایج DL-only یا UL-only به عنوان ورودی‌های معتبر GOOD برای استخر شما در نظر گرفته شوند.

---

## ⚙️ مرجع تنظیمات

| پارامتر | پیش‌فرض | بازه | توضیح |
|-----------|---------|-------|-------------|
| **Workers** | 6 | 1-64 | تعداد نخ‌های اسکن همزمان |
| **SOCKS Base Port** | 19080 | 1024-65500 | پورت شروع برای پروکسی‌های SOCKS5 (هر Worker پورت base+wid می‌گیرد) |
| **DL Bytes** | 20,000,000 | 100K-200M | تعداد بایت برای دانلود تست سرعت |
| **UL Bytes** | 3,000,000 | 100K-50M | تعداد بایت برای آپلود تست سرعت |
| **Min DL (Mbps)** | 10.0 | 0-10000 | حداقل سرعت دانلود برای واجد شرایط شدن GOOD |
| **Min UL (Mbps)** | 2.0 | 0-10000 | حداقل سرعت آپلود برای واجد شرایط شدن GOOD |
| **Limit** | 254 | 0-10M | حداکثر IP برای تست (0 = نامحدود) |
| **Upload URL** | Cloudflare | هر HTTP(S) | نقطه پایانی سفارشی برای تست آپلود |

### الگوریتم امتیازدهی

```
امتیاز = (دانلود × 0.75) + (آپلود × 0.25) - (پینگ / 50)
```

برای نتایج فقط دانلود یا فقط آپلود:
```
امتیاز = (سرعت موجود × 0.7) - (پینگ / 60)
```

---

## 🏗️ معماری

### نمای کلی اجزا

```
┌─────────────────────┐
│   MainWindow (UI)   │
│  - به‌روزرسانی زنده │
│  - داشبورد ۱۰ تای   │
│  - جدول نتایج       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Scanner Workers   │
│  - استخر نخ‌ها      │
│  - صف IP            │
│  - صف نتایج         │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   Xray Core (SOCKS) │
│  - پروکسی هر Worker │
│  - کانفیگ پویا      │
│  - چرخه حیات تمیز   │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   تست‌های شبکه      │
│  - پینگ (ICMP)      │
│  - دانلود (curl)    │
│  - آپلود (curl)     │
│  - Colo (trace)     │
└─────────────────────┘
```

### چرخه حیات یک اسکن

1. **تولید استخر IP** – تجزیه اهداف، گسترش رنج‌ها، شافل
2. **توزیع Worker** – IP ها به صف FIFO ارسال و توسط نخ‌ها مصرف می‌شوند
3. **خط لوله هر IP**:
   ```
   تست پینگ → [پیش‌فیلتر TLS] → تولید کانفیگ Xray → 
   شروع پروکسی → تست دانلود → تست آپلود → جستجوی Colo → 
   محاسبه امتیاز → ارسال نتیجه → پاکسازی پروکسی
   ```
4. **پردازش لحظه‌ای** – نتایج به رابط کاربری ارسال می‌شود، استخر GOOD به‌روزرسانی می‌شود
5. **خاموشی ایمن** – دکمه `Stop Safely` تمام زیرفرآیندها را به صورت پاک متوقف می‌کند

---

## 📊 آشنایی با نتایج

### طبقه‌بندی وضعیت‌ها

| وضعیت | معیار | آیکون |
|--------|----------|------|
| **GOOD** | دانلود ≥ آستانه و آپلود ≥ آستانه | 🚀 |
| **DL-only** | فقط تست دانلود موفق بود | ⚡ |
| **UL-only** | فقط تست آپلود موفق بود | ⚡ |
| **Below** | هر دو تست کامل شد اما زیر آستانه | 🌐 |

### تفسیر امتیاز

- **> ۲۵** – عالی، نقطه پایانی پرسرعت (🚀)
- **۱۵-۲۵** – خوب، عملکرد قابل اعتماد (⚡)  
- **< ۱۵** – قابل قبول، سرعت‌های قابل استفاده (🌐)

---

## 📁 فرمت‌های خروجی

### استخر GOOD زنده
```
1.1.1.1	GOOD	ping=45ms	dl=85.23	ul=23.45	colo=LAX	score=78.92
188.114.97.2	GOOD	ping=32ms	dl=92.11	ul=18.67	colo=CDG	score=85.34
```

### خروجی v2rayN
```
vless://uuid@1.1.1.1:443?security=tls&type=ws&path=%2F#Config-score-78.92-GOOD
vmess://eyJhZGQiOiIxLjEuMS4xIiwgInBzIjogIkNvbmZpZy0xLjEuMS4xLXNjb3JlLTc4LjkyLUdPT0QiLCAuLi59
```

---

## 🔧 رفع اشکال

### مشکلات رایج

**"xray.exe not found"**
- مطمئن شوید `xray.exe` در همان پوشه `main.py` است
- از دکمه "Browse xray.exe" برای تنظیم صریح مسیر استفاده کنید

**"No results showing"**
- بررسی کنید که URI شما `security=tls` دارد – بیشتر IP های کلودفلر نیاز به TLS دارند
- تعداد Worker را افزایش دهید
- تأیید کنید که رنج IP، کلودفلر معتبر است

**"All results are Below threshold"**
- آستانه‌های حداقل دانلود/آپلود را کاهش دهید
- اتصال اینترنت خود را بررسی کنید
- رنج‌های IP کلودفلر متفاوت را امتحان کنید

**"curl not found"**
- curl را نصب کنید یا به PATH اضافه کنید
- مطمئن شوید از PowerShell یا CMD استفاده می‌کنید

**مشکلات پاکسازی فرآیند**
- از دکمه "Stop Safely" (نه بستن پنجره) برای توقف پاک استفاده کنید
- اگر فرآیندهای Xray باقی ماندند، دستی اجرا کنید: `taskkill /F /IM xray.exe`

---

## 🤝 مشارکت

مشارکت‌ها خوش‌آمد هستند! زمینه‌هایی که نیاز به توجه دارند:

- **پشتیبانی از Linux/macOS** – تطبیق دستورات مخصوص پلتفرم
- **پروتکل‌های اضافی** – Shadowsocks، Trojan، Hysteria2
- **بهینه‌سازی عملکرد** – تست موازی سریع‌تر
- **بهبودهای رابط کاربری** – نمودارهای اضافی، فرمت‌های خروجی
- **باگ‌ها/مشکلات** – از طریق GitHub Issues گزارش دهید

---

## 📝 مجوز

این پروژه تحت مجوز MIT منتشر شده است – برای جزئیات به فایل [LICENSE](LICENSE) مراجعه کنید.

---

## ⚠️ سلب مسئولیت

این ابزار فقط برای اهداف تست و بهینه‌سازی شبکه طراحی شده است. کاربران مسئول اطمینان از رعایت قوانین و مقررات محلی خود در رابطه با ابزارهای پروکسی و اسکن شبکه هستند. توسعه‌دهندگان هیچ مسئولیتی در قبال سوءاستفاده یا هرگونه خسارت ناشی از استفاده از این نرم‌افزار نمی‌پذیرند.

---

## 🙏 قدردانی

- **XTLS/Xray-core** – پلتفرم پروکسی قدرتمند
- **Cloudflare** – زیرساخت CDN و نقاط پایانی تست سرعت
- **جامعه** – مدافعان آزادی شبکه ایران برای تست و بازخورد

---

<div align="center">

**برنامه‌نویسی شده توسط MacanDev**  
📢 **کانال تلگرام:** [@EzAccess1](https://t.me/EzAccess1)

**اگر این ابزار به شما کمک کرد، به مخزن ستاره بدهید! ⭐**

</div>
